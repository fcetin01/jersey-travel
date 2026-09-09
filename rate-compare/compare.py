#!/usr/bin/env python3
"""Mekke/Medine otelleri: Paximum net maliyetimiz vs Booking/OTA fiyatlari.

Tek seferlik analiz araci. Soru: sistematik olarak Booking'den ucuz muyuz,
yoksa sadece bazi otellerde mi?

Ornekler:
  python compare.py --dry-run
  python compare.py --limit 5
  python compare.py --limit 10 --dates 2 --margin 0.15
"""
import argparse
import csv
import os
import statistics
import sys
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv

import config
from makcorps import MakcorpsClient, MakcorpsError, cheapest, find_booking, parse_comparison
from paximum import PaximumClient

BASE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE, "output")

# MakCorps /hotel fiyatlari GECELIK gelir; Paximum ise konaklamanin TAMAMI icin
# net fiyat verir. Karsilastirma icin OTA fiyatini gece sayisiyla carpiyoruz.
OTA_PRICE_IS_PER_NIGHT = True


def load_hotels(path, limit=None):
    """CSV'yi okur. Limit verilirse sehirler arasinda sirayla secer ki
    kucuk limitlerde de hem Mekke hem Medine ornegi olsun."""
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("name")]
    if not limit or limit >= len(rows):
        return rows
    by_city = {}
    for r in rows:
        by_city.setdefault(r["city"], []).append(r)
    picked, cities = [], list(by_city)
    while len(picked) < limit:
        progressed = False
        for c in cities:
            if by_city[c]:
                picked.append(by_city[c].pop(0))
                progressed = True
                if len(picked) == limit:
                    break
        if not progressed:
            break
    return picked


def margin_label(margin):
    pct = margin * 100
    return f"%{int(pct) if pct == int(pct) else pct}_marjla_satis"


def dry_run(hotels, scenarios, mc):
    mapping_calls, price_calls, cached = 0, 0, 0
    seen_map = set()
    print("\n=== DRY RUN - hicbir API cagrisi yapilmadi ===")
    print(f"Otel sayisi: {len(hotels)}  |  Tarih senaryosu: {len(scenarios)}")
    for sc in scenarios:
        print(f"  - {sc['label']}: {sc['checkin']} -> {sc['checkout']} ({sc['nights']} gece)")
    for h in hotels:
        key = (h["name"], h["city"])
        if key not in seen_map:
            seen_map.add(key)
            if mc.has_mapping(h["name"], h["city"]):
                cached += 1
            else:
                mapping_calls += 1
        hid = (mc.mappings.get(mc.mapping_key(h["name"], h["city"])) or {}).get("hotel_id")
        for sc in scenarios:
            if hid and mc.has_prices(hid, sc["checkin"], sc["checkout"]):
                cached += 1
            else:
                price_calls += 1
    total = mapping_calls + price_calls
    print(f"\nMakCorps mapping cagrisi   : {mapping_calls}")
    print(f"MakCorps otel fiyat cagrisi: {price_calls}")
    print(f"Cache'ten gelecek (bedava) : {cached}")
    print(f"TOPLAM HARCANACAK KREDI    : {total}")
    print(f"Butce durumu: harcanan {mc.used}/{mc.budget}, kalan {mc.remaining}")
    if total > mc.remaining:
        print(f"!! UYARI: {total - mc.remaining} kredi eksik. --limit veya --dates dusur.")
    print("(Paximum cagrilari kredi harcamaz; sehir basina tek arama yapilir.)\n")
    return total


def collect(hotels, scenarios, mc, pax, margin):
    rows, detail_rows, failures = [], [], []
    for sc in scenarios:
        print(f"\n### {sc['label']}: {sc['checkin']} -> {sc['checkout']} "
              f"({sc['nights']} gece)")
        city_data = {}
        for city in dict.fromkeys(h["city"] for h in hotels):
            try:
                city_data[city] = pax.search_city(city, sc["checkin"], sc["nights"])
            except Exception as exc:  # noqa: BLE001 - tek sehir hatasi tum akisi dusurmesin
                print(f"  !! Paximum {city} araması basarisiz: {exc}")
                city_data[city] = []
                failures.append({"otel": f"(tum {city})", "sehir": city,
                                 "checkin": sc["checkin"], "sebep": f"paximum: {exc}"})

        for h in hotels:
            name, city = h["name"], h["city"]
            print(f"\n  -> {name} ({city})")
            pax_hit = PaximumClient.match(name, city_data.get(city, []))
            if pax_hit:
                print(f"     paximum net: {pax_hit['price']:.2f} USD "
                      f"[{pax_hit['room']} / {pax_hit['board']}] "
                      f"(eslesme {pax_hit['match_score']})")
            else:
                print("     paximum: fiyat bulunamadi")

            ota_rows = []
            try:
                hid = mc.get_hotel_id(name, city)
                if not hid:
                    raise MakcorpsError("mapping'de HOTEL kaydi yok")
                payload = mc.get_prices(hid, sc["checkin"], sc["checkout"])
                ota_rows = parse_comparison(payload)
                if not ota_rows:
                    raise MakcorpsError("comparison bos (o tarihte fiyat yok olabilir)")
                print(f"     ota: {len(ota_rows)} vendor")
            except Exception as exc:  # noqa: BLE001
                print(f"     !! makcorps: {exc}")
                failures.append({"otel": name, "sehir": city,
                                 "checkin": sc["checkin"], "sebep": f"makcorps: {exc}"})

            mult = sc["nights"] if OTA_PRICE_IS_PER_NIGHT else 1
            for r in ota_rows:
                stay = (r["total_price"] if r["total_price"] is not None else r["price"])
                detail_rows.append({
                    "otel": name, "sehir": city, "checkin": sc["checkin"],
                    "vendor": r["vendor"], "gecelik_usd": r["price"],
                    "ota_ham_toplam_usd": r["total_price"],
                    "konaklama_toplam_usd": round(stay * mult, 2) if stay is not None else None,
                    "booking_mu": "EVET" if "booking" in r["vendor"].lower() else "",
                })

            def stay_total(rec):
                v = rec["total_price"] if rec["total_price"] is not None else rec["price"]
                return round(v * mult, 2) if v is not None else None

            b = find_booking(ota_rows)
            c = cheapest(ota_rows)
            booking_usd = stay_total(b) if b else None
            cheap_usd = stay_total(c) if c else None
            pax_usd = round(pax_hit["price"], 2) if pax_hit else None
            # Booking satiri yoksa referans olarak en ucuz OTA kullanilir.
            ref = booking_usd if booking_usd is not None else cheap_usd

            fark = fark_pct = satis = hala = None
            if pax_usd is not None and ref:
                fark = round(ref - pax_usd, 2)
                fark_pct = round(fark / ref * 100, 2)
                satis = round(pax_usd * (1 + margin), 2)
                hala = "EVET" if satis < ref else "HAYIR"

            rows.append({
                "otel": name, "sehir": city, "checkin": sc["checkin"],
                "gece": sc["nights"],
                "paximum_net_usd": pax_usd,
                "oda_tipi": pax_hit["room"] if pax_hit else None,
                "pansiyon": pax_hit["board"] if pax_hit else None,
                "booking_usd": booking_usd,
                "en_ucuz_ota": c["vendor"] if c else None,
                "en_ucuz_ota_usd": cheap_usd,
                "fark_usd": fark,
                "fark_yuzde": fark_pct,
                margin_label(margin): satis,
                "marjla_hala_ucuz_mu": hala,
            })
    return rows, detail_rows, failures


def write_excel(rows, detail_rows, failures, margin):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR,
                        f"karsilastirma_{datetime.now():%Y%m%d}.xlsx")
    df = pd.DataFrame(rows, columns=[
        "otel", "sehir", "checkin", "gece", "paximum_net_usd", "oda_tipi", "pansiyon",
        "booking_usd", "en_ucuz_ota", "en_ucuz_ota_usd", "fark_usd", "fark_yuzde",
        margin_label(margin), "marjla_hala_ucuz_mu"])
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="karsilastirma", index=False)
        pd.DataFrame(detail_rows).to_excel(xl, sheet_name="ota_detay", index=False)
        pd.DataFrame(failures or [{"otel": "-", "sebep": "yok"}]).to_excel(
            xl, sheet_name="basarisizlar", index=False)
        for ws in xl.book.worksheets:
            for col in ws.columns:
                width = max((len(str(c.value)) for c in col if c.value is not None),
                            default=8)
                ws.column_dimensions[col[0].column_letter].width = min(38, width + 2)
    return path, df


def summarize(df, failures, margin):
    print("\n" + "=" * 62)
    print("OZET")
    print("=" * 62)
    ok = df[df["fark_yuzde"].notna()]
    nodata = len(df) - len(ok)
    cheaper = ok[ok["fark_usd"] > 0]
    pricier = ok[ok["fark_usd"] <= 0]
    print(f"Toplam satir            : {len(df)}")
    print(f"Booking/OTA'dan UCUZUZ  : {len(cheaper)}")
    print(f"Booking/OTA'dan PAHALIYIZ: {len(pricier)}")
    print(f"Veri yok                : {nodata}")
    if len(ok):
        vals = list(ok["fark_yuzde"])
        print(f"Ortalama fark yuzdesi   : {statistics.mean(vals):.2f}%")
        print(f"Medyan fark yuzdesi     : {statistics.median(vals):.2f}%")
        still = ok[ok["marjla_hala_ucuz_mu"] == "EVET"]
        print(f"%{margin*100:.0f} marj sonrasi hala ucuz: {len(still)}/{len(ok)} otel")
        top = ok.sort_values("fark_yuzde", ascending=False)
        n = min(5, len(top))
        bottom = top.tail(n).iloc[::-1]
        if len(top) < 2 * n:
            print(f"\n(not: sadece {len(top)} satir var, iki liste ortusuyor)")
        print("\nEN BUYUK 5 AVANTAJ (biz cok daha ucuzuz):")
        for _, r in top.head(n).iterrows():
            print(f"  {r['otel'][:34]:<34} {r['fark_yuzde']:>7.1f}%  "
                  f"(net {r['paximum_net_usd']} vs ota {r['booking_usd'] or r['en_ucuz_ota_usd']})")
        print("\nEN BUYUK 5 DEZAVANTAJ (biz pahaliyiz / fark az):")
        for _, r in bottom.iterrows():
            print(f"  {r['otel'][:34]:<34} {r['fark_yuzde']:>7.1f}%  "
                  f"(net {r['paximum_net_usd']} vs ota {r['booking_usd'] or r['en_ucuz_ota_usd']})")
    if failures:
        print(f"\nBASARISIZ ({len(failures)}):")
        for f in failures:
            print(f"  - {f['otel']} / {f.get('checkin','')}: {f['sebep']}")


def main():
    load_dotenv(os.path.join(BASE, ".env"))
    p = argparse.ArgumentParser(description="Paximum net vs Booking/OTA fiyat karsilastirma")
    p.add_argument("--limit", type=int, default=10, help="kac otel (varsayilan 10)")
    p.add_argument("--dates", type=int, default=1, help="kac tarih senaryosu (varsayilan 1)")
    p.add_argument("--margin", type=float, default=config.MARGIN, help="satis marji, orn 0.10")
    p.add_argument("--hotels", default=os.path.join(BASE, "hotels.csv"))
    p.add_argument("--budget", type=int, default=config.CREDIT_BUDGET, help="MakCorps kredi butcesi")
    p.add_argument("--dry-run", action="store_true", help="API cagirmadan kredi maliyetini yaz")
    args = p.parse_args()

    hotels = load_hotels(args.hotels, args.limit)
    scenarios = config.build_scenarios(args.dates)
    mc = MakcorpsClient(budget=args.budget)

    if args.dry_run:
        dry_run(hotels, scenarios, mc)
        return 0

    planned = dry_run(hotels, scenarios, mc)
    if planned > mc.remaining:
        print("Kredi yetersiz, calistirma iptal edildi.")
        return 2

    try:
        pax = PaximumClient()
        pax.login()
    except Exception as exc:  # noqa: BLE001
        print(f"\n!! Paximum baglantisi kurulamadi: {exc}")
        print("   Net maliyet olmadan karsilastirma anlamsiz; MakCorps kredisi "
              "harcanmadan cikiliyor.")
        return 2

    rows, detail_rows, failures = collect(hotels, scenarios, mc, pax, args.margin)
    path, df = write_excel(rows, detail_rows, failures, args.margin)
    summarize(df, failures, args.margin)
    print(f"\nExcel: {path}")
    print(f"MakCorps kredi: bu calistirmada {mc.calls_this_run}, "
          f"toplam {mc.used}/{mc.budget}, kalan {mc.remaining}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

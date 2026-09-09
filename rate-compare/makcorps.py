"""MakCorps - Booking/OTA fiyatlari.

Iki adim:
  1) /mapping?name=Otel+Adi,+Sehir   -> document_id (hotel id).  mappings.json'a KALICI cache.
  2) /hotel?hotelid=..&cur=USD&..    -> OTA fiyatlari.            cache/makcorps/ altina cache.

Kredi kotasi kucuk oldugu icin: her basarili cagri diske yazilir ve
ayni (hotelid, checkin, checkout) icin bir daha ASLA cagri yapilmaz.
DIKKAT: /hotel endpoint'inde para birimi parametresi `cur=` (currency= DEGIL).
"""
import json
import os
import re
import time

import requests

import config
from paximum import name_score, _slug

BASE = os.path.dirname(__file__)
CACHE_DIR = os.path.join(BASE, "cache", "makcorps")
RAW_DIR = os.path.join(BASE, "raw")
MAPPINGS_FILE = os.path.join(BASE, "mappings.json")
CREDITS_FILE = os.path.join(BASE, "credits.json")


class MakcorpsError(RuntimeError):
    pass


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            return default
    return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_price(val):
    """'$150', '150.00', 150 -> 150.0 ; bulunamazsa None."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(val))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_comparison(payload):
    """Ic ice `comparison` dizisinden vendorN/priceN/TotalpriceN desenini cikarir.

    Index'e guvenmez: hangi N varsa onu okur. Vendor ve fiyat ayni dict'te
    degilse ayni gruptaki dict'ler birlestirilerek aranir.
    """
    comparison = payload.get("comparison") if isinstance(payload, dict) else None
    if not comparison:
        return []
    out = []
    for group in comparison:
        if isinstance(group, dict):
            group = [group]
        if not isinstance(group, list):
            continue
        merged = {}
        for entry in group:
            if isinstance(entry, dict):
                merged.update(entry)
        for entry in group:
            if not isinstance(entry, dict):
                continue
            for key, vendor in list(entry.items()):
                m = re.fullmatch(r"vendor(\d+)", str(key))
                if not m or not vendor:
                    continue
                n = m.group(1)
                price = parse_price(entry.get(f"price{n}", merged.get(f"price{n}")))
                total = parse_price(entry.get(f"Totalprice{n}",
                                              merged.get(f"Totalprice{n}",
                                                         merged.get(f"totalprice{n}"))))
                if price is None and total is None:
                    continue
                out.append({
                    "vendor": str(vendor).strip(),
                    "price": price,
                    "total_price": total,
                    "tax": parse_price(entry.get(f"tax{n}", merged.get(f"tax{n}"))),
                })
    # ayni vendor birden fazla gelirse en ucuzunu tut
    dedup = {}
    for r in out:
        key = r["vendor"].lower()
        cur = dedup.get(key)
        if cur is None or (r["price"] or 1e9) < (cur["price"] or 1e9):
            dedup[key] = r
    return list(dedup.values())


def find_booking(rows):
    for r in rows:
        if "booking" in r["vendor"].lower():
            return r
    return None


def cheapest(rows):
    valid = [r for r in rows if r.get("price") is not None]
    return min(valid, key=lambda r: r["price"]) if valid else None


class MakcorpsClient:
    def __init__(self, api_key=None, verbose=True, budget=None):
        self.api_key = api_key or os.getenv("MAKCORPS_API_KEY")
        self.base = config.MAKCORPS_BASE_URL.rstrip("/")
        self.verbose = verbose
        self.budget = config.CREDIT_BUDGET if budget is None else budget
        self.mappings = _load_json(MAPPINGS_FILE, {})
        self.credits = _load_json(CREDITS_FILE, {"used": 0})
        self.calls_this_run = 0

    # --- kredi ---
    @property
    def used(self):
        return int(self.credits.get("used", 0))

    @property
    def remaining(self):
        return self.budget - self.used

    def _spend(self, what):
        self.credits["used"] = self.used + 1
        self.calls_this_run += 1
        _save_json(CREDITS_FILE, self.credits)
        print(f"  [kredi] {what} -> harcanan: {self.used}/{self.budget}, "
              f"kalan: {self.remaining}")

    def _require_key(self):
        if not self.api_key:
            raise MakcorpsError(".env icinde MAKCORPS_API_KEY yok")

    def _get(self, path, params, raw_name):
        self._require_key()
        if self.remaining <= 0:
            raise MakcorpsError(f"kredi butcesi bitti ({self.used}/{self.budget}) - "
                                "config.CREDIT_BUDGET ile artirabilirsin")
        url = f"{self.base}{path}"
        r = requests.get(url, params={**params, "api_key": self.api_key}, timeout=60)
        os.makedirs(RAW_DIR, exist_ok=True)
        with open(os.path.join(RAW_DIR, raw_name), "w", encoding="utf-8") as f:
            f.write(r.text)
        if r.status_code != 200:
            self._spend(f"{path} (HTTP {r.status_code})")
            raise MakcorpsError(f"{path} HTTP {r.status_code}: {r.text[:200]}")
        try:
            data = r.json()
        except ValueError:
            self._spend(f"{path} (parse hatasi)")
            raise MakcorpsError(f"{path} JSON degil: {r.text[:200]}")
        self._spend(path)
        time.sleep(config.SLEEP_BETWEEN_CALLS)
        return data

    # --- adim 1: mapping ---
    def mapping_key(self, name, city):
        return f"{name}|{city}".lower()

    def has_mapping(self, name, city):
        return self.mapping_key(name, city) in self.mappings

    def get_hotel_id(self, name, city):
        """document_id dondurur. Sonucu mappings.json'a kalici yazar."""
        key = self.mapping_key(name, city)
        if key in self.mappings:
            hit = self.mappings[key]
            if self.verbose:
                print(f"  [mapping] cache: {name} -> {hit.get('hotel_id')}")
            return hit.get("hotel_id")

        query = f"{name}, {city}"
        data = self._get("/mapping", {"name": query},
                         f"makcorps_mapping_{_slug(query)}.json")
        items = data if isinstance(data, list) else (data.get("data") or data.get("results") or [])
        hotels = [i for i in items
                  if isinstance(i, dict) and str(i.get("type", "")).upper() == "HOTEL"]

        chosen = None
        # 1) tam isim
        for h in hotels:
            if str(h.get("title", "")).strip().lower() == name.strip().lower():
                chosen = h
                break
        # 2) kismi / benzerlik
        if chosen is None:
            scored = sorted(((name_score(name, str(h.get("title", ""))), h) for h in hotels),
                            key=lambda t: t[0], reverse=True)
            if scored and scored[0][0] >= 0.5:
                chosen = scored[0][1]
        # 3) ilk sonuc
        if chosen is None and hotels:
            chosen = hotels[0]

        record = {
            "query": query, "hotel_id": None, "matched_title": None,
            "candidates": [{"title": h.get("title"), "document_id": h.get("document_id")}
                           for h in hotels[:5]],
        }
        if chosen:
            record["hotel_id"] = chosen.get("document_id")
            record["matched_title"] = chosen.get("title")
        self.mappings[key] = record
        _save_json(MAPPINGS_FILE, self.mappings)
        if self.verbose:
            print(f"  [mapping] {name} -> {record['hotel_id']} ({record['matched_title']})")
        return record["hotel_id"]

    # --- adim 2: otel fiyatlari ---
    @staticmethod
    def price_cache_path(hotel_id, checkin, checkout):
        return os.path.join(CACHE_DIR, f"{hotel_id}_{checkin}_{checkout}.json")

    def has_prices(self, hotel_id, checkin, checkout):
        return os.path.exists(self.price_cache_path(hotel_id, checkin, checkout))

    def get_prices(self, hotel_id, checkin, checkout):
        """OTA fiyatlarini dondurur. Ayni kombinasyon icin ikinci kez cagri YAPMAZ."""
        path = self.price_cache_path(hotel_id, checkin, checkout)
        if os.path.exists(path):
            if self.verbose:
                print(f"  [hotel] cache: {hotel_id} {checkin}->{checkout}")
            return _load_json(path, {})
        data = self._get("/hotel", {
            "hotelid": hotel_id,
            "rooms": config.ROOMS,
            "adults": config.ADULTS,
            "checkin": checkin,
            "checkout": checkout,
            "cur": config.PAXIMUM_CURRENCY,   # DIKKAT: cur=, currency= degil
        }, f"makcorps_hotel_{hotel_id}_{checkin}_{checkout}.json")
        os.makedirs(CACHE_DIR, exist_ok=True)
        _save_json(path, data)
        return data

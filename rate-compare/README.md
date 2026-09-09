# rate-compare — Paximum net vs Booking/OTA

Mekke/Medine otelleri icin **online (Booking/OTA) fiyatlari** ile **Paximum net
maliyetimizi** yan yana koyan tek seferlik analiz araci. Production servisi degil.

Iki taraf birbirinden **bagimsiz** calisir:

| Mod | Komut | Ne yapar |
|---|---|---|
| Sadece online | `--ota-only` | Yalnizca MakCorps'tan Booking/Expedia/... fiyatlarini ceker. Paximum'a hic baglanmaz, kimlik bilgisi istemez. |
| Karsilastirma | (bayrak yok) | Online fiyat + Paximum net maliyet, fark ve marj hesabi. |

Once online fiyatlari toplamak icin `--ota-only` yeterli; kendi tedarik tarafi
(Paximum) sonradan devreye alinabilir, o zaman ayni cache tekrar kullanilir.

## Kurulum

```bash
cd ~/code/rate-compare
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env      # sonra .env'i doldur
```

`.env` (asla commit edilmez, `.gitignore`'da):

```
PAXIMUM_PASSWORD=...
MAKCORPS_API_KEY=...
```

## Komutlar

```bash
# --- sadece online (OTA) fiyatlar ---
./venv/bin/python compare.py --ota-only --dry-run --limit 5   # kredi harcamadan maliyeti gor
./venv/bin/python compare.py --ota-only --limit 5             # 5 otel online fiyat
./venv/bin/python compare.py --ota-only --limit 0             # listedeki 20 otelin hepsi
./venv/bin/python compare.py --ota-only --hotel "Voco Makkah, Makkah"   # listede olmayan otel

# --- online + kendi net maliyetimiz (karsilastirma) ---
./venv/bin/python compare.py --limit 5
./venv/bin/python compare.py --limit 10 --dates 2 --margin 0.15
```

Sadece `.env` icinde `MAKCORPS_API_KEY` varsa `--ota-only` calisir;
`PAXIMUM_PASSWORD` sadece karsilastirma modunda gerekir.

| Bayrak | Varsayilan | Aciklama |
|---|---|---|
| `--limit` | 10 | Kac otel. `0` = hepsi. Sehirler arasinda sirayla secer (5 dersen ~3 Mekke 2 Medine). |
| `--hotel` | – | Listede olmayan otel ekle: `--hotel "Otel Adi, Sehir"`. Birden fazla kez kullanilabilir, limitten muaftir. |
| `--ota-only` | – | Sadece online/OTA fiyatlari cek, Paximum'a hic baglanma. |
| `--dates` | 1 | Kac tarih senaryosu (`config.DATE_SCENARIOS` sirasiyla). |
| `--margin` | 0.10 | Satis marji. Excel'deki `%N_marjla_satis` sutunu buna gore adlandirilir. |
| `--budget` | 30 | MakCorps kredi butcesi. |
| `--dry-run` | – | Hic API cagirmadan kac kredi gerektigini yazar. |

## Kredi maliyeti

MakCorps ucretsiz kotasi ~30 cagri. Paximum cagrilari kredi harcamaz.

| Islem | Kredi | Cache |
|---|---|---|
| Mapping (`/mapping`, otel ID) | otel basina 1 | `mappings.json` — **kalici**, bir daha sorulmaz |
| Otel fiyati (`/hotel`) | (otel x tarih senaryosu) basina 1 | `cache/makcorps/<id>_<in>_<out>.json` — ayni kombinasyon icin ikinci cagri YOK |
| Paximum arama | 0 | `cache/paximum/` — sehir basina tek arama, tum oteller tek yanittan |

| Calistirma | Ilk sefer | Cache doluyken |
|---|---|---|
| `--limit 5 --dates 1` | 10 kredi | 0 |
| `--limit 10 --dates 1` | 20 kredi | 0 |
| `--limit 10 --dates 2` | 30 kredi | 10 (yeni tarihler icin) |
| `--limit 20 --dates 3` | 80 kredi | — kota yetmez |

Harcanan krediler `credits.json` icinde tutulur, her cagridan sonra kalan sayi konsola basilir.
Planlanan kredi kalandan fazlaysa calistirma en basta iptal edilir. Cagrilar arasi 1 sn beklenir.

## Cikti

Karsilastirma modunda `output/karsilastirma_YYYYMMDD.xlsx`,
sadece online modunda `output/online_fiyatlar_YYYYMMDD.xlsx`. Her ikisi de 3 sayfa:

1. **karsilastirma** — `otel, sehir, checkin, gece, paximum_net_usd, oda_tipi, pansiyon,
   booking_usd, en_ucuz_ota, en_ucuz_ota_usd, fark_usd, fark_yuzde, %10_marjla_satis,
   marjla_hala_ucuz_mu`
   (sadece online modunda bu sayfa **online_fiyatlar** olur:
   `otel, sehir, checkin, gece, booking_usd, en_ucuz_ota, en_ucuz_ota_usd, vendor_sayisi`)
2. **ota_detay** — her otel icin **tum** vendor'lar (Booking satiri `booking_mu=EVET` ile isaretli)
3. **basarisizlar** — veri gelmeyen oteller ve sebepleri

Hesaplar: `fark_usd = booking_usd - paximum_net_usd`,
`fark_yuzde = fark_usd / booking_usd * 100`,
`%10_marjla_satis = paximum_net_usd * 1.10`,
`marjla_hala_ucuz_mu = (%10_marjla_satis < booking_usd)`.

Tum ham yanitlar `raw/` altina yazilir (sonradan tekrar parse edilebilir).

## Bilinmesi gereken varsayimlar

- **Gecelik vs toplam fiyat.** Paximum konaklamanin tamami icin net fiyat verir;
  MakCorps fiyatlari gecelik gelir. `compare.py` icindeki
  `OTA_PRICE_IS_PER_NIGHT = True` ile OTA fiyati gece sayisiyla carpilir.
  Ilk gercek calistirmada `raw/` altindaki bir MakCorps yanitini gozle dogrula;
  fiyatlar zaten toplam geliyorsa bu bayragi `False` yap — yoksa 3 kat sapma olur.
- **OTA fiyatlarinda vergi.** `Totalprice` varsa o kullanilir (vergi dahil),
  yoksa `price`. Paximum tarafi net maliyet, komisyon/vergi haric.
- **Booking satiri yoksa** referans olarak en ucuz OTA alinir; o satirda
  `booking_usd` bos kalir ama `fark_yuzde` yine dolar.
- **Para birimi.** Her iki tarafta da USD. `/hotel` endpoint'inde parametre
  `cur=` (`currency=` degil) — yanlis yazilirsa sessizce yanlis sonuc doner.
- **Otel eslestirmesi** isim benzerligiyle yapilir (`config.NAME_MATCH_THRESHOLD`,
  varsayilan 0.60). Eslesme skoru konsola basilir; supheli satirlari gozden gecir.
- **Paximum istek govdeleri** (`login` / `getarrivalautocomplete` / `pricesearch`)
  v2 API'sinin dokumante akisina gore yazildi; referans repo
  (`jt-otel-asistan-v2`) bu makinede bulunmadigi icin canli yanitla dogrulanamadi.
  Ilk calistirmada alan adlari uyusmazsa `paximum.py` icindeki `_parse_hotel`
  ve `search_city` govdesi tek noktada duzeltilebilir; ham yanit `raw/` altindadir.

## Saglamlik

Bir otel icin veri gelmezse o satir bos gecilir, calistirma devam eder;
sonunda basarisizlar hem konsolda listelenir hem Excel'de ayri sayfada durur.
Karsilastirma modunda Paximum'a hic baglanilamazsa MakCorps kredisi harcanmadan
cikilir (online fiyatlari yine de toplamak icin `--ota-only` kullan).

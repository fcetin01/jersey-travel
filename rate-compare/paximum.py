"""Paximum v2 - net maliyet fiyatlarimiz.

Akis: login -> arrival autocomplete (sehir id) -> pricesearch (sehirdeki tum oteller).
Sehir bazinda tek arama yapip sonucu cache'liyoruz; otel eslestirmesi lokal.
"""
import json
import os
import re
import time
import unicodedata
from difflib import SequenceMatcher

import requests

import config

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "paximum")
RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")


def _slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def normalize_name(s):
    """Otel adlarini kabaca esitler: noktalama, 'hotel/makkah' gibi genel kelimeler."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    stop = {"hotel", "hotels", "the", "and", "by", "al", "makkah", "mecca", "madinah",
            "medina", "madina", "saudi", "arabia", "ksa"}
    return " ".join(w for w in s.split() if w not in stop)


def name_score(a, b):
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    base = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    overlap = len(ta & tb) / max(1, min(len(ta), len(tb)))
    return max(base, overlap * 0.95)


def _dump_raw(name, payload):
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(os.path.join(RAW_DIR, name), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


class PaximumError(RuntimeError):
    pass


class PaximumClient:
    def __init__(self, password=None, verbose=True):
        self.password = password or os.getenv("PAXIMUM_PASSWORD")
        if not self.password:
            raise PaximumError(".env icinde PAXIMUM_PASSWORD yok")
        self.base = config.PAXIMUM_BASE_URL.rstrip("/")
        self.token = None
        self.verbose = verbose
        self.session = requests.Session()
        self._loc_cache = {}

    # --- dusuk seviye ---
    def _post(self, path, body, timeout=90):
        url = f"{self.base}{path}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        r = self.session.post(url, json=body, headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        header = data.get("header") or {}
        if header.get("success") is False:
            msgs = "; ".join(m.get("message", "") for m in header.get("messages", []))
            raise PaximumError(f"{path} basarisiz: {msgs or data}")
        return data

    def login(self):
        data = self._post("/api/authenticationservice/login", {
            "Agency": config.PAXIMUM_AGENCY,
            "User": config.PAXIMUM_USER,
            "Password": self.password,
        })
        self.token = (data.get("body") or {}).get("token")
        if not self.token:
            raise PaximumError(f"token alinamadi: {data}")
        if self.verbose:
            print("  [paximum] login OK")
        return self.token

    # --- sehir id ---
    def city_location(self, city):
        if city in self._loc_cache:
            return self._loc_cache[city]
        data = self._post("/api/productservice/getarrivalautocomplete", {
            "ProductType": 2, "Query": city, "Culture": config.PAXIMUM_CULTURE,
        })
        _dump_raw(f"paximum_autocomplete_{_slug(city)}.json", data)
        items = (data.get("body") or {}).get("items") or []
        loc = None
        for it in items:
            c = it.get("city") or {}
            if c.get("id"):
                loc = {"id": c["id"], "type": it.get("type", 2), "name": c.get("name", city)}
                break
        if not loc:
            raise PaximumError(f"'{city}' icin lokasyon bulunamadi")
        self._loc_cache[city] = loc
        if self.verbose:
            print(f"  [paximum] {city} -> location id {loc['id']} ({loc['name']})")
        return loc

    # --- sehirdeki tum oteller icin fiyat ---
    def search_city(self, city, checkin, nights, use_cache=True):
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(CACHE_DIR, f"{_slug(city)}_{checkin}_{nights}n.json")
        if use_cache and os.path.exists(cache_file):
            with open(cache_file, encoding="utf-8") as f:
                if self.verbose:
                    print(f"  [paximum] cache: {city} {checkin} ({nights} gece)")
                return json.load(f)

        if not self.token:
            self.login()
        loc = self.city_location(city)
        body = {
            "CheckAllotment": True,
            "CheckStopSale": True,
            "GetOnlyDiscountedPrice": False,
            "GetOnlyBestOffers": True,
            "ProductType": 2,
            "ArrivalLocations": [{"id": loc["id"], "type": loc["type"]}],
            "RoomCriteria": [{"adult": config.ADULTS, "childAges": []}] * config.ROOMS,
            "Nationality": config.PAXIMUM_NATIONALITY,
            "CheckIn": checkin,
            "Night": nights,
            "Currency": config.PAXIMUM_CURRENCY,
            "Culture": config.PAXIMUM_CULTURE,
        }
        data = self._post("/api/productservice/pricesearch", body)
        _dump_raw(f"paximum_search_{_slug(city)}_{checkin}_{nights}n.json", data)
        hotels = (data.get("body") or {}).get("hotels") or []
        parsed = [self._parse_hotel(h) for h in hotels]
        parsed = [p for p in parsed if p]
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        if self.verbose:
            print(f"  [paximum] {city} {checkin}: {len(parsed)} otel fiyati")
        time.sleep(config.SLEEP_BETWEEN_CALLS)
        return parsed

    @staticmethod
    def _parse_hotel(h):
        """Bir otelin EN DUSUK net teklifini cikarir."""
        name = h.get("name") or h.get("hotelName")
        if not name:
            return None
        best = None
        for offer in h.get("offers") or []:
            price = offer.get("price") or {}
            amount = price.get("amount")
            if amount is None:
                continue
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                continue
            rooms = offer.get("rooms") or []
            room = rooms[0] if rooms else {}
            board = (room.get("boardName") or room.get("board", {}).get("name")
                     or offer.get("boardName") or "")
            cand = {
                "price": amount,
                "currency": price.get("currency") or config.PAXIMUM_CURRENCY,
                "room": room.get("name") or room.get("roomName") or "",
                "board": board,
                "offer_id": offer.get("offerId") or offer.get("id"),
            }
            if best is None or cand["price"] < best["price"]:
                best = cand
        if not best:
            return None
        return {"hotel_id": h.get("id"), "hotel_name": name, **best}

    @staticmethod
    def match(hotel_name, parsed_hotels, threshold=None):
        """Listeden en iyi eslesen oteli dondurur (yoksa None)."""
        threshold = config.NAME_MATCH_THRESHOLD if threshold is None else threshold
        best, best_score = None, 0.0
        for ph in parsed_hotels:
            s = name_score(hotel_name, ph["hotel_name"])
            if s > best_score:
                best, best_score = ph, s
        if best and best_score >= threshold:
            return {**best, "match_score": round(best_score, 3)}
        return None

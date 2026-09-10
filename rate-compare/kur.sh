#!/usr/bin/env bash
# Tek seferlik kurulum + ilk test. Kullanim:  bash kur.sh
set -e
cd "$(dirname "$0")"

echo "=============================================="
echo " rate-compare kurulumu"
echo "=============================================="

# 1) python kontrolu
if ! command -v python3 >/dev/null 2>&1; then
  echo "HATA: python3 kurulu degil."
  echo "Mac'te:  brew install python3"
  echo "Windows: https://www.python.org/downloads/ adresinden kur"
  exit 1
fi
echo "[1/4] python3 bulundu: $(python3 --version)"

# 2) venv + paketler
if [ ! -d venv ]; then
  echo "[2/4] sanal ortam kuruluyor..."
  python3 -m venv venv
else
  echo "[2/4] sanal ortam zaten var"
fi
./venv/bin/pip install -q -r requirements.txt
echo "      paketler hazir"

# 3) API key
if [ ! -f .env ]; then
  echo
  echo "[3/4] MakCorps API key gerekiyor."
  echo "      (makcorps.com hesabinizin panelinde yaziyor)"
  read -r -p "      API key'i yapistirip Enter'a bas: " KEY
  if [ -z "$KEY" ]; then
    echo "HATA: bos birakildi, tekrar calistir."
    exit 1
  fi
  echo "MAKCORPS_API_KEY=$KEY" > .env
  chmod 600 .env
  echo "      .env olusturuldu (bu dosya git'e gitmez)"
else
  echo "[3/4] .env zaten var, dokunulmadi"
fi

# 4) once dry-run, sonra onayla gercek calistirma
echo
echo "[4/4] Once PROVA: kac kredi harcanacagini gosterir, API'ye dokunmaz."
echo
./venv/bin/python compare.py --ota-only --dry-run --limit 2

echo
read -r -p "Gercek fiyatlari cekelim mi? (e/h): " YANIT
if [ "$YANIT" = "e" ] || [ "$YANIT" = "E" ]; then
  ./venv/bin/python compare.py --ota-only --limit 2
  echo
  echo "=============================================="
  echo " BITTI"
  echo "=============================================="
  echo "Excel dosyasi:  output/ klasorunde"
  echo "Ham yanitlar :  raw/ klasorunde"
  echo
  echo "Sonraki adim: raw/ klasorundeki makcorps_hotel_*.json dosyasini"
  echo "Claude'a yapistir ki fiyatlarin dogru okundugunu kontrol etsin."
else
  echo "Tamam, birsey cekilmedi. Hazir oldugunda tekrar: bash kur.sh"
fi

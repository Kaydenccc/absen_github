import os
import requests
import random
import math
import time
import pytz
import json
import shutil
from pathlib import Path
from datetime import datetime, time as dt_time

# ================= FILE CACHE =================
CACHE_FILE = Path(".absen_cache.json")
BACKUP_FILE = Path(".absen_cache.backup.json")

# ================= CACHE =================
def load_cache():
    if not CACHE_FILE.exists():
        return {}

    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ CACHE RUSAK")
        return {"__CORRUPTED__": True}

def save_cache(cache):
    if CACHE_FILE.exists():
        shutil.copy(CACHE_FILE, BACKUP_FILE)

    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

# ================= TELEGRAM =================
def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=10
        )
    except Exception as e:
        print("Telegram error:", e)

# ================= MODE OFF =================
def mode_off_manual():
    return os.getenv("ABSEN_MODE", "ON").upper() == "OFF"

# ================= LOGIKA WAKTU =================
def tentukan_jenis_absen(now):
    hari = now.weekday()  # 0=Senin
    jam = now.time()

    # Sabtu & Minggu
    if hari >= 5:
        return None

    # MASUK Senin–Jumat 06:00–07:15
    if dt_time(6, 0) <= jam <= dt_time(7, 15):
        return "masuk"

    # PULANG Senin–Kamis 16:00–17:00
    if hari <= 3 and dt_time(16, 0) <= jam <= dt_time(17, 0):
        return "pulang"

    # PULANG Jumat 16:30–17:30
    if hari == 4 and dt_time(16, 30) <= jam <= dt_time(17, 30):
        return "pulang"

    return None

# ================= MAIN =================
def main():
    if mode_off_manual():
        print("⛔ MODE OFF AKTIF")
        return

    if not CACHE_FILE.exists():
        save_cache({})

    # Konfigurasi
    NIP = "199909262025051003"
    LAT_KANTOR = -3.2795460218952925
    LON_KANTOR = 119.85262806281504

    wita = pytz.timezone("Asia/Makassar")
    now = datetime.now(wita)
    today = now.strftime("%Y-%m-%d")

    print("=" * 50)
    print("🚀 SISTEM ABSEN OTOMATIS")
    print(now.strftime("📅 %d/%m/%Y"))
    print(now.strftime("🕒 %H:%M:%S WITA"))
    print("=" * 50)

    # Tentukan jenis
    jenis_input = os.getenv("JENIS_ABSEN", "auto")
    jenis = tentukan_jenis_absen(now) if jenis_input == "auto" else jenis_input

    if jenis not in ("masuk", "pulang"):
        print("⏸️ BUKAN WAKTU ABSEN")
        return

    # Cache
    cache = load_cache()
    if "__CORRUPTED__" in cache:
        send_telegram("⚠️ <b>CACHE ABSEN RUSAK</b>\nWorkflow dihentikan.")
        return

    if today not in cache:
        cache[today] = {"masuk": False, "pulang": False}

    if cache[today][jenis]:
        send_telegram(
            f"⛔ <b>ABSEN DIBATALKAN</b>\n"
            f"Jenis: {jenis.upper()}\n"
            f"Tanggal: {today}\n"
            f"Alasan: Sudah absen"
        )
        return

    # Delay natural
    delay = random.randint(30, 300)
    print(f"⏳ Delay {delay} detik")
    time.sleep(delay)

    # Lokasi acak ±20m
    r = (20 / 111111) * math.sqrt(random.random())
    t = random.random() * 2 * math.pi
    lat = LAT_KANTOR + r * math.cos(t)
    lon = LON_KANTOR + r * math.sin(t) / math.cos(math.radians(LAT_KANTOR))
    lokasi = f"{round(lat,7)},{round(lon,7)}"

    print(f"🎯 Absen: {jenis}")
    print(f"📍 Lokasi: {lokasi}")

    try:
        res = requests.post(
            "https://sielka.kemenagtanatoraja.id/tambahabsentes.php",
            data={"nip": NIP, "lokasi": lokasi},
            headers={
                "User-Agent": "Dalvik/2.1.0 (Linux; Android 12; Redmi Note 11 Pro)"
            },
            timeout=30
        )

        if res.status_code == 200:
            cache[today][jenis] = True
            save_cache(cache)

            send_telegram(
                f"✅ <b>ABSEN {jenis.upper()} BERHASIL</b>\n"
                f"{now.strftime('%d/%m/%Y %H:%M:%S')} WITA\n"
                f"📍 {lokasi}"
            )
        else:
            send_telegram(
                f"❌ <b>ABSEN GAGAL</b>\n"
                f"Status: {res.status_code}"
            )

    except Exception as e:
        send_telegram(f"🚨 ERROR\n{e}")

if __name__ == "__main__":
    main()


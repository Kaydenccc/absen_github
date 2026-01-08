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

CACHE_FILE = Path(".absen_cache.json")
BACKUP_FILE = Path(".absen_cache.backup.json")

# ================= CACHE =================
def load_cache():
    if not CACHE_FILE.exists() or CACHE_FILE.stat().st_size == 0:
        return {}
    try:
        with CACHE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError
            return data
    except Exception:
        shutil.copy(CACHE_FILE, BACKUP_FILE)
        return {"__CORRUPTED__": True}

def save_cache(cache: dict):
    if CACHE_FILE.exists():
        shutil.copy(CACHE_FILE, BACKUP_FILE)

    tmp = CACHE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    tmp.replace(CACHE_FILE)

# ================= TELEGRAM =================
def send_telegram(msg):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
        timeout=10
    )

# ================= MODE OFF =================
def mode_off_manual():
    return os.getenv("ABSEN_MODE", "ON").upper() == "OFF"

# ================= JENIS ABSEN (HANYA MENENTUKAN JENIS) =================
def tentukan_jenis_absen(now):
    hari = now.weekday()
    jam = now.time()

    if hari >= 5:
        return None

    if dt_time(6, 0) <= jam <= dt_time(7, 15):
        return "masuk"

    if hari <= 3 and dt_time(16, 0) <= jam <= dt_time(17, 0):
        return "pulang"

    if hari == 4 and dt_time(16, 30) <= jam <= dt_time(17, 30):
        return "pulang"

    return None

# ================= JAM MANUSIAWI =================
def generate_target_time(start: dt_time, end: dt_time):
    start_sec = start.hour*3600 + start.minute*60
    end_sec = end.hour*3600 + end.minute*60
    rand = random.randint(start_sec, end_sec)

    h = rand // 3600
    m = (rand % 3600) // 60
    s = random.randint(0, 59)

    return f"{h:02d}:{m:02d}:{s:02d}"

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

    jenis = tentukan_jenis_absen(now)
    if jenis not in ("masuk", "pulang"):
        print("⏸️ Di luar jam absen")
        return

    cache = load_cache()
    if "__CORRUPTED__" in cache:
        send_telegram("⚠️ CACHE RUSAK, workflow dihentikan")
        return

    # Inisialisasi hari
    if today not in cache:
        cache[today] = {
            "masuk": {"done": False, "target": None},
            "pulang": {"done": False, "target": None}
        }

    # Jika sudah absen
    if cache[today][jenis]["done"]:
        print("⛔ Sudah absen hari ini")
        return

    # Tentukan target jam SEKALI SAJA
    if not cache[today][jenis]["target"]:
        if jenis == "masuk":
            cache[today][jenis]["target"] = generate_target_time(
                dt_time(6, 10), dt_time(7, 10)
            )
        else:
            if now.weekday() == 4:
                cache[today][jenis]["target"] = generate_target_time(
                    dt_time(16, 35), dt_time(17, 20)
                )
            else:
                cache[today][jenis]["target"] = generate_target_time(
                    dt_time(16, 10), dt_time(16, 55)
                )
        save_cache(cache)

    target = datetime.strptime(
        cache[today][jenis]["target"], "%H:%M:%S"
    ).time()

    # BELUM WAKTUNYA
    if now.time() < target:
        print(f"⏳ Menunggu jam target {target}")
        return

    # ================= LOKASI =================
    r = (20 / 111111) * math.sqrt(random.random())
    t = random.random() * 2 * math.pi
    lat = LAT_KANTOR + r * math.cos(t)
    lon = LON_KANTOR + r * math.sin(t) / math.cos(math.radians(LAT_KANTOR))
    lokasi = f"{round(lat,7)},{round(lon,7)}"

    print(f"🎯 Absen {jenis} @ {lokasi}")

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
            cache[today][jenis]["done"] = True
            save_cache(cache)

            send_telegram(
                f"✅ <b>ABSEN {jenis.upper()} BERHASIL</b>\n"
                f"📅 {now.strftime('%d/%m/%Y %H:%M:%S')} WITA\n"
                f"📍 {lokasi}\n"
                f"📝 {res.text.strip()}"
            )
        else:
            send_telegram(f"❌ ABSEN GAGAL ({res.status_code})")

    except Exception as e:
        send_telegram(f"🚨 ERROR\n{e}")

if __name__ == "__main__":
    main()

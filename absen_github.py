import os
import requests
import random
import math
import pytz
import json
import shutil
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta

# ================= FILE CACHE =================
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
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print("Telegram error:", e)

# ================= MODE =================
def mode_off():
    return os.getenv("ABSEN_MODE", "ON").upper() == "OFF"

# ================= JENIS ABSEN =================
def tentukan_jenis_absen(now):
    hari = now.weekday()
    jam = now.time()

    if hari >= 5:
        return None

    # MASUK: 06:00 – 07:30
    if dt_time(6, 0) <= jam <= dt_time(7, 30):
        return "masuk"

    # PULANG SENIN–KAMIS
    if hari <= 3 and dt_time(16, 0) <= jam <= dt_time(17, 30):
        return "pulang"

    # PULANG JUMAT
    if hari == 4 and dt_time(16, 30) <= jam <= dt_time(18, 0):
        return "pulang"

    return None

# ================= OFFSET MENIT =================
def generate_offset(jenis, hari):
    if jenis == "masuk":
        return random.randint(5, 30)   # maksimal 07:00
    if hari == 4:  # Jumat
        return random.randint(5, 30)
    return random.randint(5, 30)

# ================= MAIN =================
def main():
    if mode_off():
        print("⛔ MODE OFF")
        return

    if not CACHE_FILE.exists():
        save_cache({})

    # DATA ABSEN
    NIP = "199909262025051003"
    LAT = -3.279389
    LON = 119.852500

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
        send_telegram("⚠️ CACHE RUSAK – workflow dihentikan")
        return

    # ===== NORMALISASI CACHE (ANTI ERROR LAMA) =====
    if today not in cache:
        cache[today] = {}

    if jenis not in cache[today] or isinstance(cache[today][jenis], bool):
        cache[today][jenis] = {"done": False, "offset": None}

    if cache[today][jenis]["done"]:
        print("⛔ Sudah absen hari ini")
        return

    # ===== OFFSET SEKALI PER HARI =====
    if cache[today][jenis]["offset"] is None:
        offset = generate_offset(jenis, now.weekday())
        cache[today][jenis]["offset"] = offset
        save_cache(cache)
    else:
        offset = cache[today][jenis]["offset"]

    # ===== JAM DASAR =====
    if jenis == "masuk":
        base_time = dt_time(6, 0)
    elif now.weekday() == 4:
        base_time = dt_time(16, 30)
    else:
        base_time = dt_time(16, 0)

    target_time = (
        datetime.combine(now.date(), base_time) + timedelta(minutes=offset)
    ).time()

    # BATAS MASUK 07:30
    if jenis == "masuk" and target_time > dt_time(7, 30):
        target_time = dt_time(7, 30)

    if now.time() < target_time:
        print(f"⏳ Menunggu jam manusiawi {target_time}")
        return

    # ===== LOKASI (simulasi GPS HP — akurasi 5-18m, 6 desimal) =====
    radius = random.uniform(5, 18)
    r = (radius / 111111) * math.sqrt(random.random())
    t = random.random() * 2 * math.pi
    lat = LAT + r * math.cos(t)
    lon = LON + r * math.sin(t) / math.cos(math.radians(LAT))
    lokasi = f"{round(lat,6)},{round(lon,6)}"

    try:
        res = requests.post(
            "https://sielka.kemenagtanatoraja.id/tambahabsentes.php",
            data={"nip": NIP, "lokasi": lokasi},
            headers={"User-Agent": "Dalvik/2.1.0"},
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

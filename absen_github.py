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

# ================= KONFIGURASI =================
NIP         = "199909262025051003"
PASSWORD    = os.getenv("SIELKA_PASSWORD")
DEVICE_ID   = os.getenv("SIELKA_DEVICE_ID")
BASE_URL    = "https://absensi.kemenagtanatoraja.id/api"

# Koordinat kantor / lokasi kerja
LAT_BASE    = -3.279546
LON_BASE    = 119.852628

# Cloudflare Worker relay
CF_WORKER_URL   = os.getenv("CF_WORKER_URL")
CF_RELAY_SECRET = os.getenv("CF_RELAY_SECRET")

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
    token   = os.getenv("TELEGRAM_TOKEN")
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

# ================= HEADERS =================
def get_headers():
    """Header yang meniru aplikasi Flutter SIELKA asli."""
    return {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept":       "application/json",
        "X-Device-ID":  DEVICE_ID,
        "X-User-NIP":   NIP,
        "User-Agent":   "Dalvik/2.1.0 (Linux; U; Android 11; 2201116SG Build/RKQ1.211001.001)",
    }

# ================= REQUEST VIA RELAY =================
def relay_request(method, url, form_data=None, session_cookies=None):
    """Kirim request lewat Cloudflare Worker relay."""
    payload = {
        "url":     url,
        "method":  method.upper(),
        "headers": get_headers(),
        "data":    form_data,
        "cookies": session_cookies or {},
    }
    res = requests.post(
        CF_WORKER_URL,
        json=payload,
        headers={
            "Content-Type":   "application/json",
            "X-Relay-Secret": CF_RELAY_SECRET,
        },
        timeout=30
    )
    result = res.json()
    body = result.get("body", "{}")
    try:
        body_json = json.loads(body)
    except Exception:
        body_json = {"raw": body}

    new_cookies = result.get("cookies", {})
    return result.get("status", 0), body_json, new_cookies

# ================= LOGIN =================
def login(session: requests.Session):
    """Login ke SIELKA v2."""
    form_data = {
        "nip":       NIP,
        "password":  PASSWORD,
        "device_id": DEVICE_ID,
    }
    try:
        if CF_WORKER_URL:
            status, data, cookies = relay_request("POST", f"{BASE_URL}/login", form_data)
        else:
            res = session.post(
                f"{BASE_URL}/login",
                data=form_data,        # form-urlencoded
                headers=get_headers(),
                timeout=30
            )
            data    = res.json()
            cookies = {}

        if data.get("success"):
            # Simpan cookie ke session
            for k, v in cookies.items():
                session.cookies.set(k, v)
            print(f"✅ Login berhasil — {data['data']['nama']} ({data['data']['unit']})")
            return True, cookies
        else:
            print(f"❌ Login gagal: {data.get('message')}")
            send_telegram(f"❌ <b>LOGIN GAGAL</b>\n{data.get('message')}")
            return False, {}
    except Exception as e:
        print(f"❌ Login error: {e}")
        send_telegram(f"🚨 <b>LOGIN ERROR</b>\n{e}")
        return False, {}

# ================= JENIS ABSEN =================
def tentukan_jenis_absen(now):
    hari = now.weekday()
    jam  = now.time()

    if hari >= 5:
        return None

    if dt_time(6, 0) <= jam <= dt_time(7, 30):
        return "masuk"

    if hari <= 3 and dt_time(16, 0) <= jam <= dt_time(17, 30):
        return "pulang"

    if hari == 4 and dt_time(16, 30) <= jam <= dt_time(18, 0):
        return "pulang"

    return None

# ================= OFFSET =================
def generate_offset(jenis, hari):
    return random.randint(5, 30)

# ================= SIMULASI GPS =================
def simulasi_gps():
    radius = random.uniform(5, 18)
    r = (radius / 111111) * math.sqrt(random.random())
    t = random.random() * 2 * math.pi
    lat = LAT_BASE + r * math.cos(t)
    lon = LON_BASE + r * math.sin(t) / math.cos(math.radians(LAT_BASE))
    accuracy = round(random.uniform(5.0, 18.0), 1)
    return round(lat, 7), round(lon, 7), accuracy

# ================= REKAM ABSEN =================
def rekam_absen(session: requests.Session, lat, lon, accuracy, relay_cookies=None):
    """Kirim data absensi ke endpoint SIELKA v2."""
    form_data = {
        "latitude":          str(lat),
        "longitude":         str(lon),
        "accuracy":          str(accuracy),
        "altitude":          "0.0",
        "altitude_accuracy": "0.0",
        "speed_accuracy":    "0.0",
        "heading_accuracy":  "0.0",
    }
    try:
        if CF_WORKER_URL:
            _, data, _ = relay_request(
                "POST",
                f"{BASE_URL}/attendance/record",
                form_data,
                relay_cookies
            )
        else:
            res = session.post(
                f"{BASE_URL}/attendance/record",
                data=form_data,        # form-urlencoded
                headers=get_headers(),
                timeout=30
            )
            data = res.json()

        return data.get("success", False), data.get("message", str(data))
    except Exception as e:
        return False, str(e)

# ================= MAIN =================
def main():
    if mode_off():
        print("⛔ MODE OFF — absen dilewati")
        return

    if not PASSWORD or not DEVICE_ID:
        msg = "⚠️ SIELKA_PASSWORD atau SIELKA_DEVICE_ID belum diset!"
        print(msg)
        send_telegram(msg)
        return

    if CF_WORKER_URL:
        print("🔀 Mode: Cloudflare Worker Relay")
    else:
        print("🔗 Mode: Direct Request")

    if not CACHE_FILE.exists():
        save_cache({})

    wita  = pytz.timezone("Asia/Makassar")
    now   = datetime.now(wita)
    today = now.strftime("%Y-%m-%d")

    print("=" * 50)
    print("🚀 SISTEM ABSEN OTOMATIS — SIELKA v2")
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

    if today not in cache:
        cache[today] = {}
    if jenis not in cache[today] or isinstance(cache[today][jenis], bool):
        cache[today][jenis] = {"done": False, "offset": None}

    if cache[today][jenis]["done"]:
        print(f"⛔ Absen {jenis} hari ini sudah tercatat")
        return

    if cache[today][jenis]["offset"] is None:
        offset = generate_offset(jenis, now.weekday())
        cache[today][jenis]["offset"] = offset
        save_cache(cache)
    else:
        offset = cache[today][jenis]["offset"]

    if jenis == "masuk":
        base_time = dt_time(6, 0)
    elif now.weekday() == 4:
        base_time = dt_time(16, 30)
    else:
        base_time = dt_time(16, 0)

    target_time = (
        datetime.combine(now.date(), base_time) + timedelta(minutes=offset)
    ).time()

    if jenis == "masuk" and target_time > dt_time(7, 30):
        target_time = dt_time(7, 30)

    if now.time() < target_time:
        print(f"⏳ Menunggu jam manusiawi → {target_time.strftime('%H:%M')} WITA")
        return

    lat, lon, accuracy = simulasi_gps()
    print(f"📍 Lokasi: {lat}, {lon} (±{accuracy}m)")

    session = requests.Session()
    ok, relay_cookies = login(session)
    if not ok:
        return

    print(f"📤 Mengirim absen {jenis.upper()}...")
    success, message = rekam_absen(session, lat, lon, accuracy, relay_cookies)

    if success:
        cache[today][jenis]["done"] = True
        save_cache(cache)
        hari_nama = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"][now.weekday()]
        send_telegram(
            f"✅ <b>ABSEN {jenis.upper()} BERHASIL</b>\n"
            f"📅 {hari_nama}, {now.strftime('%d/%m/%Y %H:%M:%S')} WITA\n"
            f"📍 {lat}, {lon} (±{accuracy}m)\n"
            f"💬 {message}"
        )
        print(f"✅ Absen {jenis} berhasil: {message}")
    else:
        send_telegram(
            f"❌ <b>ABSEN {jenis.upper()} GAGAL</b>\n"
            f"📅 {now.strftime('%d/%m/%Y %H:%M:%S')} WITA\n"
            f"💬 {message}"
        )
        print(f"❌ Absen {jenis} gagal: {message}")

if __name__ == "__main__":
    main()

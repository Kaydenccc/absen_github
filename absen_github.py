import os
import requests
import random
import math
import time
from datetime import datetime
import pytz


def send_telegram(message):
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    if not token or not chat_id:
        print("⚠️ Telegram token/chat_id tidak ditemukan")
        return

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Telegram error: {e}")


def tentukan_jenis_absen(now):
    """
    Menentukan jenis absen berdasarkan waktu WITA
    """
    hari = now.weekday()   # 0=Senin ... 4=Jumat
    jam = now.hour
    menit = now.minute

    # === ABSEN MASUK (Senin–Jumat 06:00–07:15) ===
    if 0 <= hari <= 4:
        if jam == 6:
            return "masuk"
        if jam == 7 and menit <= 15:
            return "masuk"

    # === ABSEN PULANG SENIN–KAMIS (16:00–17:00) ===
    if 0 <= hari <= 3:
        if jam == 16:
            return "pulang"
        if jam == 17 and menit == 0:
            return "pulang"

    # === ABSEN PULANG JUMAT (16:30–17:30) ===
    if hari == 4:
        if (jam == 16 and menit >= 30) or (jam == 17 and menit <= 30):
            return "pulang"

    return None

def sudah_absen(jenis, now):
    tanggal = now.strftime("%Y-%m-%d")
    os.makedirs(".absen_log", exist_ok=True)
    file_log = f".absen_log/{tanggal}_{jenis}.log"
    return os.path.exists(file_log), file_log

def cek_dan_buat_log(jenis, now):
    tanggal = now.strftime("%Y-%m-%d")
    os.makedirs(".absen_log", exist_ok=True)
    path = f".absen_log/{tanggal}_{jenis}.log"

    if os.path.exists(path):
        return False, path   # sudah absen

    return True, path

def mode_off_manual():
    mode = os.getenv("ABSEN_MODE", "ON").upper()
    return mode == "OFF"


def main():
    # ================= MODE OFF MANUAL =================
    if mode_off_manual():
        print("⛔ MODE OFF MANUAL AKTIF - absensi dinonaktifkan")
        return

    # ================= KONFIGURASI =================
    NIP = "199909262025051003"
    LAT_KANTOR = -3.2795460218952925
    LON_KANTOR = 119.85262806281504

    wita = pytz.timezone("Asia/Makassar")
    now = datetime.now(wita)

    print("=" * 50)
    print("🚀 SISTEM ABSEN OTOMATIS")
    print(f"📅 {now.strftime('%d/%m/%Y')}")
    print(f"🕒 {now.strftime('%H:%M:%S')} WITA")
    print("=" * 50)

    # ================= JENIS ABSEN =================
    jenis_input = os.getenv("JENIS_ABSEN", "auto")

    if jenis_input == "auto":
        jenis = tentukan_jenis_absen(now)
        if not jenis:
            print("⏸️ Di luar jam absen")
            return
    else:
        jenis = jenis_input

    # ================= PROTEKSI 1 HARI 1x =================
    boleh, file_log = cek_dan_buat_log(jenis, now)
    if not boleh:
       print(f"⛔ Absen {jenis} hari ini sudah dilakukan")
       return




    # ================= RANDOM DELAY =================
    delay = random.randint(30, 300)
    print(f"⏳ Delay {delay} detik agar natural...")
    time.sleep(delay)

    # ================= RANDOM LOKASI =================
    radius_deg = 20 / 111111.0
    r = radius_deg * math.sqrt(random.random())
    theta = random.random() * 2 * math.pi

    delta_lat = r * math.cos(theta)
    delta_lon = r * math.sin(theta) / math.cos(math.radians(LAT_KANTOR))

    lat = LAT_KANTOR + delta_lat
    lon = LON_KANTOR + delta_lon
    lokasi = f"{round(lat,7)},{round(lon,7)}"

    print(f"🎯 Absen: {jenis}")
    print(f"📍 Lokasi: {lokasi}")

    # ================= KIRIM ABSEN =================
    try:
        response = requests.post(
            "https://sielka.kemenagtanatoraja.id/tambahabsentes.php",
            data={"nip": NIP, "lokasi": lokasi},
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        sukses = response.status_code == 200 and "berhasil" in response.text.lower()

        if sukses:
            with open(file_log, "w") as f:
                f.write(f"{now.isoformat()} | {lokasi}\n")

            send_telegram(
                f"✅ <b>ABSEN {jenis.upper()} BERHASIL</b>\n"
                f"📅 {now.strftime('%d/%m/%Y %H:%M:%S')} WITA\n"
                f"📍 {lokasi}\n"
                f"📝 {response.text.strip()}"
            )
        else:
            send_telegram(
                f"❌ <b>ABSEN {jenis.upper()} GAGAL</b>\n"
                f"📅 {now.strftime('%d/%m/%Y %H:%M:%S')} WITA\n"
                f"📍 {lokasi}\n"
                f"🔢 {response.status_code}\n"
                f"📝 {response.text[:120]}"
            )

    except Exception as e:
        send_telegram(f"🚨 <b>ERROR SISTEM</b>\n{str(e)}")


if __name__ == "__main__":
    main()

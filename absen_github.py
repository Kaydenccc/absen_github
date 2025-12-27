import os
import requests
import random
import math
from datetime import datetime, time as dt_time
import pytz

def send_telegram(message):
    """Send notification to Telegram"""
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("⚠️ Telegram token/chat_id tidak ditemukan")
        return
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=10)
        print(f"📱 Telegram sent: {response.status_code}")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

def main():
    # Konfigurasi
    NIP = "199909262025051003"
    LAT_KANTOR = -3.2795460218952925
    LON_KANTOR = 119.85262806281504
    
    # Waktu sekarang (WITA)
    wita = pytz.timezone('Asia/Makassar')
    now = datetime.now(wita)
    hari = now.weekday()  # 0=Senin, 4=Jumat
    jam = now.time()
    
    print("=" * 50)
    print(f"🚀 SISTEM ABSEN OTOMATIS")
    print(f"📅 Tanggal: {now.strftime('%d/%m/%Y')}")
    print(f"🕒 Waktu: {now.strftime('%H:%M:%S')} WITA")
    print(f"📆 Hari: {['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'][hari]}")
    print("=" * 50)
    
    # Tentukan jenis absen
    # 1. Cek input manual dari workflow_dispatch
    jenis_input = os.getenv('JENIS_ABSEN', 'auto')
    
    # 2. Jika auto, tentukan berdasarkan waktu
    if jenis_input == 'auto':
        # Cek masuk (Senin-Jumat 06:10-07:20)
        if 0 <= hari <= 4 and dt_time(6, 10) <= jam <= dt_time(7, 20):
            jenis = "masuk"
        # Cek pulang Senin-Kamis (16:00-17:00)
        elif 0 <= hari <= 3 and dt_time(16, 0) <= jam <= dt_time(17, 0):
            jenis = "pulang"
        # Cek pulang Jumat (16:30-17:10)
        elif hari == 4 and dt_time(16, 30) <= jam <= dt_time(17, 10):
            jenis = "pulang_jumat"
        else:
            print("⏸️ Bukan waktu absen")
            send_telegram(f"⏸️ <b>BUKAN WAKTU ABSEN</b>\n🕒 {now.strftime('%H:%M:%S')} WITA")
            return
    else:
        jenis = jenis_input
    
    # Generate random coordinate within 20m
    radius_deg = 20 / 111111.0
    r = radius_deg * math.sqrt(random.random())
    theta = random.random() * 2 * math.pi
    
    delta_lat = r * math.cos(theta)
    delta_lon = r * math.sin(theta) / math.cos(math.radians(LAT_KANTOR))
    
    lat = LAT_KANTOR + delta_lat
    lon = LON_KANTOR + delta_lon
    lokasi = f"{round(lat, 7)},{round(lon, 7)}"
    
    print(f"🎯 Jenis absen: {jenis}")
    print(f"📍 Koordinat acak: {lokasi}")
    
    # Kirim request absen
    try:
        data = {
            'nip': NIP,
            'lokasi': lokasi
        }
        
        print(f"📤 Mengirim request ke API...")
        response = requests.post(
            'https://sielka.kemenagtanatoraja.id/tambahabsentes.php',
            data=data,
            timeout=30,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        
        print(f"📥 Response code: {response.status_code}")
        print(f"📝 Response text: {response.text.strip()}")
        
        # Kirim notifikasi Telegram
        if response.status_code == 200 and "berhasil" in response.text.lower():
            message = (
                f"✅ <b>ABSEN {jenis.upper()} BERHASIL</b>\n"
                f"📅 {now.strftime('%d/%m/%Y %H:%M:%S')} WITA\n"
                f"📍 {lokasi}\n"
                f"📝 {response.text.strip()}"
            )
            send_telegram(message)
        else:
            message = (
                f"❌ <b>ABSEN {jenis.upper()} GAGAL</b>\n"
                f"📅 {now.strftime('%d/%m/%Y %H:%M')}\n"
                f"📍 {lokasi}\n"
                f"🔢 Status: {response.status_code}\n"
                f"📝 Pesan: {response.text[:100]}"
            )
            send_telegram(message)
        
    except Exception as e:
        error_msg = f"🚨 <b>ERROR SISTEM</b>\n{str(e)}"
        print(f"❌ Exception: {e}")
        send_telegram(error_msg)

if __name__ == "__main__":
    main()
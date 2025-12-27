import os
import requests
import random
import math
from datetime import datetime, time as dt_time
import pytz

def main():
    # Konfigurasi
    NIP = "199909262025051003"
    LAT_KANTOR = -3.2795460218952925
    LON_KANTOR = 119.85262806281504
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # Setup timezone
    wita = pytz.timezone('Asia/Makassar')
    now = datetime.now(wita)
    hari = now.weekday()
    jam = now.time()
    
    # Generate random coordinate
    radius_deg = 20 / 111111.0
    r = radius_deg * math.sqrt(random.random())
    theta = random.random() * 2 * math.pi
    delta_lat = r * math.cos(theta)
    delta_lon = r * math.sin(theta) / math.cos(math.radians(LAT_KANTOR))
    
    lat = LAT_KANTOR + delta_lat
    lon = LON_KANTOR + delta_lon
    lokasi = f"{round(lat, 7)},{round(lon, 7)}"
    
    # Tentukan jenis absen
    jenis = None
    
    # Check masuk
    if 0 <= hari <= 4:  # Senin-Jumat
        if dt_time(6, 10) <= jam <= dt_time(7, 20):
            jenis = "masuk"
    
    # Check pulang
    if 0 <= hari <= 3:  # Senin-Kamis
        if dt_time(16, 0) <= jam <= dt_time(17, 0):
            jenis = "pulang"
    elif hari == 4:  # Jumat
        if dt_time(16, 30) <= jam <= dt_time(17, 10):
            jenis = "pulang_jumat"
    
    if not jenis:
        print("⏸️ Bukan waktu absen")
        return
    
    # Kirim absen
    data = {'nip': NIP, 'lokasi': lokasi}
    
    try:
        response = requests.post(
            'https://sielka.kemenagtanatoraja.id/tambahabsentes.php',
            data=data,
            timeout=30
        )
        
        if response.status_code == 200:
            # Kirim notifikasi Telegram
            if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
                msg = f"✅ <b>ABSEN {jenis.upper()}</b>\n"
                msg += f"📅 {now.strftime('%d/%m/%Y %H:%M')} WITA\n"
                msg += f"📍 {lokasi}\n"
                msg += f"📝 {response.text}"
                
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                requests.post(url, json={
                    'chat_id': TELEGRAM_CHAT_ID,
                    'text': msg,
                    'parse_mode': 'HTML'
                })
            
            print(f"✅ Success: {response.text}")
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"🚨 Error: {e}")

if __name__ == "__main__":
    main()
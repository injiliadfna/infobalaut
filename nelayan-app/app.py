from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import csv
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database_pasut.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- 1. KONFIGURASI LOKASI ---
LOKASI_INFO = {
    "Manado": {
        "lat": 1.4977, 
        "lon": 124.8394,
        "foto": "/static/images/manado.jpg",
        "deskripsi": "Urat nadi transportasi penumpang (Sitaro, Sangihe, Talaud) dan akses utama menuju Bunaken."
    },  # <--- TAMBAHKAN KOMA DI SINI
    "Bitung": {
        "lat": 1.4490794119586439, 
        "lon": 125.20737763152611,
        "foto": "/static/images/bitung.jpg",
        "deskripsi": "Pusat industri perikanan terbesar dan Pelabuhan Hub Internasional di Indonesia Timur."
    },  # <--- TAMBAHKAN KOMA DI SINI
    "Likupang": {
        "lat": 1.6902969042667804, 
        "lon": 125.06386941954833,
        "foto": "/static/images/likupang.jpg",
        "deskripsi": "Pusat pertumbuhan baru Kawasan Ekonomi Khusus (KEK) Pariwisata Super Prioritas."
    }
}
# --- 2. MODEL DATABASE ---
class JadwalPasut(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lokasi = db.Column(db.String(50))
    waktu = db.Column(db.DateTime)
    tinggi = db.Column(db.Float)
    jenis = db.Column(db.String(20))

# --- 3. LOGIKA BARU REKOMENDASI ---
def get_rekomendasi(tinggi, jenis_next):
    # 🔴 BAHAYA: Air terlalu dangkal
    if tinggi < 0.5:
        return "BAHAYA", "from-red-600 to-rose-900", "❌", "Air terlalu dangkal! Kapal berisiko kandas."
    # 🟡 WASPADA: Pasang tinggi atau menuju surut
    elif tinggi >= 1.8 or jenis_next == 'Surut':
        msg = "Pasang tinggi (Arus Kuat)." if tinggi >= 1.8 else "Air menuju surut, tetap waspada."
        return "WASPADA", "from-amber-500 to-orange-700", "📉", msg
    # 🟢 AMAN: Tinggi normal & stabil
    else:
        return "AMAN", "from-emerald-500 to-teal-700", "🌊", "Air naik stabil. Kondisi terbaik melaut."

# --- 4. LOGIKA INSIGHT INTERVAL ---
def generate_insights(events_today):
    insights = []
    if len(events_today) < 2: return insights
    for i in range(len(events_today) - 1):
        start = events_today[i]
        end = events_today[i+1]
        
        if end.jenis == 'Pasang':
            if 0.5 <= end.tinggi < 1.8:
                st, ic, ds, cl = "AMAN", "🌊", "Air naik stabil", "text-emerald-400"
            else:
                st, ic, ds, cl = "WASPADA", "⚠️", "Arus pasang kuat", "text-amber-400"
        else:
            if end.tinggi < 0.5:
                st, ic, ds, cl = "BAHAYA", "❌", "Risiko kandas", "text-red-400"
            else:
                st, ic, ds, cl = "WASPADA", "📉", "Menuju surut", "text-amber-400"

        insights.append({
            "waktu": f"{start.waktu.strftime('%H:%M')} – {end.waktu.strftime('%H:%M')}",
            "status": st, "icon": ic, "desc": ds, "color": cl
        })
    return insights

# --- 5. ROUTES (PASTIKAN NAMA FUNGSI BERBEDA) ---

@app.route('/')
def index():
    # 1. Identifikasi Lokasi & Waktu
    lokasi_aktif = request.args.get('lokasi', 'Manado')
    daftar_kota = [k[0] for k in db.session.query(JadwalPasut.lokasi).distinct().all()]
    now = datetime.now()
    
    # 2. Ambil Detail Lokasi (Untuk Background Foto)
    lokasi_detail = LOKASI_INFO.get(lokasi_aktif, LOKASI_INFO['Manado'])

    # 3. Ambil Kejadian Hari Ini (Untuk Insight)
    events_today = JadwalPasut.query.filter(
        JadwalPasut.lokasi == lokasi_aktif, 
        db.func.date(JadwalPasut.waktu) == now.date()
    ).order_by(JadwalPasut.waktu.asc()).all()
    insights = generate_insights(events_today)

    # 4. Ambil Data Mendatang Terdekat (Untuk Status & Kartu Detail)
    data = JadwalPasut.query.filter(
        JadwalPasut.lokasi == lokasi_aktif, 
        JadwalPasut.waktu >= now
    ).order_by(JadwalPasut.waktu.asc()).first()
    
    # Hitung Rekomendasi
    status, warna, icon, tips = get_rekomendasi(data.tinggi, data.jenis) if data else ("-", "from-slate-700 to-slate-900", "?", "-")
    
    return render_template('index.html', 
                           data=data, 
                           status=status, 
                           warna=warna, 
                           icon=icon, 
                           tips=tips, 
                           lokasi_aktif=lokasi_aktif, 
                           daftar_kota=daftar_kota, 
                           now=now, 
                           insights=insights, 
                           lokasi_detail=lokasi_detail)

@app.route('/mingguan')
def mingguan():
    lokasi_aktif = request.args.get('lokasi', 'Manado')
    tgl_pilihan = request.args.get('tanggal', datetime.now().strftime('%Y-%m-%d'))
    now = datetime.now()
    
    hari_raw = db.session.query(db.func.date(JadwalPasut.waktu)).filter(
        JadwalPasut.lokasi == lokasi_aktif, 
        JadwalPasut.waktu >= now.date()
    ).distinct().order_by(db.func.date(JadwalPasut.waktu).asc()).limit(7).all()
    
    hari_indo = {'Monday': 'SENIN', 'Tuesday': 'SELASA', 'Wednesday': 'RABU', 'Thursday': 'KAMIS', 'Friday': 'JUMAT', 'Saturday': 'SABTU', 'Sunday': 'MINGGU'}
    # Mapping Bulan Indonesia
    bulan_indo = {'01': 'Januari', '02': 'Februari', '03': 'Maret', '04': 'April', '05': 'Mei', '06': 'Juni', '07': 'Juli', '08': 'Agustus', '09': 'September', '10': 'Oktober', '11': 'November', '12': 'Desember'}
    
    hari_list = []
    for h in hari_raw:
        dt_obj = datetime.strptime(h[0], '%Y-%m-%d')
        hari_list.append({
            'tgl_str': h[0],
            'tgl_tampil': dt_obj.strftime('%d'), # Hanya angka tanggal
            'bulan_tampil': bulan_indo[dt_obj.strftime('%m')], # Nama bulan
            'nama_hari': hari_indo[dt_obj.strftime('%A')]
        })
    
    events = JadwalPasut.query.filter(JadwalPasut.lokasi == lokasi_aktif, db.func.date(JadwalPasut.waktu) == tgl_pilihan).order_by(JadwalPasut.waktu.asc()).all()
    labels = [e.waktu.strftime("%H:%M") for e in events]
    values = [e.tinggi for e in events]

    return render_template('mingguan.html', lokasi_aktif=lokasi_aktif, hari_list=hari_list, tgl_pilihan=tgl_pilihan, labels=labels, values=values, events=events, now=now)

@app.route('/peta')
def peta():
    # 1. Ambil lokasi yang dipilih dari URL, jika tidak ada default ke Manado
    lokasi_aktif = request.args.get('lokasi', 'Manado')
    now = datetime.now()
    
    # 2. Ambil koordinat pusat berdasarkan lokasi terpilih
    coords = LOKASI_INFO.get(lokasi_aktif, LOKASI_INFO['Manado'])
    
    # 3. Hitung status semua pelabuhan untuk marker berwarna
    all_ports_status = []
    for lok_name, lok_detail in LOKASI_INFO.items():
        data = JadwalPasut.query.filter(JadwalPasut.lokasi == lok_name, JadwalPasut.waktu >= now).order_by(JadwalPasut.waktu.asc()).first()
        if not data:
            data = JadwalPasut.query.filter_by(lokasi=lok_name).order_by(JadwalPasut.waktu.desc()).first()

        status, _, icon, tips = get_rekomendasi(data.tinggi, data.jenis) if data else ("-", "", "?", "")
        
        # Penentuan warna marker
        marker_color = "#10b981" # Hijau (Aman)
        if status == "BAHAYA": marker_color = "#e11d48" # Merah
        elif status == "WASPADA": marker_color = "#f59e0b" # Kuning

        all_ports_status.append({
            "nama": lok_name,
            "lat": lok_detail['lat'],
            "lon": lok_detail['lon'],
            "foto": lok_detail['foto'],
            "deskripsi": lok_detail['deskripsi'],
            "status": status,
            "color": marker_color,
            "tinggi": data.tinggi if data else 0,
            "jam": data.waktu.strftime('%H:%M') if data else '--:--',
            "jenis": data.jenis if data else '-'
        })

    return render_template('peta.html', 
                           lokasi_aktif=lokasi_aktif, 
                           ports=all_ports_status, 
                           coords=coords, 
                           now=now)

@app.route('/tentang')
def tentang():
    lokasi_aktif = request.args.get('lokasi', 'Manado')
    now = datetime.now()
    return render_template('tentang.html', lokasi_aktif=lokasi_aktif, now=now)

# --- 6. START SERVER ---
def seed_db():
    if JadwalPasut.query.count() == 0:
        files = [f for f in os.listdir('.') if f.endswith('.csv')]
        for filename in files:
            lok = filename.replace('.csv', '')
            with open(filename, mode='r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    db.session.add(JadwalPasut(lokasi=lok, waktu=datetime.strptime(row['Waktu'], '%Y-%m-%d %H:%M:%S'), tinggi=float(row['Ketinggian (m)']), jenis=row['Jenis']))
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_db()
    app.run(debug=True)
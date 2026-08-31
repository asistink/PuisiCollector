# PACS262521 - Pengembangan Perangkat Lunak Scalable
## Penugasan Terstruktur: Pembangunan Aplikasi Monolitik Stateful dan Deployment pada AWS EC2
**Dosen Pengampu**: I Gede Mujiyatna (`demuji@ugm.ac.id`)

---

## 1. Ringkasan Arsitektur Sistem

Aplikasi ini dibangun sebagai **"ground truth" (baseline) arsitektur monolitik-stateful** murni tanpa framework besar, sesuai batasan teknis penugasan.

### Karakteristik Utama Arsitektur:
1. **Backend Murni (Python Standard Library)**:
   - Menggunakan modul bawaan `http.server`, `sqlite3`, dan `json`.
   - **Zero external dependencies**: Tidak memerlukan `pip install`, `composer`, maupun `npm`.
2. **Pola Single-Path Routing**:
   - Seluruh aksi backend diakses melalui satu titik masuk URL: `http://<HOST>:8080/app.py?action=<aksi>`.
   - Aksi yang didukung:
     - `POST /app.py?action=register`: Mendaftarkan user baru dengan sequence `no_id` otomatis (`USER-0001`, `USER-0002`, dst.).
     - `POST /app.py?action=login`: Memverifikasi kredensial dan menerbitkan cookie sesi `session_id`.
     - `POST /app.py?action=submit_puisi`: Mengunggah puisi (terproteksi sesi).
     - `GET /app.py?action=daftar_puisi`: Mengambil koleksi puisi (terproteksi sesi).
     - `POST /app.py?action=logout`: Menghapus sesi dari memori server dan mengosongkan cookie.
     - `GET /app.py?action=session_info`: Endpoint pembantu untuk memeriksa status sesi saat ini.
3. **Stateful Server-Side Local Session (In-Memory RAM)**:
   - Sesi pengguna disimpan secara eksklusif dalam struktur data memori RAM server (`SESSIONS = {}`).
   - Browser menerima Session ID melalui header `Set-Cookie: session_id=<UUID>; Path=/; HttpOnly; SameSite=Lax`.
   - **Ketergantungan Mesin**: Jika proses server dimatikan atau direstart, seluruh sesi pengguna langsung hilang. Jika ada 2 instance server di belakang load balancer tanpa session replication/sticky session, permintaan pengguna akan gagal (*state mismatch*).
4. **Basis Data Relasional Lokal (SQLite)**:
   - Menggunakan file database lokal `database.db` dengan penegakan Foreign Key (`PRAGMA foreign_keys = ON;`).
   - Relasi: `puisi.user_id (FK) -> users.id (PK) ON DELETE CASCADE`.
5. **Frontend Minimalis (Vanilla HTML + CSS + JS)**:
   - Tanpa framework (tanpa Tailwind, Bootstrap, React, atau Vue).
   - Menggunakan native `fetch()` dengan konfigurasi wajib `credentials: 'include'` agar browser mengelola dan mengirimkan Cookie jar secara otomatis.

---

## 2. Struktur Proyek

```text
.
├── app.py              # Backend monolitik tunggal (HTTP Server, Session Store, DB, Routing)
├── index.html          # Frontend minimalis vanilla (HTML5, CSS3, Fetch API)
├── test_app.py         # Test suite otomatis (10 test cases: Unit & Integration Test)
├── database.db         # File SQLite lokal (dibuat otomatis saat app.py pertama kali dijalankan)
└── README.md           # Panduan teknis & deployment EC2
```

---

## 3. Menjalankan Aplikasi Secara Lokal

### Prasyarat:
- Python 3.8+ (Sudah terpasang secara default di Linux/macOS/Windows).

### Menjalankan Server:
```bash
python3 app.py
```
Server akan aktif di:
- **Web Interface**: `http://localhost:8080/`
- **Single-Path API**: `http://localhost:8080/app.py?action=...`

---

## 4. Menjalankan Pengujian Otomatis (TDD Suite)

Aplikasi dilengkapi dengan pengujian menyeluruh (10 skenario pengujian) mencakup registrasi sequence, kegagalan kredensial, proteksi sesi, manipulasi cookie, dan simulasi hilangnya sesi akibat restart server:

```bash
python3 -m unittest test_app.py -v
```

---

## 5. Panduan Observasi Cookie Jar (DevTools Network Tab)

Sesuai instruksi penugasan, mekanisme state wajib diobservasi melalui browser:
1. Buka browser (Google Chrome, Firefox, atau Edge) dan akses `http://localhost:8080/`.
2. Buka **Developer Tools** (tekan `F12` atau `Ctrl + Shift + I`), lalu pilih tab **Network**.
3. Centang opsi **Preserve log**.
4. **Lakukan Registrasi**:
   - Masukkan username, nama, dan password.
   - Amati request `POST /app.py?action=register` dengan status `201 Created` dan data `no_id: USER-0001`.
5. **Lakukan Login**:
   - Masukkan kredensial yang telah didaftarkan.
   - Amati request `POST /app.py?action=login` dengan status `200 OK`.
   - Pada panel **Response Headers**, amati header:
     ```http
     Set-Cookie: session_id=b2c8...; Path=/; HttpOnly; SameSite=Lax
     ```
   - Buka tab **Application** (Chrome) atau **Storage** (Firefox) -> **Cookies** -> `http://localhost:8080`. Anda akan melihat cookie `session_id` telah tersimpan di browser cookie jar.
6. **Submit Puisi**:
   - Isi form puisi dan klik **Unggah Puisi**.
   - Pada tab Network, klik request `POST /app.py?action=submit_puisi`.
   - Pada panel **Request Headers**, perhatikan header:
     ```http
     Cookie: session_id=b2c8...
     ```
     Ini membuktikan `fetch()` dengan `credentials: 'include'` berhasil menyertakan konteks sesi ke endpoint terproteksi.
7. **Uji Ketergantungan State (Restart Server)**:
   - Matikan server di terminal (`Ctrl + C`), lalu jalankan kembali (`python3 app.py`).
   - Di browser (tanpa logout), klik tombol **Refresh** pada koleksi puisi.
   - Request `GET /app.py?action=daftar_puisi` akan mengembalikan `401 Unauthorized` ("Sesi tidak valid atau telah kedaluwarsa").
   - **Kesimpulan Praktikum**: Ini membuktikan secara langsung bahwa sesi hanya hidup di RAM mesin tersebut dan tidak bertahan terhadap restart proses.

---

## 6. Panduan Deployment pada AWS EC2

### Langkah 1: Luncurkan Instance EC2
1. Buka AWS Management Console -> EC2 -> **Launch Instance**.
2. **Name**: `PACS-Stateful-Monolith`.
3. **AMI**: Ubuntu Server 24.04 LTS atau Amazon Linux 2023.
4. **Instance Type**: `t2.micro` (Eligible Free Tier).
5. **Key Pair**: Pilih atau buat key pair baru (misal: `pacs-key.pem`).

### Langkah 2: Konfigurasi Security Group
Pastikan **Inbound Rules** membuka port berikut:
| Type | Protocol | Port Range | Source | Keterangan |
| :--- | :--- | :--- | :--- | :--- |
| SSH | TCP | 22 | My IP (atau 0.0.0.0/0) | Akses remote SSH terminal |
| Custom TCP | TCP | **8080** | **0.0.0.0/0** | Akses publik ke aplikasi web |

### Langkah 3: Transfer File ke EC2
Dari terminal komputer lokal Anda:
```bash
# Ganti pacs-key.pem dan <EC2_PUBLIC_IP> sesuai instance Anda
scp -i pacs-key.pem app.py index.html ubuntu@<EC2_PUBLIC_IP>:~/
```

### Langkah 4: Hubungkan ke EC2 & Jalankan Server via Systemd
Masuk ke instance EC2 via SSH:
```bash
ssh -i pacs-key.pem ubuntu@<EC2_PUBLIC_IP>
```

Agar aplikasi tetap berjalan di latar belakang meskipun sesi SSH ditutup, buat systemd service:
```bash
sudo bash -c 'cat << "EOF" > /etc/systemd/system/stateful-app.service
[Unit]
Description=Stateful Monolithic Poetry Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/usr/bin/python3 /home/ubuntu/app.py 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF'
```

Aktifkan dan jalankan service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable stateful-app
sudo systemctl start stateful-app
sudo systemctl status stateful-app
```

### Langkah 5: Pengujian Akses Publik
Buka browser di komputer Anda dan akses:
```text
http://<EC2_PUBLIC_IP>:8080/
```
Verifikasi seluruh fungsionalitas (Register, Login, Submit Puisi, dan Daftar Puisi) berfungsi normal di lingkungan produksi AWS EC2.

---

## 7. Materi Pembahasan untuk Laporan PDF Tugas

Saat menyusun laporan tugas singkat, pastikan Anda menyertakan poin-poin analisis arsitektur berikut:
1. **Analisis Stateful vs Stateless**:
   - Mengapa aplikasi ini disebut *stateful*? Karena *state* sesi disimpan di RAM lokal server (`SESSIONS = {}`) pada satu instance EC2.
2. **Keterbatasan Horizontal Scaling**:
   - Jika traffic meningkat dan instance EC2 diduplikasi menjadi 2 (Instance A dan Instance B) di balik AWS Application Load Balancer (ALB) *round-robin*, pengguna yang login di Instance A akan tiba-tiba ter-*logout* (mendapat `401 Unauthorized`) saat request berikutnya diteruskan ke Instance B.
3. **Solusi Evolusioner ke Depan (Arsitektur Modern)**:
   - Menggunakan *Distributed Cache* (misal: Redis / Memcached / DynamoDB) untuk *session store* eksternal bersama, ATAU
   - Mengubah autentikasi menjadi *Stateless* menggunakan JWT dengan cryptographic signature.

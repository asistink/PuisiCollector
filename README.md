# Puisi Collector

<p align="center">
  <strong>Platform Kurasi dan Apresiasi Karya Sastra Puisi Berbasis Web</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/Database-SQLite3-003B57?style=flat&logo=sqlite&logoColor=white" alt="SQLite3">
  <img src="https://img.shields.io/badge/Dependencies-Zero%20External-success?style=flat" alt="Zero Dependencies">
</p>

---

## 📖 Tentang Proyek

**Puisi Collector** adalah aplikasi web monolitik ringan yang dirancang untuk menerbitkan, mengurasi, dan membaca karya puisi. Proyek ini dibangun dengan filosofi **Zero External Dependencies** — memanfaatkan keandalan Python Standard Library (`http.server` dan `sqlite3`) untuk backend, serta Vanilla HTML5, CSS3, dan JavaScript (Fetch API) untuk antarmuka pengguna.

Arsitektur sistem menggunakan pola **Single-Path Routing** dan **Server-Side Session Management** berbasis cookie `HttpOnly` untuk menghadirkan performa cepat, konsumsi memori minimal, dan kemudahan pemeliharaan.

---

## ✨ Fitur Utama

- **Autentikasi & Akun Pengguna**:
  - Pendaftaran akun dengan format Sequence ID unik otomatis (`USER-0001`, `USER-0002`, dst.).
  - Keamanan kredensial menggunakan hashing password PBKDF2 HMAC-SHA256.
  - Manajemen sesi *stateful* aman via cookie `HttpOnly` dan `SameSite=Lax`.
- **Manajemen Karya Puisi**:
  - Publikasi puisi lengkap dengan judul, isi, tanggal terbit, kategori, dan tags (kata kunci).
  - Penjelajahan koleksi puisi terkurasi dengan pembaruan data asinkron (*non-blocking*).
  - Integritas data terjamin menggunakan relasi *Foreign Key* dan *Cascade Deletion*.
- **Antarmuka Bersih & Responsif**:
  - Tampilan modern dengan tema gelap elegan tanpa ketergantungan framework CSS pihak ketiga.
  - Interaksi asinkron murni menggunakan native `fetch()` dengan manajemen cookie otomatis.
- **Zero External Dependencies**:
  - Tidak memerlukan `pip install`, `npm`, atau `composer`. Cukup Python standar.

---

## 🏛️ Arsitektur Sistem & Alur Sesi

```
[Browser / Klien]
       │
       ├─► 1. POST /app.py?action=login (JSON)
       │
[Puisi Collector Backend (app.py)]
       ├─► Verifikasi Kredensial (SQLite `users` table)
       ├─► Generate UUID Session ID & Simpan ke Memory Store
       │
       ◄─- 2. Response 200 OK + Header "Set-Cookie: session_id=...; HttpOnly"
[Browser Cookie Jar]
       │
       ├─► 3. POST /app.py?action=submit_puisi (Header "Cookie: session_id=...")
       │
[Puisi Collector Backend]
       ├─► Validasi Session ID di Memory -> Ekstraksi User Context
       ├─► INSERT INTO puisi (user_id, judul, isi, ...)
       │
       ◄─- 4. Response 201 Created (JSON)
```

---

## 🗄️ Skema Basis Data

Aplikasi menggunakan basis data relasional lokal **SQLite** (`database.db`) dengan integritas referensial:

```sql
PRAGMA foreign_keys = ON;

-- Tabel Pengguna
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    nama TEXT NOT NULL,
    no_id TEXT NOT NULL UNIQUE
);

-- Tabel Puisi
CREATE TABLE IF NOT EXISTS puisi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    judul TEXT NOT NULL,
    tgl_submit TEXT NOT NULL,
    isi TEXT NOT NULL,
    kategori TEXT NOT NULL,
    keyword TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

---

## 🔌 Spesifikasi API (Single-Path Routing)

Semua operasi API dilayani melalui endpoint utama: `/app.py?action=<aksi>`

| Aksi (`?action=`) | Method | Autentikasi | Payload Request (JSON) | Deskripsi |
| :--- | :--- | :--- | :--- | :--- |
| `register` | `POST` | Publik | `{"username", "password", "nama"}` | Mendaftarkan akun baru dan menghasilkan sequence ID. |
| `login` | `POST` | Publik | `{"username", "password"}` | Verifikasi kredensial dan menerbitkan session cookie. |
| `submit_puisi` | `POST` | Terproteksi | `{"judul", "isi", "tgl_submit", "kategori", "keyword"}` | Mengunggah karya puisi baru yang terhubung ke akun aktif. |
| `daftar_puisi` | `GET` | Terproteksi | *(None)* | Mengambil seluruh daftar karya puisi yang tersedia. |
| `session_info` | `GET` | Terproteksi | *(None)* | Memeriksa status dan profil sesi pengguna aktif. |
| `logout` | `POST` | Terproteksi | *(None)* | Menghapus sesi aktif dari server dan mengosongkan cookie. |

---

## 🚀 Memulai (Quick Start)

### Prasyarat
- **Python 3.8+** (telah terpasang secara default di sebagian besar sistem operasi).

### Instalasi & Menjalankan Lokal
1. **Clone Repositori**:
   ```bash
   git clone https://github.com/asistink/PuisiCollector.git
   cd PuisiCollector
   ```

2. **Jalankan Aplikasi**:
   ```bash
   python3 app.py
   ```
   *Secara default server akan berjalan pada port `8080`.*

3. **Buka di Browser**:
   Akses antarmuka web melalui:
   ```text
   http://localhost:8080/
   ```

---

## 🧪 Pengujian Otomatis (Test Suite)

Proyek ini dilengkapi dengan unit dan integration testing komprehensif:

```bash
python3 -m unittest test_app.py -v
```

Cakupan pengujian:
- Validasi registrasi akun dan format sequence `USER-0001`.
- Pencegahan duplikasi username.
- Verifikasi password hashing dan penolakan kredensial salah.
- Pembuatan dan masa berlaku cookie sesi `session_id`.
- Proteksi otorisasi endpoint puisi tanpa sesi valid.
- Penyajian file statis antarmuka `index.html`.


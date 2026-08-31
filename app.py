#!/usr/bin/env python3
"""
Puisi Collector - Platform Kurasi Karya Puisi
Backend Monolitik Stateful Murni (Standard Library Python)
- Single-Path Routing: /app.py?action=...
- Server-Side Local Session (In-Memory RAM Store)
- RDBMS Lokal: SQLite dengan Foreign Keys
"""

import http.server
import socketserver
import urllib.parse
import json
import sqlite3
import uuid
import hashlib
import os
import sys

# Konfigurasi Database & Port
DB_FILE = os.environ.get("DB_FILE", "database.db")
DEFAULT_PORT = int(os.environ.get("PORT", 8080))

# In-Memory Stateful Session Store (RAM Lokal Proses)
# Menyimpan: session_id -> {"user_id": int, "username": str, "nama": str}
# Kehilangan seluruh state jika server di-restart (Stateful Ground Truth)
SESSIONS = {}

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inisialisasi skema tabel users dan puisi dengan foreign key constraint."""
    conn = get_db()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                nama TEXT NOT NULL,
                no_id TEXT NOT NULL UNIQUE
            );
        """)
        conn.execute("""
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
        """)
    conn.close()

def hash_password(password: str) -> str:
    """Hashing password menggunakan PBKDF2 HMAC-SHA256 untuk keamanan kredensial."""
    salt = "scalable_system_salt_2026"
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()

class StatefulMonolithHandler(http.server.BaseHTTPRequestHandler):
    server_version = "StatefulMonolith/1.0"

    def _send_json(self, status_code: int, data: dict, headers: dict = None):
        """Kirim response JSON dengan status code dan header tambahan."""
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def _get_cookie_session_id(self) -> str:
        """Ekstraksi session_id dari header Cookie browser."""
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        cookies = cookie_header.split(";")
        for c in cookies:
            parts = c.strip().split("=", 1)
            if len(parts) == 2 and parts[0] == "session_id":
                return parts[1]
        return None

    def _get_authenticated_user(self):
        """Verifikasi session ID terhadap RAM lokal server (SESSIONS dict)."""
        session_id = self._get_cookie_session_id()
        if not session_id or session_id not in SESSIONS:
            return None
        return SESSIONS[session_id]

    def _parse_json_body(self):
        """Membaca dan mem-parsing request body JSON."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return {}
        raw_body = self.rfile.read(content_length)
        try:
            return json.loads(raw_body.decode("utf-8"))
        except Exception:
            return None

    def do_HEAD(self):
        """Mendukung request HEAD dengan mengeksekusi do_GET."""
        self.do_GET()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        action = query.get("action", [None])[0]

        # Sajikan Frontend Minimalis (index.html) jika request ke root '/'
        if path in ("/", "/index.html"):
            html_file = os.path.join(os.path.dirname(__file__), "index.html")
            if os.path.exists(html_file):
                with open(html_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self._send_json(404, {"status": "error", "message": "index.html tidak ditemukan"})
                return

        # Endpoint Single-Path Routing: /app.py?action=daftar_puisi atau /app?action=daftar_puisi
        if path in ("/app.py", "/app"):
            if action == "daftar_puisi":
                self.handle_daftar_puisi()
                return
            elif action == "session_info":
                # Helper endpoint untuk mengecek state sesi aktif saat ini
                user = self._get_authenticated_user()
                if user:
                    self._send_json(200, {"status": "success", "authenticated": True, "data": user})
                else:
                    self._send_json(200, {"status": "success", "authenticated": False})
                return
            else:
                self._send_json(400, {"status": "error", "message": f"Action GET '{action}' tidak dikenali"})
                return

        self._send_json(404, {"status": "error", "message": "Resource not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        action = query.get("action", [None])[0]

        if path not in ("/app.py", "/app"):
            self._send_json(404, {"status": "error", "message": "Endpoint not found"})
            return

        if action == "register":
            self.handle_register()
        elif action == "login":
            self.handle_login()
        elif action == "submit_puisi":
            self.handle_submit_puisi()
        elif action == "logout":
            self.handle_logout()
        else:
            self._send_json(400, {"status": "error", "message": f"Action POST '{action}' tidak dikenali"})

    # --- ACTION HANDLERS ---

    def handle_register(self):
        body = self._parse_json_body()
        if body is None:
            self._send_json(400, {"status": "error", "message": "Format payload JSON tidak valid"})
            return

        username = body.get("username", "").strip()
        password = body.get("password", "").strip()
        nama = body.get("nama", "").strip()

        if not username or not password or not nama:
            self._send_json(400, {"status": "error", "message": "Field username, password, dan nama wajib diisi"})
            return

        conn = get_db()
        cursor = conn.cursor()
        try:
            # Hitung total user saat ini untuk generate sequence USER-0001, USER-0002, dst.
            cursor.execute("SELECT COUNT(*) AS total FROM users")
            count = cursor.fetchone()["total"]
            no_id = f"USER-{(count + 1):04d}"

            hashed_pwd = hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, password, nama, no_id) VALUES (?, ?, ?, ?)",
                (username, hashed_pwd, nama, no_id)
            )
            conn.commit()
            new_id = cursor.lastrowid

            self._send_json(201, {
                "status": "success",
                "message": "Registrasi berhasil",
                "data": {
                    "id": new_id,
                    "username": username,
                    "nama": nama,
                    "no_id": no_id
                }
            })
        except sqlite3.IntegrityError:
            self._send_json(400, {"status": "error", "message": "Username sudah terdaftar"})
        except Exception as e:
            self._send_json(500, {"status": "error", "message": f"Kesalahan server: {str(e)}"})
        finally:
            conn.close()

    def handle_login(self):
        body = self._parse_json_body()
        if body is None:
            self._send_json(400, {"status": "error", "message": "Format payload JSON tidak valid"})
            return

        username = body.get("username", "").strip()
        password = body.get("password", "").strip()

        if not username or not password:
            self._send_json(400, {"status": "error", "message": "Username dan password wajib diisi"})
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password, nama, no_id FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if not user or user["password"] != hash_password(password):
            self._send_json(401, {"status": "error", "message": "Kredensial username atau password salah"})
            return

        # Buat Session ID baru dan simpan di memori lokal RAM (Server-Side Stateful)
        session_id = str(uuid.uuid4())
        SESSIONS[session_id] = {
            "user_id": user["id"],
            "username": user["username"],
            "nama": user["nama"],
            "no_id": user["no_id"]
        }

        # Kirim Set-Cookie header ke browser
        cookie_header = f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax"
        self._send_json(200, {
            "status": "success",
            "message": "Login berhasil",
            "data": {
                "username": user["username"],
                "nama": user["nama"],
                "no_id": user["no_id"]
            }
        }, headers={"Set-Cookie": cookie_header})

    def handle_submit_puisi(self):
        # Verifikasi autentikasi sesi stateful
        user = self._get_authenticated_user()
        if not user:
            self._send_json(401, {"status": "error", "message": "Sesi tidak valid atau telah kedaluwarsa"})
            return

        body = self._parse_json_body()
        if body is None:
            self._send_json(400, {"status": "error", "message": "Format payload JSON tidak valid"})
            return

        judul = body.get("judul", "").strip()
        isi = body.get("isi", "").strip()
        tgl_submit = body.get("tgl_submit", "").strip()
        kategori = body.get("kategori", "").strip()
        keyword = body.get("keyword", "").strip()

        if not judul or not isi or not tgl_submit or not kategori or not keyword:
            self._send_json(400, {
                "status": "error",
                "message": "Semua field (judul, isi, tgl_submit, kategori, keyword) wajib diisi"
            })
            return

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO puisi (user_id, judul, tgl_submit, isi, kategori, keyword)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user["user_id"], judul, tgl_submit, isi, kategori, keyword)
            )
            conn.commit()
            puisi_id = cursor.lastrowid

            self._send_json(201, {
                "status": "success",
                "message": "Puisi berhasil diunggah",
                "data": {
                    "id": puisi_id,
                    "judul": judul,
                    "tgl_submit": tgl_submit,
                    "kategori": kategori
                }
            })
        except Exception as e:
            self._send_json(500, {"status": "error", "message": f"Gagal menyimpan puisi: {str(e)}"})
        finally:
            conn.close()

    def handle_daftar_puisi(self):
        # Verifikasi autentikasi sesi stateful
        user = self._get_authenticated_user()
        if not user:
            self._send_json(401, {"status": "error", "message": "Sesi tidak valid atau telah kedaluwarsa"})
            return

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, tgl_submit, judul, kategori
                FROM puisi
                ORDER BY id DESC
                """
            )
            rows = cursor.fetchall()
            puisi_list = [
                {
                    "id": r["id"],
                    "tgl_submit": r["tgl_submit"],
                    "judul": r["judul"],
                    "kategori": r["kategori"]
                }
                for r in rows
            ]

            self._send_json(200, {
                "status": "success",
                "data": puisi_list
            })
        except Exception as e:
            self._send_json(500, {"status": "error", "message": f"Gagal mengambil data puisi: {str(e)}"})
        finally:
            conn.close()

    def handle_logout(self):
        session_id = self._get_cookie_session_id()
        if session_id and session_id in SESSIONS:
            del SESSIONS[session_id]

        expired_cookie = "session_id=deleted; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax"
        self._send_json(200, {
            "status": "success",
            "message": "Logout berhasil"
        }, headers={"Set-Cookie": expired_cookie})

def create_server(host="0.0.0.0", port=DEFAULT_PORT):
    # Mengizinkan reuse address untuk menghindari Address Already in Use
    socketserver.TCPServer.allow_reuse_address = True
    return socketserver.TCPServer((host, port), StatefulMonolithHandler)

if __name__ == "__main__":
    init_db()
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    server = create_server("0.0.0.0", port)
    print(f"============================================================")
    print(f"Puisi Collector - Backend Server Running on port {port}")
    print(f"Web Interface: http://localhost:{port}/")
    print(f"Single-Path API: http://localhost:{port}/app.py?action=...")
    print(f"Stateful Session Storage: In-Memory (RAM)")
    print(f"Tekan Ctrl+C untuk menghentikan server.")
    print(f"============================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nMematikan server...")
        server.shutdown()
        server.server_close()

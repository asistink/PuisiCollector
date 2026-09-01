import unittest
import urllib.request
import urllib.parse
import json
import threading
import time
import os
import sqlite3
from http.client import HTTPResponse

# Import server components from app
import app

TEST_PORT = 8999
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

class StatefulMonolithTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Override database to an in-memory or isolated test DB
        cls.test_db_path = "test_database.db"
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)
            
        app.DB_FILE = cls.test_db_path
        app.init_db()
        
        # Clear in-memory sessions
        app.SESSIONS.clear()
        
        # Start test HTTP server in background thread
        cls.server = app.create_server(port=TEST_PORT)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)  # Allow server to bind

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception:
                pass

    def _request(self, method, action, data=None, cookie=None):
        url = f"{BASE_URL}/app.py?action={action}"
        headers = {}
        body = None
        
        if data is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8")
            
        if cookie:
            headers["Cookie"] = cookie
            
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = resp.read().decode("utf-8")
                return {
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body": json.loads(resp_body) if resp_body else {}
                }
        except urllib.error.HTTPError as e:
            resp_body = e.read().decode("utf-8")
            return {
                "status": e.code,
                "headers": dict(e.headers),
                "body": json.loads(resp_body) if resp_body else {}
            }

    def test_01_register_success(self):
        payload = {
            "username": "budi123",
            "password": "PasswordRahasia!",
            "nama": "Budi Santoso"
        }
        res = self._request("POST", "register", payload)
        self.assertEqual(res["status"], 201)
        self.assertEqual(res["body"]["status"], "success")
        self.assertEqual(res["body"]["data"]["no_id"], "USER-0001")
        self.assertEqual(res["body"]["data"]["username"], "budi123")

    def test_02_register_duplicate_username(self):
        payload = {
            "username": "budi123",
            "password": "OtherPassword",
            "nama": "Budi Duplikat"
        }
        res = self._request("POST", "register", payload)
        self.assertEqual(res["status"], 400)
        self.assertEqual(res["body"]["status"], "error")

    def test_03_register_sequence_increment(self):
        payload = {
            "username": "siti456",
            "password": "PasswordSiti!",
            "nama": "Siti Aminah"
        }
        res = self._request("POST", "register", payload)
        self.assertEqual(res["status"], 201)
        self.assertEqual(res["body"]["data"]["no_id"], "USER-0002")

    def test_04_login_invalid_credentials(self):
        payload = {
            "username": "budi123",
            "password": "SalahPassword"
        }
        res = self._request("POST", "login", payload)
        self.assertEqual(res["status"], 401)
        self.assertEqual(res["body"]["status"], "error")

    def test_05_login_success_and_cookie_generation(self):
        payload = {
            "username": "budi123",
            "password": "PasswordRahasia!"
        }
        res = self._request("POST", "login", payload)
        self.assertEqual(res["status"], 200)
        self.assertEqual(res["body"]["status"], "success")
        
        # Verify Set-Cookie header is sent
        set_cookie = res["headers"].get("Set-Cookie", "")
        self.assertIn("session_id=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        
        # Extract session_id for next tests
        cookie_val = set_cookie.split(";")[0]
        self.__class__.session_cookie = cookie_val

    def test_06_submit_puisi_unauthorized(self):
        payload = {
            "judul": "Hujan Bulan Juni",
            "isi": "Tak ada yang lebih tabah...",
            "tgl_submit": "2026-08-31",
            "kategori": "Romansa",
            "keyword": "hujan, rindu"
        }
        # Request without Cookie
        res = self._request("POST", "submit_puisi", payload)
        self.assertEqual(res["status"], 401)

    def test_07_submit_puisi_authorized(self):
        payload = {
            "judul": "Hujan Bulan Juni",
            "isi": "Tak ada yang lebih tabah dari hujan bulan Juni.",
            "tgl_submit": "2026-08-31",
            "kategori": "Romansa",
            "keyword": "hujan, rindu"
        }
        res = self._request("POST", "submit_puisi", payload, cookie=self.session_cookie)
        self.assertEqual(res["status"], 201)
        self.assertEqual(res["body"]["status"], "success")

    def test_08_daftar_puisi_authorized(self):
        res = self._request("GET", "daftar_puisi", cookie=self.session_cookie)
        self.assertEqual(res["status"], 200)
        self.assertEqual(res["body"]["status"], "success")
        puisi_list = res["body"]["data"]
        self.assertIsInstance(puisi_list, list)
        self.assertGreaterEqual(len(puisi_list), 1)
        
        item = puisi_list[0]
        self.assertIn("tgl_submit", item)
        self.assertIn("judul", item)
        self.assertIn("kategori", item)
        self.assertEqual(item["judul"], "Hujan Bulan Juni")

    def test_08b_detail_puisi_authorized(self):
        # Ambil detail puisi ID 1 dengan session aktif
        res = self._request("GET", "detail_puisi&id=1", cookie=self.session_cookie)
        self.assertEqual(res["status"], 200)
        self.assertEqual(res["body"]["status"], "success")
        data = res["body"]["data"]
        self.assertEqual(data["judul"], "Hujan Bulan Juni")
        self.assertIn("Tak ada yang lebih tabah", data["isi"])
        self.assertEqual(data["penulis"], "Budi Santoso")
        self.assertEqual(data["kategori"], "Romansa")
        self.assertEqual(data["keyword"], "hujan, rindu")

    def test_08c_detail_puisi_not_found(self):
        # Puisi ID tidak ada
        res = self._request("GET", "detail_puisi&id=9999", cookie=self.session_cookie)
        self.assertEqual(res["status"], 404)
        self.assertEqual(res["body"]["status"], "error")

    def test_08d_detail_puisi_unauthorized(self):
        # Request tanpa cookie
        res = self._request("GET", "detail_puisi&id=1")
        self.assertEqual(res["status"], 401)

    def test_09_stateful_dependency_memory_loss(self):
        # Simulate server memory restart by clearing in-memory SESSIONS
        app.SESSIONS.clear()
        
        # Subsequent request with old cookie must fail (Stateful dependency demonstration)
        res = self._request("GET", "daftar_puisi", cookie=self.session_cookie)
        self.assertEqual(res["status"], 401)
        self.assertEqual(res["body"]["message"], "Sesi tidak valid atau telah kedaluwarsa")

    def test_10_serve_index_html(self):
        req = urllib.request.Request(f"{BASE_URL}/", method="GET")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers.get("Content-Type", ""))
            content = resp.read().decode("utf-8")
            self.assertIn("Puisi Collector", content)

if __name__ == "__main__":
    unittest.main()

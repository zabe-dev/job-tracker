import base64
import io
import json
import http.client
import os
import re
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
import urllib.error
import urllib.request
import zipfile
from urllib.parse import urlparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "northstar.db"
SEARCH_LOCK = threading.Lock()

def db_connection():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def mask_api_key(value):
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + ("•" * (len(value) - 8)) + value[-4:]

def initialize_database():
    with db_connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL, category TEXT NOT NULL, status TEXT NOT NULL, date TEXT NOT NULL, follow TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL, location TEXT NOT NULL, summary TEXT NOT NULL, category TEXT NOT NULL, verified TEXT NOT NULL, url TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        db.execute("DELETE FROM leads WHERE rowid NOT IN (SELECT MIN(rowid) FROM leads GROUP BY url)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_url ON leads(url)")
        db.execute("INSERT OR IGNORE INTO settings VALUES ('roles', 'WordPress|Virtual Assistant|Tech VA|DNS management|Web Admin|Data Entry|AI-assisted')")
        db.execute("INSERT OR IGNORE INTO settings VALUES ('frequency', 'Every 6 hours')")
        db.commit()

def current_state():
    with db_connection() as db:
        settings = {row["key"]: row["value"] for row in db.execute("SELECT key, value FROM settings")}
        return {
            "applications": [dict(row) for row in db.execute("SELECT * FROM applications ORDER BY rowid DESC")],
            "leads": [dict(row) for row in db.execute("SELECT * FROM leads ORDER BY rowid DESC")],
            "settings": {key: settings[key] for key in ("roles", "frequency", "resume_name", "last_search", "api_key_updated") if key in settings} | {"api_key_set": bool(settings.get("api_key")), "api_key_hint": mask_api_key(settings.get("api_key"))},
        }

def replace_state(state):
    with db_connection() as db:
        db.execute("DELETE FROM applications")
        db.execute("DELETE FROM leads")
        db.executemany("INSERT INTO applications VALUES (:id, :title, :company, :category, :status, :date, :follow, :url)", state.get("applications", []))
        db.executemany("INSERT INTO leads VALUES (:id, :title, :company, :location, :summary, :category, :verified, :url)", state.get("leads", []))
        for key, value in state.get("settings", {}).items():
            if key not in ("roles", "frequency", "resume_name", "last_search"):
                continue
            db.execute("INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        db.commit()

def setting(name):
    with db_connection() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (name,)).fetchone()
    return row[0] if row else ""

def verify_posting_url(url):
    parsed = urlparse(url)
    blocked_hosts = ("indeed.com", "linkedin.com", "glassdoor.com", "ziprecruiter.com", "monster.com")
    if parsed.scheme not in ("http", "https") or any(parsed.netloc.lower().endswith(host) for host in blocked_hosts):
        return False
    if parsed.path in ("", "/"):
        return False
    request = urllib.request.Request(url, headers={"User-Agent": "Jobtracker/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            final = urlparse(response.geturl())
            if response.status >= 400 or final.path in ("", "/"):
                return False
            page = response.read(400_000).decode("utf-8", "ignore").lower()
            closed_markers = ("position has been filled", "no longer accepting", "job is closed", "role is closed", "job expired", "position filled")
            return not any(marker in page for marker in closed_markers)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False

def extract_resume(file_name, encoded):
    raw = base64.b64decode(encoded.split(",", 1)[-1])
    if file_name.lower().endswith(".docx"):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8", "ignore")
        return re.sub(r"<[^>]+>", " ", xml).replace("&amp;", "&")
    if file_name.lower().endswith(".pdf"):
        try:
            extracted = subprocess.run(["pdftotext", "-layout", "-", "-"], input=raw, capture_output=True, check=True).stdout.decode("utf-8", "ignore")
            if extracted.strip():
                return extracted
        except (OSError, subprocess.CalledProcessError):
            pass
        return re.sub(r"\s+", " ", raw.decode("latin-1", "ignore"))
    return raw.decode("utf-8", "ignore")

def run_ai_search():
    if not SEARCH_LOCK.acquire(blocking=False):
        raise ValueError("A lead search is already running.")
    try:
        return _run_ai_search_locked()
    finally:
        SEARCH_LOCK.release()

def _run_ai_search_locked():
    resume = setting("resume_text")
    roles = setting("roles")
    if not resume.strip():
        raise ValueError("Upload a resume in Settings first.")
    prompt = f"""Find current open job postings matching this candidate resume and target roles.
Target roles: {roles.replace('|', ', ')}
Resume:
{resume[:12000]}

Use web search. Verify every URL is the exact live company or ATS job posting page, not a job board results page. Return JSON only: {{\"leads\":[{{\"title\":\"\",\"company\":\"\",\"location\":\"\",\"summary\":\"\",\"category\":\"\",\"url\":\"\"}}]}}. Return zero leads when no direct open posting can be verified."""
    try:
        result = subprocess.run(["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--json", "--sandbox", "read-only", "-"], input=prompt, text=True, capture_output=True, timeout=120, check=True)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise ValueError("Codex CLI search failed. Check codex-lb and Codex login.") from error
    text = ""
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            text = item.get("text", "")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("AI returned no structured job results.")
    leads = json.loads(match.group(0)).get("leads", [])
    stamp = "Verified open · just now"
    search_time = datetime.now().astimezone().strftime("%b %-d, %Y %-I:%M %p")
    now = int(__import__("time").time() * 1000)
    with db_connection() as db:
        existing_urls = {row[0] for row in db.execute("SELECT url FROM leads WHERE url != ''")}
        existing_urls.update(row[0] for row in db.execute("SELECT url FROM applications WHERE url != ''"))
    normalized = []
    for lead in leads:
        url = lead.get("url", "")
        if not url or url in existing_urls or not verify_posting_url(url):
            continue
        existing_urls.add(url)
        normalized.append({"id": now + len(normalized), "title": lead.get("title", "Untitled role"), "company": lead.get("company", "Unknown company"), "location": lead.get("location", "Location not listed"), "summary": lead.get("summary", "Matched to your resume."), "category": lead.get("category", "Other"), "verified": stamp, "url": url})
    with db_connection() as db:
        for lead in normalized:
            db.execute("INSERT OR IGNORE INTO leads VALUES (:id, :title, :company, :location, :summary, :category, :verified, :url)", lead)
        db.execute("INSERT INTO settings(key, value) VALUES ('last_search', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (search_time,))
        db.commit()
    return normalized

def search_interval_seconds():
    value = setting("frequency")
    return {"Every 6 hours": 6 * 3600, "Every 12 hours": 12 * 3600, "Every 24 hours": 24 * 3600}.get(value, 6 * 3600)

def scheduler_loop():
    while True:
        try:
            last = setting("last_search")
            should_run = False
            if not last:
                should_run = True
            else:
                try:
                    previous = datetime.strptime(last, "%b %d, %Y %I:%M %p")
                    should_run = (datetime.now() - previous).total_seconds() >= search_interval_seconds()
                except ValueError:
                    should_run = True
            if should_run and setting("resume_text"):
                run_ai_search()
        except Exception as error:
            print(f"Scheduled lead search skipped: {error}")
        time.sleep(60)

class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/applications", "/leads", "/settings", "/overview"):
            self.path = "/index.html"
        if self.path == "/api/state":
            self.send_json(current_state())
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/resume/remove":
            with db_connection() as db:
                db.execute("DELETE FROM settings WHERE key IN ('resume_text', 'resume_name')")
                db.commit()
            self.send_json({"ok": True, "state": current_state()})
            return
        if self.path == "/api/resume":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                text = extract_resume(payload["name"], payload["data"])
                with db_connection() as db:
                    db.execute("INSERT INTO settings(key, value) VALUES ('resume_text', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (text,))
                    db.execute("INSERT INTO settings(key, value) VALUES ('resume_name', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (payload["name"],))
                    db.commit()
                self.send_json({"ok": True, "name": payload["name"]})
            except (KeyError, ValueError, json.JSONDecodeError, sqlite3.Error, zipfile.BadZipFile) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if self.path == "/api/search":
            try:
                leads = run_ai_search()
                self.send_json({"leads": leads, "state": current_state()})
            except (ValueError, urllib.error.URLError, http.client.RemoteDisconnected) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if self.path == "/api/settings":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                with db_connection() as db:
                    for key in ("roles", "frequency"):
                        if key in payload:
                            db.execute("INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(payload[key])))
                    if payload.get("api_key"):
                        db.execute("INSERT INTO settings(key, value) VALUES ('api_key', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (payload["api_key"],))
                        db.execute("INSERT INTO settings(key, value) VALUES ('api_key_updated', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (datetime.now().astimezone().strftime("%b %-d, %Y %-I:%M %p"),))
                    db.commit()
                self.send_json(current_state())
            except (ValueError, json.JSONDecodeError, sqlite3.Error) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if self.path != "/api/state":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            replace_state(json.loads(self.rfile.read(length)))
            self.send_json(current_state())
        except (ValueError, json.JSONDecodeError, sqlite3.Error) as error:
            self.send_json({"error": str(error)}, 400)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")

class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    initialize_database()
    threading.Thread(target=scheduler_loop, name="lead-search-scheduler", daemon=True).start()
    server = ReusableThreadingHTTPServer(("127.0.0.1", 8000), AppHandler)
    print(f"Job tracker running at http://127.0.0.1:8000\nDatabase: {DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

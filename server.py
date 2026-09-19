import base64
import email
import email.header
import email.message
import email.utils
import hashlib
import html
import hmac
import io
import json
import http.client
import imaplib
import os
import re
import sqlite3
import smtplib
import subprocess
import threading
import time
import uuid
from datetime import datetime
import urllib.error
import urllib.request
import zipfile
from urllib.parse import parse_qs, urlencode, urlparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = Path(os.environ.get("JOBTRACKER_DB_PATH", str(ROOT / "jobtracker.db")))
SERVER_HOST = os.environ.get("JOBTRACKER_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("JOBTRACKER_PORT", "8000"))
SEARCH_LOCK = threading.Lock()
INBOX_ADDRESS = os.environ.get("INBOX_ADDRESS", "jay@zabe.dev")
OUTLOOK_CLIENT_ID = os.environ.get("OUTLOOK_CLIENT_ID", "")
OUTLOOK_CLIENT_SECRET = os.environ.get("OUTLOOK_CLIENT_SECRET", "")
OUTLOOK_TENANT = os.environ.get("OUTLOOK_TENANT", "common")
OUTLOOK_REDIRECT_URI = os.environ.get("OUTLOOK_REDIRECT_URI", "http://127.0.0.1:8000/api/outlook/callback")
OUTLOOK_MAIL_KEYWORDS = tuple(word.strip().lower() for word in os.environ.get("OUTLOOK_MAIL_KEYWORDS", "job,application,interview,recruiter,recruiting,hiring,career,position,role,candidate,resume,cv,offer,follow-up,next steps").split(",") if word.strip())
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
OUTLOOK_OAUTH_STATE = None

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

def canonical_url(value):
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw.lower().rstrip("/")
    path = parsed.path.rstrip("/") or "/"
    return parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower(), path=path, fragment="").geturl()

def initialize_database():
    with db_connection() as db:
        legacy_prefix = "m" + "ail_"
        for suffix in ("accounts", "threads", "messages", "tags", "thread_tags"):
            old_name, new_name = legacy_prefix + suffix, "inbox_" + suffix
            old_exists = db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (old_name,)).fetchone()
            new_exists = db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (new_name,)).fetchone()
            if old_exists and not new_exists:
                db.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL, category TEXT NOT NULL, status TEXT NOT NULL, date TEXT NOT NULL, follow TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL, location TEXT NOT NULL, summary TEXT NOT NULL, category TEXT NOT NULL, verified TEXT NOT NULL, url TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS lead_url_history (url TEXT PRIMARY KEY, first_seen_at TEXT NOT NULL, moved_to_application INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS inbox_accounts (id INTEGER PRIMARY KEY, provider TEXT NOT NULL, email TEXT NOT NULL, display_name TEXT NOT NULL DEFAULT '', imap_host TEXT NOT NULL DEFAULT '', imap_port INTEGER NOT NULL DEFAULT 993, imap_security TEXT NOT NULL DEFAULT 'ssl', smtp_host TEXT NOT NULL DEFAULT '', smtp_port INTEGER NOT NULL DEFAULT 465, smtp_security TEXT NOT NULL DEFAULT 'ssl', username TEXT NOT NULL DEFAULT '', password TEXT NOT NULL DEFAULT '', last_sync TEXT NOT NULL DEFAULT '', sync_error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS inbox_threads (id INTEGER PRIMARY KEY, account_id INTEGER, subject TEXT NOT NULL DEFAULT '', snippet TEXT NOT NULL DEFAULT '', last_message_at TEXT NOT NULL, unread_count INTEGER NOT NULL DEFAULT 0, priority TEXT NOT NULL DEFAULT 'normal', archived INTEGER NOT NULL DEFAULT 0, application_id INTEGER, lead_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS inbox_messages (id INTEGER PRIMARY KEY, thread_id INTEGER NOT NULL, external_id TEXT NOT NULL UNIQUE, direction TEXT NOT NULL, sender TEXT NOT NULL, recipients TEXT NOT NULL DEFAULT '', subject TEXT NOT NULL DEFAULT '', body_text TEXT NOT NULL DEFAULT '', received_at TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0, is_draft INTEGER NOT NULL DEFAULT 0, attachments_json TEXT NOT NULL DEFAULT '[]');
            CREATE TABLE IF NOT EXISTS inbox_tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, color TEXT NOT NULL DEFAULT '#e3f1ed');
            CREATE TABLE IF NOT EXISTS inbox_thread_tags (thread_id INTEGER NOT NULL, tag_id INTEGER NOT NULL, PRIMARY KEY (thread_id, tag_id));
        """)
        account_columns = {row[1] for row in db.execute("PRAGMA table_info(inbox_accounts)")}
        for name, definition in (("imap_host", "TEXT NOT NULL DEFAULT ''"), ("imap_port", "INTEGER NOT NULL DEFAULT 993"), ("imap_security", "TEXT NOT NULL DEFAULT 'ssl'"), ("smtp_host", "TEXT NOT NULL DEFAULT ''"), ("smtp_port", "INTEGER NOT NULL DEFAULT 465"), ("smtp_security", "TEXT NOT NULL DEFAULT 'ssl'"), ("username", "TEXT NOT NULL DEFAULT ''"), ("password", "TEXT NOT NULL DEFAULT ''"), ("last_sync", "TEXT NOT NULL DEFAULT ''"), ("sync_error", "TEXT NOT NULL DEFAULT ''")):
            if name not in account_columns:
                db.execute(f"ALTER TABLE inbox_accounts ADD COLUMN {name} {definition}")
        thread_columns = {row[1] for row in db.execute("PRAGMA table_info(inbox_threads)")}
        if "account_id" not in thread_columns:
            db.execute("ALTER TABLE inbox_threads ADD COLUMN account_id INTEGER")
        message_columns = {row[1] for row in db.execute("PRAGMA table_info(inbox_messages)")}
        if "attachments_json" not in message_columns:
            db.execute("ALTER TABLE inbox_messages ADD COLUMN attachments_json TEXT NOT NULL DEFAULT '[]'")
        db.execute("DELETE FROM leads WHERE rowid NOT IN (SELECT MIN(rowid) FROM leads GROUP BY url)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_url ON leads(url)")
        for row in db.execute("SELECT url FROM applications WHERE trim(url) != ''"):
            url = canonical_url(row["url"])
            db.execute("INSERT OR IGNORE INTO lead_url_history(url, first_seen_at, moved_to_application) VALUES (?, ?, 1)", (url, datetime.now().astimezone().isoformat()))
        db.execute("INSERT OR IGNORE INTO settings VALUES ('roles', 'WordPress|Virtual Assistant|Tech VA|DNS management|Web Admin|Data Entry|AI-assisted')")
        db.execute("INSERT OR IGNORE INTO settings VALUES ('frequency', 'Every 6 hours')")
        db.commit()

def current_state():
    with db_connection() as db:
        settings = {row["key"]: row["value"] for row in db.execute("SELECT key, value FROM settings")}
        return {
            "applications": [dict(row) for row in db.execute("SELECT * FROM applications ORDER BY rowid DESC")],
            "leads": [dict(row) for row in db.execute("SELECT * FROM leads ORDER BY rowid DESC")],
            "inbox": {"threads": db.execute("SELECT COUNT(*) FROM inbox_threads WHERE archived = 0").fetchone()[0], "unread": db.execute("SELECT COALESCE(SUM(unread_count), 0) FROM inbox_threads WHERE archived = 0").fetchone()[0], "accounts": 1, "address": INBOX_ADDRESS, "integration": {"outlook_configured": bool(OUTLOOK_CLIENT_ID and OUTLOOK_CLIENT_SECRET), "outlook_connected": bool(settings.get("outlook_refresh_token")), "outlook_email": settings.get("outlook_email", ""), "keyword_filter": list(OUTLOOK_MAIL_KEYWORDS)}, "tags": [dict(row) for row in db.execute("SELECT id, name, color FROM inbox_tags ORDER BY name")], "threads_detail": [dict(row) | {"tags": [dict(tag) for tag in db.execute("SELECT t.id, t.name, t.color FROM inbox_tags t JOIN inbox_thread_tags tt ON tt.tag_id = t.id WHERE tt.thread_id = ? ORDER BY t.name", (row["id"],))]} for row in db.execute("SELECT id, account_id, subject, snippet, last_message_at, unread_count, priority, archived FROM inbox_threads WHERE archived = 0 ORDER BY last_message_at DESC LIMIT 100")]},
            "settings": {key: settings[key] for key in ("roles", "frequency", "resume_name", "last_search", "api_key_updated") if key in settings} | {"api_key_set": bool(settings.get("api_key")), "api_key_hint": mask_api_key(settings.get("api_key"))},
        }

def replace_state(state):
    with db_connection() as db:
        now = datetime.now().astimezone().isoformat()
        for application in state.get("applications", []):
            url = canonical_url(application.get("url"))
            if url:
                db.execute("INSERT INTO lead_url_history(url, first_seen_at, moved_to_application) VALUES (?, ?, 1) ON CONFLICT(url) DO UPDATE SET moved_to_application = 1", (url, now))
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

Use web search. Verify every URL is the exact live company or ATS job posting page, not a job board results page. Do not return postings already tracked in the job tracker. Return JSON only: {{\"leads\":[{{\"title\":\"\",\"company\":\"\",\"location\":\"\",\"summary\":\"\",\"category\":\"\",\"url\":\"\"}}]}}. Return zero leads when no direct open posting can be verified."""
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
        existing_urls = {canonical_url(row[0]) for row in db.execute("SELECT url FROM leads WHERE url != ''")}
        existing_urls.update(canonical_url(row[0]) for row in db.execute("SELECT url FROM applications WHERE url != ''"))
        existing_urls.update(canonical_url(row[0]) for row in db.execute("SELECT url FROM lead_url_history WHERE url != ''"))
    normalized = []
    for lead in leads:
        url = lead.get("url", "")
        normalized_url = canonical_url(url)
        if not normalized_url or normalized_url in existing_urls or not verify_posting_url(url):
            continue
        existing_urls.add(normalized_url)
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

def inbox_account(account_id=None):
    with db_connection() as db:
        query = "SELECT * FROM inbox_accounts"
        args = ()
        if account_id is not None:
            query += " WHERE id = ?"
            args = (account_id,)
        query += " ORDER BY id LIMIT 1"
        row = db.execute(query, args).fetchone()
    if not row:
        raise ValueError("Connect an inbox account first.")
    return dict(row)

def decode_email_header(value):
    if not value:
        return ""
    return "".join(text if isinstance(text, str) else text.decode(charset or "utf-8", "replace") for text, charset in email.header.decode_header(value)).strip()

def message_text(message):
    parts = message.walk() if message.is_multipart() else (message,)
    for part in parts:
        if part.get_content_type() == "text/plain" and not part.get_filename():
            try:
                return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace").strip()
            except (AttributeError, UnicodeDecodeError):
                return str(part.get_payload())[:4000]
    return ""

def connect_inbox_imap(account):
    host, port, security = account["imap_host"], int(account["imap_port"]), account["imap_security"]
    if not host or not account["username"] or not account["password"]:
        raise ValueError("IMAP host, username, and password are required.")
    client = imaplib.IMAP4_SSL(host, port) if security == "ssl" else imaplib.IMAP4(host, port)
    if security == "starttls":
        client.starttls()
    client.login(account["username"], account["password"])
    return client

def connect_inbox_smtp(account):
    host, port, security = account["smtp_host"], int(account["smtp_port"]), account["smtp_security"]
    if not host or not account["username"] or not account["password"]:
        raise ValueError("SMTP host, username, and password are required.")
    client = smtplib.SMTP_SSL(host, port, timeout=20) if security == "ssl" else smtplib.SMTP(host, port, timeout=20)
    client.ehlo()
    if security == "starttls":
        client.starttls()
        client.ehlo()
    client.login(account["username"], account["password"])
    return client

def test_inbox_connection(account):
    imap = connect_inbox_imap(account)
    imap.logout()
    smtp = connect_inbox_smtp(account)
    smtp.quit()

def sync_inbox(account):
    imap = connect_inbox_imap(account)
    try:
        status, _ = imap.select("INBOX", readonly=True)
        if status != "OK":
            raise ValueError("Could not open inbox.")
        status, result = imap.uid("search", None, "ALL")
        if status != "OK":
            raise ValueError("Could not search inbox.")
        uids = result[0].split()[-50:]
        imported = 0
        with db_connection() as db:
            for uid in uids:
                external_id = f"{account['id']}:{uid.decode()}"
                if db.execute("SELECT 1 FROM inbox_messages WHERE external_id = ?", (external_id,)).fetchone():
                    continue
                status, fetched = imap.uid("fetch", uid, "(RFC822)")
                if status != "OK":
                    continue
                raw = next((item[1] for item in fetched if isinstance(item, tuple)), None)
                if not raw:
                    continue
                message = email.message_from_bytes(raw)
                subject = decode_email_header(message.get("Subject", "(No subject)")) or "(No subject)"
                sender = decode_email_header(message.get("From", "Unknown sender"))
                received = email.utils.parsedate_to_datetime(message.get("Date", "")) if message.get("Date") else datetime.now().astimezone()
                received_at = received.astimezone().isoformat() if received.tzinfo else received.isoformat()
                body = message_text(message)
                thread = db.execute("SELECT id FROM inbox_threads WHERE account_id = ? AND subject = ? ORDER BY last_message_at DESC LIMIT 1", (account["id"], subject)).fetchone()
                thread_id = thread[0] if thread else None
                if thread_id is None:
                    now = datetime.now().astimezone().isoformat()
                    thread_id = db.execute("INSERT INTO inbox_threads(account_id, subject, snippet, last_message_at, unread_count, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?) RETURNING id", (account["id"], subject, body[:240], received_at, now, now)).fetchone()[0]
                else:
                    db.execute("UPDATE inbox_threads SET snippet = ?, last_message_at = ?, unread_count = unread_count + 1, updated_at = ? WHERE id = ?", (body[:240], received_at, datetime.now().astimezone().isoformat(), thread_id))
                db.execute("INSERT INTO inbox_messages(thread_id, external_id, direction, sender, recipients, subject, body_text, received_at, is_read) VALUES (?, ?, 'received', ?, ?, ?, ?, ?, 0)", (thread_id, external_id, sender, message.get("To", ""), subject, body, received_at))
                imported += 1
            db.execute("UPDATE inbox_accounts SET last_sync = ?, sync_error = '' WHERE id = ?", (datetime.now().astimezone().strftime("%b %-d, %Y %-I:%M %p"), account["id"]))
            db.commit()
        return imported
    except Exception as error:
        with db_connection() as db:
            db.execute("UPDATE inbox_accounts SET sync_error = ? WHERE id = ?", (str(error)[:300], account["id"]))
            db.commit()
        raise
    finally:
        try:
            imap.logout()
        except Exception:
            pass

def send_inbox_message(account, recipient, subject, body):
    if not recipient or not subject or not body:
        raise ValueError("Recipient, subject, and message are required.")
    outgoing = email.message.EmailMessage()
    outgoing["From"] = account["email"]
    outgoing["To"] = recipient
    outgoing["Subject"] = subject
    outgoing["Message-ID"] = email.utils.make_msgid()
    outgoing.set_content(body)
    smtp = connect_inbox_smtp(account)
    try:
        smtp.send_message(outgoing)
    finally:
        smtp.quit()
    now = datetime.now().astimezone().isoformat()
    with db_connection() as db:
        thread_id = db.execute("INSERT INTO inbox_threads(account_id, subject, snippet, last_message_at, unread_count, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?) RETURNING id", (account["id"], subject, body[:240], now, now, now)).fetchone()[0]
        db.execute("INSERT INTO inbox_messages(thread_id, external_id, direction, sender, recipients, subject, body_text, received_at, is_read) VALUES (?, ?, 'sent', ?, ?, ?, ?, ?, 1)", (thread_id, "local:" + uuid.uuid4().hex, account["email"], recipient, subject, body, now))
        db.commit()

def store_inbound_message(sender, recipient, subject, body_text, body_html="", received_at=None):
    received_at = received_at or datetime.now().astimezone().isoformat()
    subject = (subject or "(No subject)").strip() or "(No subject)"
    body_text = body_text or ""
    with db_connection() as db:
        thread = db.execute("SELECT id FROM inbox_threads WHERE subject = ? ORDER BY last_message_at DESC LIMIT 1", (subject,)).fetchone()
        now = datetime.now().astimezone().isoformat()
        if thread:
            thread_id = thread[0]
            db.execute("UPDATE inbox_threads SET snippet = ?, last_message_at = ?, unread_count = unread_count + 1, updated_at = ? WHERE id = ?", (body_text[:240], received_at, now, thread_id))
        else:
            thread_id = db.execute("INSERT INTO inbox_threads(account_id, subject, snippet, last_message_at, unread_count, created_at, updated_at) VALUES (NULL, ?, ?, ?, 1, ?, ?) RETURNING id", (subject, body_text[:240], received_at, now, now)).fetchone()[0]
        external_id = "webhook:" + hashlib.sha256(f"{sender}\n{recipient}\n{subject}\n{received_at}\n{body_text}".encode()).hexdigest()
        db.execute("INSERT OR IGNORE INTO inbox_messages(thread_id, external_id, direction, sender, recipients, subject, body_text, received_at, is_read) VALUES (?, ?, 'received', ?, ?, ?, ?, ?, 0)", (thread_id, external_id, sender, recipient, subject, body_text, received_at))
        haystack = f"{sender} {subject} {body_text}".lower()
        tag_names = []
        if any(word in haystack for word in ("interview", "phone screen", "next steps")):
            tag_names.append(("Interview", "#e3f1ed"))
        if any(word in haystack for word in ("application", "applied", "candidate", "resume", "cv")):
            tag_names.append(("Application", "#fff0e4"))
        if any(word in haystack for word in ("recruit", "recruiter", "talent", "hiring")):
            tag_names.append(("Recruiter", "#eeeafb"))
        if any(word in haystack for word in ("follow up", "follow-up", "checking in")):
            tag_names.append(("Follow-up", "#f7f1d9"))
        if not tag_names:
            tag_names.append(("Unsorted", "#eef2ed"))
        for tag_name, color in tag_names:
            db.execute("INSERT INTO inbox_tags(name, color) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET color=excluded.color", (tag_name, color))
            tag_id = db.execute("SELECT id FROM inbox_tags WHERE name = ?", (tag_name,)).fetchone()[0]
            db.execute("INSERT OR IGNORE INTO inbox_thread_tags(thread_id, tag_id) VALUES (?, ?)", (thread_id, tag_id))
        db.commit()

def save_setting_values(values):
    with db_connection() as db:
        for key, value in values.items():
            db.execute("INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        db.commit()

def setting_values(names):
    with db_connection() as db:
        rows = db.execute("SELECT key, value FROM settings WHERE key IN ({})".format(",".join("?" for _ in names)), tuple(names)).fetchall()
    return {row["key"]: row["value"] for row in rows}

def outlook_authorization_url():
    global OUTLOOK_OAUTH_STATE
    if not OUTLOOK_CLIENT_ID:
        raise ValueError("Set OUTLOOK_CLIENT_ID in the server environment first.")
    OUTLOOK_OAUTH_STATE = uuid.uuid4().hex
    params = {"client_id": OUTLOOK_CLIENT_ID, "response_type": "code", "redirect_uri": OUTLOOK_REDIRECT_URI, "response_mode": "query", "scope": "openid profile email offline_access https://graph.microsoft.com/Mail.Read", "state": OUTLOOK_OAUTH_STATE}
    return f"https://login.microsoftonline.com/{OUTLOOK_TENANT}/oauth2/v2.0/authorize?{urlencode(params)}"

def exchange_outlook_code(code):
    if not OUTLOOK_CLIENT_SECRET:
        raise ValueError("Set OUTLOOK_CLIENT_SECRET in the server environment first.")
    body = urlencode({"client_id": OUTLOOK_CLIENT_ID, "client_secret": OUTLOOK_CLIENT_SECRET, "code": code, "redirect_uri": OUTLOOK_REDIRECT_URI, "grant_type": "authorization_code", "scope": "openid profile email offline_access https://graph.microsoft.com/Mail.Read"}).encode()
    request = urllib.request.Request(f"https://login.microsoftonline.com/{OUTLOOK_TENANT}/oauth2/v2.0/token", data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            token = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        raise ValueError("Microsoft OAuth token exchange failed.") from error
    if not token.get("refresh_token") or not token.get("access_token"):
        raise ValueError("Microsoft OAuth returned no usable token.")
    save_setting_values({"outlook_access_token": token["access_token"], "outlook_refresh_token": token["refresh_token"], "outlook_expires_at": int(time.time()) + int(token.get("expires_in", 3600))})

def outlook_access_token():
    values = setting_values(("outlook_access_token", "outlook_refresh_token", "outlook_expires_at"))
    if values.get("outlook_access_token") and int(values.get("outlook_expires_at", "0")) > int(time.time()) + 60:
        return values["outlook_access_token"]
    if not values.get("outlook_refresh_token"):
        raise ValueError("Connect Outlook first.")
    body = urlencode({"client_id": OUTLOOK_CLIENT_ID, "client_secret": OUTLOOK_CLIENT_SECRET, "refresh_token": values["outlook_refresh_token"], "grant_type": "refresh_token", "scope": "openid profile email offline_access https://graph.microsoft.com/Mail.Read"}).encode()
    request = urllib.request.Request(f"https://login.microsoftonline.com/{OUTLOOK_TENANT}/oauth2/v2.0/token", data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            token = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        raise ValueError("Microsoft OAuth refresh failed. Reconnect Outlook.") from error
    save_setting_values({"outlook_access_token": token["access_token"], "outlook_refresh_token": token.get("refresh_token", values["outlook_refresh_token"]), "outlook_expires_at": int(time.time()) + int(token.get("expires_in", 3600))})
    return token["access_token"]

def sync_outlook_messages():
    token = outlook_access_token()
    params = urlencode({"$top": "50", "$orderby": "receivedDateTime desc", "$select": "id,internetMessageId,subject,from,toRecipients,body,receivedDateTime,isRead,hasAttachments"})
    next_url = f"https://graph.microsoft.com/v1.0/me/messages?{params}"
    imported = 0
    while next_url and imported < 50:
        request = urllib.request.Request(next_url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            raise ValueError("Microsoft Graph mail sync failed.") from error
        for message in payload.get("value", []):
            sender = (((message.get("from") or {}).get("emailAddress") or {}).get("address") or "Unknown sender")
            recipients = ", ".join(((item.get("emailAddress") or {}).get("address") or "") for item in message.get("toRecipients", []))
            body = message.get("body") or {}
            body_text = body.get("content", "")
            if body.get("contentType") == "html":
                body_text = re.sub(r"<[^>]+>", " ", body_text)
            searchable = f"{sender} {message.get('subject', '')} {body_text}".lower()
            if OUTLOOK_MAIL_KEYWORDS and not any(keyword in searchable for keyword in OUTLOOK_MAIL_KEYWORDS):
                continue
            before = len(current_state()["inbox"]["threads_detail"])
            store_inbound_message(sender, recipients, message.get("subject", ""), re.sub(r"\s+", " ", body_text).strip(), body.get("content", ""), message.get("receivedDateTime"))
            after = len(current_state()["inbox"]["threads_detail"])
            imported += 1 if after >= before else 0
        next_url = payload.get("@odata.nextLink")
    save_setting_values({"outlook_last_sync": datetime.now().astimezone().strftime("%b %-d, %Y %-I:%M %p")})
    return imported

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
        if self.path.split("?", 1)[0] in ("/applications", "/leads", "/inbox", "/settings", "/overview"):
            self.path = "/index.html"
        if self.path == "/api/outlook/connect":
            try:
                location = outlook_authorization_url()
            except ValueError as error:
                location = "/inbox?outlook_error=" + urlencode({"message": str(error)})
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()
            return
        if self.path.startswith("/api/outlook/callback"):
            query = parse_qs(urlparse(self.path).query)
            if query.get("state", [""])[0] != OUTLOOK_OAUTH_STATE:
                self.send_response(302)
                self.send_header("Location", "/inbox?outlook_error=Invalid+OAuth+state")
                self.end_headers()
                return
            try:
                exchange_outlook_code(query.get("code", [""])[0])
                self.send_response(302)
                self.send_header("Location", "/inbox?outlook=connected")
                self.end_headers()
            except ValueError as error:
                self.send_response(302)
                self.send_header("Location", "/inbox?outlook_error=" + urlencode({"message": str(error)}))
                self.end_headers()
            return
        if self.path.startswith("/api/inbox/thread"):
            try:
                thread_id = int(self.path.split("thread_id=", 1)[1])
                with db_connection() as db:
                    messages = [dict(row) for row in db.execute("SELECT id, thread_id, external_id, direction, sender, recipients, subject, body_text, received_at, is_read FROM inbox_messages WHERE thread_id = ? ORDER BY received_at", (thread_id,))]
                self.send_json({"messages": messages})
            except (ValueError, sqlite3.Error) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if self.path == "/api/state":
            self.send_json(current_state())
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/emails/inbound":
            supplied = self.headers.get("x-webhook-secret", "")
            if not WEBHOOK_SECRET or not hmac.compare_digest(supplied, WEBHOOK_SECRET):
                self.send_response(401)
                self.end_headers()
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                store_inbound_message(payload.get("from", ""), payload.get("to", INBOX_ADDRESS), payload.get("subject", ""), payload.get("text", ""), payload.get("html", ""), payload.get("receivedAt"))
                self.send_json({"ok": True})
            except (ValueError, json.JSONDecodeError, sqlite3.Error) as error:
                self.send_json({"error": str(error)}, 400)
            return
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
        if self.path == "/api/outlook/sync":
            try:
                imported = sync_outlook_messages()
                self.send_json({"ok": True, "imported": imported, "state": current_state()})
            except (ValueError, urllib.error.URLError) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if self.path == "/api/inbox/account":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                account_id = int(payload["id"]) if payload.get("id") else None
                existing = inbox_account(account_id) if account_id else None
                now = datetime.now().astimezone().isoformat()
                account = {
                    "provider": "imap-smtp",
                    "email": payload.get("email", "").strip(),
                    "display_name": payload.get("display_name", "").strip(),
                    "imap_host": payload.get("imap_host", "").strip(),
                    "imap_port": int(payload.get("imap_port", 993)),
                    "imap_security": payload.get("imap_security", "ssl"),
                    "smtp_host": payload.get("smtp_host", "").strip(),
                    "smtp_port": int(payload.get("smtp_port", 465)),
                    "smtp_security": payload.get("smtp_security", "ssl"),
                    "username": payload.get("username", "").strip(),
                    "password": payload.get("password") or (existing["password"] if existing else ""),
                }
                if not account["email"] or not account["imap_host"] or not account["smtp_host"] or not account["username"] or not account["password"]:
                    raise ValueError("Email, IMAP, SMTP, username, and password are required.")
                if account["imap_security"] not in ("ssl", "starttls", "none") or account["smtp_security"] not in ("ssl", "starttls", "none"):
                    raise ValueError("Security must be SSL, STARTTLS, or None.")
                with db_connection() as db:
                    if existing:
                        db.execute("UPDATE inbox_accounts SET provider = ?, email = ?, display_name = ?, imap_host = ?, imap_port = ?, imap_security = ?, smtp_host = ?, smtp_port = ?, smtp_security = ?, username = ?, password = ?, updated_at = ? WHERE id = ?", (*account.values(), now, account_id))
                    else:
                        account_id = db.execute("INSERT INTO inbox_accounts(provider, email, display_name, imap_host, imap_port, imap_security, smtp_host, smtp_port, smtp_security, username, password, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id", (*account.values(), now, now)).fetchone()[0]
                    db.commit()
                self.send_json({"ok": True, "account_id": account_id, "state": current_state()})
            except (KeyError, ValueError, json.JSONDecodeError, sqlite3.Error) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if self.path == "/api/inbox/test":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                account = inbox_account(int(payload["account_id"])) if payload.get("account_id") else payload
                test_inbox_connection(account)
                self.send_json({"ok": True, "message": "IMAP receive and SMTP send connections are working."})
            except (KeyError, ValueError, OSError, imaplib.IMAP4.error, smtplib.SMTPException) as error:
                self.send_json({"error": str(error)}, 400)
            return
        if self.path == "/api/inbox/sync":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length)) if length else {}
                imported = sync_inbox(inbox_account(int(payload["account_id"])) if payload.get("account_id") else inbox_account())
                self.send_json({"ok": True, "imported": imported, "state": current_state()})
            except (KeyError, ValueError, OSError, imaplib.IMAP4.error, smtplib.SMTPException) as error:
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
        if self.path == "/api/api-key/remove":
            try:
                with db_connection() as db:
                    db.execute("DELETE FROM settings WHERE key IN ('api_key', 'api_key_updated')")
                    db.commit()
                self.send_json(current_state())
            except sqlite3.Error as error:
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
    server = ReusableThreadingHTTPServer((SERVER_HOST, SERVER_PORT), AppHandler)
    print(f"Job tracker running at http://{SERVER_HOST}:{SERVER_PORT}\nDatabase: {DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

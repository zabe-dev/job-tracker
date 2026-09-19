# Job Tracker

Local, single-user job application dashboard. Tracker data persists in a local SQLite file, with browser local storage as a fallback when the API is unavailable.

## Run

```bash
python3 server.py
```

Open <http://127.0.0.1:8000>.

The health-check launcher is `./jobtracker`; it runs syntax checks, starts the server if needed, verifies `/api/state`, and opens the browser. To install it as the `jobtracker` command, run once:

```bash
sudo cp /Users/jaybeza/Desktop/zb/job-tracker/jobtracker /usr/local/bin/jobtracker
sudo chmod 755 /usr/local/bin/jobtracker
```

No package install is required. `requirements.txt` is intentionally empty because the server uses the Python standard library. The first run creates `jobtracker.db` beside `server.py`. A blank `jobtracker.template.db` is included for repository setup; personal resume and API-key data stays in the ignored local database.

## Current slice

- Dashboard stats and weekly application trend
- Application tracker with status, category, sorting, and search
- Leads queue with verification badges and move-to-tracker action
- Search Now interaction with local demo results
- Resume drop zone and editable search preferences
- Persistent SQLite storage for applications, leads, roles, preferences, resume name, and last search time
- Built-in background scheduler runs verified lead search every 6, 12, or 24 hours
- Lead URLs are unique and are not re-added after moving into applications
- Editable target-role chips (press Enter or Add; remove with ×)

AI search invokes local `codex exec`; Codex CLI uses the running `codex-lb` service at `http://127.0.0.1:2455/v1`. The server keeps stored settings local and never returns the API key to the frontend.

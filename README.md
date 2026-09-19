# jobtracker

Local, single-user job application dashboard. Tracker data persists in a local SQLite file, with browser local storage as a fallback when the API is unavailable.

## Run

```bash
python3 server.py
```

Open <http://127.0.0.1:8000>.

## Docker / Dokploy

Deploy this repository as a Dokploy Application using its `Dockerfile`. Set the application port to `8000`, attach a persistent volume at `/data`, and add `jobtracker.zabe.dev` as the domain. The container binds to `0.0.0.0` automatically and stores SQLite data at `/data/jobtracker.db`.

For Docker Compose, run `docker compose up -d --build`. Compose publishes port `8000` and persists Jobtracker data in the `jobtracker-data` volume.

The image includes Poppler for PDF resume extraction and Codex CLI for AI search. Persist `/data/codex` through the same `/data` volume, then configure/login Codex CLI inside the container. The Codex CLI configuration must point to the `codex-lb` service over the shared Docker network, not `127.0.0.1`; for example, use the codex-lb backend endpoint at `http://codex-lb:2455/backend-api/codex` when both services share Dokploy’s Docker network.

Do not expose the Jobtracker container database or Codex state as a public volume. Keep `1455` for codex-lb’s OAuth callback and route the codex-lb domain to port `2455`.

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
- AI search through the local Codex CLI/Codex LB connection
- Resume drop zone and editable search preferences
- Persistent SQLite storage for applications, leads, roles, preferences, resume name, and last search time
- Built-in background scheduler runs verified lead search every 6, 12, or 24 hours
- Lead URLs are unique and are not re-added after moving into applications
- Editable target-role chips (press Enter or Add; remove with ×)

AI search invokes local `codex exec`; Codex CLI uses the running `codex-lb` service at `http://127.0.0.1:2455/v1`. The server keeps stored settings local and never returns the API key to the frontend.

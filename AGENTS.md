# Build Prompt: Local Job Application Tracker with AI Deep-Search

Copy everything below into codex (or another coding assistant) to build the app.

---

## Project Goal

Build a **simple, locally-run web app** that helps me manage my job search. It has two core parts:

1. **Application Tracker** — a dashboard to log and track the status of every job I apply to.
2. **AI Job Finder** — an AI-powered "deep search" agent that periodically searches the web for job postings matching my resume and interests, and returns the **exact URL of the actual job posting** (the company's own application page or ATS listing — e.g., Greenhouse, Lever, Workday, BambooHR, or the company's own careers page) — **never a job board search/listing page** like Indeed, LinkedIn Jobs search results, ZipRecruiter, or Glassdoor aggregator pages.

The whole thing must run locally on my machine — no cloud hosting, no external database service required.

---

## Tech Stack (keep it simple)

- **Backend:** Python (FastAPI or Flask) — easy to run locally with `python app.py` or `uvicorn`.
- **Database:** SQLite (single file, no setup needed).
- **Frontend:** A single-page app using plain HTML/CSS/JS, or a lightweight framework (e.g., Flask + Jinja templates, or a small React app served statically). No build pipeline complexity — prioritize "clone and run."
- **AI Integration:** Use the Anthropic API (codex) with **web search enabled** for the deep-search feature. Store the API key in a local `.env` file (never hardcoded).
- **Scheduler:** Use a simple background job (e.g., Python `schedule` library, or `APScheduler`) to run the deep search periodically (configurable interval — e.g., every 6/12/24 hours), without needing an external cron service.

---

## Core Features

### 1. Resume Intake & Analysis

- Let me upload my resume (PDF or DOCX).
- Parse it and extract: skills, tools/software proficiency, years of experience, past roles, and keywords.
- Store this as a structured "candidate profile" in the database, which is then used to drive the job search queries.
- Allow me to manually edit/add keywords or preferences after the automatic parse (e.g., add "DNS management," "cPanel," "WHM," "GoDaddy domain admin" if not captured).

### 2. Target Roles / Interests (configurable list)

The search should focus on these role types and related tasks/responsibilities (editable in settings, not hardcoded):

- WordPress (development, maintenance, admin)
- Virtual Assistant (general VA)
- Tech VA
- DNS Management
- Web Admin / Website Administration
- Data Entry
- AI-assisted jobs / roles where AI tools are used as part of the responsibilities

### 3. AI Deep Search for Job Listings

- On a schedule (and on-demand via a "Search Now" button), the app calls codex with web search enabled to find current, open job postings matching my profile and target roles.
- **Hard requirement:** The AI must return the **direct/exact URL of the job posting itself** — a page where I can actually read the full job description and click "Apply" — not a search results page, not a job board homepage, not a category/listing page.
    - Acceptable: `https://company.com/careers/wordpress-admin-role`, `https://boards.greenhouse.io/company/jobs/12345`, `https://jobs.lever.co/company/abcd-1234`
    - Not acceptable: `https://www.linkedin.com/jobs/search/?keywords=wordpress`, `https://www.indeed.com/jobs?q=virtual+assistant`
- For each result, capture: job title, company name, exact posting URL, date found, brief AI-generated summary of why it matches my profile, and (if available) posted date and location/remote status.
- De-duplicate: don't re-surface a listing already in my tracker.
- Save all found listings into a "New Leads" queue in the app — separate from my active applications — so I can review and decide which to apply to.

### 3a. Open/Active Verification (Hard Requirement)

Every listing added to "New Leads" must be confirmed as **currently open and accepting applications** at the time of search. This is not optional:

- Before saving a result, the AI must fetch/re-check the posting URL itself and confirm the page does not show "closed," "no longer accepting applications," "position filled," "expired," or similar language, and does not 404/redirect to a generic careers homepage (a redirect to the homepage is a strong signal the specific listing is gone).
- Discard and do not save any listing that is closed, expired, filled, or unreachable — do not merely flag it as closed and add it anyway.
- Store a `verified_open_at` timestamp alongside each saved listing so I know when it was last confirmed live.
- On each periodic search run, also **re-check existing "New Leads" and "Applied" entries** (not just find new ones): re-fetch their stored URLs and update a `status_check` field (Open / Closed / Unreachable) with a `last_checked_at` timestamp. If a listing I've already applied to closes, flag it in the dashboard (e.g., a small "posting closed" badge) so I know context has changed, but do not remove it from my applied history.
- If the AI cannot confidently determine whether a listing is still open (ambiguous page, JS-heavy site that didn't load cleanly, etc.), it should mark it as "Unverified" rather than assuming open — unverified leads should be visually distinguished in the UI and never silently treated as confirmed-open.

### 4. Application Tracker Dashboard

- A table/board view of all jobs I've applied to (or moved from "New Leads" into "Applied").
- Fields per entry: Job Title, Company, Exact Posting URL, Role Category (WordPress/VA/Tech VA/DNS/Web Admin/Data Entry/AI-assisted/Other), Date Applied, Status, Notes, Follow-up Date.
- Status options (editable): New Lead → Applied → Interview Scheduled → Interviewed → Offer → Rejected → Withdrawn.
- Ability to filter/sort by status, category, and date.
- Simple stats view: total applications, applications by status, response rate, applications per week.

### 5. Settings Page

- Edit target role list/keywords.
- Set search frequency (e.g., every X hours).
- Upload/replace resume.
- Enter/update Codex API Key (stored locally, not exposed to frontend).

---

## Non-Functional Requirements

- Must run fully offline except for the AI search calls themselves (which require internet).
- No user accounts/auth needed — this is single-user, local-only.
- Provide a `README.md` with setup instructions: install dependencies, set `.env` with API key, run the app, access via `localhost`.
- Provide a `requirements.txt` (or `package.json`) with pinned versions.
- Keep the codebase modular: separate the resume parser, the search agent, the scheduler, and the web app/API layer into distinct files/modules so each part is easy to inspect and modify.

---

## Deliverables

1. Full source code for the app (backend + frontend).
2. SQLite schema/migration script.
3. `.env.example` file showing required environment variables.
4. `README.md` with local setup + run instructions.
5. A short note on how to adjust the search prompt sent to codex if I want to refine what counts as a "matching" job.

---

## Open Questions to Ask Me Before/While Building

- Do I want a simple single-file SQLite browser-based UI, or would I prefer a terminal/CLI mode too?
- Should "New Leads" require my manual approval before being added to the tracker, or auto-added with a "New Lead" status?
- Any specific locations/remote-only preference to filter by?

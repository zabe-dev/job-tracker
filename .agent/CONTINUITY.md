# Continuity

## [PLANS]

- [2026-09-19T13:10+08:00] [USER] Build `/job-tracker` as a local job tracker site.
- [2026-09-19T13:10+08:00] [ASSUMPTION] Ship a runnable browser-first MVP with local persistence and clear seams for later AI/API wiring.

## [DECISIONS]

- [2026-09-19T13:10+08:00] [CODE] Use plain HTML, CSS, JavaScript, and Python standard-library server to keep setup dependency-free.

## [PROGRESS]

- [2026-09-19T15:44+08:00] [CODE] Added toast feedback when search frequency changes through the custom or native frequency control.
- [2026-09-19T15:44+08:00] [CODE] Added X control and `/api/api-key/remove` endpoint to clear saved Codex API key and update SQLite state.
- [2026-09-19T15:48+08:00] [USER] Renamed visible Mail workspace label to Inbox; preserved `/mail` route and internal mail tables.
- [2026-09-19T15:52+08:00] [TOOL] API-key removal appeared broken because live server process predated endpoint code; restarted server with `jobtracker` so current route is loaded.
- [2026-09-19T15:58+08:00] [USER] Requested workspace rename across codebase.
- [2026-09-19T15:58+08:00] [CODE] Renamed workspace route, view identifiers, state key, counters, CSS classes, and inbox tables to Inbox; migrated both live and template SQLite tables without losing records.
- [2026-09-19T15:58+08:00] [TOOL] Verified `/api/state` returns `inbox`, `/inbox` serves app shell, and no standalone Mail route/identifier remains in source.
- [2026-09-19T16:12+08:00] [USER] Requested Inbox implementation using VPS-hosted mailbox through Dokploy.
- [2026-09-19T16:12+08:00] [CODE] Added generic IMAP/SMTP account storage, connection testing, real inbox sync (latest 50 messages), thread/message display, and SMTP sending; credentials stay server-side and are excluded from state responses.
- [2026-09-19T16:12+08:00] [TOOL] Verified live `/api/state` includes inbox metadata, `/inbox` includes account/connect UI, and unauthenticated test endpoint returns controlled HTTP 400.
- [2026-09-19T16:16+08:00] [USER] Specified `jay@zabe.dev` as Inbox inbound address and outbound sender identity for Cloudflare/Resend integration.
- [2026-09-19T16:24+08:00] [USER] Requested guide implementation in existing codebase.
- [2026-09-19T16:24+08:00] [CODE] Added Cloudflare inbound webhook with constant-time shared-secret validation, Resend outbound API integration, environment-driven `jay@zabe.dev` identity, integration readiness state, and deployable `mail-worker/` scaffold using Postal MIME.
- [2026-09-19T16:30+08:00] [USER] Reported Inbox layout was wrong.
- [2026-09-19T16:30+08:00] [CODE] Prevented empty conversation panel from stretching to compose height, reduced setup card spacing, and aligned Inbox grid panels to content height.
- [2026-09-19T16:35+08:00] [USER] Requested Messages and Compose cards share one column, and reported attachments unavailable.
- [2026-09-19T16:35+08:00] [CODE] Stacked Inbox cards into one column and added multi-file attachment selection with Resend payload encoding and size validation.
- [2026-09-19T16:38+08:00] [USER] Requested two-column Inbox: Recent conversations left; integration and Compose stacked right.
- [2026-09-19T16:38+08:00] [CODE] Added two-column Inbox layout and moved integration card plus Compose into stacked right-side column.
- [2026-09-19T16:45+08:00] [USER] Changed Inbox scope to receive-only; replies happen in regular mail app.
- [2026-09-19T16:45+08:00] [CODE] Removed outbound UI/API path, kept Cloudflare inbound webhook, and auto-tags received messages as Interview, Application, Recruiter, Follow-up, or Unsorted.
- [2026-09-19T16:49+08:00] [TOOL] Verified receive-only UI has no Compose/send controls, live `/api/state` remains healthy, and unauthenticated inbound webhook requests return `401`.
- [2026-09-19T16:53+08:00] [USER] Requested removal of Inbox top status card.
- [2026-09-19T16:53+08:00] [CODE] Replaced status card with compact configured/not configured badge in Inbox page heading.
- [2026-09-19T16:56+08:00] [USER] Requested exact `Not configured` text and hidden badge when receiving is configured.
- [2026-09-19T17:02+08:00] [USER] Requested removal of Dokploy references.
- [2026-09-19T17:02+08:00] [CODE] Replaced Dokploy-specific configuration wording with generic server-environment wording.
- [2026-09-19T17:05+08:00] [USER] Requested Outlook Graph as sole Inbox provider, keyword filtering, and removal of deployment-provider, Resend, and Cloudflare references.
- [2026-09-19T17:05+08:00] [CODE] Added Outlook OAuth connect button, token callback, Graph `/me/messages` sync, and configurable job-keyword filtering through `OUTLOOK_MAIL_KEYWORDS`.
- [2026-09-19T17:08+08:00] [CODE] Removed active outbound provider path and legacy worker files; Inbox UI now exposes only Outlook connection and receive/sort/tag flow.
- [2026-09-19T17:12+08:00] [USER] Requested Outlook-themed button with icon.
- [2026-09-19T17:12+08:00] [CODE] Styled Connect Outlook button in Microsoft blue with envelope icon and connected state.
- [2026-09-19T17:15+08:00] [USER] Requested Iconify package/library for Outlook icon.
- [2026-09-19T17:15+08:00] [CODE] Added Iconify web component CDN and `logos:microsoft-outlook` icon to Connect Outlook button.
- [2026-09-19T16:56+08:00] [CODE] Inbox badge now shows only `Not configured` while inbound setup is missing and hides after configuration.
- [2026-09-19T17:00+08:00] [USER] Requested removal of Leads page Search now button.
- [2026-09-19T17:00+08:00] [CODE] Hid visible Leads search button; scheduled backend search remains unchanged.
- [2026-09-19T16:37+08:00] [USER] Requested Iconify replacement for all possible UI icons.
- [2026-09-19T16:37+08:00] [CODE] Replaced visible text-symbol icons in navigation, actions, status controls, links, deletion, pagination, upload, close, and role/API/resume removal controls with Iconify web components using Lucide icons.
- [2026-09-19T16:37+08:00] [TOOL] `node --check app.js`, `python3 -m py_compile server.py`, and `git diff --check` pass; source contains no remaining legacy UI icon glyphs.
- [2026-09-19T16:42+08:00] [USER] Reported missing Outlook icon and subtle animation.
- [2026-09-19T16:42+08:00] [CODE] Replaced invalid `logos:microsoft-outlook` name with verified `mdi:microsoft-outlook` and added gentle icon float, hover lift, and keyboard focus motion styling.
- [2026-09-19T16:42+08:00] [TOOL] Iconify endpoint returns HTTP 200; JavaScript, Python, and diff checks pass.
- [2026-09-19T16:45+08:00] [USER] Requested original jobtracker logo/icon restored.
- [2026-09-19T16:45+08:00] [CODE] Restored original `✳` brand mark only; kept remaining UI controls on Iconify.
- [2026-09-19T16:41+08:00] [USER] Requested moved leads stay out of Leads and not return in later AI searches.
- [2026-09-19T16:41+08:00] [CODE] Added SQLite `lead_url_history`, canonical URL comparison, application URL backfill, and prompt-level exclusion for tracked postings; moved lead persistence now awaits server save.
- [2026-09-19T16:41+08:00] [TOOL] Restarted local server with migration; history table exists. Syntax, diff, canonical URL, and moved URL persistence checks pass.
- [2026-09-19T16:44+08:00] [USER] Requested workspace indicator show `STATUS: ONLINE/OFFLINE` with pulsing green/red dot.
- [2026-09-19T16:44+08:00] [CODE] Wired sidebar status text to live `/api/state` health check and added independent green online/red offline pulse animations.
- [2026-09-19T16:48+08:00] [USER] Requested server status moved to global top-right without visible status text.
- [2026-09-19T16:48+08:00] [CODE] Replaced sidebar label with compact accessible top-right status dot; tooltip and ARIA label expose online/offline state while color and pulse remain visible.
- [2026-09-19T16:50+08:00] [USER] Reported leftover whitespace after moving status indicator.
- [2026-09-19T16:50+08:00] [CODE] Removed sidebar bottom padding left behind by the deleted status footer while preserving bottom-anchored settings card.
- [2026-09-19T17:09+08:00] [USER] Provided VPS SSH target and requested UFW access for Codex LB ports after checking Docker firewall handling.
- [2026-09-19T17:09+08:00] [TOOL] VPS UFW rules allow TCP 1455/2455 only from SSH source `136.158.62.149`; persistent `/usr/local/sbin/docker-firewall` allowlist updated and `docker-firewall.service` restarted. Port 2455 accepts externally; port 1455 reaches its firewall rule but service resets the connection.
- [2026-09-19T17:20+08:00] [USER] Requested favicon before deploying Jobtracker through Dokploy.
- [2026-09-19T17:20+08:00] [CODE] Added navy/mint SVG favicon and linked it from the HTML app shell.
- [2026-09-19T17:30+08:00] [USER] Requested Jobtracker Dockerization for Dokploy.
- [2026-09-19T17:30+08:00] [CODE] Added Dockerfile with Python runtime, Poppler PDF support, official Codex CLI install, `/data` persistence, healthcheck, and container-safe bind configuration; added `.dockerignore`.
- [2026-09-19T17:22+08:00] [CODE] Set Dokploy deployment target to `jobtracker.zabe.dev` on container port `8000`; Docker build, container `/api/state` smoke test, JavaScript/Python checks, and diff check pass.
- [2026-09-19T17:22+08:00] [TOOL] VPS UFW and persistent `SERVER-DOCKER` rules now allow TCP `8000` only from `136.158.62.149`; `docker-firewall.service` active. Public domain currently reaches Cloudflare but returns `404` until Dokploy route is configured.

- [2026-09-19T13:10+08:00] [TOOL] Repo contains only `AGENTS.md`; implementation starts from empty state.
- [2026-09-19T13:18+08:00] [CODE] Added browser UI, local-storage data model, Python standard-library server, setup docs, and environment placeholder.
- [2026-09-19T13:18+08:00] [TOOL] `node --check app.js` and `python3 -m py_compile server.py` pass. Managed environment blocks local socket bind during server smoke test.
- [2026-09-19T13:32+08:00] [CODE] Replaced browser-only persistence with SQLite-backed `/api/state`; browser storage remains fallback cache.
- [2026-09-19T13:32+08:00] [CODE] Replaced target-role textarea with add/remove role chips backed by SQLite settings.
- [2026-09-19T13:39+08:00] [USER] Requested no dummy records.
- [2026-09-19T13:39+08:00] [CODE] Removed application/lead seed inserts and cleared existing `northstar.db` rows; new workspace starts empty.

## [OUTCOMES]

- [2026-09-19T13:32+08:00] [CODE] MVP now persists applications, leads, target roles, search frequency, and resume filename in `northstar.db`.
- [2026-09-19T13:39+08:00] [CODE] Persistent database verified with zero applications and zero leads after cleanup.
- [2026-09-19T13:55+08:00] [USER] Required Codex LB/Codex CLI only; no Anthropic integration.
- [2026-09-19T13:55+08:00] [CODE] Search client now targets local `codex-lb` Responses endpoint on `127.0.0.1:1455`; removed Anthropic references from app, docs, and env example.
- [2026-09-19T14:10+08:00] [TOOL] End-to-end search verified through Codex CLI using codex-lb: resume extracted with `pdftotext`, Codex web search returned 10 direct ATS/company URLs, and SQLite stored all 10 leads.
- [2026-09-19T14:10+08:00] [CODE] Search now invokes local `codex exec` so Codex CLI owns auth and web search; fixed proxy base to codex-lb `2455/v1` for diagnostics.
- [2026-09-19T14:25+08:00] [CODE] Added SQLite-backed last-search timestamp, daemon scheduler using 6/12/24-hour frequency, URL uniqueness/indexing, application URL de-duplication, live posting verification, lead Load more, and application number pagination.
- [2026-09-19T14:25+08:00] [TOOL] Verification passed: JavaScript/Python syntax, 24 stored leads with 24 unique URLs, last search timestamp `Sep 19, 2026 2:20 PM`, API state excludes resume text, and no Anthropic references remain.
- [2026-09-19T14:35+08:00] [CODE] Preserved the dashboard AI finder copy and leads notice; replaced stale verification/brand language with useful review-and-save guidance.
- [2026-09-19T14:40+08:00] [CODE] Added a direct `View job posting ↗` link to each application row when its stored posting URL exists.
- [2026-09-19T14:50+08:00] [CODE] Persisted the selected view in the URL hash, made application activity count real application dates, added a follow-up date input, and moved posting links into a dedicated icon-only Link column.
- [2026-09-19T14:55+08:00] [USER] Reverted the SSR architecture request; the 14:50 server-rendered implementation was superseded and is no longer active.
- [2026-09-19T15:05+08:00] [CODE] Replaced hash-only navigation with real `/applications`, `/leads`, and `/settings` paths; the static server now serves the app shell for each route and client navigation uses pathname history.
- [2026-09-19T15:25+08:00] [CODE] Resume upload now shows an analyzing state, static resume badges were removed, and the Remove resume action clears stored resume data through `/api/resume/remove`.
- [2026-09-19T15:26+08:00] [TOOL] A destructive endpoint smoke-test accidentally removed the stored resume; the original 2-page PDF was recovered from SQLite page remnants and restored under its original filename. API state still does not expose resume text.
- [2026-09-19T15:40+08:00] [CODE] Inbox Stage 1 added additive SQLite tables for accounts, threads, messages, tags, and thread tags; added `/inbox` navigation and an empty workspace shell without connecting external providers.
- [2026-09-19T13:32+08:00] [ASSUMPTION] Live AI search, resume parsing, URL verification, and scheduler remain next backend slice; current UI keeps explicit integration seam.

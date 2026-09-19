# Continuity

## [PLANS]

- [2026-09-19T13:10+08:00] [USER] Build `/job-tracker` as a local job tracker site.
- [2026-09-19T13:10+08:00] [ASSUMPTION] Ship a runnable browser-first MVP with local persistence and clear seams for later AI/API wiring.

## [DECISIONS]

- [2026-09-19T13:10+08:00] [CODE] Use plain HTML, CSS, JavaScript, and Python standard-library server to keep setup dependency-free.

## [PROGRESS]

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
- [2026-09-19T15:40+08:00] [CODE] Mail Stage 1 added additive SQLite tables for accounts, threads, messages, tags, and thread tags; added `/mail` navigation and an empty workspace shell without connecting external providers.
- [2026-09-19T13:32+08:00] [ASSUMPTION] Live AI search, resume parsing, URL verification, and scheduler remain next backend slice; current UI keeps explicit integration seam.

# Badeel (بديل) — Lost/Damaged Nusuk Card Reporting System

A web application built for the Hajj 1446H season to speed up and standardise the
reporting of lost or damaged Nusuk cards. Fully Arabic, right-to-left, and
self-contained: the entire dataset lives in a single SQLite file, so the app runs
anywhere a container runs, with no external database to provision.

---

## Overview

Badeel gives field staff and administrators one place to:

- File a report the moment a pilgrim's Nusuk card is lost or damaged.
- Track each report through its lifecycle — new, found, request sent, card
  received, card delivered.
- Mark operational progress per report: whether the request was uploaded, and
  whether it was written into the register.
- Read live statistics and a status breakdown chart.

---

## Technology

| Layer     | Choice                                                        |
| --------- | ------------------------------------------------------------- |
| Backend   | Python 3.11+, Flask (application factory + blueprints)        |
| Database  | SQLite in WAL mode, accessed through a small repository module |
| Frontend  | Jinja templates, Bootstrap 5 RTL, vanilla JS, Chart.js         |
| Serving   | gunicorn                                                       |
| Deploying | Docker, targeted at Coolify with a persistent volume           |

---

## Project layout

```
app/
  __init__.py        create_app() — builds the app, registers blueprints
  config.py          settings, all overridable by environment variables
  constants.py       statuses, reasons, Arabic labels, user-facing messages
  db.py              connection handling, PRAGMAs, schema, versioning
  timeutil.py        UTC storage, Riyadh display
  repository.py      every SQL statement in the application
  routes/
    public.py        /            /statistics   /healthz
    employee.py      /employee    /submit_request
    admin.py         /admin       /update_status  /update_flag  /update_total_hajj
  templates/         Jinja templates
  static/            CSS and JS
scripts/
  migrate_from_supabase.py   one-off import from the previous backend
tests/               pytest suite
wsgi.py              gunicorn entry point
```

Routes hold validation and HTTP concerns; `repository.py` holds storage. No SQL
appears outside the repository, and no `request`/`session` object appears inside it.

---

## Data model

**`card_requests`** — one row per report.

| Column                                | Notes                                             |
| ------------------------------------- | ------------------------------------------------- |
| `id`                                  | autoincrement primary key                         |
| `employee_name`, `employee_number`    | reporter; the number must match `05XXXXXXXX`      |
| `hajj_name`, `passport_number`, `visa_number` | pilgrim details                           |
| `request_reason`                      | `Lost Card` or `Damaged Card`, enforced by CHECK  |
| `card_returned`                       | damaged cards only                                |
| `request_upload`, `is_written`        | admin-toggled progress flags                      |
| `status`                              | one of five values, enforced by CHECK             |
| `created_at`, `updated_at`            | ISO 8601, stored in **UTC**                       |

A partial unique index (`passport_number WHERE status = 'New'`) allows at most one
open report per passport. The database enforces this, so two simultaneous
submissions cannot both slip through.

Passport numbers are hand-typed and SQLite compares text byte-for-byte, so they
are folded to a canonical form (uppercased, interior spaces removed) before being
stored or looked up. Without that, `a1234567` and `A123 4567` would each be able
to open their own report for the same pilgrim.

Two consequences worth knowing:

- Moving a closed report back to **New** when the passport has since been reported
  again is a genuine conflict. The admin endpoint answers `409` naming the
  passport, rather than a generic failure.
- If the database already contains duplicate open reports — which the previous
  backend's check-then-insert logic permitted — the index cannot be built. The app
  **still starts**, logs the offending passports as an error, and runs without the
  constraint, because `/admin` is the only place to resolve them. Close the stale
  reports and restart, and the index is created automatically.

Timestamps are stored in UTC and converted to Riyadh time (+03:00) for display.
Storing a single offset keeps `ORDER BY created_at` correct, since SQLite compares
those columns as text.

**`app_settings`** — a key/value table; currently holds `total_hajj`.

---

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

cp .env.example .env          # then set SESSION_SECRET
make run                      # http://127.0.0.1:5000
make test
```

The database file is created automatically at `data/badeel.db` on first boot.

---

## Deploying on Coolify

1. **New resource → Docker Compose**, pointed at this repository. Coolify reads
   `docker-compose.yaml` and provisions the `badeel-data` volume itself. The
   `.yaml` spelling matters: Coolify looks for `/docker-compose.yaml` by default,
   and reports "Docker Compose file not found" if the file uses `.yml` instead.
2. **Set `SESSION_SECRET`** in the environment tab. Generate one with:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   The compose file refuses to start without it.
3. **Deploy.** The container listens on port 8000 and reports readiness at
   `/healthz`, which Coolify's health check uses.

The SQLite file lives at `/data/badeel.db` on the mounted volume, so it survives
redeploys and image rebuilds. Back it up by copying that file — while the app is
running, copy `badeel.db`, `badeel.db-wal` and `badeel.db-shm` together, or use
`sqlite3 /data/badeel.db ".backup /data/backup.db"` for a consistent snapshot.

To build and run the image directly instead:

```bash
make docker-build
SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))") make docker-up
```

---

## Migrating the existing Supabase data

Run this once, locally, while the old Supabase project is still reachable.

```bash
pip install -e '.[migrate]'
export SUPABASE_URL=... SUPABASE_KEY=...

python scripts/migrate_from_supabase.py --dry-run          # inspect the counts
python scripts/migrate_from_supabase.py --database data/badeel.db
```

Then copy `data/badeel.db` onto the Coolify volume at `/data/badeel.db`.

The script pages through the API rather than taking the default first 1000 rows,
normalises every timestamp to UTC, and keys rows by their original ids so a second
run overwrites rather than duplicates.

If the legacy data contains a passport with more than one open report — possible
under the old check-then-insert logic — the script imports everything, reports the
offending passports, and exits non-zero without creating the uniqueness index. The
resulting database is still usable: start the app against it, resolve the
duplicates in the admin portal, then run the script again to finish.

---

## Configuration

| Variable                   | Default           | Purpose                                  |
| -------------------------- | ----------------- | ---------------------------------------- |
| `SESSION_SECRET`           | insecure default  | signs the session cookie; **set this**   |
| `DATABASE_PATH`            | `data/badeel.db`  | SQLite file location                     |
| `DISPLAY_UTC_OFFSET_HOURS` | `3`               | timezone used when rendering timestamps  |
| `SQLITE_BUSY_TIMEOUT_MS`   | `5000`            | how long a write waits behind another    |
| `LOG_LEVEL`                | `INFO`            | logging verbosity                        |

---

## Security note

`/admin` and `/statistics` are **not authenticated**. Anyone who can reach those
URLs can change report statuses and the pilgrim total. Keep the deployment on a
private network, or put an authentication layer in front of it.

---

## Developer

**Abdulaziz Hafiz** — Computer Science, Umm Al-Qura University (UQU)
[LinkedIn](https://www.linkedin.com/in/ahhafiz) · abdulazizhafez2004@gmail.com

All rights reserved © 2025 Abdulaziz Hafiz

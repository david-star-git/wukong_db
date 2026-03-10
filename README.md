# Wukong DB
#### Video Demo: https://www.youtube.com/watch?v=dQFruL8uqTY
#### Description:

Wukong DB is an internal workforce management web application built for our construction company. It allows administrators to import weekly attendance and payroll data from CSV files, view per-worker statistics and performance analytics on a dashboard, inspect the raw week-by-week attendance grid, and manage worker and construction site metadata through a settings panel. The application is designed to run on a local network, specifically on a Raspberry Pi, and is not intended to be exposed to the public internet for security reasons.

---

## Background and motivation

Our company receives a weekly CSV spreadsheet exported from our attendance system made in Excel. Each file contains a row per worker with half-day attendance codes for each day of the week (Monday through Saturday, AM and PM), plus columns for weekly salary, bonus, and total. Before this project existed, those files had no permanent home, we uploaded them to whatsapp and they where difficult to query historically. Wukong DB solves this by giving the files a structured destination and building an analytics layer on top.

---

## Technology stack

- **Backend:** Python 3 with Flask and a SQLite database accessed via the standard `sqlite3` module (no ORM). Gunicorn is used as the production WSGI server.
- **Frontend:** Jinja2 HTML templates, vanilla JavaScript, and Chart.js for visualizations. No frontend framework. The application is intentionally lightweight.
- **Deployment:** Docker and Docker Compose, with an Nginx reverse proxy on the host. The database is persisted in a named Docker volume so it survives container rebuilds.
- **Styling:** A consistent dark theme based on the Catppuccin Mocha palette throughout all pages.

---

## File and directory structure

### `app.py`
Creates the Flask app, registers all blueprints, sets up the session lifetime (30 days), and registers global error handlers for 404, 500, and unhandled `ValueError` exceptions. The use of a factory function rather than a module-level app instance allows the app to be instantiated cleanly by Gunicorn without side effects.

### `schema.sql`
Defines the five database tables. `workers` stores each person's display name, a normalized version of that name used for deduplication across CSV imports, their cédula (national ID number), and an active flag. `construction_sites` stores site codes and optional display names. `weeks` stores distinct (year, week_number) pairs. `attendance` records each individual half-day a worker was present, linking to a worker, a week, and a construction site, with a `sort_order` column that preserves the row order from the original CSV. `payroll_reference` stores the weekly salary rate, bonus, and total per worker per week.

### `core/db.py`
Handles database connection and initialization. `get_db()` opens a SQLite connection with `row_factory = sqlite3.Row` so results can be accessed by column name. `init_db()` runs `schema.sql` using `executescript`, which means the tables are created if they don't exist on every request, safe due to `IF NOT EXISTS` guards.

### `core/auth.py`
Contains the `login_required` decorator. Any route wrapped with it checks `session["logged_in"]` and redirects to `/login` if the session is not authenticated, preserving the original destination in a `next` query parameter.

### `core/csv_import.py`
The most complex file in the project. Parses the weekly CSV format, which is not a standard layout. The week number is in the first row, the column headers are in the second row, and worker data starts at the third row. Worker names often include leading numbers or inconsistent casing, so they are normalized before being stored or looked up. Site codes are created lazily on first encounter. The function detects payroll columns by name rather than position to be robust against column order changes. It returns the week number, year, a boolean indicating whether the week already existed, and counts of workers and attendance records processed, the latter two are used for the post-upload flash message.

### `core/helpers.py`
Small utility functions for querying which years and week numbers have data, used by the week overview page.

### `routes/auth.py`
Handles `/login` (GET and POST) and `/logout`. Credentials are read from the `WUKOND_USER` and `WUKOND_PASS` environment variables, which are set in the `.env` file and never committed to version control. On successful login the session is marked permanent with a 30-day lifetime.

### `routes/dashboard.py`
Renders the main `/` route. Fetches the worker list ordered by `id` (which reflects insertion order, matching the CSV row order) and passes the first worker's ID to the template so the dashboard loads with a worker already selected.

### `routes/api_workers.py`
Provides two JSON endpoints consumed by the dashboard's JavaScript. `/api/worker/<id>/profile` returns the worker's name, cédula, all-time totals, and the computed stats (stars, bonus likelihood, seniority, weeks on record). `/api/worker/<id>/charts` returns the data arrays for all three charts. The stats computation is done in Python rather than SQL because it involves multi-step logic. The star rating and bonus likelihood are both composite scores calculated over a rolling four-week window.

The **star rating** (1–5) is computed as: `ceil((0.55 × attendance_score + 0.45 × bonus_score) × 5)`, where `attendance_score` is the average days worked per week divided by 6 (the maximum possible), and `bonus_score` is `0.6 × (weeks with bonus / total weeks) + 0.4 × (average bonus / average salary)`.

The **bonus likelihood** (0–100%) uses the same bonus score formula multiplied by 100, looking only at the last four weeks of data.

The **total salary** is calculated correctly by multiplying each week's salary rate by the number of days actually worked that week (`salary_rate × halves / 2`), then summing across all weeks. This matters because the CSV stores a daily rate, not a weekly total.

### `routes/upload.py`
Handles CSV file upload at `/upload`. On POST it delegates to `upload_service.handle_upload()`. If the week already exists in the database it renders a confirmation page asking whether to overwrite. On success it flashes a message showing how many workers and attendance records were imported, then redirects to the week view. The `/overwrite-week` endpoint re-runs the import from the already-saved file.

### `routes/weeks.py`
Two routes: `/weeks/<year>` renders an overview of all weeks with data for that year, and `/week/<year>/<kw>` renders the full attendance grid for a specific week, showing every worker's half-day codes in a table.

### `routes/settings.py`
Allows assigning cédula numbers to workers and display names to construction sites. Workers are listed in insertion order (by `id`). Both forms POST to the same endpoint and the page re-renders after saving.

### `routes/api.py`
Placeholder file noting that the old duplicate API implementation has been consolidated into `routes/api_workers.py`. Kept in the repository to avoid breaking any cached imports.

### `services/upload_service.py`
Orchestrates the upload flow: reads and decodes the file, saves it to the `uploads/` directory as both a per-year backup and a flat archive copy, calls `import_csv`, and returns a structured result dict. The `overwrite_existing_week` function re-reads the archived file and runs the import again.

### `services/week_service.py`
Builds the data structures for the week view: fetches all workers, all attendance rows for the week, and the payroll entries, then assembles them into a nested dict keyed by worker ID. Site display logic mirrors the dashboard: name if available, then code, then raw numeric ID as a last resort.

### `templates/`
- `base.html`: shared layout with the sticky header, navigation links, logout button (shown only when logged in), and flash message rendering.
- `login.html`: standalone page, does not extend `base.html` since it has no navigation.
- `dashboard.html`: worker sidebar, stats cards, star rating block, bonus likelihood bar, and three Chart.js canvases.
- `week_view.html`: the full attendance grid table.
- `week_overview.html`: year/week navigation links.
- `upload.html`: drag-and-drop file upload form.
- `confirm_overwrite.html`: shown when uploading a CSV for a week that already has data.
- `error.html`: generic error page showing the HTTP status code and message.
- `settings.html`: tabbed form for workers and construction sites.

### `static/js/dashboard.js`
Fetches profile and chart data for the selected worker, renders the stat cards and star rating, animates the bonus likelihood progress bar, and draws or redraws the three Chart.js charts. All chart colors are taken from the Catppuccin Mocha palette to match the rest of the UI.

### `static/css/`
One CSS file per page. `style.css` defines the root CSS variables (the color palette) and shared utilities including flash message styles. `dashboard.css` handles the two-column layout, stat cards, star display, and chart grid. `login.css` styles the centered login card. The remaining files handle the upload form, week tables, settings grid, and header.

### `Dockerfile` and `docker-compose.yml`
The Dockerfile builds from `python:3.12-slim`, installs dependencies, and runs Gunicorn bound to `0.0.0.0:8080`. The Compose file maps host port 8080 to container port 8080 and mounts a named volume at `/app/instance` so the SQLite database persists across container rebuilds. An Nginx reverse proxy on the host handles port 80 and routes the custom local domain `wukong.db` to the container.

---

## Design decisions

**SQLite over PostgreSQL.** The application has a single user and runs on a local network. SQLite requires zero configuration, the database is a single file that is trivial to back up, and the write concurrency limitations are irrelevant for this use case.

**No ORM.** The queries are straightforward and writing them in raw SQL made it easier to reason about correctness, especially for the salary calculation (multiplying the daily rate by days worked per week) and the rolling-window stats. An ORM would have added abstraction without benefit.

**Half-day granularity.** The attendance system records AM and PM separately. Rather than collapsing these to whole days at import time, the database stores individual halves and all calculations divide by 2 where needed. This preserves the original data fidelity and makes the charts accurate for workers who regularly work half-days.

**Session-based authentication.** A single shared credential stored in environment variables is appropriate for an internal tool used by one administrator on a trusted local network. Adding per-user accounts with hashed passwords would be the right next step if the tool were to be shared with multiple people.

**Worker ordering.** Workers are displayed in the order they appear in the CSV files, which matches how the company's existing spreadsheets are organized. This is achieved by using the database insertion order (`ORDER BY id`) since workers are inserted in CSV row order on first import.

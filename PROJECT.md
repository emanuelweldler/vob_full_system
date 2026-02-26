# WellBrook Recovery Healthcare Portal

## Project Overview

This is an internal healthcare portal built for WellBrook Recovery, a substance abuse / behavioral health treatment facility. The system provides two primary functions for clinical and administrative staff:

1. **VOB (Verification of Benefits) Search** - Search and review insurance benefit records captured during patient intake, including deductibles, out-of-pocket maximums, network status, and funding type.
2. **Reimbursement Analytics** - Look up historical insurance reimbursement rates by member and level of care, displayed as per-LOC averages with drill-down to individual claim rows.

The portal is a **local-only, intranet-facing web application**. It is explicitly not cloud-hosted; it reads directly from a local SQLite database and is designed to be run on a single machine within the facility's network.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend / HTTP Server | Python 3 standard library (`http.server.ThreadingHTTPServer`, `SimpleHTTPRequestHandler`) |
| Database | SQLite 3 (via Python `sqlite3` module) |
| Authentication | Session-based cookies with SHA-256 password hashing (`hashlib`, `secrets`) |
| Frontend | Vanilla HTML5 / CSS3 / JavaScript (no frameworks, no build step) |
| Styling | Custom CSS with CSS variables, responsive grid, animated backgrounds |
| Database GUI | DB Browser for SQLite (`.sqbpro` project files in `VOB_DB/`) |

There is no Node.js, no npm, no React/Vue/Angular, no external package manager, and no cloud services. The entire stack runs with a standard Python installation.

---

## Project Structure

```
fullStackSystem/
├── server.py               # Main entry point — HTTP server + all API route handlers + query logic
├── auth.py                 # Authentication module (refactored version, used by modular layout)
├── db_connect/             # Database access layer (Python package)
│   ├── __init__.py         # Empty init (marks as package)
│   ├── db_utils.py         # Shared DB utilities: get_connection(), table_has_column()
│   ├── vob_queries.py      # VOB record query functions
│   └── reimb_queries.py    # Reimbursement query functions
├── public/                 # Static web root — all files served to the browser
│   ├── index.html          # Login page (served at / and /index.html)
│   ├── portal.html         # Main app page (protected, requires auth session)
│   ├── app.js              # All frontend JavaScript for the portal
│   ├── styles.css          # Portal application styles
│   ├── login_styles.css    # Login page styles (animated, branded)
│   └── logo.png            # WellBrook Recovery logo
└── VOB_DB/                 # SQLite database files (NOT tracked in git history)
    ├── vob.db              # Primary database (~7 MB, ~22,900+ records)
    ├── vb.db               # Empty/placeholder database
    ├── vob.sqbpro          # DB Browser for SQLite project file (main)
    └── vob_raw_import.sqbpro # DB Browser project file (raw import view)
```

### Note on `server.py` vs. `db_connect/`

`server.py` contains an older, self-contained implementation where all query logic lives directly in the file. The `db_connect/` package and `auth.py` represent a **refactored modular version** of the same logic introduced in the authentication commit. Both implement identical business logic; the `db_connect/` module is intended for future use when the server is split further. Currently `server.py` is the running server that is actually executed.

---

## Key Features and Functionality

### Authentication System

- Session-based login with HttpOnly cookies (`session_token`, 24-hour expiry)
- Passwords stored as SHA-256 hashes in the `users` table
- In-memory session store (Python dict `SESSIONS`) — sessions are lost on server restart
- Protected routes: `/portal.html` redirects to `/index.html` if no valid session
- Client-side auth guard on `portal.html` also calls `/api/auth/check` on load
- Login/logout via POST `/api/auth/login` and GET `/api/auth/logout`
- User record tracks `login_count` and `last_login` timestamp, updated on each successful login

### VOB (Verification of Benefits) Search

Search fields:
- **Member ID** (partial match against both `insurance_id` and `insurance_id_clean`)
- **Date of Birth** (exact match)
- **Payer name** (partial match against `insurance_name_raw`)
- **BCBS State** (smart filter: dynamically shown when payer contains "bcbs", "blue", or "anthem"; searches for BCBS/Blue Cross/Anthem plans within the selected state)
- **Facility name** (partial match)
- **Employer name** (partial match)
- **First Name / Last Name** (partial match)
- **Result limit** (25 / 50 / 100 / 200)

Results display in a table showing ID, created date, name, DOB, payer, network status, funding type, deductible, OOP max, and facility.

A green dot indicator ( filled circle in teal ) appears on rows where the member also has reimbursement data. Clicking any row opens a modal with full VOB detail JSON. If reimbursement data exists, the modal shows a **split view**: VOB data on the left, reimbursement summary by LOC on the right.

### Reimbursement Analytics

Search fields:
- **Prefix / Member ID starts-with** (prefix search)
- **Payer contains** (partial match; also triggers BCBS state dropdown)
- **BCBS State** (same smart BCBS filter as VOB search)
- **First Name / Last Name** (partial match)
- **Employer** (partial match; gracefully skipped if `employer_name` column does not exist)

Results are **grouped by person** (member_id + payer_name + name) and show average allowed amounts broken down by Level of Care (LOC):
- **DTX** — Detox
- **RTC** — Residential Treatment Center
- **PHP** — Partial Hospitalization Program
- **IOP** — Intensive Outpatient Program

Each person card has:
- A "Copy summary" button (copies formatted text to clipboard)
- LOC buttons (DTX / RTC / PHP / IOP) that open a modal with individual daily reimbursement rows
- A back button to return from LOC detail view to the person summary

### BCBS Smart Search

A notable feature is the intelligent BCBS state filtering, which handles the fact that Blue Cross Blue Shield plans are branded differently across states. When "bcbs", "blue", or "anthem" is typed in the payer field, a state dropdown appears. The search then matches records containing any of: `%bcbs%`, `%blue%cross%`, or `%anthem%` AND either `%{state}%` or `%OF {state}%` in the insurance name — capturing all common naming variants.

---

## Database Schema

All data lives in `VOB_DB/vob.db` (SQLite).

### `vob_records` (2,141 rows)
Stores insurance benefit verification data captured at intake.

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| created_at | TIMESTAMP | Record creation timestamp |
| facility_name | TEXT | Treating facility |
| insurance_name_raw | TEXT | Raw insurance name as captured |
| payer_canonical | TEXT | Normalized payer name (often NULL) |
| insurance_id | TEXT | Raw member ID |
| insurance_id_clean | TEXT | Cleaned/normalized member ID |
| group_number | TEXT | Raw group number |
| group_number_clean | TEXT | Cleaned group number |
| in_out_network | TEXT | In-network or out-of-network status |
| deductible_individual | TEXT | Individual deductible amount |
| family_deductible | TEXT | Family deductible amount |
| oop_individual | TEXT | Individual out-of-pocket maximum |
| oop_family | TEXT | Family out-of-pocket maximum |
| self_or_commercial_funded | TEXT | Self-funded vs. commercial insurance |
| exchange_or_employer | TEXT | Marketplace exchange vs. employer plan |
| employer_name | TEXT | Employer name |
| first_name | TEXT | Patient first name |
| last_name | TEXT | Patient last name |
| dob | TEXT | Date of birth |
| source_file | TEXT | Source file the record was imported from |
| error_details | TEXT | Any errors noted during import |

### `reimbursement_rates` (20,786 rows)
Stores historical insurance claim reimbursement amounts by service date and level of care.

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| facility | TEXT | Facility name |
| status | TEXT | Claim status |
| payment_type | TEXT | Payment type |
| payer_id | TEXT | Payer identifier |
| payer_name | TEXT | Insurance payer name |
| last_name | TEXT | Patient last name |
| first_name | TEXT | Patient first name |
| member_id | TEXT | Member/insurance ID |
| service_date_from | DATE | Service start date |
| service_date_to | DATE | Service end date |
| loc | TEXT | Level of care (DTX, RTC, PHP, IOP) |
| allowed_amount | REAL | Insurance allowed/reimbursed amount |
| created_at | DATETIME | Record creation timestamp |
| employer_name | TEXT | Employer name |
| employer_source | TEXT | Source of employer data |

### `users` (1 row)
Stores portal user accounts.

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| username | TEXT | Login username |
| password_hash | TEXT | SHA-256 hash of password |
| first_name | TEXT | User first name |
| last_name | TEXT | User last name |
| role | TEXT | User role (e.g., admin, staff) |
| department | TEXT | User department |
| login_count | INTEGER | Cumulative login count |
| last_login | TIMESTAMP | Last successful login time |
| created_at | TIMESTAMP | Account creation timestamp |
| is_active | INTEGER | 1 = active, 0 = disabled |

### Other Tables (import/staging)
- `VOB_Extracted_Data_20260107_223516` — historical extract snapshot
- `VOB_raw_PH` — raw VOB data (partial hospitalization source)
- `wellbrook_raw` — raw Wellbrook data
- `vob_raw_import` — raw import staging table
- `temp_claims_import` — temporary claims import table

---

## API Endpoints

All endpoints are served by `server.py` on `http://localhost:8000`.

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check; returns `{"ok": true/false, "dbPath": "..."}` |
| POST | `/api/auth/login` | Login; body: `{"username": "...", "password": "..."}` |
| GET | `/api/auth/check` | Check current session validity |
| GET | `/api/auth/logout` | Destroy session and clear cookie |
| GET | `/api/vob/search` | Search VOB records (see query params below) |
| GET | `/api/reimb/summary` | Get reimbursement averages by member/LOC |
| GET | `/api/reimb/rows` | Get individual reimbursement rows for a member+LOC |
| GET | `/api/reimb/check-members` | Check which member IDs have any reimbursement data |

### `/api/vob/search` query parameters
`memberId`, `dob`, `payer`, `bcbsState`, `facility`, `employer`, `firstName`, `lastName`, `limit` (default 50, max 200)

### `/api/reimb/summary` query parameters
`prefix`, `payer`, `bcbsState`, `employer`, `firstName`, `lastName`

### `/api/reimb/rows` query parameters
`memberId`, `loc`, `limit` (default 500, max 2000)

### `/api/reimb/check-members` query parameters
`memberIds[]` (repeating array parameter)

---

## How to Run

### Prerequisites

- Python 3.7+ (uses `http.server.ThreadingHTTPServer`, available since Python 3.7)
- No external Python packages required — standard library only
- The SQLite database file must exist at the path configured in `server.py`

### Configuration

Open `server.py` and update the `DB_PATH` constant at the top of the file to point to your local database:

```python
# Line 11 in server.py
DB_PATH = r"C:\data\VOB_DB\vob.db"
```

The database is currently located in the project at `VOB_DB/vob.db`. To use the local copy, change the path to:

```python
DB_PATH = os.path.join(os.path.dirname(__file__), "VOB_DB", "vob.db")
```

If using the `db_connect` module separately, also update `DB_PATH` in `db_connect/db_utils.py` (line 7).

### Starting the Server

```bash
python server.py
```

The server starts at `http://localhost:8000` and prints:
```
Healthcare Portal with Auth running: http://localhost:8000
Login at: http://localhost:8000
```

Open a browser and navigate to `http://localhost:8000` to see the login page.

### Creating a User Account

Users must be inserted directly into the database. Passwords must be stored as SHA-256 hashes. To create a user from Python:

```python
import sqlite3, hashlib

DB_PATH = r"VOB_DB\vob.db"
username = "youruser"
password = "yourpassword"
password_hash = hashlib.sha256(password.encode()).hexdigest()

conn = sqlite3.connect(DB_PATH)
conn.execute("""
    INSERT INTO users (username, password_hash, first_name, last_name, role, department, is_active)
    VALUES (?, ?, ?, ?, ?, ?, 1)
""", (username, password_hash, "First", "Last", "staff", "Clinical"))
conn.commit()
conn.close()
```

---

## Key Files and Their Roles

| File | Role |
|---|---|
| `server.py` | **Single entry point.** Contains the `ThreadingHTTPServer`, the `Handler` class (routing all GET/POST requests), authentication logic, and all SQL query functions. This is the file you run. |
| `auth.py` | Refactored authentication module with cleaner function signatures and docstrings. Imports from `db_connect`. Currently exists as a module but is not imported by `server.py` directly — its logic is duplicated inline in `server.py`. |
| `db_connect/db_utils.py` | Shared database utilities: `get_connection()` factory and `table_has_column()` helper. Holds `DB_PATH` for the modular codebase. |
| `db_connect/vob_queries.py` | Encapsulates all VOB search query logic in `query_vob()`. Refactored version of what lives in `server.py`. |
| `db_connect/reimb_queries.py` | Encapsulates reimbursement queries: `reimb_summary()`, `reimb_rows()`, and `check_member_reimb()`. |
| `public/index.html` | Login page. Contains the two-panel branding + form layout and an inline `<script>` that POSTs credentials to `/api/auth/login` and redirects to `/portal.html` on success. |
| `public/portal.html` | Main application shell. Has an inline auth guard that redirects to login if the session is invalid. Contains the VOB search form, results table, reimbursement search form, and both modal overlays. Loads `app.js` and `styles.css`. |
| `public/app.js` | All portal JavaScript (~600 lines). Handles tab switching, VOB and reimbursement search/fetch/render, modal open/close, BCBS state dropdown toggling, clipboard copy, and the `groupPeople()` aggregation function. |
| `public/styles.css` | Dark-themed portal styles. CSS custom properties for color palette, grid layout, table styles, modal overlay/card styles, split-view modal, reimbursement indicator dot, and responsive breakpoints. |
| `public/login_styles.css` | Animated login page styles. Features animated background grid, floating gradient shapes, logo entrance animation, and a polished login card with loading indicator and error shake animation. |
| `VOB_DB/vob.db` | The live SQLite database. Contains all VOB records, reimbursement rates, and user accounts. |

---

## Notable Patterns and Architectural Decisions

### Self-Contained Python HTTP Server
Rather than using Flask, FastAPI, or Django, the server uses Python's built-in `http.server` module. This eliminates all external dependencies and simplifies deployment — the entire backend is one `python server.py` command with no virtual environment or package installation needed.

### No Frontend Build Tooling
The frontend is plain HTML, CSS, and JavaScript. No bundler, no TypeScript, no JSX. This makes the frontend trivially editable and runnable without any Node.js toolchain.

### Dual Implementation Pattern
The codebase has an intentional duplication: `server.py` is a monolith that works standalone, while `auth.py` and `db_connect/` represent a cleaner, modular refactor of the same logic. The refactored modules have better docstrings and separation of concerns. The intention appears to be incrementally migrating `server.py` to import from these modules, but this migration is not yet complete.

### In-Memory Session Store
Sessions are stored in a Python dictionary (`SESSIONS = {}`). This is simple and has zero infrastructure requirements, but it means all sessions are lost when the server process restarts. For an internal tool run on a single machine with low concurrency, this is an acceptable tradeoff noted in comments throughout the code.

### BCBS Smart Filter
Blue Cross Blue Shield is a federation of independent regional insurers with inconsistent naming (BCBS California, Anthem Blue Cross, Blue Cross of Texas, etc.). The application detects when a user is searching for a BCBS variant and reveals a state dropdown, then constructs a compound SQL query matching against all known name patterns (`%bcbs%`, `%blue%cross%`, `%anthem%`) combined with a state string match. This was an iterative fix (commit `e4bed22` specifically addressed an Anthem bug).

### Parameterized SQL with Named Placeholders
All SQL queries use named bind parameters (`:paramName` syntax with a dict) to prevent SQL injection. The only dynamic SQL element is the `LIMIT` clause, which is sanitized with `max(1, min(int(limit), MAX))` before interpolation.

### Reimbursement Indicator Pre-check
When VOB results are rendered, the app immediately fires a batch `/api/reimb/check-members` request with all member IDs from the current result set. This populates a set of IDs that have reimbursement data, allowing the green dot indicator to be shown on each row without loading the full reimbursement detail upfront.

### Protected Route — Dual Guard
The portal page is protected in two places:
1. **Server-side (Python):** `/portal.html` route checks the session cookie and issues an HTTP 302 redirect to `/index.html` if not authenticated.
2. **Client-side (JavaScript):** An immediately-invoked async function at the top of `portal.html` calls `/api/auth/check` and redirects if `authenticated` is false.

This defense-in-depth approach ensures protection even if the server-side redirect were bypassed.

### Responsive Design
Both pages use CSS Grid with media query breakpoints. The portal grid collapses from 4 columns to 2 to 1 at 900px and 520px. The login page hides the branding panel below 1200px. The VOB/reimbursement split-view modal switches from horizontal to vertical stacking at 768px.

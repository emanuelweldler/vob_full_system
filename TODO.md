# TODO - Go Live Checklist

## 1. Migrate Database from SQLite to PostgreSQL
- Sign up for a PostgreSQL database on Render (free tier available)
- Update `server.py` to use `psycopg2` instead of `sqlite3`
- Update all queries (SQLite uses `?` placeholders, PostgreSQL uses `%s`)
- Update `vob_extractor.py` to write to PostgreSQL instead of SQLite
- Migrate existing data from local `vob.db` to the new Render PostgreSQL instance

## 2. Deploy Server to Render
- Push codebase to GitHub
- Create a new Web Service on Render pointed at the repo
- Set the `PORT` environment variable (Render assigns this dynamically)
- Update `server.py` to read port from environment: `PORT = int(os.environ.get("PORT", 8000))`
- Update `DB_PATH` to use Render's PostgreSQL connection string via environment variable
- Create a `requirements.txt` with all dependencies:
  - `PyPDF2`
  - `psycopg2-binary`
- Test the live URL

## 3. Set Up Email Automation via Microsoft Graph API
- Go to portal.azure.com and register a new app
- Add `Mail.Read` and `Mail.ReadWrite` API permissions (Microsoft Graph)
- Generate a client secret
- Store credentials as environment variables on Render:
  - `AZURE_CLIENT_ID`
  - `AZURE_CLIENT_SECRET`
  - `AZURE_TENANT_ID`
- Rewrite `vob_email_watcher.py` to use Graph API instead of win32com
  - Poll inbox for unread emails where subject starts with "VOB"
  - Download PDF attachments
  - POST to the upload API endpoint
  - Mark email as read
- Deploy the watcher as a Render Cron Job (runs on a schedule, e.g. every 15 minutes)
- Test end to end: send a VOB email → confirm it appears in the portal

## 4. Reps Portal — AI Policy Evaluation Tool

### Overview
A tool inside the portal where reps enter a member's insurance info and receive a plain-English recommendation (green/yellow/red rating + one-liner). Reps never see the underlying data, rules, or AI reasoning.

### Phase 1 — Lookup Against Claims History
- Build a `policy_rules` database table for internal payer/employer/state/TPA rules (admin-managed, never exposed to reps)
- New endpoint `POST /api/policy/evaluate`:
  - Accepts: payer name, member ID prefix, employer, state, TPA, network type
  - Queries `reimbursement_rates` to compute per-LOC averages for matching payer/employer/state
  - Loads any matching rules from `policy_rules` table
  - Sends clean summary (never raw rows) + rules to Claude API
  - Returns structured response: `{ rating, short_message }` only
- New rep-facing UI tab in the portal:
  - Simple form: payer, prefix, employer, state, TPA, network type
  - Displays only the rating (🟢🟡🔴) and short message
  - Admin view shows full AI reasoning; rep view does not
- Migrate existing GPT prompt rules (BCBS prefixes, UMR Aurora symbol, UHC Shared Services, Centivo, Cigna OON, Aetna, Allegiance, Dean Health, etc.) into `policy_rules` table

### Phase 2 — Benefits Verification API Integration (Availity or VerifyTx)
- Research Availity API and VerifyTx API — compare access requirements, cost, and data returned
- Goal: rep enters member ID + payer once, portal fetches live benefits data automatically
- New endpoint `POST /api/policy/verify`:
  - Calls Availity/VerifyTx API with member info
  - Returns live benefits: OON deductible, OOP max, network status, active coverage
- Pipe that live benefits data directly into the AI evaluation alongside claims history and rules
- Result: one form submission → live benefits check + historical analysis + rules → single recommendation
- This eliminates the need for reps to use Availity separately

### Phase 3 — Insurance Card Image Recognition
- Allow reps to upload or photograph an insurance card
- Use Claude vision to extract: payer name, member ID prefix, employer, network info, TPA
- Pre-fill the evaluation form automatically from the card image
- Apply visual rules (UMR Aurora symbol, Centivo network info, Cigna OON fields, etc.)

## Notes
- Current local DB: `C:\Users\EmanuelW\OneDrive - Midwest Detox\code\fullStackSystem\VOB_DB\vob.db`
- Current server reads from same path (updated)
- Upload page is already built and working locally
- Duplicate PDF protection is already in place (checks `source_file` before inserting)

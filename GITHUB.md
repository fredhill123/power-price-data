# Auto-refresh (GitHub Actions) — operations & handover

This repo keeps the ENTSO-E power-price CSVs fresh automatically, so the Excel
workbook (set to *refresh-on-open*) is always current — a non-technical user
just opens the file. Nobody has to run anything.

## How it works
- `.github/workflows/refresh.yml` runs on a schedule (monthly, 2nd @ 06:00 UTC)
  and on demand. It fetches ENTSO-E, rebuilds the summaries, and publishes CSVs
  to `published/` (served at stable raw URLs).
- The workbook's Power Query connections point at those URLs and refresh on open.

## Run it manually (anyone with repo access)
GitHub → **Actions** tab → *Refresh ENTSO-E power-price data* → **Run workflow**.
Takes ~30–45 min. When it finishes, `published/*.csv` is updated; open the
workbook and it pulls the new data.

## The API key
Stored as the encrypted repo **Secret** `ENTSOE_API_KEY` (Settings → Secrets and
variables → Actions). It is never in the code. Get a free key at
https://transparency.entsoe.eu/ (register → request API access).

## Handover to a colleague / your company
1. **Give them access** — add them as a collaborator (Settings → Collaborators),
   or **transfer** the repo into your company's GitHub Organization
   (Settings → General → Transfer ownership).
2. **Swap the API key** — the successor creates their own ENTSO-E key and updates
   the `ENTSOE_API_KEY` Secret. (Do this if the original key owner leaves.)
3. **If the repo path changed** (e.g. personal → org), update the CSV URLs in the
   workbook once: Data → Queries & Connections → edit each query's source URL to
   the new `raw.githubusercontent.com/<owner>/<repo>/main/published/<name>.csv`.
   Keeping the repo in a stable org avoids this entirely.
4. Nothing else is account-specific. The pipeline, schedule and docs travel with
   the repo.

## Change the refresh cadence
Edit the `cron:` line in `.github/workflows/refresh.yml` (uses standard cron, UTC).

## If a run fails
Open the failed run under **Actions** to see logs. Most failures are transient
ENTSO-E 503s — just re-run. The workflow already does a second fetch pass to fill
any gaps; a re-run fills the rest.

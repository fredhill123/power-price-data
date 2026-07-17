# Power Price Data — current status

_Last updated: 2026-07-16_

## State: ✅ Built & validated — v1 complete
Full ENTSO-E dataset (2019–2026, 5 countries) fetched, assembled, summarised, and
written to a fixed-cell-reference Excel workbook. Reference charts reproduce all 8
Redburn ENTSO-E figures. Ready for PowerPoint linking.

## What exists
- **Data store**: `data/raw/*.parquet` (337 raw pulls) → `data/processed/hourly_master.parquet`
  (330,430 hourly rows × 26 cols) + `capacity_annual.parquet` + `power.duckdb`.
- **Summaries**: `data/processed/summaries/*.parquet` (10 tables).
- **Deliverable**: `outputs/PowerPriceData.xlsx` (11 tabs, fixed cells, pre-allocated to 2035).
- **Charts**: `outputs/charts/*.png` (8 Rothschild-style reference renders).
- **Pipeline**: `_tools/{config,fetch,build_hourly,summaries,build_excel,charts,validate}.py`,
  `refresh.sh`, `.venv`.

## Validation (2026-07-16): 6/6 checks pass
- 100% price & generation coverage across all 40 country-years.
- DE 2024 avg daily spread €112 (Redburn: €112; min €32 vs ref €33, max €144 vs ref €144).
- DE 2024 near-negative hours 628 (Redburn: ">600"); negative(<0) 457.
- Solar capture −41%, Gas +21% (matches Fig 5). IT PUN proxy €108.5 (actual ~€108).

## Key decisions (locked with Fred)
- Charts: Figs 1–6 + Fig 7 + Fig 9. · Italy price = load-weighted PUN proxy.
- Delivery = fixed-cell data; Fred links PPT charts once (see `LINKING_GUIDE.md`).
- Intraday buckets = **UTC hour**. · Everything stored UTC (DST-safe).
- Future-proof: pipeline auto-fetches new years; workbook pre-allocated to 2035.

## To refresh
`cd _tools && ./refresh.sh` (auto-targets current + previous year), then update links in PPT.

## Open / possible next steps (Phase 1 polish)
- Confirm the workbook tab structure suits your PPT workflow (trim/rearrange if needed).
- If you want the intraday charts in **local** clock instead of UTC, it's a one-line change.
- Fig 6/Fig 7 currently hold all country-years; say if you want them trimmed for size.

---

## PHASE 2 — GitHub-hosted auto-refresh (2026-07-17, in progress)
**Chosen approach** (superseded Option C direct-from-Excel — Mac Excel can't author PQ / has no
"From Web", and Mac testing was unreliable under CRD/virtual displays). Constraint: must be
refreshable by a **non-technical person while Fred is away**, on a **Windows** work PC.

**Design:** scheduled GitHub Action runs the Python pipeline monthly (+ on-demand), publishes
chart-ready CSVs to public raw URLs. Windows Excel loads them via **From Web** with
**refresh-on-open** → a non-technical user just OPENS the file and it's current. PPT links auto-update.

**Built & live:**
- Public repo **github.com/fredhill123/power-price-data** (owner fredhill123). Pushed pipeline +
  workflow. `ENTSOE_API_KEY` set as encrypted Actions Secret (key NOT in code — resolves from env or
  git-ignored `_tools/.entsoe_key`).
- `.github/workflows/refresh.yml` (cron 2nd@06:00 UTC + workflow_dispatch, double-fetch pass).
- `_tools/export_csv.py` (tidy CSVs) + `_tools/chart_csv.py` (chart-ready WIDE CSVs, pre-allocated to
  2035). Validated vs Phase-1 numbers. Published raw URLs confirmed HTTP 200.
- Docs: `GITHUB.md` (ops + handover — repo is transferable to a colleague/org; successor swaps their
  own ENTSO-E key), `EXCEL_SETUP.md` (one-time Windows setup: load CSVs, refresh-on-open, charts, PPT).
- First Action run triggered (run 29559544914) to prove the cloud pipeline end-to-end.

**Uncommitted locally (push after the running Action finishes, to avoid push conflict):** workflow
update adding chart_csv step, `chart_csv.py`, seeded `published/charts/*.csv`, `EXCEL_SETUP.md`.

**Division of labour (agreed):** Claude builds the CHARTS (openpyxl can't add Power Query, and would
STRIP it if it saved a file that had queries — so Claude must go FIRST, Fred adds queries LAST in Excel
which preserves the charts). Never open Fred's query-file with openpyxl and save.

**BUILT since:** `_tools/build_linked.py` -> `outputs/PowerPriceData_Linked.xlsx` (13 sheets): each
figure sheet has its chart CSV's data at A1 + a pre-built native Excel chart wired to the Redburn-relevant
columns (Fig1 line, Fig2/3cum/4 line, Fig3/5/9 clustered bar, Fig6 scatter, Fig7 stacked-col+price-line
combo), styled navy/teal. All chart types validated by rendering to PDF via soffice (charts display OK).
Delivered to Fred. Each sheet carries a red SETUP note with its From-Web URL + load target; READ_ME_FIRST
tab included.

**INCREMENTAL refresh (2026-07-17):** history (2019-2025) frozen as committed `data/processed/
master_fixed.parquet` (24MB) + `capacity_fixed.parquet`. Each Action run fetches ONLY the current year
(2026) per country, `build_hourly.py` (default = incremental) stitches it onto the frozen history →
runs drop from ~65min to ~5-10min. `build_hourly.py --full` re-freezes everything (annual rollover /
bootstrap). Regression-checked: identical numbers (DE24 457/628, Fig5 Solar -41.1, Fig1 SD 52.73).
Workflow fetch step now `--years $CURRENT --force`. Annual TODO: after a year completes, run a `--full`
build once to fold it into master_fixed.

**Fig1 calibration PASSED** on the no-seed file: chart reads live query table (B-F), G-L empty, no shift.
Mechanism proven end-to-end on Fred's Windows Excel. Fred clear to wire the remaining sheets.
Gotcha learned: the SEED (data at load target) caused Power Query to insert+shift; empty target loads in
place. Also: two same-named downloads confused which file was tested (the `(1)` file was the real one).

**NEXT / where we paused:** (1) Fred wires just the **Fig1** query on Windows (From Web -> Load to
'Fig1_PriceSD'!A1), saves, sends the file BACK. Claude opens it READ-ONLY (safe — reading never strips PQ)
to confirm Power Query's exact table layout matches the chart's cell refs; adjust build_linked.py if
needed, resend. (2) Fred then wires the remaining queries + ticks refresh-on-open on each. (3) Paste-link
charts into PPT (set links Automatic). (4) Verify Action run went green + auto-committed fresh CSVs.
Known wrinkle: fig6/fig7 CSVs are very wide (fig7=1701 cols) — functional but could be narrowed later.

### (archived) Option C attempt — direct-from-Excel
**Goal:** update the workbook on Fred's **Windows work PC** (locked down: no terminal, no installs,
Excel only, can reach any external URL) purely via Excel **Power Query** hitting ENTSO-E — so the
Python pipeline here is the initial build, but ongoing refresh is Excel-native. Trigger = manual
(Data > Refresh All). Decided to **build C** and test on THIS Mac's Excel first.

**Progress:**
- Confirmed raw ENTSO-E REST works with a plain GET (HTTP 200, parseable XML). Key gotcha: prices are
  now `PT15M` — M must parse TimeSeries>Period>Point, compute UTC ts from period start + resolution,
  resample to hourly.
- Drafted first M query: `_tools/powerquery/01_DE_prices.m` (DE prices -> hourly UTC).
- Made scratch `outputs/Test_PQ.xlsx`; began driving Excel via AppleScript automation.

**⚠️ BLOCKER discovered — must resolve first:** This Mac's Excel (v16.111) menu bar does NOT expose
Power Query "Get Data / From Web / Blank Query / Advanced Editor". Data > Get External Data only has
the LEGACY "Run Web Query..." + Microsoft Query — not Power Query authoring. Took a screenshot
(`$CLAUDE_JOB_DIR/tmp/excel_state.png`) to check the ribbon but PAUSED before reading it.
**Open question:** does Mac Excel 16.111 have Power Query authoring in the ribbon (not menu bar), or
is it too limited to author/test here? If limited, on-device testing of C isn't viable on this Mac and
we need another test path (Windows VM, or test directly on the work PC, or reconsider).

**Excel is currently open** with Test_PQ.xlsx; M code was on the clipboard.

**Resume by:** reading `excel_state.png`, checking the Data-tab RIBBON for a "Get Data"/Power Query
control (System Events AXToolbar), and determining whether Advanced-Editor authoring exists on this
build. If yes → paste `01_DE_prices.m`, Close & Load, test Refresh. If no → discuss alternative test
path with Fred before building further.

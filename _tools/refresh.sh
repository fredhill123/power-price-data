#!/usr/bin/env bash
# One-shot refresh: re-pull latest years, rebuild master, summaries, workbook.
# Usage: ./refresh.sh [years]   (default: re-fetch 2025,2026)
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate
# default: re-fetch current & previous calendar year (auto — no edit needed each year)
YEARS="${1:-$(python -c "from datetime import date;y=date.today().year;print(f'{y-1},{y}')")}"
echo ">> fetch --years $YEARS --force"
python fetch.py --years "$YEARS" --force
echo ">> build_hourly"
python build_hourly.py
echo ">> summaries"
python summaries.py
echo ">> build_excel"
python build_excel.py
echo ">> done: output/PowerPriceData.xlsx"

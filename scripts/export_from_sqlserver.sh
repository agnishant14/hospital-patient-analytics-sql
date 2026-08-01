#!/usr/bin/env bash

CONTAINER="${HOSPITAL_SQL_CONTAINER:-hospital-sql}"
DATABASE="${HOSPITAL_SQL_DATABASE:-HospitalPatientAnalytics}"
SQLCMD="${HOSPITAL_SQLCMD:-/opt/mssql-tools18/bin/sqlcmd}"

set -euo pipefail

if [[ -z "${HOSPITAL_SQL_PASSWORD:-}" ]]; then
  echo "error: set HOSPITAL_SQL_PASSWORD first." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/exports"

run_query() {
  local sql_file="$1"
  local name
  name="$(basename "$sql_file" .sql)"

  docker exec -i "$CONTAINER" "$SQLCMD" \
      -S localhost -U sa -P "$HOSPITAL_SQL_PASSWORD" -C \
      -d "$DATABASE" -b -s"," -W -h 1 -Q "SET NOCOUNT ON; $(cat "$sql_file")" \
    | sed '2{/^-\+\(,-\+\)*$/d}' \
    | sed '/^(.* rows affected)$/d' \
    | sed '/^$/d' \
    > "$ROOT/exports/$name.csv"

  printf '  %-34s %6s rows\n' "$name.csv" "$(($(wc -l < "$ROOT/exports/$name.csv") - 1))"
}

echo "Exporting star-schema tables..."
for sql_file in "$ROOT"/analysis/model/*.sql; do run_query "$sql_file"; done

echo "Exporting analytical query results..."
for sql_file in "$ROOT"/analysis/queries/*.sql; do run_query "$sql_file"; done

echo
echo "Done. Now verify SQL Server and the oracle agree:"
echo "    python3 tests/verify_results.py"

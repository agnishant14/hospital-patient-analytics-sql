"""Differential test: does the T-SQL analysis layer agree with the oracle?

``exports/*.csv`` comes out of SQL Server. ``tests/oracle.py`` recomputes the
same figures independently, straight from the generator specification, without
a database. This script diffs them cell by cell and exits non-zero on the first
disagreement.

That is the real claim this project makes: not "here are some numbers", but
"two independent implementations produce identical numbers, so the numbers are
right". Roughly 1,900 aggregate values are checked.

Usage:
    python3 tests/verify_results.py            # check everything
    python3 tests/verify_results.py q07        # check one result set
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from oracle import generate_visits, load_dimensions  # noqa: E402
from queries import ALL_QUERIES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "exports"

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
)


def normalise(value) -> str:
    """Compare 45.69 and '45.690' as equal, and treat NULL/'' alike."""
    text = str(value).strip()
    if text.upper() in {"NULL", "NA", ""}:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    return f"{number:.4f}" if number % 1 else f"{number:.0f}"


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    return (rows[0], rows[1:]) if rows else ([], [])


def compare(name: str, header: list[str], expected: list[list]) -> list[str]:
    """Return a list of human-readable problems; empty means the check passed."""
    path = EXPORTS / f"{name}.csv"
    if not path.exists():
        return [f"missing export: exports/{name}.csv"]

    actual_header, actual_rows = read_csv(path)
    problems: list[str] = []

    if [h.strip() for h in actual_header] != header:
        problems.append(
            f"header mismatch\n    expected: {header}\n    actual:   {actual_header}"
        )
        return problems

    if len(actual_rows) != len(expected):
        problems.append(
            f"row count mismatch: expected {len(expected)}, got {len(actual_rows)}"
        )

    for index, (expected_row, actual_row) in enumerate(zip(expected, actual_rows), 1):
        for column, (want, got) in enumerate(zip(expected_row, actual_row)):
            if normalise(want) != normalise(got):
                problems.append(
                    f"row {index}, column '{header[column]}': "
                    f"expected {want!r}, got {got!r}"
                )
                if len(problems) >= 10:
                    problems.append("... further differences suppressed")
                    return problems
    return problems


def main() -> int:
    wanted = sys.argv[1] if len(sys.argv) > 1 else None

    if not EXPORTS.exists():
        print(f"{RED}exports/ not found.{RESET}")
        print("Run scripts/export_from_sqlserver.sh (with SQL Server running),")
        print("or scripts/build_exports.py to generate them without a database.")
        return 1

    provenance_file = EXPORTS / "PROVENANCE.txt"
    provenance = ""
    if provenance_file.exists():
        first_line = provenance_file.read_text(encoding="utf-8").splitlines()[0]
        provenance = first_line.removeprefix("source:").strip()

    print(f"{DIM}Rebuilding oracle from the generator specification...{RESET}")
    dims = load_dimensions()
    visits = generate_visits(dims)

    # Structural assertions that mirror validation/08_data_quality_checks.sql.
    checks = [
        ("fact row count", len(visits), 50_000),
        ("clean patients", len(dims["patients"]), 2_431),
        ("clean departments", len(dims["departments"]), 33),
        ("doctors", len(dims["doctors"]), 200),
        ("diagnoses", len(dims["diagnoses"]), 40),
        ("treatments", len(dims["treatments"]), 30),
        ("payment methods", len(dims["payment_methods"]), 4),
    ]
    failures = 0
    for label, actual, expected in checks:
        if actual != expected:
            print(f"{RED}FAIL{RESET}  {label}: expected {expected}, got {actual}")
            failures += 1

    total_cells = 0
    for query in ALL_QUERIES:
        name, header, rows = query(visits, dims)
        if wanted and wanted not in name:
            continue
        problems = compare(name, header, rows)
        cells = len(rows) * len(header)
        total_cells += cells
        if problems:
            failures += 1
            print(f"{RED}FAIL{RESET}  {name}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"{GREEN}pass{RESET}  {name:<32} {len(rows):>4} rows x "
                  f"{len(header)} cols")

    print()
    if failures:
        print(f"{RED}{failures} check(s) failed.{RESET}")
        print("SQL Server and the oracle disagree. One of them has a bug -- that")
        print("is exactly what this test exists to catch.")
        return 1

    if provenance == "oracle":
        print(f"{YELLOW}All checks passed, but this proved very little.{RESET}")
        print(f"{total_cells:,} values were checked against exports that the oracle")
        print("generated itself, so the comparison is circular. Run the pipeline in")
        print("SQL Server and re-export to make this test meaningful:")
        print("    ./scripts/export_from_sqlserver.sh && python3 tests/verify_results.py")
        return 0

    print(f"{GREEN}All checks passed.{RESET} "
          f"{total_cells:,} values agree between SQL Server and the oracle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

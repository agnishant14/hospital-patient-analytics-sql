"""Structural checks on the SQL layer, for the machine that has no SQL Server.

None of this executes T-SQL. It checks the invariants that hold *between* the
SQL files -- the ones that break silently, because each file still looks
perfectly correct on its own:

  1. Every ``:r`` path resolves. sqlcmd resolves includes against its working
     directory rather than the including file, so the whole project writes them
     from the repository root. One file using the other convention works from
     one directory and fails from the next.
  2. The index names ``analysis/09_index_performance.sql`` drops are exactly
     the ones ``schema/06_create_indexes.sql`` creates, and the count it asserts
     on restore matches. Rename an index in step 06 and the benchmark would
     otherwise keep running, silently measuring an unchanged table twice.
  3. Every column the benchmark workloads reference exists on
     ``dbo.PatientVisits`` as ``cleaning/05_data_cleaning.sql`` defines it.
  4. Every query in ``analysis/queries/`` is wired into the driver and has an
     export, and nothing in ``exports/`` is orphaned.
  5. ``run_all.sql``'s step labels are sequential and agree with how many steps
     it actually runs.
  6. The benchmark's phase names match the ones its report joins on, and the
     cursor is opened, closed and deallocated exactly once.
  7. No two city spellings in the exported dimension share a SOUNDEX code, and
     ``dbo.Ref_CityAlias`` and ``tests/oracle.py`` carry the same alias map.
  8. The committed schema diagram declares exactly the foreign keys the DDL
     declares, and the row counts it prints are the ones ``validation/08``
     asserts. The hand-drawn diagram this replaced showed the fact table joined
     to the raw dimensions instead of the cleaned ones.

Usage:
    python3 tests/verify_sql_layout.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"

HARNESS = ROOT / "analysis" / "09_index_performance.sql"
INDEX_DDL = ROOT / "schema" / "06_create_indexes.sql"
FACT_DDL = ROOT / "cleaning" / "05_data_cleaning.sql"
DRIVER = ROOT / "analysis" / "07_business_analysis.sql"
RUN_ALL = ROOT / "run_all.sql"


def strip_comments(sql: str, keep_strings: bool = True) -> str:
    """Drop comments so they cannot fake a match, leaving string literals alone.

    A regex cannot do this. ``s/--[^\\n]*//`` looks correct until the file
    contains ``' (unstable -- rerun)'``, at which point it deletes the rest of
    a real line of code -- here, an ``END`` -- and every downstream count is
    quietly wrong. So walk the text instead, tracking whether we are inside a
    literal. T-SQL escapes a quote by doubling it, which needs no special case:
    the closing quote ends the string and the next one immediately opens
    another, and comment markers stay invisible throughout.

    Pass ``keep_strings=False`` to blank literals out too, for checks that
    tokenise code and would otherwise see ``P1234`` as an identifier.
    """
    out: list[str] = []
    index, length = 0, len(sql)
    while index < length:
        char = sql[index]
        if char == "'":
            end = index + 1
            while end < length and sql[end] != "'":
                end += 1
            out.append(sql[index:end + 1] if keep_strings else "''")
            index = end + 1
        elif sql.startswith("--", index):
            while index < length and sql[index] != "\n":
                index += 1
        elif sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            index = length if end == -1 else end + 2
            out.append(" ")
        else:
            out.append(char)
            index += 1
    return "".join(out)


def soundex(name: str) -> str:
    """Standard American Soundex, which is what SQL Server's SOUNDEX() computes.

    Reimplemented rather than imported so this file has no dependencies. The
    rule it encodes -- consonant classes, doubled letters collapsed, vowels
    dropped after the first letter -- is why 'Chennai' and 'Chennnai' both
    reduce to C500.
    """
    codes = {**dict.fromkeys("BFPV", "1"), **dict.fromkeys("CGJKQSXZ", "2"),
             **dict.fromkeys("DT", "3"), "L": "4",
             **dict.fromkeys("MN", "5"), "R": "6"}
    letters = "".join(c for c in name.upper() if c.isalpha())
    if not letters:
        return ""
    out, previous = letters[0], codes.get(letters[0], "")
    for char in letters[1:]:
        code = codes.get(char, "")
        if code and code != previous:
            out += code
            if len(out) == 4:
                break
        if char not in "HW":
            previous = code
    return (out + "000")[:4]


def includes(path: Path) -> list[str]:
    return re.findall(r"^\s*:r\s+(\S+)", path.read_text(encoding="utf-8"), re.M)


def fact_columns() -> set[str]:
    """Column names from the CREATE TABLE dbo.PatientVisits block."""
    body = re.search(
        r"CREATE TABLE dbo\.PatientVisits\s*\((.*?)\n\)\s*;",
        strip_comments(FACT_DDL.read_text(encoding="utf-8")),
        re.S,
    )
    if not body:
        raise SystemExit("could not find CREATE TABLE dbo.PatientVisits")
    columns = set()
    for line in body.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith(("CONSTRAINT", ")")):
            continue
        name = line.split()[0]
        if name.isidentifier():
            columns.add(name)
    return columns


def main() -> int:
    failures: list[str] = []

    # --- 1. every :r resolves from the repository root ----------------------
    sql_files = sorted(ROOT.glob("**/*.sql"))
    for path in sql_files:
        if ".git" in path.parts:
            continue
        for target in includes(path):
            resolved = (ROOT / target.lstrip("./")).resolve()
            if not resolved.is_file():
                failures.append(
                    f"{path.relative_to(ROOT)} includes '{target}', which does not "
                    f"exist relative to the repository root"
                )

    # --- 2. the harness drops exactly what step 06 creates ------------------
    created = set(re.findall(
        r"CREATE\s+INDEX\s+(\w+)", strip_comments(INDEX_DDL.read_text(encoding="utf-8"))
    ))
    harness_sql = strip_comments(HARNESS.read_text(encoding="utf-8"))
    dropped = set(re.findall(r"DROP INDEX IF EXISTS\s+(\w+)", harness_sql))

    for name in sorted(created - dropped):
        failures.append(f"schema/06 creates {name}, but the benchmark never drops it "
                        f"-- pass 2 would measure it as if it were absent")
    for name in sorted(dropped - created):
        failures.append(f"the benchmark drops {name}, which schema/06 does not create")

    guard = re.search(r"index_id > 1\) <> (\d+)", harness_sql)
    if not guard:
        failures.append("the benchmark lost its post-restore index count assertion")
    elif int(guard.group(1)) != len(created):
        failures.append(f"the benchmark asserts {guard.group(1)} indexes after restore, "
                        f"schema/06 creates {len(created)}")

    if created and not any(name in harness_sql for name in ("IF NOT EXISTS", "THROW")):
        failures.append("the benchmark no longer checks the indexes exist before pass 1")

    # --- 3. workload columns exist on the fact table ------------------------
    columns = fact_columns()
    workloads = re.findall(r"N'\s*(.*?)'\)[,;]", harness_sql, re.S)
    if len(workloads) != 8:
        failures.append(f"expected 8 benchmark workloads, parsed {len(workloads)}")

    keywords = {
        "SELECT", "FROM", "WHERE", "GROUP", "BY", "HAVING", "AS", "AND", "OR", "ON",
        "CASE", "WHEN", "THEN", "ELSE", "END", "SUM", "AVG", "COUNT", "COUNT_BIG",
        "CAST", "DECIMAL", "YEAR", "MONTH", "DISTINCT", "dbo", "PatientVisits", "INT",
    }
    for workload in workloads:
        # Recover the real query text before tokenising. These queries live
        # inside a string literal, so their own quotes are doubled: blanking
        # ''P1234'' naively removes two empty strings and leaves P1234 looking
        # exactly like a column reference. Un-double, then blank.
        code = re.sub(r"'[^']*'", " ", workload.replace("''", "'"))
        for token in set(re.findall(r"\b([A-Za-z_]\w*)\b", code)):
            if token in keywords or token.islower() or len(token) < 3:
                continue
            if token not in columns:
                failures.append(f"benchmark workload references '{token}', which is "
                                f"not a column of dbo.PatientVisits")

    # --- 4. queries, driver and exports line up -----------------------------
    query_files = sorted((ROOT / "analysis" / "queries").glob("q*.sql"))
    driven = {Path(target).stem for target in includes(DRIVER)}
    for path in query_files:
        if path.stem not in driven:
            failures.append(f"{path.name} is not included by 07_business_analysis.sql")
        if not (ROOT / "exports" / f"{path.stem}.csv").is_file():
            failures.append(f"{path.name} has no matching exports/{path.stem}.csv")
    for name in sorted(driven - {path.stem for path in query_files}):
        failures.append(f"07_business_analysis.sql includes {name}.sql, which is gone")

    model_files = sorted((ROOT / "analysis" / "model").glob("*.sql"))
    for path in model_files:
        if not (ROOT / "exports" / f"{path.stem}.csv").is_file():
            failures.append(f"analysis/model/{path.name} has no matching export")
    expected_exports = {p.stem for p in query_files} | {p.stem for p in model_files}
    for csv_path in sorted((ROOT / "exports").glob("*.csv")):
        if csv_path.stem not in expected_exports:
            failures.append(f"exports/{csv_path.name} has no SQL file that produces it")

    # --- 5. run_all's step labels are honest --------------------------------
    run_all = RUN_ALL.read_text(encoding="utf-8")
    labels = re.findall(r"PRINT '(\d+)/(\d+) -", run_all)
    steps = len(includes(RUN_ALL))
    if len(labels) != steps:
        failures.append(f"run_all.sql prints {len(labels)} step labels but runs {steps} files")
    for position, (index, total) in enumerate(labels, start=1):
        if int(index) != position:
            failures.append(f"run_all.sql step label {index}/{total} is out of sequence "
                            f"at position {position}")
        if int(total) != len(labels):
            failures.append(f"run_all.sql step {index} says of {total}, "
                            f"but there are {len(labels)} steps")

    # --- 6. the benchmark's two phases agree with the report's two phases ----
    #
    # Unbalanced BEGIN/END is not checked here. SQL Server reports it on the
    # first run, in a line-numbered error, better than a keyword counter can.
    # The failure worth catching is the one that produces no error at all: the
    # report pairs the phases with INNER JOINs, so a phase renamed in one place
    # and not the other yields zero rows and a report that looks merely empty.
    measured = set(re.findall(r"@Phase\s*=\s*'(\w+)'", harness_sql))
    reported = set(re.findall(r"\.Phase\s*=\s*'(\w+)'", harness_sql))
    if measured != reported:
        failures.append(
            f"the benchmark measures phases {sorted(measured)} but the report joins on "
            f"{sorted(reported)}; the INNER JOINs would return no rows"
        )
    width = re.search(r"@Phase\s+VARCHAR\((\d+)\)", harness_sql)
    if width and measured and int(width.group(1)) < max(len(p) for p in measured):
        failures.append(f"@Phase is VARCHAR({width.group(1)}) but the longest phase "
                        f"name is {max(len(p) for p in measured)} characters; it would "
                        f"be truncated and the join would miss")

    for verb in ("DECLARE workloads CURSOR", "OPEN workloads", "CLOSE workloads",
                 "DEALLOCATE workloads"):
        if harness_sql.count(verb) != 1:
            failures.append(f"'{verb}' appears {harness_sql.count(verb)} times in the "
                            f"benchmark; a cursor needs exactly one of each")

    # --- 7. the SOUNDEX rule in validation/08, evaluated against the data ---
    #
    # validation/08 fails the build if two city spellings share a SOUNDEX code.
    # Nobody here can run it, so run the same rule in Python against the export
    # the load produces. If this passes and the SQL still fails, the two have
    # drifted; if this fails, a variant spelling reached the dimension without
    # a row in dbo.Ref_CityAlias.
    quality = strip_comments((ROOT / "validation" / "08_data_quality_checks.sql")
                             .read_text(encoding="utf-8"))
    if "SOUNDEX" not in quality:
        failures.append("validation/08 no longer checks for sound-alike city spellings")
    else:
        with (ROOT / "exports" / "dim_patient.csv").open(encoding="utf-8") as handle:
            spellings = {row["City"] for row in csv.DictReader(handle)}
        codes: dict[str, list[str]] = {}
        for city in sorted(spellings):
            codes.setdefault(soundex(city), []).append(city)
        for code, members in sorted(codes.items()):
            if len(members) > 1:
                failures.append(
                    f"city spellings {' / '.join(members)} share SOUNDEX {code}; "
                    f"validation/08 would fail the build. Map the variant in "
                    f"dbo.Ref_CityAlias and mirror it in tests/oracle.py"
                )

        # The alias map only helps if both implementations carry it.
        aliases = dict(re.findall(
            r"\('([^']+)',\s*'([^']+)'\)",
            re.search(r"INSERT INTO dbo\.Ref_CityAlias[^;]*;",
                      strip_comments((ROOT / "cleaning" / "05_data_cleaning.sql")
                                     .read_text(encoding="utf-8")), re.S).group(0)))
        oracle_src = (ROOT / "tests" / "oracle.py").read_text(encoding="utf-8")
        mirrored = dict(re.findall(
            r'"([^"]+)":\s*"([^"]+)"',
            re.search(r"CITY_ALIASES = \{([^}]*)\}", oracle_src).group(1)))
        if aliases != mirrored:
            failures.append(f"dbo.Ref_CityAlias holds {aliases} but tests/oracle.py "
                            f"mirrors {mirrored}; they must match")
        for variant in aliases:
            if variant in spellings:
                failures.append(f"'{variant}' is mapped in dbo.Ref_CityAlias but still "
                                f"appears in exports/dim_patient.csv")

    # --- 8. the schema diagram still describes this schema ------------------
    #
    # diagrams/database_diagram.png used to be drawn by hand, and it was wrong:
    # it showed dbo.PatientVisits joined to the raw dimensions rather than the
    # _Clean ones, and left the four staging tables out entirely. A reader would
    # have concluded the cleaning step did not exist. scripts/generate_erd.py now
    # derives both diagrams from the DDL, which fixes the drawing but not the
    # staleness: the committed files are only correct until the next schema
    # change. So parse the foreign keys again here, independently of that script,
    # and require the committed mermaid to agree.
    ddl = "".join(
        strip_comments((ROOT / name).read_text(encoding="utf-8"))
        for name in ("schema/01_create_tables.sql", "cleaning/05_data_cleaning.sql")
    )
    expected_edges: set[str] = set()
    for block in re.finditer(r"CREATE TABLE dbo\.(\w+)\s*\((.*?)\n\)\s*;", ddl, re.S):
        table, body = block.group(1), block.group(2)
        for column, referenced in re.findall(
            r"FOREIGN KEY\s*\(\s*(\w+)\s*\)\s*REFERENCES dbo\.(\w+)", body
        ):
            expected_edges.add(f"{referenced} ||--o{{ {table} : {column}")

    mermaid_path = ROOT / "diagrams" / "schema.mmd"
    if not mermaid_path.is_file():
        failures.append("diagrams/schema.mmd is missing; run scripts/generate_erd.py")
    else:
        committed = {line.strip() for line in
                     mermaid_path.read_text(encoding="utf-8").splitlines()
                     if "||--o{" in line}
        for edge in sorted(expected_edges - committed):
            failures.append(f"the DDL declares '{edge}' but diagrams/schema.mmd does "
                            f"not; re-run scripts/generate_erd.py")
        for edge in sorted(committed - expected_edges):
            failures.append(f"diagrams/schema.mmd draws '{edge}', which the DDL no "
                            f"longer declares; re-run scripts/generate_erd.py")

    # The README embeds a deliberately partial diagram -- the six joins the
    # published queries make -- because all 14 tables inline would be unreadable.
    # Partial is fine; wrong is not, and "wrong" is exactly what the old
    # hand-drawn PNG was. So every edge it draws must be one the DDL declares.
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for line in readme.splitlines():
        if "||--o{" in line and line.strip() not in expected_edges:
            failures.append(f"README.md draws '{line.strip()}', which the DDL does "
                            f"not declare")

    # The diagram prints row counts, which it cannot verify against a database.
    # validation/08 is the thing that asserts them, so require the two to agree
    # rather than letting the picture quote a number nothing enforces.
    asserted = {table: int(count) for table, count in
                re.findall(r"FROM dbo\.(\w+)\)\s*<>\s*(\d+)", quality)}
    erd_source = (ROOT / "scripts" / "generate_erd.py").read_text(encoding="utf-8")
    labelled = {table: int(count.replace("_", "")) for table, count in re.findall(
        r'"(\w+)":\s*([\d_]+),',
        re.search(r"ROW_COUNTS = \{([^}]*)\}", erd_source).group(1))}
    for table, count in sorted(labelled.items()):
        if table not in asserted:
            failures.append(f"the schema diagram labels {table} with {count:,} rows, "
                            f"but validation/08 does not assert that count")
        elif asserted[table] != count:
            failures.append(f"the schema diagram says {table} has {count:,} rows, "
                            f"validation/08 asserts {asserted[table]:,}")

    if failures:
        print(f"{RED}{len(failures)} problem(s) in the SQL layer.{RESET}")
        for failure in failures[:20]:
            print(f"  {failure}")
        return 1

    print(f"{GREEN}SQL layer is internally consistent.{RESET}")
    print(f"  {sum(len(includes(p)) for p in sql_files if '.git' not in p.parts)} "
          f":r includes resolve from the repository root")
    print(f"  {len(created)} indexes: created, dropped and restored by the same names")
    print(f"  {len(query_files)} queries wired into the driver, each with an export")
    print(f"  {len(expected_edges)} foreign keys drawn in diagrams/schema.mmd "
          f"match the DDL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

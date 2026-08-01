
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "exports"
POWERBI = ROOT / "powerbi"
DASHBOARD = ROOT / "docs" / "index.html"

GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"

TABLES = {
    "fact_patientvisits": "Fact Visits",
    "dim_patient": "Patient",
    "dim_doctor": "Doctor",
    "dim_department": "Department",
    "dim_diagnosis": "Diagnosis",
    "dim_treatment": "Treatment",
    "dim_paymentmethod": "Payment Method",
}

DATE_COLUMNS = {
    "Date", "Year", "Month Number", "Month Name",
    "Month Start", "Year Month", "Day Name", "Day Type",
}
CALCULATED = {"Fact Visits": {"Age At Visit", "Age Band", "Age Band Order"}}

def dec(value, places: int = 2) -> Decimal:
    return Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)

def read_csv(name: str) -> list[dict]:
    with (EXPORTS / f"{name}.csv").open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))

def money(value: Decimal) -> str:
    quantized = dec(value)
    whole = quantized.to_integral_value()
    if quantized == whole:
        return f"₹{int(whole):,}"
    return f"₹{quantized:,}"

def checklist_figures() -> list[tuple[str, str]]:
    facts = read_csv("fact_patientvisits")
    patients = {row["PatientID"]: row for row in read_csv("dim_patient")}
    departments = {row["DepartmentID"]: row for row in read_csv("dim_department")}
    total = len(facts)

    revenue = sum(Decimal(row["BillAmount"]) for row in facts)
    insurance = sum(Decimal(row["InsuranceAmount"]) for row in facts)
    wait = sum(Decimal(row["WaitTimeMinutes"]) for row in facts)
    satisfaction = sum(Decimal(row["SatisfactionScore"]) for row in facts)

    visits_per_patient = Counter(row["PatientID"] for row in facts)
    distinct_patients = len(visits_per_patient)
    repeat = sum(1 for count in visits_per_patient.values() if count > 1)

    within30 = sum(1 for row in facts if int(row["WaitTimeMinutes"]) <= 30)
    satisfied = sum(1 for row in facts if int(row["SatisfactionScore"]) >= 4)
    weekend = sum(
        1 for row in facts if date.fromisoformat(row["VisitDate"]).isoweekday() >= 6
    )

    def pct(part: int, whole: int = total) -> str:
        return f"{dec(Decimal(part) * 100 / whole, 1)}%"

    figures = [
        ("Total Visits", f"| `Total Visits` | {total:,} |"),
        ("Distinct Patients", f"| `Distinct Patients` | {distinct_patients:,} |"),
        ("Total Revenue", f"| `Total Revenue` | {money(revenue)} |"),
        ("Average Bill", f"| `Average Bill` | {money(revenue / total)} |"),
        ("Average Wait Minutes", f"| `Average Wait Minutes` | {dec(wait / total)} |"),
        ("Average Satisfaction", f"| `Average Satisfaction` | {dec(satisfaction / total)} |"),
        ("Insurance Covered", f"| `Insurance Covered` | {money(insurance)} |"),
        ("Seen Within 30 Min", f"| `Seen Within 30 Min` | {within30:,} → {pct(within30)} |"),
        ("Satisfied Visits", f"| `Satisfied Visits` | {satisfied:,} → {pct(satisfied)} |"),
        ("Repeat Patients",
         f"| `Repeat Patients` | {repeat:,} → {pct(repeat, distinct_patients)}"),
        ("Visits per Patient",
         f"| `Visits per Patient` | {dec(Decimal(total) / distinct_patients)} |"),
        ("Active Doctors",
         f"| `Active Doctors` | {len({row['DoctorID'] for row in facts}):,} |"),
        ("Weekend Visits", f"| `Weekend Visits` | {weekend:,} → {pct(weekend)}"),
    ]

    growth = read_csv("q02_annual_growth")
    by_year = {row["VisitYear"]: row for row in growth}
    figures.append(("2021 growth", f"| {by_year['2021']['VisitGrowthPercent']}% |"))
    figures.append((
        "growth series",
        ", ".join(row["VisitGrowthPercent"] for row in growth if row["VisitGrowthPercent"])
        + " percent",
    ))

    leap = sum(1 for row in facts if row["VisitDate"] == "2020-02-29")
    y2020 = sum(1 for row in facts if row["VisitDate"][:4] == "2020")
    y2021 = sum(1 for row in facts if row["VisitDate"][:4] == "2021")
    wrong = dec(Decimal(y2021 - (y2020 - leap)) * 100 / (y2020 - leap))
    figures.append(("DATEADD trap", f"**{wrong}%**"))
    figures.append(("leap day count", f"the {leap} visits dated 2020-02-29"))

    bands: Counter[str] = Counter()
    for row in facts:
        visit = date.fromisoformat(row["VisitDate"])
        born = date.fromisoformat(patients[row["PatientID"]]["DOB"])
        years = visit.year - born.year - ((visit.month, visit.day) < (born.month, born.day))
        bands["0-17" if years < 18 else "18-35" if years <= 35
              else "36-55" if years <= 55 else "56+"] += 1
    figures.append((
        "age bands",
        " / ".join(f"{bands[band]:,}" for band in ("0-17", "18-35", "36-55", "56+")),
    ))

    emergency = [
        row for row in facts
        if departments[row["DepartmentID"]]["DepartmentName"] == "Emergency Medicine"
    ]
    emergency_wait = dec(
        sum(Decimal(row["WaitTimeMinutes"]) for row in emergency) / len(emergency)
    )
    figures.append((
        "Emergency Medicine",
        f"{emergency_wait} over {len(emergency):,} visits",
    ))

    leaderboard = read_csv("q10_top_doctors")
    figures.append(("leaderboard length", f"**{len(leaderboard)} rows**"))

    cities = Counter(row["City"] for row in patients.values())
    figures.append(("Chennai typo", f"`Chennai` ({cities['Chennai']} patients)"))
    figures.append(("department count", f"the {len(departments)} departments"))
    return figures

def dax_references(text: str) -> tuple[set[tuple[str, str]], set[str], set[str]]:
    qualified = set(re.findall(r"'([^']+)'\[([^\]]+)\]", text))

    body = re.sub(r"//[^\n]*", "", text)
    defined = {
        name.strip()
        for name in re.findall(r"^([A-Za-z][^=\n]*?) =$", body, re.M)
        if not name.startswith("VAR ")
    }
    bare = {
        name for name in re.findall(r"(?<![\w'])\[([^\]]+)\]", body)
    }
    return qualified, bare, defined

def main() -> int:
    failures: list[str] = []

    readme = (POWERBI / "README.md").read_text(encoding="utf-8")
    figures = checklist_figures()
    for label, needle in figures:
        if needle not in readme:
            failures.append(f"README is stale for {label}: exports say {needle!r}")

    dax = (POWERBI / "measures.dax").read_text(encoding="utf-8")
    qualified, bare, defined = dax_references(dax)

    known: dict[str, set[str]] = {"Date": set(DATE_COLUMNS)}
    for stem, table in TABLES.items():
        with (EXPORTS / f"{stem}.csv").open(newline="", encoding="utf-8-sig") as handle:
            known[table] = set(next(csv.reader(handle)))
        known[table] |= CALCULATED.get(table, set())

    for table, column in sorted(qualified):
        if table not in known:
            failures.append(f"measures.dax references unknown table '{table}'")
        elif column not in known[table]:
            failures.append(f"measures.dax references '{table}'[{column}], "
                            f"which is not a column of that table")

    for name in sorted(bare - defined - {"Date"}):
        failures.append(f"measures.dax calls [{name}], which nothing defines")

    measures = defined - {"Date", "Age At Visit", "Age Band", "Age Band Order"}
    claimed = re.search(r"and (\d+) measures", readme)
    if claimed and int(claimed.group(1)) != len(measures):
        failures.append(f"README claims {claimed.group(1)} measures, "
                        f"measures.dax defines {len(measures)}")

    if DASHBOARD.exists():
        page = DASHBOARD.read_text(encoding="utf-8")
        css_ramp = [
            re.search(rf"--s{tier}:\s*(#[0-9A-Fa-f]{{6}})", page).group(1).upper()
            for tier in (5, 4, 3, 2, 1)
        ]
        block = re.search(r"Wait Band Colour =.*?\n\n", dax, re.S).group(0)
        dax_ramp = [colour.upper() for colour in
                    re.findall(r'"(#[0-9A-Fa-f]{6})"', block)][1:]
        if css_ramp != dax_ramp:
            failures.append(f"colour ramps differ: dashboard {css_ramp}, DAX {dax_ramp}")

        css_cuts = re.search(r"THRESHOLDS = \[([\d,\s]+)\]", page).group(1)
        css_cuts = [int(n) for n in css_cuts.split(",")]
        dax_cuts = [int(n) for n in re.findall(r"Wait <= (\d+)", block)]
        if css_cuts != dax_cuts:
            failures.append(f"wait thresholds differ: dashboard {css_cuts}, DAX {dax_cuts}")

    try:
        theme = json.loads((POWERBI / "theme.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        failures.append(f"theme.json is not valid JSON: {error}")
        theme = {}
    for key in ("name", "dataColors", "textClasses", "visualStyles"):
        if key not in theme:
            failures.append(f"theme.json is missing the '{key}' key")

    if failures:
        print(f"{RED}{len(failures)} problem(s) in the Power BI kit.{RESET}")
        for failure in failures[:20]:
            print(f"  {failure}")
        return 1

    print(f"{GREEN}Power BI kit agrees with exports/.{RESET}")
    print(f"  {len(figures)} published figures recomputed and found in the checklist")
    print(f"  {len(measures)} measures, {len(qualified)} column references, all resolving")
    print(f"  wait thresholds and colour ramp match docs/index.html")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

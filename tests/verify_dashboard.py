
from __future__ import annotations

import base64
import csv
import json
import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "exports"
DATA_JS = ROOT / "docs" / "data.js"

GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"

def dec(value, places: int = 2) -> Decimal:
    return Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)

def read_csv(name: str) -> list[dict]:
    with (EXPORTS / f"{name}.csv").open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))

def load_payload() -> tuple[dict, dict]:
    text = DATA_JS.read_text(encoding="utf-8")
    meta = json.loads(re.search(r"window\.HOSPITAL_META = (\{.*?\});\n", text, re.S).group(1))
    encoded = re.search(r'window\.HOSPITAL_FACTS = "([A-Za-z0-9+/=]+)";', text).group(1)
    raw = base64.b64decode(encoded)

    rows = meta["rows"]
    expected = rows * 7 + rows * 4
    if len(raw) != expected:
        raise SystemExit(f"payload is {len(raw):,} bytes, expected {expected:,}")

    def u8(index: int) -> memoryview:
        return memoryview(raw)[index * rows:(index + 1) * rows]

    def u16(byte_offset: int) -> list[int]:
        chunk = raw[byte_offset:byte_offset + rows * 2]
        return [chunk[i] | (chunk[i + 1] << 8) for i in range(0, len(chunk), 2)]

    columns = {
        "monthweek": u8(0),
        "dept": u8(1),
        "pay": u8(2),
        "age": u8(3),
        "doctor": u8(4),
        "sat": u8(5),
        "wait": u8(6),
        "bill": [value + meta["billOffset"] for value in u16(rows * 7)],
        "patient": u16(rows * 7 + rows * 2),
    }
    return meta, columns

def main() -> int:
    if not DATA_JS.exists():
        print(f"{RED}docs/data.js not found.{RESET} Run scripts/build_dashboard_data.py")
        return 1

    meta, col = load_payload()
    rows = meta["rows"]
    departments = [d["name"] for d in meta["departments"]]
    failures: list[str] = []

    def check(label: str, actual, expected) -> None:
        if str(actual) != str(expected):
            failures.append(f"{label}: dashboard {actual}, warehouse {expected}")

    kpi = read_csv("q01_operating_kpis")[0]
    check("total visits", rows, int(kpi["TotalVisits"]))
    check("distinct patients", len(set(col["patient"])), int(kpi["DistinctPatients"]))
    check("total revenue", dec(sum(col["bill"])), dec(Decimal(kpi["TotalBilledRevenueINR"])))
    check("average bill", dec(Decimal(sum(col["bill"])) / rows), dec(Decimal(kpi["AverageBillINR"])))
    check("average wait", dec(Decimal(sum(col["wait"])) / rows), dec(Decimal(kpi["AverageWaitMinutes"])))
    check("average satisfaction", dec(Decimal(sum(col["sat"])) / rows), dec(Decimal(kpi["AverageSatisfaction"])))

    by_dept: dict[int, list[int]] = defaultdict(list)
    for row in range(rows):
        by_dept[col["dept"][row]].append(row)
    for record in read_csv("q07_department_service_risk"):
        position = departments.index(record["DepartmentName"])
        members = by_dept[position]
        check(f"{record['DepartmentName']} visits", len(members), int(record["TotalVisits"]))
        check(
            f"{record['DepartmentName']} avg wait",
            dec(Decimal(sum(col["wait"][r] for r in members)) / len(members)),
            dec(Decimal(record["AverageWaitMinutes"])),
        )
        check(
            f"{record['DepartmentName']} avg satisfaction",
            dec(Decimal(sum(col["sat"][r] for r in members)) / len(members)),
            dec(Decimal(record["AverageSatisfaction"])),
        )

    for record in read_csv("q04_payment_mix"):
        position = meta["payments"].index(record["PaymentMethod"])
        members = [r for r in range(rows) if col["pay"][r] == position]
        check(f"{record['PaymentMethod']} visits", len(members), int(record["TotalVisits"]))
        check(
            f"{record['PaymentMethod']} revenue",
            dec(sum(col["bill"][r] for r in members)),
            dec(Decimal(record["TotalRevenueINR"])),
        )

    for record in read_csv("q05_age_band"):
        position = meta["ageBands"].index(record["AgeGroup"])
        members = [r for r in range(rows) if col["age"][r] == position]
        check(f"age {record['AgeGroup']} visits", len(members), int(record["TotalVisits"]))
        check(
            f"age {record['AgeGroup']} avg bill",
            dec(Decimal(sum(col["bill"][r] for r in members)) / len(members)),
            dec(Decimal(record["AverageBillINR"])),
        )

    for record in read_csv("q08_weekday_weekend"):
        weekend = record["DayType"] == "Weekend"
        members = [r for r in range(rows) if bool(col["monthweek"][r] & 0x80) == weekend]
        check(f"{record['DayType']} visits", len(members), int(record["TotalVisits"]))
        check(
            f"{record['DayType']} revenue",
            dec(sum(col["bill"][r] for r in members)),
            dec(Decimal(record["TotalRevenueINR"])),
        )

    repeat = read_csv("q11_repeat_patients")[0]
    counts: dict[int, int] = defaultdict(int)
    for value in col["patient"]:
        counts[value] += 1
    check("repeat patients", sum(1 for n in counts.values() if n > 1), int(repeat["RepeatPatients"]))

    year_visits: dict[int, int] = defaultdict(int)
    year_revenue: dict[int, int] = defaultdict(int)
    for row in range(rows):
        year = meta["baseYear"] + ((col["monthweek"][row] & 0x7F) // 12)
        year_visits[year] += 1
        year_revenue[year] += col["bill"][row]
    for record in read_csv("q02_annual_growth"):
        year = int(record["VisitYear"])
        check(f"{year} visits", year_visits[year], int(record["TotalVisits"]))
        check(f"{year} revenue", dec(year_revenue[year]), dec(Decimal(record["TotalRevenueINR"])))

    if failures:
        print(f"{RED}{len(failures)} value(s) differ between the dashboard payload "
              f"and exports/.{RESET}")
        for failure in failures[:20]:
            print(f"  {failure}")
        print("\nRebuild the payload: python3 scripts/build_dashboard_data.py")
        return 1

    print(f"{GREEN}Dashboard payload agrees with exports/.{RESET}")
    print(f"  {rows:,} rows unpacked from {DATA_JS.stat().st_size / 1024:,.0f} KB")
    print(f"  KPIs, all {len(departments)} departments, payment mix, age bands,")
    print(f"  weekday/weekend, repeat rate and all 6 year buckets reconcile.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

"""Pack exports/ into the single binary payload the web dashboard reads.

The dashboard re-aggregates all 50,000 fact rows in the browser on every filter
change, so it needs the fact table itself, not pre-baked summaries. Shipping it
as CSV would cost ~4.5 MB. Packed into typed-array columns it is 550 KB, or
733 KB once base64-encoded into a .js file.

Column layout of the payload (row order is VisitID order):

    offset        bytes    column
         0       50,000    monthweek  month index 0..71, weekend in bit 7
    50,000       50,000    dept       0-based index into departments[]
   100,000       50,000    pay        0-based index into payments[]
   150,000       50,000    age        0-based index into ageBands[]
   200,000       50,000    doctor     0-based index into doctors[]
   250,000       50,000    sat        satisfaction score, 1..5
   300,000       50,000    wait       wait minutes, fits a byte
   350,000      100,000    bill       uint16 LE, BillAmount - BILL_OFFSET
   450,000      100,000    patient    uint16 LE, index into patients[]
                 -------
                 550,000

Usage:
    python3 scripts/build_dashboard_data.py
"""

from __future__ import annotations

import base64
import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "exports"
DOCS = ROOT / "docs"

ROWS = 50_000
BASE_YEAR = 2020
MONTHS = 72
BILL_OFFSET = 3_000
AGE_BANDS = ["0-17", "18-35", "36-55", "56+"]

def read(name: str) -> list[dict]:
    with (EXPORTS / f"{name}.csv").open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))

def index_of(values: list[str]) -> dict[str, int]:
    return {value: position for position, value in enumerate(values)}

def main() -> None:
    if not EXPORTS.exists():
        raise SystemExit(
            "exports/ not found. Run scripts/export_from_sqlserver.sh (or "
            "scripts/build_exports.py) first."
        )

    departments = read("dim_department")
    payments = read("dim_paymentmethod")
    doctors = read("dim_doctor")
    patients = read("dim_patient")
    facts = read("fact_patientvisits")

    if len(facts) != ROWS:
        raise SystemExit(f"expected {ROWS:,} fact rows, found {len(facts):,}")

    dept_ix = index_of([d["DepartmentID"] for d in departments])
    pay_ix = index_of([p["PaymentMethodID"] for p in payments])
    doc_ix = index_of([d["DoctorID"] for d in doctors])
    pat_ix = index_of([p["PatientID"] for p in patients])
    age_ix = index_of(AGE_BANDS)
    dob = {p["PatientID"]: date.fromisoformat(p["DOB"]) for p in patients}

    if len(doctors) > 256 or len(departments) > 256:
        raise SystemExit("a dimension outgrew its byte column; widen the payload")

    monthweek = bytearray(ROWS)
    dept = bytearray(ROWS)
    pay = bytearray(ROWS)
    age = bytearray(ROWS)
    doctor = bytearray(ROWS)
    sat = bytearray(ROWS)
    wait = bytearray(ROWS)
    bill = bytearray(ROWS * 2)
    patient = bytearray(ROWS * 2)

    for row_no, fact in enumerate(facts):
        visit_date = date.fromisoformat(fact["VisitDate"])
        month = (visit_date.year - BASE_YEAR) * 12 + visit_date.month - 1
        if not 0 <= month < MONTHS:
            raise SystemExit(f"{fact['VisitID']}: date {visit_date} is outside 2020-2025")
        weekend = visit_date.weekday() >= 5
        monthweek[row_no] = month | (0x80 if weekend else 0)

        dept[row_no] = dept_ix[fact["DepartmentID"]]
        pay[row_no] = pay_ix[fact["PaymentMethodID"]]
        doctor[row_no] = doc_ix[fact["DoctorID"]]
        sat[row_no] = int(fact["SatisfactionScore"])

        minutes = int(fact["WaitTimeMinutes"])
        if not 0 <= minutes <= 255:
            raise SystemExit(f"{fact['VisitID']}: wait {minutes} does not fit a byte")
        wait[row_no] = minutes

        born = dob[fact["PatientID"]]
        years = visit_date.year - born.year - (
            (visit_date.month, visit_date.day) < (born.month, born.day)
        )
        band = (
            "0-17" if years < 18
            else "18-35" if years <= 35
            else "36-55" if years <= 55
            else "56+"
        )
        age[row_no] = age_ix[band]

        amount = int(round(float(fact["BillAmount"]))) - BILL_OFFSET
        if not 0 <= amount <= 0xFFFF:
            raise SystemExit(f"{fact['VisitID']}: bill does not fit a uint16")
        bill[row_no * 2] = amount & 0xFF
        bill[row_no * 2 + 1] = amount >> 8

        person = pat_ix[fact["PatientID"]]
        patient[row_no * 2] = person & 0xFF
        patient[row_no * 2 + 1] = person >> 8

    payload = (
        bytes(monthweek) + bytes(dept) + bytes(pay) + bytes(age) + bytes(doctor)
        + bytes(sat) + bytes(wait) + bytes(bill) + bytes(patient)
    )
    encoded = base64.b64encode(payload).decode("ascii")

    meta = {
        "rows": ROWS,
        "baseYear": BASE_YEAR,
        "months": MONTHS,
        "billOffset": BILL_OFFSET,
        "ageBands": AGE_BANDS,
        "departments": [
            {"name": d["DepartmentName"], "category": d["DepartmentCategory"]}
            for d in departments
        ],
        "payments": [p["PaymentMethod"] for p in payments],
        "doctors": [d["DoctorName"] for d in doctors],
        "patients": len(patients),
        "provenance": (EXPORTS / "PROVENANCE.txt").read_text(encoding="utf-8")
        .splitlines()[0].removeprefix("source:").strip()
        if (EXPORTS / "PROVENANCE.txt").exists() else "unknown",
    }

    DOCS.mkdir(exist_ok=True)
    out = DOCS / "data.js"
    with out.open("w", encoding="utf-8") as handle:
        handle.write("window.HOSPITAL_META = ")
        json.dump(meta, handle, separators=(",", ":"))
        handle.write(";\n")
        handle.write('window.HOSPITAL_FACTS = "')
        handle.write(encoded)
        handle.write('";\n')

    print(f"Wrote {out.relative_to(ROOT)}")
    print(f"  {len(payload):,} bytes packed -> {out.stat().st_size / 1024:,.0f} KB on disk")
    print(f"  provenance: {meta['provenance']}")

if __name__ == "__main__":
    main()

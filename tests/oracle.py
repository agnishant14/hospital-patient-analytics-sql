
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

YEAR_BOUNDARIES = (
    (5_000, 2020),
    (11_000, 2021),
    (18_500, 2022),
    (27_000, 2023),
    (37_500, 2024),
    (50_000, 2025),
)
TOTAL_VISITS = 50_000
EPOCH = date(1900, 1, 1)

def _to_decimal(value) -> Decimal:
    if isinstance(value, Fraction):
        with localcontext() as context:
            context.prec = 60
            return Decimal(value.numerator) / Decimal(value.denominator)
    return Decimal(value)

def dec(value, places: int = 2) -> Decimal:
    quantum = Decimal(1).scaleb(-places)
    return _to_decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)

def pct(numerator, denominator, places: int = 2) -> Decimal | str:
    if not denominator:
        return ""
    return dec(Decimal(100) * Decimal(numerator) / Decimal(denominator), places)

def average(total, count, places: int = 2) -> Decimal | str:
    if not count:
        return ""
    return dec(Decimal(total) / Decimal(count), places)

def _sql_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8", errors="replace")

def _field(raw: str) -> str | None:
    raw = raw.strip()
    if raw == "NULL":
        return None
    return raw[1:-1] if raw.startswith("'") else raw

def _parse_inserts(text: str, table: str, column_count: int) -> list[list[str | None]]:
    pattern = re.compile(
        r"INSERT INTO dbo\." + re.escape(table) + r"\s*\([^)]*\)\s*VALUES\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )

    splitter = re.compile(r",(?=(?:[^']*'[^']*')*[^']*$)")
    rows: list[list[str | None]] = []
    for match in pattern.finditer(text):
        fields = [_field(part) for part in splitter.split(match.group(1))]
        if len(fields) != column_count:
            raise ValueError(f"{table}: expected {column_count} columns, got {len(fields)}")
        rows.append(fields)
    return rows

def title_case(value: str) -> str:
    trimmed = value.strip()
    return trimmed[:1].upper() + trimmed[1:].lower()

CITY_ALIASES = {"Chennnai": "Chennai"}

def load_dimensions() -> dict:
    people = _sql_text("data/02_insert_patients_doctors.sql")
    reference = _sql_text("data/03_insert_reference_dimensions.sql")

    patients: dict[str, dict] = {}
    raw_patient_count = 0
    for patient_id, first, last, gender, dob, location in _parse_inserts(
        people, "Dim_Patient", 6
    ):
        raw_patient_count += 1
        if not (first or "").strip() or not (last or "").strip():
            continue
        if (gender or "").strip().upper() not in {"M", "MALE", "F", "FEMALE"}:
            continue
        if dob is None or location is None or location.count(",") != 2:
            continue
        city, state, country = (part.strip() for part in location.split(","))
        patients[patient_id] = {
            "PatientID": patient_id,
            "FullName": f"{title_case(first)} {title_case(last)}",
            "Gender": "Male" if gender.strip().upper() in {"M", "MALE"} else "Female",
            "DOB": date.fromisoformat(dob),
            "City": CITY_ALIASES.get(city, city),
            "State": state,
            "Country": country,
        }

    doctors = {
        doctor_id: {
            "DoctorID": doctor_id,
            "DoctorName": f"{first} {last}",
            "Gender": gender,
            "ExperienceYears": int(experience),
        }
        for doctor_id, first, last, gender, experience in _parse_inserts(
            people, "Dim_Doctor", 5
        )
    }

    departments: dict[str, dict] = {}
    raw_department_count = 0
    for dept_id, _name, category, specialization, _hod in _parse_inserts(
        reference, "Dim_Department", 5
    ):
        raw_department_count += 1
        if not (specialization or "").strip() or not (category or "").strip():
            continue
        departments[dept_id] = {
            "DepartmentID": dept_id,
            "DepartmentName": specialization.strip(),
            "DepartmentCategory": category.strip(),
        }

    diagnoses = {
        key: {"DiagnosisID": key, "DiagnosisName": name}
        for key, name in _parse_inserts(reference, "Dim_Diagnosis", 2)
    }
    treatments = {
        key: {"TreatmentID": key, "TreatmentName": name}
        for key, name in _parse_inserts(reference, "Dim_Treatment", 2)
    }
    payment_methods = {
        key: {"PaymentMethodID": key, "PaymentMethod": name}
        for key, name in _parse_inserts(reference, "Dim_PaymentMethod", 2)
    }

    return {
        "patients": patients,
        "doctors": doctors,
        "departments": departments,
        "diagnoses": diagnoses,
        "treatments": treatments,
        "payment_methods": payment_methods,
        "raw_patient_count": raw_patient_count,
        "raw_department_count": raw_department_count,
    }

def _year_and_sequence(n: int) -> tuple[int, int]:
    previous = 0
    for boundary, year in YEAR_BOUNDARIES:
        if n <= boundary:
            return year, n - previous - 1
        previous = boundary
    raise ValueError(n)

def generate_visits(dimensions: dict) -> list[dict]:
    patients = dimensions["patients"]
    visits: list[dict] = []

    for n in range(1, TOTAL_VISITS + 1):
        year, sequence = _year_and_sequence(n)
        days_in_year = 366 if year in (2020, 2024) else 365
        visit_date = date(year, 1, 1) + timedelta(
            days=((sequence * 37) + (sequence // 7) * 11) % days_in_year
        )

        patient_no = n if n <= 486 else 487 + ((n * 37 + (n // 11) * 17) % 1945)
        doctor_no = ((n * 29 + (n // 13) * 7) % 200) + 1

        bucket = n % 20
        if bucket in (0, 1, 2):
            department_no = 20
        elif bucket in (3, 4):
            department_no = 1
        else:
            department_no = ((n * 17 + (n // 7) * 5) % 33) + 1

        payment_no = ((n * 7 + (n // 9) * 3) % 4) + 1
        diagnosis_no = ((n * 11 + department_no * 3 + (n // 17)) % 40) + 1
        treatment_no = (
            ((diagnosis_no - 1) % 30) + 1
            if n % 10 <= 6
            else ((n * 13 + department_no) % 30) + 1
        )

        if department_no == 20:
            base_wait = 50
        elif department_no == 1:
            base_wait = 24
        else:
            base_wait = 12 + (department_no % 7) * 4
        is_weekend = (visit_date - EPOCH).days % 7 in (5, 6)
        wait_minutes = base_wait + ((n * 17) % 31) + (8 if is_weekend else 0)

        bill = (
            2_500
            + department_no * 475
            + treatment_no * 190
            + ((n * 7_919) % 35_000)
            + (9_000 if department_no == 20 else 0)
        )
        insurance = (
            Decimal(0)
            if n % 5 == 0
            else dec(Decimal(bill) * Decimal(25 + n % 51) / Decimal(100))
        )

        if wait_minutes <= 25:
            satisfaction = 5
        elif wait_minutes <= 40:
            satisfaction = 4
        elif wait_minutes <= 55:
            satisfaction = 3
        elif wait_minutes <= 70:
            satisfaction = 2
        else:
            satisfaction = 1

        patient_id = f"P{patient_no:04d}"
        dob = patients[patient_id]["DOB"]
        age = visit_date.year - dob.year - (
            (visit_date.month, visit_date.day) < (dob.month, dob.day)
        )

        visits.append(
            {
                "VisitID": f"V{n:06d}",
                "PatientID": patient_id,
                "DoctorID": f"D{doctor_no:03d}",
                "DepartmentID": f"DEP{department_no:02d}",
                "DiagnosisID": f"DX{diagnosis_no:02d}",
                "TreatmentID": f"TR{treatment_no:02d}",
                "PaymentMethodID": f"PM{payment_no:02d}",
                "VisitDate": visit_date,
                "VisitTime": f"{7 + (n * 7) % 14:02d}:{(n * 13) % 60:02d}:{(n * 19) % 60:02d}",
                "DischargeDate": visit_date
                + timedelta(days=(1 + n % 5) if department_no == 20 else n % 3),
                "BillAmount": Decimal(bill),
                "InsuranceAmount": insurance,
                "SatisfactionScore": satisfaction,
                "WaitTimeMinutes": wait_minutes,

                "VisitYear": visit_date.year,
                "DayType": "Weekend" if is_weekend else "Weekday",
                "PatientAge": age,
                "AgeGroup": (
                    "0-17" if age < 18
                    else "18-35" if age <= 35
                    else "36-55" if age <= 55
                    else "56+"
                ),
            }
        )

    return visits

AGE_ORDER = {"0-17": 1, "18-35": 2, "36-55": 3, "56+": 4}


from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from oracle import generate_visits, load_dimensions
from queries import ALL_QUERIES

EXPORTS = ROOT / "exports"

def write_csv(name: str, header: list[str], rows: list[list]) -> Path:
    path = EXPORTS / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return path

def main() -> None:
    EXPORTS.mkdir(exist_ok=True)
    dims = load_dimensions()
    visits = generate_visits(dims)

    write_csv(
        "dim_patient",
        ["PatientID", "FullName", "Gender", "DOB", "City", "State", "Country"],
        [[p["PatientID"], p["FullName"], p["Gender"], p["DOB"].isoformat(),
          p["City"], p["State"], p["Country"]]
         for p in sorted(dims["patients"].values(), key=lambda p: p["PatientID"])],
    )
    write_csv(
        "dim_doctor",
        ["DoctorID", "DoctorName", "Gender", "ExperienceYears"],
        [[d["DoctorID"], d["DoctorName"], d["Gender"], d["ExperienceYears"]]
         for d in sorted(dims["doctors"].values(), key=lambda d: d["DoctorID"])],
    )
    write_csv(
        "dim_department",
        ["DepartmentID", "DepartmentName", "DepartmentCategory"],
        [[d["DepartmentID"], d["DepartmentName"], d["DepartmentCategory"]]
         for d in sorted(dims["departments"].values(), key=lambda d: d["DepartmentID"])],
    )
    write_csv(
        "dim_diagnosis", ["DiagnosisID", "DiagnosisName"],
        [[d["DiagnosisID"], d["DiagnosisName"]]
         for d in sorted(dims["diagnoses"].values(), key=lambda d: d["DiagnosisID"])],
    )
    write_csv(
        "dim_treatment", ["TreatmentID", "TreatmentName"],
        [[t["TreatmentID"], t["TreatmentName"]]
         for t in sorted(dims["treatments"].values(), key=lambda t: t["TreatmentID"])],
    )
    write_csv(
        "dim_paymentmethod", ["PaymentMethodID", "PaymentMethod"],
        [[p["PaymentMethodID"], p["PaymentMethod"]]
         for p in sorted(dims["payment_methods"].values(),
                         key=lambda p: p["PaymentMethodID"])],
    )

    write_csv(
        "fact_patientvisits",
        ["VisitID", "PatientID", "DoctorID", "DepartmentID", "DiagnosisID",
         "TreatmentID", "PaymentMethodID", "VisitDate", "VisitTime",
         "DischargeDate", "BillAmount", "InsuranceAmount", "SatisfactionScore",
         "WaitTimeMinutes"],
        [[v["VisitID"], v["PatientID"], v["DoctorID"], v["DepartmentID"],
          v["DiagnosisID"], v["TreatmentID"], v["PaymentMethodID"],
          v["VisitDate"].isoformat(), v["VisitTime"],
          v["DischargeDate"].isoformat(), v["BillAmount"], v["InsuranceAmount"],
          v["SatisfactionScore"], v["WaitTimeMinutes"]]
         for v in visits],
    )

    for query in ALL_QUERIES:
        name, header, rows = query(visits, dims)
        write_csv(name, header, rows)

    written = sorted(EXPORTS.glob("*.csv"))

    (EXPORTS / "PROVENANCE.txt").write_text(
        "source: oracle\n"
        "generated-by: scripts/build_exports.py\n"
        "\n"
        "These CSVs were produced by the Python oracle, not by SQL Server.\n"
        "They are a deterministic bootstrap so that the Power BI kit and the\n"
        "web dashboard work on a machine without SQL Server.\n"
        "\n"
        "To make them authoritative, run the real pipeline and re-export:\n"
        "    ./scripts/export_from_sqlserver.sh\n"
        "    python3 tests/verify_results.py\n",
        encoding="utf-8",
    )

    total_kb = sum(path.stat().st_size for path in written) / 1024
    print(f"Wrote {len(written)} CSV files to exports/ ({total_kb:,.0f} KB)")
    for path in written:
        print(f"  {path.name}")
    print("\nProvenance: oracle (no SQL Server involved).")
    print("Run scripts/export_from_sqlserver.sh to replace these with real exports.")

if __name__ == "__main__":
    main()

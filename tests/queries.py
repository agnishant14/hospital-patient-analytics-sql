
from __future__ import annotations

from collections import defaultdict
from datetime import date
from fractions import Fraction

from oracle import AGE_ORDER, average, dec, pct

def _sum_by(visits, key, value=lambda v: 1):
    totals = defaultdict(Fraction)
    for visit in visits:
        totals[key(visit)] += Fraction(value(visit))
    return totals

def q01_operating_kpis(visits, dims):
    total = len(visits)
    revenue = sum(v["BillAmount"] for v in visits)
    return (
        "q01_operating_kpis",
        [
            "TotalVisits", "DistinctPatients", "TotalBilledRevenueINR",
            "AverageBillINR", "AverageWaitMinutes", "AverageSatisfaction",
        ],
        [[
            total,
            len({v["PatientID"] for v in visits}),
            dec(revenue),
            average(revenue, total),
            average(sum(v["WaitTimeMinutes"] for v in visits), total),
            average(sum(v["SatisfactionScore"] for v in visits), total),
        ]],
    )

def q02_annual_growth(visits, dims):
    counts = defaultdict(int)
    revenue = defaultdict(int)
    for visit in visits:
        counts[visit["VisitYear"]] += 1
        revenue[visit["VisitYear"]] += visit["BillAmount"]

    rows = []
    years = sorted(counts)
    for index, year in enumerate(years):
        prior = years[index - 1] if index else None
        rows.append([
            year,
            counts[year],
            dec(revenue[year]),
            pct(counts[year] - counts[prior], counts[prior]) if prior else "",
            pct(revenue[year] - revenue[prior], revenue[prior]) if prior else "",
        ])
    return (
        "q02_annual_growth",
        ["VisitYear", "TotalVisits", "TotalRevenueINR",
         "VisitGrowthPercent", "RevenueGrowthPercent"],
        rows,
    )

def q03_doctor_patient_load(visits, dims):
    patients = defaultdict(set)
    totals = defaultdict(int)
    for visit in visits:
        patients[visit["DoctorID"]].add(visit["PatientID"])
        totals[visit["DoctorID"]] += 1

    rows = [
        [doctor_id, dims["doctors"][doctor_id]["DoctorName"],
         len(patients[doctor_id]), totals[doctor_id]]
        for doctor_id in totals
    ]
    rows.sort(key=lambda r: (-r[2], -r[3], r[0]))
    return (
        "q03_doctor_patient_load",
        ["DoctorID", "DoctorName", "DistinctPatients", "TotalVisits"],
        rows,
    )

def q04_payment_mix(visits, dims):
    counts = defaultdict(int)
    revenue = defaultdict(int)
    for visit in visits:
        counts[visit["PaymentMethodID"]] += 1
        revenue[visit["PaymentMethodID"]] += visit["BillAmount"]
    grand_total = sum(revenue.values())

    rows = [
        [dims["payment_methods"][key]["PaymentMethod"], counts[key],
         dec(revenue[key]), pct(revenue[key], grand_total)]
        for key in counts
    ]
    rows.sort(key=lambda r: -r[2])
    return (
        "q04_payment_mix",
        ["PaymentMethod", "TotalVisits", "TotalRevenueINR", "RevenueSharePercent"],
        rows,
    )

def q05_age_band(visits, dims):
    counts = defaultdict(int)
    revenue = defaultdict(int)
    for visit in visits:
        counts[visit["AgeGroup"]] += 1
        revenue[visit["AgeGroup"]] += visit["BillAmount"]

    rows = [[group, counts[group], average(revenue[group], counts[group])]
            for group in counts]
    rows.sort(key=lambda r: AGE_ORDER[r[0]])
    return "q05_age_band", ["AgeGroup", "TotalVisits", "AverageBillINR"], rows

def q06_department_rank(visits, dims):
    counts = defaultdict(int)
    revenue = defaultdict(int)
    for visit in visits:
        counts[visit["DepartmentID"]] += 1
        revenue[visit["DepartmentID"]] += visit["BillAmount"]

    by_category = defaultdict(list)
    for dept_id in counts:
        department = dims["departments"][dept_id]
        by_category[department["DepartmentCategory"]].append(
            (department["DepartmentName"], counts[dept_id], revenue[dept_id])
        )

    rows = []
    for category in sorted(by_category):
        members = by_category[category]

        distinct_revenue = sorted({member[2] for member in members}, reverse=True)
        ranking = {value: index + 1 for index, value in enumerate(distinct_revenue)}
        ranked = [
            [category, name, visit_count, dec(total), ranking[total]]
            for name, visit_count, total in members
        ]
        ranked.sort(key=lambda r: (r[4], r[1]))
        rows.extend(ranked)

    return (
        "q06_department_rank",
        ["DepartmentCategory", "DepartmentName", "TotalVisits",
         "TotalRevenueINR", "RevenueRankWithinCategory"],
        rows,
    )

def q07_department_service_risk(visits, dims):
    counts = defaultdict(int)
    satisfaction = defaultdict(int)
    wait = defaultdict(int)
    within_30 = defaultdict(int)
    for visit in visits:
        key = visit["DepartmentID"]
        counts[key] += 1
        satisfaction[key] += visit["SatisfactionScore"]
        wait[key] += visit["WaitTimeMinutes"]
        within_30[key] += 1 if visit["WaitTimeMinutes"] <= 30 else 0

    rows = [
        [dims["departments"][key]["DepartmentName"], counts[key],
         average(satisfaction[key], counts[key]),
         average(wait[key], counts[key]),
         pct(within_30[key], counts[key])]
        for key in counts
    ]
    rows.sort(key=lambda r: (-r[3], r[2]))
    return (
        "q07_department_service_risk",
        ["DepartmentName", "TotalVisits", "AverageSatisfaction",
         "AverageWaitMinutes", "VisitsWithin30MinutesPercent"],
        rows,
    )

def q08_weekday_weekend(visits, dims):
    counts = defaultdict(int)
    revenue = defaultdict(int)
    for visit in visits:
        counts[visit["DayType"]] += 1
        revenue[visit["DayType"]] += visit["BillAmount"]

    rows = [[day_type, counts[day_type], dec(revenue[day_type]),
             average(revenue[day_type], counts[day_type])]
            for day_type in counts]
    rows.sort(key=lambda r: 1 if r[0] == "Weekday" else 2)
    return (
        "q08_weekday_weekend",
        ["DayType", "TotalVisits", "TotalRevenueINR", "AverageBillINR"],
        rows,
    )

def q09_monthly_trend(visits, dims):
    counts = defaultdict(int)
    for visit in visits:
        visit_date = visit["VisitDate"]
        counts[date(visit_date.year, visit_date.month, 1)] += 1

    months = sorted(counts)
    rows = []
    running = 0
    for index, month in enumerate(months):
        running += counts[month]

        prior = counts[months[index - 12]] if index >= 12 else None
        rows.append([
            month.isoformat(),
            counts[month],
            running,
            pct(counts[month] - prior, prior) if prior is not None else "",
        ])
    return (
        "q09_monthly_trend",
        ["MonthStart", "TotalVisits", "CumulativeVisits",
         "YearOverYearVisitGrowthPercent"],
        rows,
    )

def q10_top_doctors(visits, dims):
    counts = defaultdict(int)
    satisfaction = defaultdict(int)
    wait = defaultdict(int)
    for visit in visits:
        key = visit["DoctorID"]
        counts[key] += 1
        satisfaction[key] += visit["SatisfactionScore"]
        wait[key] += visit["WaitTimeMinutes"]

    eligible = [
        (
            key,
            dims["doctors"][key]["DoctorName"],
            counts[key],
            Fraction(satisfaction[key], counts[key]),
            Fraction(wait[key], counts[key]),
        )
        for key in counts
        if counts[key] >= 100
    ]

    keys = sorted({(-row[3], row[4], -row[2]) for row in eligible})
    ranking = {value: index + 1 for index, value in enumerate(keys)}

    rows = []
    for doctor_id, name, visit_count, avg_satisfaction, avg_wait in eligible:
        rank = ranking[(-avg_satisfaction, avg_wait, -visit_count)]
        if rank <= 10:
            rows.append([rank, doctor_id, name, visit_count,
                         dec(avg_satisfaction), dec(avg_wait)])
    rows.sort(key=lambda r: (r[0], r[1]))
    return (
        "q10_top_doctors",
        ["PerformanceRank", "DoctorID", "DoctorName", "TotalVisits",
         "AverageSatisfaction", "AverageWaitMinutes"],
        rows,
    )

def q11_repeat_patients(visits, dims):
    frequency = defaultdict(int)
    for visit in visits:
        frequency[visit["PatientID"]] += 1

    distinct = len(frequency)
    repeat = sum(1 for count in frequency.values() if count >= 2)
    return (
        "q11_repeat_patients",
        ["DistinctPatients", "RepeatPatients", "RepeatPatientRatePercent",
         "AverageVisitsPerPatient"],
        [[distinct, repeat, pct(repeat, distinct),
          average(sum(frequency.values()), distinct)]],
    )

def q12_diagnosis_treatment(visits, dims):
    counts = defaultdict(int)
    for visit in visits:
        counts[(visit["DiagnosisID"], visit["TreatmentID"])] += 1

    by_diagnosis = defaultdict(list)
    for (diagnosis_id, treatment_id), count in counts.items():
        by_diagnosis[diagnosis_id].append((treatment_id, count))

    rows = []
    for diagnosis_id, pairs in by_diagnosis.items():
        best = max(count for _, count in pairs)
        for treatment_id, count in pairs:
            if count == best:
                rows.append([
                    dims["diagnoses"][diagnosis_id]["DiagnosisName"],
                    dims["treatments"][treatment_id]["TreatmentName"],
                    count,
                ])
    rows.sort(key=lambda r: (r[0], r[1]))
    return "q12_diagnosis_treatment", ["DiagnosisName", "TreatmentName", "TreatmentCount"], rows

ALL_QUERIES = [
    q01_operating_kpis, q02_annual_growth, q03_doctor_patient_load,
    q04_payment_mix, q05_age_band, q06_department_rank,
    q07_department_service_risk, q08_weekday_weekend, q09_monthly_trend,
    q10_top_doctors, q11_repeat_patients, q12_diagnosis_treatment,
]

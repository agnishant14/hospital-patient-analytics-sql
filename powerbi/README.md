# Power BI build kit

Text-based assets for rebuilding the SQL analysis in Power BI without committing a binary `.pbix` file.

| File | Purpose |
| --- | --- |
| `measures.dax` | Date table, three calculated columns, and 40 measures |
| `theme.json` | Shared dashboard colours and visual defaults |

## Build the model

Import these files from `../exports/` and rename the tables as shown. Do not import the `qNN_*.csv` result files.

| CSV | Power BI table |
| --- | --- |
| `fact_patientvisits.csv` | `Fact Visits` |
| `dim_patient.csv` | `Patient` |
| `dim_doctor.csv` | `Doctor` |
| `dim_department.csv` | `Department` |
| `dim_diagnosis.csv` | `Diagnosis` |
| `dim_treatment.csv` | `Treatment` |
| `dim_paymentmethod.csv` | `Payment Method` |

Set `VisitDate`, `DischargeDate`, and `DOB` to **Date**. Keep `VisitTime` and all identifiers as **Text**.

Create one-to-many, single-direction relationships from each dimension to `Fact Visits`:

| Dimension key | Fact key |
| --- | --- |
| `Date[Date]` | `Fact Visits[VisitDate]` |
| `Patient[PatientID]` | `Fact Visits[PatientID]` |
| `Doctor[DoctorID]` | `Fact Visits[DoctorID]` |
| `Department[DepartmentID]` | `Fact Visits[DepartmentID]` |
| `Diagnosis[DiagnosisID]` | `Fact Visits[DiagnosisID]` |
| `Treatment[TreatmentID]` | `Fact Visits[TreatmentID]` |
| `Payment Method[PaymentMethodID]` | `Fact Visits[PaymentMethodID]` |

Then apply `measures.dax` in file order:

1. Create and mark the `Date` table.
2. Add `Age At Visit`, `Age Band`, and `Age Band Order`.
3. Sort `Month Name` by `Month Number`, `Year Month` by `Month Start`, and `Age Band` by `Age Band Order`.
4. Add the measures and apply `theme.json`.

## Acceptance checklist

With no filters applied, the model must return:

| Measure | Expected |
| --- | ---: |
| `Total Visits` | 50,000 |
| `Distinct Patients` | 2,431 |
| `Total Revenue` | ₹1,584,479,195 |
| `Average Bill` | ₹31,689.58 |
| `Average Wait Minutes` | 45.69 |
| `Average Satisfaction` | 3.16 |
| `Insurance Covered` | ₹625,205,809.70 |
| `Seen Within 30 Min` | 8,247 → 16.5% |
| `Satisfied Visits` | 19,821 → 39.6% |
| `Repeat Patients` | 1,945 → 80.0% |
| `Visits per Patient` | 20.57 |
| `Active Doctors` | 200 |
| `Weekend Visits` | 14,283 → 28.6% |

| Diagnostic check | Expected |
| --- | ---: |
| 2021 visit growth | 20.00% |
| Annual growth series | 20.00, 25.00, 13.33, 23.53, 19.05 percent |
| Age-band visits | 7,629 / 13,253 / 15,814 / 13,304 |
| Emergency Medicine wait | 67.27 over 8,638 visits |
| Doctor leaderboard at rank ≤ 10 | **11 rows** |
| Clean city value | `Chennai` (5 patients) |

Using `DATEADD` for prior-year visits incorrectly produces **20.29%** because it drops the 12 visits dated 2020-02-29. Use the year-bucket measure supplied in `measures.dax`. The department model should contain the 33 departments.

Run `python3 tests/verify_powerbi.py` to reconcile these figures, all DAX references, thresholds, colours, and the theme against the committed exports.

## Suggested report pages

- **Overview:** KPIs, monthly trend, payment mix, and age bands.
- **Departments:** service-risk matrix with wait-time conditional formatting.
- **Doctors:** ranked performance table and satisfaction-versus-wait scatterplot.
- **Patients:** repeat visits, visits per patient, and geographic distribution.

Percentiles may differ slightly from the web dashboard because DAX uses interpolation while the dashboard uses nearest rank. Use `Doctor Performance Rank (exact)` when SQL-compatible tie-breaking is required.

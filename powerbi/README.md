# Power BI kit

Everything needed to rebuild the analysis as a Power BI report on top of the
same data the SQL layer publishes.

| File | What it is |
| --- | --- |
| `measures.dax` | The Date table, three calculated columns, and 40 measures. Every one names the SQL query it mirrors. |
| `theme.json` | Report theme. Same palette as the web dashboard, so the two read as one project. |
| `README.md` | This file: model spec, build order, and the numbers to check against. |

**There is no `.pbix` in this repo, deliberately.** A `.pbix` is a binary
archive containing a compiled tabular model, so it cannot be diffed, reviewed,
or merged, and it goes stale the moment the data changes. The model is defined
here as text instead. Building it takes about twenty minutes and the acceptance
table at the end tells you whether you got it right.

The inputs are `../exports/*.csv`, the same seven files the web dashboard and
`tests/verify_results.py` read.

---

## 1. Load the data

Get Data → Text/CSV, once per file in `exports/`. Skip the `qNN_*.csv` files —
those are query *results*, and the whole point is to recompute them.

Rename each table on the way in. The filenames are warehouse-side names; the
model is what business users will see in the field list.

| File | Table name |
| --- | --- |
| `fact_patientvisits.csv` | `Fact Visits` |
| `dim_patient.csv` | `Patient` |
| `dim_doctor.csv` | `Doctor` |
| `dim_department.csv` | `Department` |
| `dim_diagnosis.csv` | `Diagnosis` |
| `dim_treatment.csv` | `Treatment` |
| `dim_paymentmethod.csv` | `Payment Method` |

In Power Query, check the auto-generated **Changed Type** step before you load.
Power BI infers types from the first 200 rows and gets two things wrong here:

- `VisitDate`, `DischargeDate` and `DOB` should be **Date**, not Date/Time. The
  time component is always midnight and carrying it makes the date table
  relationship fail silently — every fact row lands on no date at all.
- `VisitTime` should be **Text**. It is a clock time with no date, and Power BI
  will try to make it a Duration, which then formats as `14:13:19` in some
  visuals and `0.59` in others.

Everything else is right by default: the IDs are text (`P0001`, `DEP01`),
`BillAmount` / `SatisfactionScore` / `WaitTimeMinutes` are whole numbers, and
`InsuranceAmount` is decimal.

## 2. Build the star

Seven relationships, all of them one-to-many from the dimension to the fact,
all single cross-filter direction.

| One side | Many side | Key |
| --- | --- | --- |
| `Date[Date]` | `Fact Visits[VisitDate]` | date |
| `Patient[PatientID]` | `Fact Visits[PatientID]` | text |
| `Doctor[DoctorID]` | `Fact Visits[DoctorID]` | text |
| `Department[DepartmentID]` | `Fact Visits[DepartmentID]` | text |
| `Diagnosis[DiagnosisID]` | `Fact Visits[DiagnosisID]` | text |
| `Treatment[TreatmentID]` | `Fact Visits[TreatmentID]` | text |
| `Payment Method[PaymentMethodID]` | `Fact Visits[PaymentMethodID]` | text |

Leave every one of them **single direction**. Power BI will offer to make some
bidirectional and it is worth understanding why to decline: with bidirectional
filters, selecting a department would filter the `Patient` table down to
patients who visited it, which sounds helpful right up until `Repeat Patients`
starts counting a different denominator depending on which visual you read it
in. Ambiguity in a star schema shows up as numbers that disagree with each
other on the same page. If a specific visual genuinely needs the reverse filter,
use `CROSSFILTER` inside that one measure.

Then hide from report view: every `*ID` column on the fact table (users should
slice by name, not key), `Fact Visits[VisitID]`, and `Patient[DOB]` once the
age column exists.

## 3. Date table and calculated columns

Run the first two sections of `measures.dax`, in order:

1. Create the `Date` calculated table. Then **Table tools → Mark as date
   table → Date**. Time intelligence does nothing until you do this, and it
   fails quietly rather than erroring.
2. Set the sort-by columns: `Month Name` sorts by `Month Number`, `Year Month`
   sorts by `Month Start`.
3. Add the `Age At Visit`, `Age Band` and `Age Band Order` calculated columns to
   `Fact Visits`, then set `Age Band` to sort by `Age Band Order`.
4. Relate `Date[Date]` to `Fact Visits[VisitDate]`.

Age is a column rather than a measure because it is an attribute of the visit
that people slice by, and it has to be age *at the visit* — this data spans six
years, so a patient's band changes underneath them.

## 4. Add the measures

By hand: Modeling → New measure, paste one block from `measures.dax`, repeat.
Tedious but requires nothing extra, and the blocks are in dependency order.

Faster: install **Tabular Editor 2** (free, open source), open it from the
External Tools ribbon, and paste each definition into a new measure there —
it saves back to the model in one commit and lets you set the display folders
in bulk. The folder names are in the section headers (`01 Core`, `02 Service`,
and so on).

Apply the theme last: View → Themes → Browse for themes → `theme.json`.

The theme reserves ochre, amber and red for one job only — a wait time that has
crossed a threshold. Everything else is teal and grey. It is a small discipline
that pays off: on any page in the report, a warm colour means the same thing.

## 5. Check it before you build anything on it

With no slicers applied, a card for each measure should read exactly this. The
right-hand column is what a wrong number would be telling you.

| Measure | Expected | If it differs |
| --- | --- | --- |
| `Total Visits` | 50,000 | A load or filter step dropped rows |
| `Distinct Patients` | 2,431 | — |
| `Total Revenue` | ₹1,584,479,195 | — |
| `Average Bill` | ₹31,689.58 | — |
| `Average Wait Minutes` | 45.69 | — |
| `Average Satisfaction` | 3.16 | — |
| `Insurance Covered` | ₹625,205,809.70 | `InsuranceAmount` loaded as whole number |
| `Seen Within 30 Min` | 8,247 → 16.5% | — |
| `Satisfied Visits` | 19,821 → 39.6% | — |
| `Repeat Patients` | 1,945 → 80.0% | A bidirectional relationship |
| `Visits per Patient` | 20.57 | — |
| `Active Doctors` | 200 | — |
| `Weekend Visits` | 14,283 → 28.6% | `WEEKDAY` called without the `2` argument |

Four more that each catch a specific, easy mistake:

| Check | Expected | If it differs |
| --- | --- | --- |
| `Visit Growth %` for 2021 | 20.00% | **20.29%** means `Visits LY` uses `DATEADD` or `SAMEPERIODLASTYEAR`, which drops the 12 visits dated 2020-02-29 because 2021 has no leap day to map them onto |
| Age band split | 7,629 / 13,253 / 15,814 / 13,304 | Age computed from today rather than from the visit date, or `DATEDIFF(..., YEAR)` used without the birthday adjustment |
| `Average Wait Minutes`, Emergency Medicine | 67.27 over 8,638 visits | The `Department` relationship is joined on the wrong column |
| Leaderboard rows at rank ≤ 10 | **11 rows** | Ten rows means `RANKX` is not set to `DENSE`; two doctors legitimately share rank 6 |

The full year-on-year series is 20.00, 25.00, 13.33, 23.53, 19.05 percent.
Every figure above also appears in `../exports/qNN_*.csv`, so the report is
checkable against the warehouse at any time — that is the point of writing the
DAX to mirror the queries one-for-one.

## 6. Report pages

Four pages, mapping onto the analysis rather than onto the visual types Power
BI happens to offer.

**Overview.** The six KPI cards, the 72-month trend with `Cumulative Visits` on
a secondary axis, payment mix, and the age band split. Slicers for year,
department and day type down the left.

**Departments.** A matrix of the 33 departments with visits, average wait,
average satisfaction and `Seen Within 30 Min %`. Set conditional formatting on
the wait column to **Field value → `Wait Band Colour`**, which ports the
dashboard's threshold ramp exactly. Add `Revenue Rank in Category` as a column
and a category slicer beside it.

**Doctors.** The leaderboard: `Doctor Performance Rank (exact)` filtered to ≤ 10,
with visits, satisfaction and wait. A scatter of satisfaction against wait for
all 200 doctors, sized by visits, makes the relationship the whole project is
about visible in one shape.

**Patients.** Repeat behaviour, visits per patient, and a filled map on
`Patient[State]`. The map is the one thing Power BI gives you that the web
dashboard does not, so it is worth the page.

## 7. Where this will not match the SQL exactly

Two places, both by design, both worth being able to explain:

`PERCENTILE.INC` interpolates between neighbouring values. The web dashboard
reads percentiles off an integer histogram using the nearest-rank convention.
On 50,000 rows they agree within a minute, but they are different definitions
and will not tie out to the decimal. Pick one per report and label it.

`RANKX` ranks on a single expression, so `Doctor Performance Rank` reproduces
q10's primary sort but not its tie-breaks. `Doctor Performance Rank (exact)`
folds the wait-time tie-break into a composite key; the arithmetic that makes
that safe is worked out in the comment above the measure, and it depends on the
100-visit floor and the 12–88 minute wait range. Re-check the margin if either
changes.

## 8. What the map found

`Patient[City]` now shows `Chennai` (5 patients) and no `Chennnai` (0). It did
not start that way. The source data records two of those five patients in
`Chennnai`, and the cleaning step used to pass the misspelling straight through:
it split and trimmed `CityStateCountry` and normalised casing, but did no name
standardisation. A city-level visual showed Chennai twice.

That is worth knowing about because of how long it survived. The typo was
invisible in all twelve SQL queries — none of them group by city — so every
published number was correct while the dimension quietly contained two cities
where there is one. It took building a map to surface it.

The fix went upstream into the cleaning step rather than into Power Query, so
every consumer gets the corrected spelling: `dbo.Ref_CityAlias` maps variant
spellings to canonical ones and `cleaning/05_data_cleaning.sql` joins to it.
The more useful half is the check that came with it. `validation/08` now groups
the dimension by `SOUNDEX(City)` and fails the build if two spellings share a
code, which is how the *next* misspelling gets caught in the load rather than a
year later on a map. Across these 38 city spellings that check is exact: 37
codes, one collision, and the collision was the real defect.

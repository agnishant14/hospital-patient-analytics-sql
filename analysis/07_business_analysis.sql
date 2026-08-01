/*
  Step 07: business analysis.

  Each of the 12 questions lives in its own file under analysis/queries/ so
  that exactly one copy of every query exists. This driver runs them in order
  for an interactive SSMS session; scripts/export_from_sqlserver.sh runs the
  same files one at a time to produce exports/*.csv, which is what Power BI
  and the web dashboard consume.

  Requires SQLCMD Mode (Query > SQLCMD Mode in SSMS) for the :r includes.

  Those paths are relative to the repository root, not to this file. sqlcmd
  resolves :r against its own working directory, so every :r in this project is
  written from the root and every entry point says to start there. Mixing the
  two conventions is the failure mode -- it works from one directory and gives
  "file not found" from the next one over.

  Currency amounts are synthetic Indian rupees (INR).
*/

SET NOCOUNT ON;

:r ./analysis/queries/q01_operating_kpis.sql
:r ./analysis/queries/q02_annual_growth.sql
:r ./analysis/queries/q03_doctor_patient_load.sql
:r ./analysis/queries/q04_payment_mix.sql
:r ./analysis/queries/q05_age_band.sql
:r ./analysis/queries/q06_department_rank.sql
:r ./analysis/queries/q07_department_service_risk.sql
:r ./analysis/queries/q08_weekday_weekend.sql
:r ./analysis/queries/q09_monthly_trend.sql
:r ./analysis/queries/q10_top_doctors.sql
:r ./analysis/queries/q11_repeat_patients.sql
:r ./analysis/queries/q12_diagnosis_treatment.sql

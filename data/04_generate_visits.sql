/*
  Step 04: generate 50,000 deterministic synthetic hospital visits.

  The data is synthetic and contains no real patient information. The formulas
  deliberately create realistic analytical patterns: annual volume growth,
  heavier emergency demand, longer emergency wait times, and a dominant
  treatment for each diagnosis. A fixed formula makes every run reproducible.
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;

CREATE TABLE #GeneratedVisits (
    VisitID            VARCHAR(20)   NOT NULL PRIMARY KEY,
    PatientID          VARCHAR(20)   NOT NULL,
    DoctorID           VARCHAR(20)   NOT NULL,
    DepartmentID       VARCHAR(20)   NOT NULL,
    DiagnosisID        VARCHAR(20)   NOT NULL,
    TreatmentID        VARCHAR(20)   NOT NULL,
    PaymentMethodID    VARCHAR(20)   NOT NULL,
    VisitDate          DATE          NOT NULL,
    VisitTime          TIME          NOT NULL,
    DischargeDate      DATE          NOT NULL,
    BillAmount         DECIMAL(18,2) NOT NULL,
    InsuranceAmount    DECIMAL(18,2) NOT NULL,
    SatisfactionScore  INT           NOT NULL,
    WaitTimeMinutes    INT           NOT NULL
);

;WITH Numbers AS (
    SELECT TOP (50000)
        CAST(ROW_NUMBER() OVER (ORDER BY a.object_id, b.object_id) AS INT) AS n
    FROM sys.all_objects AS a
    CROSS JOIN sys.all_objects AS b
),
YearAssignment AS (
    SELECT
        n,
        CASE
            WHEN n <=  5000 THEN 2020
            WHEN n <= 11000 THEN 2021
            WHEN n <= 18500 THEN 2022
            WHEN n <= 27000 THEN 2023
            WHEN n <= 37500 THEN 2024
            ELSE 2025
        END AS VisitYear,
        CASE
            WHEN n <=  5000 THEN n -     1
            WHEN n <= 11000 THEN n -  5001
            WHEN n <= 18500 THEN n - 11001
            WHEN n <= 27000 THEN n - 18501
            WHEN n <= 37500 THEN n - 27001
            ELSE                 n - 37501
        END AS YearSequence
    FROM Numbers
),
Calendar AS (
    SELECT
        n,
        DATEADD(
            DAY,
            ((YearSequence * 37) + ((YearSequence / 7) * 11))
                % CASE WHEN VisitYear IN (2020, 2024) THEN 366 ELSE 365 END,
            DATEFROMPARTS(VisitYear, 1, 1)
        ) AS VisitDate
    FROM YearAssignment
),
EntityKeys AS (
    SELECT
        n,
        VisitDate,
        CASE
            -- Keep 20% of patients as one-time visitors and distribute the
            -- remaining visits across a repeat-care cohort.
            WHEN n <= 486 THEN n
            ELSE 487 + ((n * 37 + (n / 11) * 17) % 1945)
        END AS PatientNo,
        ((n * 29 + (n / 13) * 7) % 200) + 1 AS DoctorNo,
        CASE
            WHEN n % 20 IN (0, 1, 2) THEN 20 -- Emergency Medicine
            WHEN n % 20 IN (3, 4)    THEN 1  -- Cardiology
            ELSE ((n * 17 + (n / 7) * 5) % 33) + 1
        END AS DepartmentNo,
        ((n * 7 + (n / 9) * 3) % 4) + 1 AS PaymentMethodNo
    FROM Calendar
),
ClinicalKeys AS (
    SELECT
        *,
        ((n * 11 + DepartmentNo * 3 + (n / 17)) % 40) + 1 AS DiagnosisNo
    FROM EntityKeys
),
TreatmentKeys AS (
    SELECT
        *,
        CASE
            WHEN n % 10 <= 6 THEN ((DiagnosisNo - 1) % 30) + 1
            ELSE ((n * 13 + DepartmentNo) % 30) + 1
        END AS TreatmentNo
    FROM ClinicalKeys
),
OperationalMeasures AS (
    SELECT
        *,
        CASE
            WHEN DepartmentNo = 20 THEN 50
            WHEN DepartmentNo = 1  THEN 24
            ELSE 12 + (DepartmentNo % 7) * 4
        END
        + ((n * 17) % 31)
        + CASE
            -- 1900-01-01 was a Monday; values 5 and 6 are Saturday/Sunday.
            WHEN DATEDIFF(DAY, CONVERT(DATE, '19000101', 112), VisitDate) % 7 IN (5, 6)
                THEN 8
            ELSE 0
          END AS WaitTimeMinutes
    FROM TreatmentKeys
),
FinancialMeasures AS (
    SELECT
        *,
        CAST(
            2500
            + DepartmentNo * 475
            + TreatmentNo * 190
            + ((n * 7919) % 35000)
            + CASE WHEN DepartmentNo = 20 THEN 9000 ELSE 0 END
            AS DECIMAL(18,2)
        ) AS BillAmount
    FROM OperationalMeasures
)
INSERT INTO #GeneratedVisits (
    VisitID,
    PatientID,
    DoctorID,
    DepartmentID,
    DiagnosisID,
    TreatmentID,
    PaymentMethodID,
    VisitDate,
    VisitTime,
    DischargeDate,
    BillAmount,
    InsuranceAmount,
    SatisfactionScore,
    WaitTimeMinutes
)
SELECT
    'V' + RIGHT('000000' + CAST(n AS VARCHAR(6)), 6),
    'P' + RIGHT('0000' + CAST(PatientNo AS VARCHAR(4)), 4),
    'D' + RIGHT('000' + CAST(DoctorNo AS VARCHAR(3)), 3),
    'DEP' + RIGHT('00' + CAST(DepartmentNo AS VARCHAR(2)), 2),
    'DX' + RIGHT('00' + CAST(DiagnosisNo AS VARCHAR(2)), 2),
    'TR' + RIGHT('00' + CAST(TreatmentNo AS VARCHAR(2)), 2),
    'PM' + RIGHT('00' + CAST(PaymentMethodNo AS VARCHAR(2)), 2),
    VisitDate,
    TIMEFROMPARTS(7 + (n * 7) % 14, (n * 13) % 60, (n * 19) % 60, 0, 0),
    DATEADD(DAY, CASE WHEN DepartmentNo = 20 THEN 1 + n % 5 ELSE n % 3 END, VisitDate),
    BillAmount,
    CAST(
        CASE
            WHEN n % 5 = 0 THEN 0
            ELSE BillAmount * (25 + n % 51) / 100.0
        END
        AS DECIMAL(18,2)
    ),
    CASE
        WHEN WaitTimeMinutes <= 25 THEN 5
        WHEN WaitTimeMinutes <= 40 THEN 4
        WHEN WaitTimeMinutes <= 55 THEN 3
        WHEN WaitTimeMinutes <= 70 THEN 2
        ELSE 1
    END,
    WaitTimeMinutes
FROM FinancialMeasures;

IF (SELECT COUNT(*) FROM #GeneratedVisits) <> 50000
    THROW 51000, 'Visit generation failed: expected 50,000 rows.', 1;

INSERT INTO dbo.PatientVisits_2020_2021
SELECT * FROM #GeneratedVisits
WHERE VisitDate >= '20200101' AND VisitDate < '20220101';

INSERT INTO dbo.PatientVisits_2022_2023
SELECT * FROM #GeneratedVisits
WHERE VisitDate >= '20220101' AND VisitDate < '20240101';

INSERT INTO dbo.PatientVisits_2024
SELECT * FROM #GeneratedVisits
WHERE VisitDate >= '20240101' AND VisitDate < '20250101';

INSERT INTO dbo.PatientVisits_2025
SELECT * FROM #GeneratedVisits
WHERE VisitDate >= '20250101' AND VisitDate < '20260101';

DROP TABLE #GeneratedVisits;

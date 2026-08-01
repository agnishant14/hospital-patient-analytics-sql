SET NOCOUNT ON;

IF (SELECT COUNT_BIG(*) FROM dbo.PatientVisits) <> 50000
    THROW 52000, 'Quality check failed: PatientVisits must contain 50,000 rows.', 1;

IF (SELECT COUNT_BIG(*) FROM dbo.PatientVisits_2020_2021) <> 11000
    THROW 52001, 'Quality check failed: 2020-2021 staging count is incorrect.', 1;

IF (SELECT COUNT_BIG(*) FROM dbo.PatientVisits_2022_2023) <> 16000
    THROW 52002, 'Quality check failed: 2022-2023 staging count is incorrect.', 1;

IF (SELECT COUNT_BIG(*) FROM dbo.PatientVisits_2024) <> 10500
    THROW 52003, 'Quality check failed: 2024 staging count is incorrect.', 1;

IF (SELECT COUNT_BIG(*) FROM dbo.PatientVisits_2025) <> 12500
    THROW 52004, 'Quality check failed: 2025 staging count is incorrect.', 1;

IF (SELECT COUNT_BIG(*) FROM dbo.Dim_Patient_Clean) <> 2431
    THROW 52005, 'Quality check failed: cleaned patient count is incorrect.', 1;

IF (SELECT COUNT_BIG(*) FROM dbo.Dim_Department_Clean) <> 33
    THROW 52006, 'Quality check failed: cleaned department count is incorrect.', 1;

IF EXISTS (
    SELECT VisitID
    FROM dbo.PatientVisits
    GROUP BY VisitID
    HAVING COUNT_BIG(*) > 1
)
    THROW 52007, 'Quality check failed: duplicate VisitID values found.', 1;

IF EXISTS (
    SELECT 1
    FROM dbo.PatientVisits
    WHERE VisitDate < '20200101'
       OR VisitDate >= '20260101'
       OR DischargeDate < VisitDate
       OR BillAmount < 0
       OR InsuranceAmount < 0
       OR InsuranceAmount > BillAmount
       OR SatisfactionScore NOT BETWEEN 1 AND 5
       OR WaitTimeMinutes < 0
)
    THROW 52008, 'Quality check failed: invalid visit measures or dates found.', 1;

IF EXISTS (
    SELECT 1
    FROM dbo.PatientVisits AS v
    LEFT JOIN dbo.Dim_Patient_Clean AS p
        ON p.PatientID = v.PatientID
    LEFT JOIN dbo.Dim_Doctor AS d
        ON d.DoctorID = v.DoctorID
    LEFT JOIN dbo.Dim_Department_Clean AS dep
        ON dep.DepartmentID = v.DepartmentID
    LEFT JOIN dbo.Dim_Diagnosis AS dx
        ON dx.DiagnosisID = v.DiagnosisID
    LEFT JOIN dbo.Dim_Treatment AS t
        ON t.TreatmentID = v.TreatmentID
    LEFT JOIN dbo.Dim_PaymentMethod AS pm
        ON pm.PaymentMethodID = v.PaymentMethodID
    WHERE p.PatientID IS NULL
       OR d.DoctorID IS NULL
       OR dep.DepartmentID IS NULL
       OR dx.DiagnosisID IS NULL
       OR t.TreatmentID IS NULL
       OR pm.PaymentMethodID IS NULL
)
    THROW 52009, 'Quality check failed: orphaned fact records found.', 1;

DECLARE @SoundalikeCities NVARCHAR(2048);

SELECT @SoundalikeCities = STRING_AGG(Collision, '; ')
FROM (
    SELECT STRING_AGG(City, ' / ') WITHIN GROUP (ORDER BY City) AS Collision
    FROM (SELECT DISTINCT City FROM dbo.Dim_Patient_Clean) AS c
    GROUP BY SOUNDEX(City)
    HAVING COUNT_BIG(*) > 1
) AS collisions;

IF @SoundalikeCities IS NOT NULL
BEGIN
    SET @SoundalikeCities = CONCAT(
        'Quality check failed: city spellings that sound alike are not ',
        'standardised. Add the variant to dbo.Ref_CityAlias -- ',
        @SoundalikeCities);
    THROW 52010, @SoundalikeCities, 1;
END;

SELECT 'Raw patients' AS Dataset, COUNT_BIG(*) AS [RowCount] FROM dbo.Dim_Patient
UNION ALL
SELECT 'Clean patients', COUNT_BIG(*) FROM dbo.Dim_Patient_Clean
UNION ALL
SELECT 'Raw departments', COUNT_BIG(*) FROM dbo.Dim_Department
UNION ALL
SELECT 'Clean departments', COUNT_BIG(*) FROM dbo.Dim_Department_Clean
UNION ALL
SELECT 'Consolidated visits', COUNT_BIG(*) FROM dbo.PatientVisits;

PRINT 'All data-quality checks passed.';

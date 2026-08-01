SET NOCOUNT ON;
SET XACT_ABORT ON;

CREATE TABLE dbo.Ref_CityAlias (
    Variant   VARCHAR(50) NOT NULL PRIMARY KEY,
    Canonical VARCHAR(50) NOT NULL,
    CONSTRAINT CK_Ref_CityAlias_NotSelf CHECK (Variant <> Canonical)
);

INSERT INTO dbo.Ref_CityAlias (Variant, Canonical) VALUES
    ('Chennnai', 'Chennai');

CREATE TABLE dbo.Dim_Patient_Clean (
    PatientID VARCHAR(20)  NOT NULL PRIMARY KEY,
    FullName  VARCHAR(120) NOT NULL,
    Gender    VARCHAR(10)  NOT NULL,
    DOB       DATE         NOT NULL,
    City      VARCHAR(50)  NOT NULL,
    State     VARCHAR(50)  NOT NULL,
    Country   VARCHAR(50)  NOT NULL,
    CONSTRAINT CK_Dim_Patient_Clean_Gender
        CHECK (Gender IN ('Male', 'Female'))
);

WITH Parsed AS (
    SELECT
        p.PatientID,
        UPPER(LEFT(LTRIM(RTRIM(p.FirstName)), 1))
            + LOWER(SUBSTRING(LTRIM(RTRIM(p.FirstName)), 2, 50))
            + ' '
            + UPPER(LEFT(LTRIM(RTRIM(p.LastName)), 1))
            + LOWER(SUBSTRING(LTRIM(RTRIM(p.LastName)), 2, 50)) AS FullName,
        CASE
            WHEN UPPER(LTRIM(RTRIM(p.Gender))) IN ('M', 'MALE') THEN 'Male'
            WHEN UPPER(LTRIM(RTRIM(p.Gender))) IN ('F', 'FEMALE') THEN 'Female'
        END AS Gender,
        p.DOB,
        LTRIM(RTRIM(PARSENAME(REPLACE(p.CityStateCountry, ',', '.'), 3))) AS City,
        LTRIM(RTRIM(PARSENAME(REPLACE(p.CityStateCountry, ',', '.'), 2))) AS State,
        LTRIM(RTRIM(PARSENAME(REPLACE(p.CityStateCountry, ',', '.'), 1))) AS Country
    FROM dbo.Dim_Patient AS p
    WHERE NULLIF(LTRIM(RTRIM(p.FirstName)), '') IS NOT NULL
      AND NULLIF(LTRIM(RTRIM(p.LastName)), '') IS NOT NULL
      AND UPPER(LTRIM(RTRIM(p.Gender))) IN ('M', 'MALE', 'F', 'FEMALE')
      AND p.DOB IS NOT NULL
      AND p.CityStateCountry LIKE '%,%,%'
)
INSERT INTO dbo.Dim_Patient_Clean (
    PatientID,
    FullName,
    Gender,
    DOB,
    City,
    State,
    Country
)
SELECT
    s.PatientID,
    s.FullName,
    s.Gender,
    s.DOB,
    COALESCE(a.Canonical, s.City) AS City,
    s.State,
    s.Country
FROM Parsed AS s
LEFT JOIN dbo.Ref_CityAlias AS a
    ON a.Variant = s.City;

CREATE TABLE dbo.Dim_Department_Clean (
    DepartmentID       VARCHAR(20)  NOT NULL PRIMARY KEY,
    DepartmentName     VARCHAR(100) NOT NULL,
    DepartmentCategory VARCHAR(100) NOT NULL
);

INSERT INTO dbo.Dim_Department_Clean (
    DepartmentID,
    DepartmentName,
    DepartmentCategory
)
SELECT
    d.DepartmentID,
    LTRIM(RTRIM(d.Specialization)) AS DepartmentName,
    LTRIM(RTRIM(d.DepartmentCategory)) AS DepartmentCategory
FROM dbo.Dim_Department AS d
WHERE NULLIF(LTRIM(RTRIM(d.Specialization)), '') IS NOT NULL
  AND NULLIF(LTRIM(RTRIM(d.DepartmentCategory)), '') IS NOT NULL;

CREATE TABLE dbo.PatientVisits (
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
    WaitTimeMinutes    INT           NOT NULL,
    CONSTRAINT FK_PatientVisits_Patient
        FOREIGN KEY (PatientID) REFERENCES dbo.Dim_Patient_Clean(PatientID),
    CONSTRAINT FK_PatientVisits_Doctor
        FOREIGN KEY (DoctorID) REFERENCES dbo.Dim_Doctor(DoctorID),
    CONSTRAINT FK_PatientVisits_Department
        FOREIGN KEY (DepartmentID) REFERENCES dbo.Dim_Department_Clean(DepartmentID),
    CONSTRAINT FK_PatientVisits_Diagnosis
        FOREIGN KEY (DiagnosisID) REFERENCES dbo.Dim_Diagnosis(DiagnosisID),
    CONSTRAINT FK_PatientVisits_Treatment
        FOREIGN KEY (TreatmentID) REFERENCES dbo.Dim_Treatment(TreatmentID),
    CONSTRAINT FK_PatientVisits_PaymentMethod
        FOREIGN KEY (PaymentMethodID) REFERENCES dbo.Dim_PaymentMethod(PaymentMethodID),
    CONSTRAINT CK_PatientVisits_DischargeDate
        CHECK (DischargeDate >= VisitDate),
    CONSTRAINT CK_PatientVisits_BillAmount
        CHECK (BillAmount >= 0),
    CONSTRAINT CK_PatientVisits_InsuranceAmount
        CHECK (InsuranceAmount BETWEEN 0 AND BillAmount),
    CONSTRAINT CK_PatientVisits_SatisfactionScore
        CHECK (SatisfactionScore BETWEEN 1 AND 5),
    CONSTRAINT CK_PatientVisits_WaitTime
        CHECK (WaitTimeMinutes >= 0)
);

;WITH AllVisits AS (
    SELECT * FROM dbo.PatientVisits_2020_2021
    UNION ALL
    SELECT * FROM dbo.PatientVisits_2022_2023
    UNION ALL
    SELECT * FROM dbo.PatientVisits_2024
    UNION ALL
    SELECT * FROM dbo.PatientVisits_2025
),
DeduplicatedVisits AS (
    SELECT
        v.*,
        ROW_NUMBER() OVER (
            PARTITION BY v.VisitID
            ORDER BY v.VisitDate DESC, v.VisitTime DESC
        ) AS DuplicateRank
    FROM AllVisits AS v
)
INSERT INTO dbo.PatientVisits (
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
    v.VisitID,
    v.PatientID,
    v.DoctorID,
    v.DepartmentID,
    v.DiagnosisID,
    v.TreatmentID,
    v.PaymentMethodID,
    v.VisitDate,
    v.VisitTime,
    v.DischargeDate,
    v.BillAmount,
    v.InsuranceAmount,
    v.SatisfactionScore,
    v.WaitTimeMinutes
FROM DeduplicatedVisits AS v
INNER JOIN dbo.Dim_Patient_Clean AS p
    ON p.PatientID = v.PatientID
INNER JOIN dbo.Dim_Department_Clean AS dep
    ON dep.DepartmentID = v.DepartmentID
WHERE v.DuplicateRank = 1;

SET NOCOUNT ON;
SET XACT_ABORT ON;

DROP TABLE IF EXISTS dbo.PatientVisits;
DROP TABLE IF EXISTS dbo.Dim_Patient_Clean;
DROP TABLE IF EXISTS dbo.Dim_Department_Clean;
DROP TABLE IF EXISTS dbo.PatientVisits_2025;
DROP TABLE IF EXISTS dbo.PatientVisits_2024;
DROP TABLE IF EXISTS dbo.PatientVisits_2022_2023;
DROP TABLE IF EXISTS dbo.PatientVisits_2020_2021;
DROP TABLE IF EXISTS dbo.Dim_PaymentMethod;
DROP TABLE IF EXISTS dbo.Dim_Treatment;
DROP TABLE IF EXISTS dbo.Dim_Diagnosis;
DROP TABLE IF EXISTS dbo.Dim_Department;
DROP TABLE IF EXISTS dbo.Dim_Doctor;
DROP TABLE IF EXISTS dbo.Dim_Patient;

CREATE TABLE dbo.Dim_Patient (
    PatientID       VARCHAR(20)  NOT NULL PRIMARY KEY,
    FirstName       VARCHAR(50)  NULL,
    LastName        VARCHAR(50)  NULL,
    Gender          VARCHAR(10)  NULL,
    DOB             DATE         NULL,
    CityStateCountry VARCHAR(150) NULL
);

CREATE TABLE dbo.Dim_Doctor (
    DoctorID       VARCHAR(20) NOT NULL PRIMARY KEY,
    FirstName      VARCHAR(50) NOT NULL,
    LastName       VARCHAR(50) NOT NULL,
    Gender         VARCHAR(10) NOT NULL,
    ExperienceYears INT        NOT NULL,
    CONSTRAINT CK_Dim_Doctor_Experience
        CHECK (ExperienceYears BETWEEN 0 AND 60)
);

CREATE TABLE dbo.Dim_Department (
    DepartmentID       VARCHAR(20)  NOT NULL PRIMARY KEY,
    DepartmentName     VARCHAR(100) NULL,
    DepartmentCategory VARCHAR(100) NULL,
    Specialization     VARCHAR(100) NULL,
    HOD                 VARCHAR(30)  NULL
);

CREATE TABLE dbo.Dim_Diagnosis (
    DiagnosisID   VARCHAR(20)  NOT NULL PRIMARY KEY,
    DiagnosisName VARCHAR(200) NOT NULL
);

CREATE TABLE dbo.Dim_Treatment (
    TreatmentID   VARCHAR(20)  NOT NULL PRIMARY KEY,
    TreatmentName VARCHAR(100) NOT NULL
);

CREATE TABLE dbo.Dim_PaymentMethod (
    PaymentMethodID VARCHAR(20) NOT NULL PRIMARY KEY,
    PaymentMethod   VARCHAR(50) NOT NULL
);

CREATE TABLE dbo.PatientVisits_2020_2021 (
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
    FOREIGN KEY (PatientID)       REFERENCES dbo.Dim_Patient(PatientID),
    FOREIGN KEY (DoctorID)        REFERENCES dbo.Dim_Doctor(DoctorID),
    FOREIGN KEY (DepartmentID)    REFERENCES dbo.Dim_Department(DepartmentID),
    FOREIGN KEY (DiagnosisID)     REFERENCES dbo.Dim_Diagnosis(DiagnosisID),
    FOREIGN KEY (TreatmentID)     REFERENCES dbo.Dim_Treatment(TreatmentID),
    FOREIGN KEY (PaymentMethodID) REFERENCES dbo.Dim_PaymentMethod(PaymentMethodID),
    CHECK (DischargeDate >= VisitDate),
    CHECK (BillAmount >= 0),
    CHECK (InsuranceAmount BETWEEN 0 AND BillAmount),
    CHECK (SatisfactionScore BETWEEN 1 AND 5),
    CHECK (WaitTimeMinutes >= 0)
);

CREATE TABLE dbo.PatientVisits_2022_2023 (
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
    FOREIGN KEY (PatientID)       REFERENCES dbo.Dim_Patient(PatientID),
    FOREIGN KEY (DoctorID)        REFERENCES dbo.Dim_Doctor(DoctorID),
    FOREIGN KEY (DepartmentID)    REFERENCES dbo.Dim_Department(DepartmentID),
    FOREIGN KEY (DiagnosisID)     REFERENCES dbo.Dim_Diagnosis(DiagnosisID),
    FOREIGN KEY (TreatmentID)     REFERENCES dbo.Dim_Treatment(TreatmentID),
    FOREIGN KEY (PaymentMethodID) REFERENCES dbo.Dim_PaymentMethod(PaymentMethodID),
    CHECK (DischargeDate >= VisitDate),
    CHECK (BillAmount >= 0),
    CHECK (InsuranceAmount BETWEEN 0 AND BillAmount),
    CHECK (SatisfactionScore BETWEEN 1 AND 5),
    CHECK (WaitTimeMinutes >= 0)
);

CREATE TABLE dbo.PatientVisits_2024 (
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
    FOREIGN KEY (PatientID)       REFERENCES dbo.Dim_Patient(PatientID),
    FOREIGN KEY (DoctorID)        REFERENCES dbo.Dim_Doctor(DoctorID),
    FOREIGN KEY (DepartmentID)    REFERENCES dbo.Dim_Department(DepartmentID),
    FOREIGN KEY (DiagnosisID)     REFERENCES dbo.Dim_Diagnosis(DiagnosisID),
    FOREIGN KEY (TreatmentID)     REFERENCES dbo.Dim_Treatment(TreatmentID),
    FOREIGN KEY (PaymentMethodID) REFERENCES dbo.Dim_PaymentMethod(PaymentMethodID),
    CHECK (DischargeDate >= VisitDate),
    CHECK (BillAmount >= 0),
    CHECK (InsuranceAmount BETWEEN 0 AND BillAmount),
    CHECK (SatisfactionScore BETWEEN 1 AND 5),
    CHECK (WaitTimeMinutes >= 0)
);

CREATE TABLE dbo.PatientVisits_2025 (
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
    FOREIGN KEY (PatientID)       REFERENCES dbo.Dim_Patient(PatientID),
    FOREIGN KEY (DoctorID)        REFERENCES dbo.Dim_Doctor(DoctorID),
    FOREIGN KEY (DepartmentID)    REFERENCES dbo.Dim_Department(DepartmentID),
    FOREIGN KEY (DiagnosisID)     REFERENCES dbo.Dim_Diagnosis(DiagnosisID),
    FOREIGN KEY (TreatmentID)     REFERENCES dbo.Dim_Treatment(TreatmentID),
    FOREIGN KEY (PaymentMethodID) REFERENCES dbo.Dim_PaymentMethod(PaymentMethodID),
    CHECK (DischargeDate >= VisitDate),
    CHECK (BillAmount >= 0),
    CHECK (InsuranceAmount BETWEEN 0 AND BillAmount),
    CHECK (SatisfactionScore BETWEEN 1 AND 5),
    CHECK (WaitTimeMinutes >= 0)
);

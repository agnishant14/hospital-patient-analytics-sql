/* Step 06: indexes supporting the portfolio's most common analytical paths. */

CREATE INDEX IX_PatientVisits_VisitDate
    ON dbo.PatientVisits (VisitDate)
    INCLUDE (PatientID, DepartmentID, BillAmount, SatisfactionScore, WaitTimeMinutes);

CREATE INDEX IX_PatientVisits_Department_VisitDate
    ON dbo.PatientVisits (DepartmentID, VisitDate)
    INCLUDE (BillAmount, SatisfactionScore, WaitTimeMinutes);

CREATE INDEX IX_PatientVisits_Doctor
    ON dbo.PatientVisits (DoctorID)
    INCLUDE (PatientID, SatisfactionScore);

CREATE INDEX IX_PatientVisits_Diagnosis_Treatment
    ON dbo.PatientVisits (DiagnosisID, TreatmentID);

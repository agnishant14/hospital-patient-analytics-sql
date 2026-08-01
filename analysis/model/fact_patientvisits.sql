-- The consolidated fact table. 50,000 rows; this is the grain Power BI imports.
SELECT VisitID, PatientID, DoctorID, DepartmentID, DiagnosisID, TreatmentID,
       PaymentMethodID, VisitDate, VisitTime, DischargeDate, BillAmount,
       InsuranceAmount, SatisfactionScore, WaitTimeMinutes
FROM dbo.PatientVisits
ORDER BY VisitID;

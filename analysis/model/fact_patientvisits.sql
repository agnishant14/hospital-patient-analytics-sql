SELECT VisitID, PatientID, DoctorID, DepartmentID, DiagnosisID, TreatmentID,
       PaymentMethodID, VisitDate, VisitTime, DischargeDate, BillAmount,
       InsuranceAmount, SatisfactionScore, WaitTimeMinutes
FROM dbo.PatientVisits
ORDER BY VisitID;

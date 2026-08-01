-- Cleaned patient dimension, as consumed by Power BI and the web dashboard.
SELECT PatientID, FullName, Gender, DOB, City, State, Country
FROM dbo.Dim_Patient_Clean
ORDER BY PatientID;

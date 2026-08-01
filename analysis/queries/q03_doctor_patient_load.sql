-- Q3. How many distinct patients has each doctor treated?
SELECT
    d.DoctorID,
    d.FirstName + ' ' + d.LastName AS DoctorName,
    COUNT(DISTINCT v.PatientID) AS DistinctPatients,
    COUNT_BIG(*) AS TotalVisits
FROM dbo.PatientVisits AS v
INNER JOIN dbo.Dim_Doctor AS d
    ON d.DoctorID = v.DoctorID
GROUP BY d.DoctorID, d.FirstName, d.LastName
ORDER BY DistinctPatients DESC, TotalVisits DESC, d.DoctorID;

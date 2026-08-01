-- Q11. What percentage of patients returned for multiple visits?
;WITH PatientVisitFrequency AS (
    SELECT
        PatientID,
        COUNT_BIG(*) AS TotalVisits
    FROM dbo.PatientVisits
    GROUP BY PatientID
)
SELECT
    COUNT_BIG(*) AS DistinctPatients,
    SUM(CASE WHEN TotalVisits >= 2 THEN 1 ELSE 0 END) AS RepeatPatients,
    CAST(
        100.0 * SUM(CASE WHEN TotalVisits >= 2 THEN 1 ELSE 0 END) / COUNT_BIG(*)
        AS DECIMAL(10,2)
    ) AS RepeatPatientRatePercent,
    CAST(AVG(CAST(TotalVisits AS DECIMAL(10,2))) AS DECIMAL(10,2)) AS AverageVisitsPerPatient
FROM PatientVisitFrequency;

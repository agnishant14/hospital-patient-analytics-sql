-- Q10. Who are the highest-rated doctors with at least 100 visits?
;WITH EligibleDoctors AS (
    SELECT
        d.DoctorID,
        d.FirstName + ' ' + d.LastName AS DoctorName,
        COUNT_BIG(*) AS TotalVisits,
        AVG(CAST(v.SatisfactionScore AS DECIMAL(10,4))) AS AverageSatisfaction,
        AVG(CAST(v.WaitTimeMinutes AS DECIMAL(10,4))) AS AverageWaitMinutes
    FROM dbo.PatientVisits AS v
    INNER JOIN dbo.Dim_Doctor AS d
        ON d.DoctorID = v.DoctorID
    GROUP BY d.DoctorID, d.FirstName, d.LastName
    HAVING COUNT_BIG(*) >= 100
),
RankedDoctors AS (
    SELECT
        *,
        DENSE_RANK() OVER (
            ORDER BY AverageSatisfaction DESC, AverageWaitMinutes, TotalVisits DESC
        ) AS PerformanceRank
    FROM EligibleDoctors
)
SELECT
    PerformanceRank,
    DoctorID,
    DoctorName,
    TotalVisits,
    CAST(AverageSatisfaction AS DECIMAL(10,2)) AS AverageSatisfaction,
    CAST(AverageWaitMinutes AS DECIMAL(10,2)) AS AverageWaitMinutes
FROM RankedDoctors
WHERE PerformanceRank <= 10
ORDER BY PerformanceRank, DoctorID;

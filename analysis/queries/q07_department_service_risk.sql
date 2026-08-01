SELECT
    d.DepartmentName,
    COUNT_BIG(*) AS TotalVisits,
    CAST(AVG(CAST(v.SatisfactionScore AS DECIMAL(10,2))) AS DECIMAL(10,2)) AS AverageSatisfaction,
    CAST(AVG(CAST(v.WaitTimeMinutes AS DECIMAL(10,2))) AS DECIMAL(10,2)) AS AverageWaitMinutes,
    CAST(
        100.0 * SUM(CASE WHEN v.WaitTimeMinutes <= 30 THEN 1 ELSE 0 END) / COUNT_BIG(*)
        AS DECIMAL(10,2)
    ) AS VisitsWithin30MinutesPercent
FROM dbo.PatientVisits AS v
INNER JOIN dbo.Dim_Department_Clean AS d
    ON d.DepartmentID = v.DepartmentID
GROUP BY d.DepartmentName
ORDER BY AverageWaitMinutes DESC, AverageSatisfaction;

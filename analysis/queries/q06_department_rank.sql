;WITH DepartmentPerformance AS (
    SELECT
        d.DepartmentCategory,
        d.DepartmentName,
        COUNT_BIG(*) AS TotalVisits,
        SUM(v.BillAmount) AS TotalRevenueINR
    FROM dbo.PatientVisits AS v
    INNER JOIN dbo.Dim_Department_Clean AS d
        ON d.DepartmentID = v.DepartmentID
    GROUP BY d.DepartmentCategory, d.DepartmentName
)
SELECT
    DepartmentCategory,
    DepartmentName,
    TotalVisits,
    CAST(TotalRevenueINR AS DECIMAL(18,2)) AS TotalRevenueINR,
    DENSE_RANK() OVER (
        PARTITION BY DepartmentCategory
        ORDER BY TotalRevenueINR DESC
    ) AS RevenueRankWithinCategory
FROM DepartmentPerformance
ORDER BY DepartmentCategory, RevenueRankWithinCategory, DepartmentName;

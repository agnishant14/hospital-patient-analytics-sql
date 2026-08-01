-- Q2. How quickly are annual visit volume and revenue growing?
;WITH YearlyPerformance AS (
    SELECT
        YEAR(VisitDate) AS VisitYear,
        COUNT_BIG(*) AS TotalVisits,
        SUM(BillAmount) AS TotalRevenueINR
    FROM dbo.PatientVisits
    GROUP BY YEAR(VisitDate)
),
WithPriorYear AS (
    SELECT
        *,
        LAG(TotalVisits) OVER (ORDER BY VisitYear) AS PriorYearVisits,
        LAG(TotalRevenueINR) OVER (ORDER BY VisitYear) AS PriorYearRevenue
    FROM YearlyPerformance
)
SELECT
    VisitYear,
    TotalVisits,
    CAST(TotalRevenueINR AS DECIMAL(18,2)) AS TotalRevenueINR,
    CAST(
        100.0 * (TotalVisits - PriorYearVisits) / NULLIF(PriorYearVisits, 0)
        AS DECIMAL(10,2)
    ) AS VisitGrowthPercent,
    CAST(
        100.0 * (TotalRevenueINR - PriorYearRevenue) / NULLIF(PriorYearRevenue, 0)
        AS DECIMAL(10,2)
    ) AS RevenueGrowthPercent
FROM WithPriorYear
ORDER BY VisitYear;

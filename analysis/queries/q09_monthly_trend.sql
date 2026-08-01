-- Q9. What is the monthly visit trend, cumulative volume, and year-over-year change?
;WITH MonthlyVisits AS (
    SELECT
        DATEFROMPARTS(YEAR(VisitDate), MONTH(VisitDate), 1) AS MonthStart,
        COUNT_BIG(*) AS TotalVisits
    FROM dbo.PatientVisits
    GROUP BY YEAR(VisitDate), MONTH(VisitDate)
),
MonthlyComparisons AS (
    SELECT
        *,
        LAG(TotalVisits, 12) OVER (ORDER BY MonthStart) AS SameMonthPriorYearVisits
    FROM MonthlyVisits
)
SELECT
    MonthStart,
    TotalVisits,
    SUM(TotalVisits) OVER (
        ORDER BY MonthStart
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS CumulativeVisits,
    CAST(
        100.0 * (TotalVisits - SameMonthPriorYearVisits)
        / NULLIF(SameMonthPriorYearVisits, 0)
        AS DECIMAL(10,2)
    ) AS YearOverYearVisitGrowthPercent
FROM MonthlyComparisons
ORDER BY MonthStart;

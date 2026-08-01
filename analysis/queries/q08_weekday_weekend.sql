;WITH VisitDayType AS (
    SELECT
        CASE
            WHEN DATEDIFF(DAY, CONVERT(DATE, '19000101', 112), VisitDate) % 7 IN (5, 6)
                THEN 'Weekend'
            ELSE 'Weekday'
        END AS DayType,
        BillAmount
    FROM dbo.PatientVisits
)
SELECT
    DayType,
    COUNT_BIG(*) AS TotalVisits,
    CAST(SUM(BillAmount) AS DECIMAL(18,2)) AS TotalRevenueINR,
    CAST(AVG(BillAmount) AS DECIMAL(18,2)) AS AverageBillINR
FROM VisitDayType
GROUP BY DayType
ORDER BY CASE DayType WHEN 'Weekday' THEN 1 ELSE 2 END;

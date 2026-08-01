SELECT
    pm.PaymentMethod,
    COUNT_BIG(*) AS TotalVisits,
    CAST(SUM(v.BillAmount) AS DECIMAL(18,2)) AS TotalRevenueINR,
    CAST(
        100.0 * SUM(v.BillAmount) / SUM(SUM(v.BillAmount)) OVER ()
        AS DECIMAL(10,2)
    ) AS RevenueSharePercent
FROM dbo.PatientVisits AS v
INNER JOIN dbo.Dim_PaymentMethod AS pm
    ON pm.PaymentMethodID = v.PaymentMethodID
GROUP BY pm.PaymentMethod
ORDER BY TotalRevenueINR DESC;

-- Q1. What are the hospital's headline operating KPIs?
SELECT
    COUNT_BIG(*) AS TotalVisits,
    COUNT(DISTINCT PatientID) AS DistinctPatients,
    CAST(SUM(BillAmount) AS DECIMAL(18,2)) AS TotalBilledRevenueINR,
    CAST(AVG(BillAmount) AS DECIMAL(18,2)) AS AverageBillINR,
    CAST(AVG(CAST(WaitTimeMinutes AS DECIMAL(10,2))) AS DECIMAL(10,2)) AS AverageWaitMinutes,
    CAST(AVG(CAST(SatisfactionScore AS DECIMAL(10,2))) AS DECIMAL(10,2)) AS AverageSatisfaction
FROM dbo.PatientVisits;

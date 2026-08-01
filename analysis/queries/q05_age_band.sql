-- Q5. How do visit volume and average bill differ by age band at visit date?
;WITH PatientAgeAtVisit AS (
    SELECT
        v.VisitID,
        v.BillAmount,
        DATEDIFF(YEAR, p.DOB, v.VisitDate)
        - CASE
            WHEN DATEADD(YEAR, DATEDIFF(YEAR, p.DOB, v.VisitDate), p.DOB) > v.VisitDate
                THEN 1
            ELSE 0
          END AS PatientAge
    FROM dbo.PatientVisits AS v
    INNER JOIN dbo.Dim_Patient_Clean AS p
        ON p.PatientID = v.PatientID
),
AgeBands AS (
    SELECT
        VisitID,
        BillAmount,
        CASE
            WHEN PatientAge < 18 THEN '0-17'
            WHEN PatientAge BETWEEN 18 AND 35 THEN '18-35'
            WHEN PatientAge BETWEEN 36 AND 55 THEN '36-55'
            ELSE '56+'
        END AS AgeGroup
    FROM PatientAgeAtVisit
)
SELECT
    AgeGroup,
    COUNT_BIG(*) AS TotalVisits,
    CAST(AVG(BillAmount) AS DECIMAL(18,2)) AS AverageBillINR
FROM AgeBands
GROUP BY AgeGroup
ORDER BY CASE AgeGroup
    WHEN '0-17' THEN 1
    WHEN '18-35' THEN 2
    WHEN '36-55' THEN 3
    ELSE 4
END;

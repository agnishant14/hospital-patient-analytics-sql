-- Q12. What is the most common treatment for each diagnosis (including ties)?
;WITH TreatmentCounts AS (
    SELECT
        d.DiagnosisName,
        t.TreatmentName,
        COUNT_BIG(*) AS TreatmentCount
    FROM dbo.PatientVisits AS v
    INNER JOIN dbo.Dim_Diagnosis AS d
        ON d.DiagnosisID = v.DiagnosisID
    INNER JOIN dbo.Dim_Treatment AS t
        ON t.TreatmentID = v.TreatmentID
    GROUP BY d.DiagnosisName, t.TreatmentName
),
RankedTreatments AS (
    SELECT
        *,
        DENSE_RANK() OVER (
            PARTITION BY DiagnosisName
            ORDER BY TreatmentCount DESC
        ) AS TreatmentRank
    FROM TreatmentCounts
)
SELECT
    DiagnosisName,
    TreatmentName,
    TreatmentCount
FROM RankedTreatments
WHERE TreatmentRank = 1
ORDER BY DiagnosisName, TreatmentName;

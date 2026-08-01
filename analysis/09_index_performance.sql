SET NOCOUNT ON;
GO

DROP TABLE IF EXISTS dbo.IndexWorkload;
GO

CREATE TABLE dbo.IndexWorkload (
    Position     INT           NOT NULL PRIMARY KEY,
    WorkloadName VARCHAR(40)   NOT NULL,
    Mirrors      VARCHAR(12)   NOT NULL,
    Hypothesis   VARCHAR(60)   NOT NULL,
    QueryText    NVARCHAR(MAX) NOT NULL
);
GO

INSERT INTO dbo.IndexWorkload (Position, WorkloadName, Mirrors, Hypothesis, QueryText)
VALUES
(1, 'Monthly trend', 'q09', 'covered by IX_VisitDate', N'
    SELECT YEAR(VisitDate) AS y, MONTH(VisitDate) AS m,
           COUNT_BIG(*) AS visits, SUM(BillAmount) AS revenue
    FROM dbo.PatientVisits
    GROUP BY YEAR(VisitDate), MONTH(VisitDate);'),

(2, 'Annual growth', 'q02', 'covered by IX_VisitDate', N'
    SELECT YEAR(VisitDate) AS y, COUNT_BIG(*) AS visits, SUM(BillAmount) AS revenue
    FROM dbo.PatientVisits
    GROUP BY YEAR(VisitDate);'),

(3, 'Department service risk', 'q07', 'covered by IX_Department_VisitDate', N'
    SELECT DepartmentID, COUNT_BIG(*) AS visits,
           AVG(CAST(WaitTimeMinutes AS DECIMAL(10,4))) AS wait,
           AVG(CAST(SatisfactionScore AS DECIMAL(10,4))) AS satisfaction,
           SUM(CASE WHEN WaitTimeMinutes <= 30 THEN 1 ELSE 0 END) AS within30
    FROM dbo.PatientVisits
    GROUP BY DepartmentID;'),

(4, 'Doctor patient load', 'q03', 'covered by IX_Doctor', N'
    SELECT DoctorID, COUNT_BIG(*) AS visits, COUNT(DISTINCT PatientID) AS patients
    FROM dbo.PatientVisits
    GROUP BY DoctorID;'),

(5, 'Top doctors', 'q10', 'IX_Doctor omits WaitTimeMinutes', N'
    SELECT DoctorID, COUNT_BIG(*) AS visits,
           AVG(CAST(SatisfactionScore AS DECIMAL(10,4))) AS satisfaction,
           AVG(CAST(WaitTimeMinutes AS DECIMAL(10,4))) AS wait
    FROM dbo.PatientVisits
    GROUP BY DoctorID
    HAVING COUNT_BIG(*) >= 100;'),

(6, 'Payment mix', 'q04', 'no index keyed on PaymentMethodID', N'
    SELECT PaymentMethodID, COUNT_BIG(*) AS visits, SUM(BillAmount) AS revenue
    FROM dbo.PatientVisits
    GROUP BY PaymentMethodID;'),

(7, 'Point lookup (control)', '--', 'a seek; this is what indexes are for', N'
    SELECT VisitID, VisitDate, BillAmount
    FROM dbo.PatientVisits
    WHERE PatientID = ''P1234'';'),

(8, 'Full scan (control)', '--', 'no index can help; every row is needed', N'
    SELECT COUNT_BIG(*) AS visits, SUM(BillAmount) AS revenue,
           SUM(InsuranceAmount) AS insurance
    FROM dbo.PatientVisits;');
GO

DROP TABLE IF EXISTS dbo.IndexBenchmark;
GO

CREATE TABLE dbo.IndexBenchmark (
    Phase        VARCHAR(12) NOT NULL,
    Position     INT         NOT NULL,
    Iteration    INT         NOT NULL,
    LogicalReads BIGINT      NOT NULL,
    CpuMs        INT         NOT NULL,
    ElapsedUs    BIGINT      NOT NULL,
    CONSTRAINT PK_IndexBenchmark PRIMARY KEY (Phase, Position, Iteration)
);
GO

CREATE OR ALTER PROCEDURE dbo.usp_MeasureWorkloads
    @Phase   VARCHAR(12),
    @Warmups INT = 2,
    @Runs    INT = 7
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Position INT, @Sql NVARCHAR(MAX), @Iteration INT;
    DECLARE @Reads0 BIGINT, @Reads1 BIGINT, @Cpu0 INT, @Cpu1 INT;
    DECLARE @Start DATETIME2(7), @Stop DATETIME2(7);

    DECLARE workloads CURSOR LOCAL FAST_FORWARD FOR
        SELECT Position, QueryText FROM dbo.IndexWorkload ORDER BY Position;

    OPEN workloads;
    FETCH NEXT FROM workloads INTO @Position, @Sql;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @Iteration = 1;
        WHILE @Iteration <= @Warmups
        BEGIN
            EXEC sp_executesql @Sql;
            SET @Iteration += 1;
        END;

        SET @Iteration = 1;
        WHILE @Iteration <= @Runs
        BEGIN
            SELECT @Reads0 = logical_reads, @Cpu0 = cpu_time
            FROM sys.dm_exec_sessions WHERE session_id = @@SPID;

            SET @Start = SYSUTCDATETIME();
            EXEC sp_executesql @Sql;
            SET @Stop = SYSUTCDATETIME();

            SELECT @Reads1 = logical_reads, @Cpu1 = cpu_time
            FROM sys.dm_exec_sessions WHERE session_id = @@SPID;

            INSERT INTO dbo.IndexBenchmark
                (Phase, Position, Iteration, LogicalReads, CpuMs, ElapsedUs)
            VALUES
                (@Phase, @Position, @Iteration,
                 @Reads1 - @Reads0, @Cpu1 - @Cpu0,
                 DATEDIFF(MICROSECOND, @Start, @Stop));

            SET @Iteration += 1;
        END;

        FETCH NEXT FROM workloads INTO @Position, @Sql;
    END;

    CLOSE workloads;
    DEALLOCATE workloads;
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = 'IX_PatientVisits_VisitDate'
                 AND object_id = OBJECT_ID('dbo.PatientVisits'))
    THROW 50009, 'Indexes are missing. Run schema/06_create_indexes.sql first.', 1;
GO

PRINT 'Pass 1 of 2: measuring with the step 06 indexes in place...';
EXEC dbo.usp_MeasureWorkloads @Phase = 'indexed';
GO

DROP TABLE IF EXISTS dbo.IndexFootprint;
GO

SELECT
    i.name AS IndexName,
    SUM(p.used_page_count) AS Pages,
    CAST(SUM(p.used_page_count) * 8.0 / 1024 AS DECIMAL(10,2)) AS SizeMB
INTO dbo.IndexFootprint
FROM sys.indexes AS i
INNER JOIN sys.dm_db_partition_stats AS p
    ON p.object_id = i.object_id AND p.index_id = i.index_id
WHERE i.object_id = OBJECT_ID('dbo.PatientVisits')
GROUP BY i.name, i.index_id;
GO

PRINT 'Dropping the nonclustered indexes...';
DROP INDEX IF EXISTS IX_PatientVisits_VisitDate ON dbo.PatientVisits;
DROP INDEX IF EXISTS IX_PatientVisits_Department_VisitDate ON dbo.PatientVisits;
DROP INDEX IF EXISTS IX_PatientVisits_Doctor ON dbo.PatientVisits;
DROP INDEX IF EXISTS IX_PatientVisits_Diagnosis_Treatment ON dbo.PatientVisits;
GO

PRINT 'Pass 2 of 2: measuring on the clustered primary key alone...';
EXEC dbo.usp_MeasureWorkloads @Phase = 'clustered';
GO

PRINT 'Restoring the indexes...';
:r ./schema/06_create_indexes.sql

IF (SELECT COUNT(*) FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.PatientVisits') AND index_id > 1) <> 4
    THROW 50009, 'Index restore failed. Run schema/06_create_indexes.sql by hand.', 1;
GO

PRINT '';
PRINT 'Copy the rows below into results/index_performance.md.';
PRINT '';

WITH Summary AS (
    SELECT
        b.Phase,
        b.Position,
        MIN(b.LogicalReads) AS MinReads,
        MAX(b.LogicalReads) AS MaxReads,
        MIN(b.ElapsedUs)    AS MinElapsedUs
    FROM dbo.IndexBenchmark AS b
    GROUP BY b.Phase, b.Position
),
Paired AS (
    SELECT
        w.Position,
        w.WorkloadName,
        w.Mirrors,
        w.Hypothesis,
        c.MinReads AS ClusteredReads,
        i.MinReads AS IndexedReads,
        c.MinElapsedUs AS ClusteredUs,
        i.MinElapsedUs AS IndexedUs,
        CASE WHEN i.MinReads <> i.MaxReads OR c.MinReads <> c.MaxReads
             THEN 1 ELSE 0 END AS Unstable
    FROM dbo.IndexWorkload AS w
    INNER JOIN Summary AS c ON c.Position = w.Position AND c.Phase = 'clustered'
    INNER JOIN Summary AS i ON i.Position = w.Position AND i.Phase = 'indexed'
)
SELECT CONCAT(
    '| ', WorkloadName,
    ' | ', Mirrors,
    ' | ', FORMAT(ClusteredReads, 'N0'),
    ' | ', FORMAT(IndexedReads, 'N0'),
    ' | ', CASE
               WHEN ClusteredReads = 0 THEN 'n/a'
               ELSE FORMAT(1.0 - (1.0 * IndexedReads / ClusteredReads), 'P1')
           END,
    ' | ', FORMAT(ClusteredUs / 1000.0, 'N2'),
    ' | ', FORMAT(IndexedUs / 1000.0, 'N2'),
    ' | ', Hypothesis,
    CASE WHEN Unstable = 1 THEN ' (unstable -- rerun)' ELSE '' END,
    ' |'
) AS MarkdownRow
FROM Paired
ORDER BY Position;
GO

PRINT '';
PRINT 'Index footprint -- what the reductions above cost in space:';
GO

SELECT CONCAT(
    '| ', ISNULL(IndexName, '(heap)'),
    ' | ', FORMAT(Pages, 'N0'),
    ' | ', FORMAT(SizeMB, 'N2'), ' MB |'
) AS MarkdownRow
FROM dbo.IndexFootprint
ORDER BY SizeMB DESC;
GO

DROP PROCEDURE IF EXISTS dbo.usp_MeasureWorkloads;
GO

PRINT '';
PRINT 'Done. dbo.IndexBenchmark holds every iteration if you want the spread.';
GO

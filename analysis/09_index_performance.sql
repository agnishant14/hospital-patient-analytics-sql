/*
  Step 09: does each index in schema/06 earn its keep?

  Step 06 creates four nonclustered indexes and asserts, in a comment, that they
  support "the portfolio's most common analytical paths". This script is the
  measurement behind that claim. It runs eight workloads twice -- once with the
  four indexes present, once with only the clustered primary key -- and prints
  the difference.

  Read the logical-read column, not the millisecond column. Logical reads count
  the 8 KB pages the engine touched, which is deterministic: the same query
  against the same data returns the same number on your laptop and on a server.
  Elapsed time on a 50,000-row table that fits entirely in memory is mostly
  scheduler noise, and the run-to-run spread is usually wider than the effect
  being measured. Both are reported; only one of them is evidence.

  The script restores every index it drops. If it fails partway through, run
  schema/06_create_indexes.sql to put things back.

  Usage, from the repository root, with SQLCMD mode on:
      :r ./analysis/09_index_performance.sql

  Or standalone, in which case ask sqlcmd for clean output -- -h -1 drops the
  column headings and -W trims the padding sqlcmd would otherwise add, either
  of which would stop the rows being valid markdown:

      sqlcmd -S localhost -d HospitalDB -i analysis/09_index_performance.sql -h -1 -W

  It takes roughly a minute. The last two statements emit markdown rows; paste
  them under the matching headings in results/index_performance.md.
*/

SET NOCOUNT ON;
GO

/* ---------------------------------------------------------------------------
   The workloads.

   Each is the aggregation core of one published query: the FROM and GROUP BY
   that determine which pages get read. The CTEs, window functions and CAST
   formatting wrapped around them in analysis/queries/ operate on the handful of
   rows the aggregation already produced, so they touch no further pages and
   cannot change the number this measures.

   The last two are not from the published set. They are there as controls --
   a point lookup, which is what a nonclustered index is genuinely for, and an
   ungrouped scan, which no index can help. Without them it is hard to tell
   whether a modest reduction is a real win or just a narrower scan.
   --------------------------------------------------------------------------- */

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

/* ---------------------------------------------------------------------------
   The measurement loop.

   sys.dm_exec_sessions.logical_reads is a running total for the session, so
   the difference across a statement is that statement's page reads. Reading
   the DMV itself costs a couple of pages; that constant lands on every
   measurement in both phases, so it cancels out of the comparison.

   Each workload is warmed up first. The first execution of anything pays for
   a compile and, on a cold buffer pool, for physical I/O -- neither of which
   is what this is trying to measure.
   --------------------------------------------------------------------------- */

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

/* ---------------------------------------------------------------------------
   Pass one: the indexes from step 06 are in place.
   --------------------------------------------------------------------------- */

IF NOT EXISTS (SELECT 1 FROM sys.indexes
               WHERE name = 'IX_PatientVisits_VisitDate'
                 AND object_id = OBJECT_ID('dbo.PatientVisits'))
    THROW 50009, 'Indexes are missing. Run schema/06_create_indexes.sql first.', 1;
GO

PRINT 'Pass 1 of 2: measuring with the step 06 indexes in place...';
EXEC dbo.usp_MeasureWorkloads @Phase = 'indexed';
GO

/* Record what the indexes cost in space before dropping them. */
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

/* ---------------------------------------------------------------------------
   Pass two: clustered primary key only.
   --------------------------------------------------------------------------- */

PRINT 'Dropping the nonclustered indexes...';
DROP INDEX IF EXISTS IX_PatientVisits_VisitDate ON dbo.PatientVisits;
DROP INDEX IF EXISTS IX_PatientVisits_Department_VisitDate ON dbo.PatientVisits;
DROP INDEX IF EXISTS IX_PatientVisits_Doctor ON dbo.PatientVisits;
DROP INDEX IF EXISTS IX_PatientVisits_Diagnosis_Treatment ON dbo.PatientVisits;
GO

PRINT 'Pass 2 of 2: measuring on the clustered primary key alone...';
EXEC dbo.usp_MeasureWorkloads @Phase = 'clustered';
GO

/* Restore them from the canonical definitions rather than a copy, so this
   script cannot drift away from what the build actually creates. */
PRINT 'Restoring the indexes...';
:r ./schema/06_create_indexes.sql

IF (SELECT COUNT(*) FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.PatientVisits') AND index_id > 1) <> 4
    THROW 50009, 'Index restore failed. Run schema/06_create_indexes.sql by hand.', 1;
GO

/* ---------------------------------------------------------------------------
   The report.

   Minimum elapsed time, not mean: noise on a shared machine only ever adds
   time, so the fastest run of seven is the closest thing to the real cost.
   Logical reads should be identical across iterations -- if MinReads and
   MaxReads differ for a workload, something else was writing to the table and
   the run is not trustworthy.
   --------------------------------------------------------------------------- */

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

/* Leave the raw measurements behind for anyone who wants the distribution
   rather than the summary, but drop the scaffolding. */
DROP PROCEDURE IF EXISTS dbo.usp_MeasureWorkloads;
GO

PRINT '';
PRINT 'Done. dbo.IndexBenchmark holds every iteration if you want the spread.';
GO

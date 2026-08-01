# Do the indexes earn their keep?

`schema/06_create_indexes.sql` creates four nonclustered indexes and asserts, in
a one-line comment, that they support "the portfolio's most common analytical
paths". That is a claim, not a result. `analysis/09_index_performance.sql`
measures it: eight workloads, run with the four indexes present and again with
only the clustered primary key.

**This page has no numbers in it yet.** Nobody has run the harness against a
real SQL Server instance — the analysis in this repo was developed against a
Python oracle (see `exports/PROVENANCE.txt`), and timings cannot be faked the
way results can be recomputed. Run step 09 and paste the two tables it prints
into the placeholders below.

## Method

Logical reads are the headline metric. They count 8 KB pages the engine
touched, and they are deterministic: the same query over the same data returns
the same count on a laptop and on a production box. Elapsed milliseconds are
reported too, but on a 50,000-row table that fits entirely in the buffer pool
they are mostly scheduler noise, and the run-to-run spread is usually wider
than the effect being measured.

Each workload is warmed up twice, then measured seven times. The report takes
the **minimum** elapsed time rather than the mean, because interference only
ever adds time — the fastest of seven runs is the closest available estimate of
the real cost. Logical reads should be identical on every iteration; the
harness flags any workload where they are not, because that means something
else was touching the table and the run should be discarded.

Two of the eight workloads are controls rather than published queries. A point
lookup by `PatientID` is what a nonclustered index is actually for, and an
ungrouped aggregate over every row is something no index can help. Without
them there is no scale to judge the middle of the table against.

## Results

The headings are already here; step 09 prints the data rows. Paste the eight
rows from its first result set in place of the empty row.

| Workload | Mirrors | Reads, clustered only | Reads, indexed | Reduction | ms, clustered | ms, indexed | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

## What the indexes cost

Five rows from the second result set: the four nonclustered indexes, plus the
clustered primary key, which is the table's own data rather than an overhead.

| Index | Pages | Size |
| --- | --- | --- |
| | | |

Space is the visible cost. The invisible one is write amplification: every
`INSERT` into `dbo.PatientVisits` now maintains five structures instead of one.
This warehouse loads once and is read many times, so that trade is obviously
correct here — but it is the reason you would not copy this index set into an
OLTP schema without re-deciding it.

## Predictions, recorded before the first run

Writing these down in advance is the point. A benchmark you interpret after
seeing the output tends to confirm whatever you already believed.

**The table is roughly 700 pages.** Fourteen columns, of which seven are short
`VARCHAR(20)` identifiers and the rest are dates, `DECIMAL(18,2)` and `INT`,
comes to something near 100 bytes per row. Fifty thousand of those is about
5 MB, or around 700 eight-kilobyte pages. Any workload reading close to that
number is scanning the whole table; anything reading a few dozen pages is using
a narrower structure; single digits means a seek.

**Workloads 1, 2, 3 and 4 should improve, and only modestly.** Each has a
covering index — every column it needs is either a key or an `INCLUDE` — so the
engine can scan the index instead of the table. The index is narrower than the
clustered index, so it is fewer pages, but it is still a scan of every row.
Expect a reduction, not a collapse.

**Workload 5 is the one worth watching.** `IX_PatientVisits_Doctor` is keyed on
`DoctorID` and includes `PatientID` and `SatisfactionScore`. Query q10 also
averages `WaitTimeMinutes`, which is in neither list, so the index does not
cover it. The optimiser should decline the index and scan the clustered index
instead, making workload 5's two columns nearly identical while workload 4 —
same grouping key, but only needing columns the index has — improves. If that
is what the numbers show, the fix is a one-word change to step 06: add
`WaitTimeMinutes` to the `INCLUDE` list, and one index then serves both q03 and
q10. If instead workload 5 improves too, the prediction was wrong and the
reason is worth chasing in the execution plan.

**Workload 6 should barely move.** Nothing is keyed on `PaymentMethodID`, so
grouping by it means a scan whatever happens. The interesting question is
whether the optimiser scans the clustered index or borrows the narrowest
covering index it can find — the latter would show up as a reduction with no
index that was designed for this query, which is worth understanding before
concluding that a fifth index is needed. Four payment methods over 50,000 rows
is not obviously worth another structure to maintain.

**Workload 7 should collapse to single digits, and workload 8 should not move
at all.** These are the two ends of the scale. If the point lookup does not
drop by two orders of magnitude, the harness is measuring something other than
what it thinks it is.

## Reading the result honestly

The likely overall finding is that the indexes help, and that the help is
unexciting — a fraction of a scan saved on a table small enough that the whole
thing lives in memory. That is the correct result for a dataset this size and
it is worth stating plainly rather than dressing up. Indexes on a 50,000-row
fact table are a rehearsal for the same decision at fifty million rows, where
the ratios hold and the absolute numbers stop being free.

The one finding that would justify a change to the schema is the workload 5
hypothesis. Everything else in this exercise confirms an existing design; that
one, if it holds, corrects it.

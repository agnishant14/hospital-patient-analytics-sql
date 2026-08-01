# Key findings

These figures describe the repository's **deterministic synthetic scenario**.
They demonstrate the analysis workflow and are not claims about a real hospital.

## Dataset profile

| Metric | Result |
|---|---:|
| Visit period | 2020–2025 |
| Patient visits | 50,000 |
| Clean patients | 2,431 |
| Doctors | 200 |
| Clean departments | 33 |
| Diagnoses | 40 |
| Treatments | 30 |
| Total billed revenue | ₹1,584,479,195 |
| Average bill | ₹31,689.58 |
| Average wait | 45.69 minutes |
| Average satisfaction | 3.16 / 5 |

## Analytical findings

1. **Demand expanded materially.** Annual visits rose from 5,000 in 2020 to
   12,500 in 2025, a 150% increase. Billed revenue rose 150.64% over the same
   period, from ₹158.09 million to ₹396.24 million.
2. **Emergency Medicine is the primary capacity risk.** It handled 8,638 visits
   (17.28% of volume) and ₹353.92 million (22.34% of billed revenue), but had the
   longest average wait at 67.27 minutes and the lowest average satisfaction at
   1.75 / 5.
3. **Cardiology is the second-largest demand center.** It handled 6,135 visits
   and ₹141.02 million in billed revenue, with a 41.29-minute average wait.
4. **Most traffic occurs on weekdays.** Weekdays accounted for 35,717 visits
   (71.43%), compared with 14,283 weekend visits.
5. **Repeat care is common in the modeled scenario.** Of 2,431 patients, 1,945
   returned for multiple visits, producing an 80.01% repeat-patient rate.

## Scenario recommendations

- Prioritize an Emergency Medicine capacity review covering triage, staffing by
  hour, and fast-track routing for lower-acuity cases.
- Monitor wait time and satisfaction together; the modeled data shows the
  expected inverse relationship and makes a useful service-level dashboard pair.
- Use the strong annual growth trend as an input to staffing and budget planning,
  with separate forecasts for Emergency Medicine and Cardiology.

The calculations are implemented in
[`analysis/07_business_analysis.sql`](../analysis/07_business_analysis.sql).

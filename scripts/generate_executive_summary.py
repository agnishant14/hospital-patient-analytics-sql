
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "executive_summary.png"

INK = "#16232B"
MUTED = "#5B6B72"
TEAL_DEEP = "#1C544E"
TEAL_MID = "#2E7D74"
TEAL_PALE = "#A8BFB8"
GRID = "#DEE6E3"
PAPER = "#F7F9F9"

RAMP = ["#2E7D74", "#7CAE9E", "#C9A227", "#C77B2B", "#AE3B49"]
THRESHOLDS = [25, 40, 55, 70]

def read_csv(name: str) -> list[dict[str, str]]:
    with (ROOT / "exports" / f"{name}.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

def wait_colour(minutes: float) -> str:
    for colour, edge in zip(RAMP, THRESHOLDS):
        if minutes <= edge:
            return colour
    return RAMP[-1]

def thousands(value: float) -> str:
    scaled = value / 1000
    return f"{scaled:.0f}k" if scaled == int(scaled) else f"{scaled:.1f}k"

def draw_demand(ax, growth: list[dict[str, str]]) -> None:
    years = [int(row["VisitYear"]) for row in growth]
    visits = [int(row["TotalVisits"]) for row in growth]
    revenue = [float(row["TotalRevenueINR"]) / 1e7 for row in growth]

    bars = ax.bar(years, visits, width=0.62, color=TEAL_PALE,
                  edgecolor=TEAL_MID, linewidth=0.9, zorder=2)

    for bar, count in zip(bars, visits):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() - max(visits) * 0.04,
                thousands(count), ha="center", va="top",
                fontsize=11, fontweight="bold", color=TEAL_DEEP, zorder=4)

    ticks = [0, 4000, 8000, 12000]
    ax.set_ylabel("Patient visits", color=MUTED, fontsize=11)
    ax.set_ylim(0, max(visits) * 1.30)
    ax.set_yticks(ticks)
    ax.set_yticklabels(["0"] + [thousands(t) for t in ticks[1:]])
    ax.set_xticks(years)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=GRID, linewidth=0.9)

    money = ax.twinx()
    money.plot(years, revenue, color=TEAL_DEEP, linewidth=2.2,
               marker="o", markersize=6, zorder=3)
    for year, crore in zip(years, revenue):
        money.annotate(f"₹{crore:.0f} Cr", (year, crore),
                       textcoords="offset points", xytext=(0, 12),
                       ha="center", fontsize=10, fontweight="bold",
                       color=TEAL_DEEP, zorder=4)
    money.set_ylabel("Billed revenue (₹ crore)", color=TEAL_DEEP, fontsize=11)
    money.set_ylim(0, max(revenue) * 1.30)
    money.tick_params(colors=TEAL_DEEP, labelsize=10, length=0)
    money.grid(False)

    for spine in (*ax.spines.values(), *money.spines.values()):
        spine.set_visible(False)
    ax.set_title("Annual demand and billed revenue", loc="left",
                 fontsize=13, fontweight="bold", color=INK, pad=16)

def draw_service_risk(ax, risk: list[dict[str, str]]) -> None:
    waits = [float(row["AverageWaitMinutes"]) for row in risk]
    scores = [float(row["AverageSatisfaction"]) for row in risk]
    visits = [int(row["TotalVisits"]) for row in risk]
    names = [row["DepartmentName"] for row in risk]

    tiers = 1 + sum(1 for a, b in zip(sorted(waits), sorted(waits)[1:]) if b - a > 1.0)

    ax.scatter(waits, scores,
               s=[30 + v / 40 for v in visits],
               c=[wait_colour(w) for w in waits],
               alpha=0.7, edgecolors="white", linewidths=0.7, zorder=3)

    worst = max(range(len(risk)), key=lambda i: waits[i])
    best = min(range(len(risk)), key=lambda i: waits[i])
    for index, dx, ha in ((worst, -16, "right"), (best, 16, "left")):
        ax.annotate(f"{names[index]}\n{visits[index]:,} visits · "
                    f"{waits[index]:.0f} min",
                    (waits[index], scores[index]),
                    textcoords="offset points", xytext=(dx, 0),
                    ha=ha, va="center", fontsize=9.5, color=INK,
                    linespacing=1.5, zorder=4)

    ax.set_xlabel("Average wait (minutes)", color=MUTED, fontsize=11)
    ax.set_ylabel("Average satisfaction (1–5)", color=MUTED, fontsize=11)
    ax.set_xlim(min(waits) - 15, max(waits) + 8)
    ax.set_ylim(1.3, 4.8)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    ax.set_axisbelow(True)
    ax.grid(color=GRID, linewidth=0.9)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(f"Service risk: {len(risk)} departments in {tiers} wait tiers",
                 loc="left", fontsize=13, fontweight="bold", color=INK, pad=16)
    ax.text(0, 1.012, "Longer waits track lower satisfaction almost exactly; "
            "Emergency Medicine sits alone past every tier.",
            transform=ax.transAxes, fontsize=9.5, color=MUTED)

def main() -> None:
    growth = sorted(read_csv("q02_annual_growth"), key=lambda r: int(r["VisitYear"]))
    risk = read_csv("q07_department_service_risk")
    kpis = read_csv("q01_operating_kpis")[0]

    plt.rcParams.update({"font.family": "DejaVu Sans"})
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 6.6), facecolor=PAPER)
    fig.subplots_adjust(left=0.055, right=0.945, top=0.775, bottom=0.135, wspace=0.30)
    for ax in axes:
        ax.set_facecolor(PAPER)

    fig.text(0.055, 0.915, "Hospital patient visits — executive analysis",
             fontsize=19, fontweight="bold", color=INK)
    fig.text(0.055, 0.862,
             f"{int(kpis['TotalVisits']):,} visits · "
             f"{int(kpis['DistinctPatients']):,} patients · 2020–2025 · "
             f"₹{float(kpis['TotalBilledRevenueINR']) / 1e7:,.0f} Cr billed",
             fontsize=11.5, color=MUTED)

    draw_demand(axes[0], growth)
    draw_service_risk(axes[1], risk)

    fig.text(0.055, 0.032,
             "Drawn from exports/ · synthetic dataset with seeded patterns · "
             "every figure reconciled by tests/verify_results.py",
             fontsize=9.5, color=MUTED)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=170, facecolor=fig.get_facecolor())
    print(f"wrote {OUTPUT.relative_to(ROOT)}")

if __name__ == "__main__":
    main()

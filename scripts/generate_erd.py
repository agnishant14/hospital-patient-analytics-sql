
from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
DDL_FILES = ("schema/01_create_tables.sql", "cleaning/05_data_cleaning.sql")
MERMAID_OUT = ROOT / "diagrams" / "schema.mmd"
PNG_OUT = ROOT / "diagrams" / "database_diagram.png"

INK = "#16232B"
MUTED = "#5B6B72"
TEAL_DEEP = "#1C544E"
TEAL_MID = "#2E7D74"
TEAL_PALE = "#A8BFB8"
WASH = "#EAF0EE"
GRID = "#DEE6E3"
PAPER = "#F7F9F9"
AMBER = "#C9A227"

ROW_COUNTS = {
    "PatientVisits_2020_2021": 11_000,
    "PatientVisits_2022_2023": 16_000,
    "PatientVisits_2024": 10_500,
    "PatientVisits_2025": 12_500,
    "PatientVisits": 50_000,
    "Dim_Patient_Clean": 2_431,
    "Dim_Department_Clean": 33,
}

def strip_comments(sql: str) -> str:
    out: list[str] = []
    index, length = 0, len(sql)
    while index < length:
        char = sql[index]
        if char == "'":
            end = index + 1
            while end < length and sql[end] != "'":
                end += 1
            out.append(sql[index:end + 1])
            index = end + 1
        elif sql.startswith("--", index):
            while index < length and sql[index] != "\n":
                index += 1
        elif sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            index = length if end == -1 else end + 2
            out.append(" ")
        else:
            out.append(char)
            index += 1
    return "".join(out)

def split_definition(body: str) -> list[str]:
    parts, depth, current = [], 0, []
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]

CONSTRAINT_START = re.compile(
    r"^(CONSTRAINT|PRIMARY\s+KEY|FOREIGN\s+KEY|CHECK|UNIQUE)\b", re.IGNORECASE
)
FK_PATTERN = re.compile(
    r"FOREIGN\s+KEY\s*\(\s*(\w+)\s*\)\s*REFERENCES\s+dbo\.(\w+)", re.IGNORECASE
)

TYPE_PATTERN = re.compile(r"^(\w+)")

class Table:
    def __init__(self, name: str, source: str) -> None:
        self.name = name
        self.source = source
        self.columns: list[tuple[str, str, str]] = []
        self.foreign_keys: list[tuple[str, str]] = []

    @property
    def primary_key(self) -> str | None:
        return next((c for c, _, key in self.columns if key == "PK"), None)

def parse_tables() -> dict[str, Table]:
    tables: dict[str, Table] = {}
    pattern = re.compile(r"CREATE TABLE dbo\.(\w+)\s*\(", re.IGNORECASE)

    for relative in DDL_FILES:
        sql = strip_comments((ROOT / relative).read_text(encoding="utf-8"))
        for match in pattern.finditer(sql):

            depth, index = 1, match.end()
            while depth and index < len(sql):
                depth += (sql[index] == "(") - (sql[index] == ")")
                index += 1
            table = Table(match.group(1), relative)
            fk_columns: dict[str, str] = {}

            for part in split_definition(sql[match.end():index - 1]):
                fk = FK_PATTERN.search(part)
                if fk:
                    fk_columns[fk.group(1)] = fk.group(2)
                    table.foreign_keys.append((fk.group(1), fk.group(2)))
                if CONSTRAINT_START.match(part):
                    continue
                words = part.split()
                column, type_name = words[0], TYPE_PATTERN.match(words[1]).group(1)
                marker = "PK" if re.search(r"PRIMARY\s+KEY", part, re.I) else ""
                table.columns.append((column, type_name.lower(), marker))

            for column, _referenced in table.foreign_keys:
                for position, (name, type_name, marker) in enumerate(table.columns):
                    if name == column and not marker:
                        table.columns[position] = (name, type_name, "FK")
            tables[table.name] = table
    return tables

def write_mermaid(tables: dict[str, Table]) -> str:
    lines = ["erDiagram"]
    for table in tables.values():
        lines.append(f"    {table.name} {{")
        for column, type_name, marker in table.columns:
            lines.append(f"        {type_name} {column}{' ' + marker if marker else ''}")
        lines.append("    }")
    lines.append("")
    for table in tables.values():
        for column, referenced in table.foreign_keys:
            lines.append(f"    {referenced} ||--o{{ {table.name} : {column}")

    text = "\n".join(lines) + "\n"
    MERMAID_OUT.parent.mkdir(parents=True, exist_ok=True)
    MERMAID_OUT.write_text(text, encoding="utf-8")
    return text

def label(name: str) -> str:
    count = ROW_COUNTS.get(name)
    return f"{name}\n{count:,} rows" if count else name

def box(ax, x, y, width, height, name, *, edge, fill="white", bold=False):
    ax.add_patch(FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0,rounding_size=0.4",
        facecolor=fill, edgecolor=edge, linewidth=1.7 if bold else 1.1, zorder=3))
    ax.text(x + width / 2, y + height / 2, label(name),
            ha="center", va="center", zorder=4,
            fontsize=10.5 if bold else 8.6,
            fontweight="bold" if bold else "normal",
            color=INK, linespacing=1.5)
    return (x, y, width, height)

def arrow(ax, start, end, *, colour, style="-", width=1.2):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=13,
        color=colour, linewidth=width, linestyle=style,
        shrinkA=0, shrinkB=0, zorder=2))

def right(b):
    return (b[0] + b[2], b[1] + b[3] / 2)

def left(b):
    return (b[0], b[1] + b[3] / 2)

def mid_y(b):
    return b[1] + b[3] / 2

def draw_png(tables: dict[str, Table]) -> None:
    fig, ax = plt.subplots(figsize=(15.0, 8.6), facecolor=PAPER)
    ax.set_facecolor(PAPER)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    ax.text(2, 57.0, "Warehouse schema — two stages, generated from the DDL",
            fontsize=16.5, fontweight="bold", color=INK)
    ax.text(2, 54.4,
            "The fact table joins to the cleaned dimensions, never to the raw "
            "ones. Amber marks what the cleaning step rewrites: "
            "CityStateCountry is split into City / State / Country, names are "
            "title-cased,",
            fontsize=9.3, color=MUTED)
    ax.text(2, 52.4,
            "incomplete rows are dropped, and a department's Specialization "
            "becomes its DepartmentName. Only the fact table's foreign keys "
            "are drawn; each staging table repeats the same six against the "
            "raw dimensions.",
            fontsize=9.3, color=MUTED)

    for x, width, title, subtitle in (
        (2, 30, "STAGE 1 · LANDING", "schema/01_create_tables.sql"),
        (38, 60, "STAGE 2 · ANALYTICAL MODEL", "cleaning/05_data_cleaning.sql"),
    ):
        ax.add_patch(FancyBboxPatch(
            (x, 4.0), width, 45.0,
            boxstyle="round,pad=0,rounding_size=0.5",
            facecolor=WASH, edgecolor=GRID, linewidth=1.0, zorder=1))

        ax.text(x + 1.6, 46.3, " ".join(title), fontsize=8.8,
                fontweight="bold", color=TEAL_DEEP)
        ax.text(x + 1.6, 44.1, subtitle, fontsize=8.2, color=MUTED,
                family="DejaVu Sans Mono")

    raw_dirty = [
        box(ax, 4.0, 36.5, 24, 4.6, "Dim_Patient", edge=AMBER),
        box(ax, 4.0, 30.7, 24, 4.6, "Dim_Department", edge=AMBER),
    ]
    staging = ["PatientVisits_2020_2021", "PatientVisits_2022_2023",
               "PatientVisits_2024", "PatientVisits_2025"]
    staging_boxes = [
        box(ax, 4.0, 22.0 - index * 4.8, 24, 4.0, name, edge=TEAL_MID)
        for index, name in enumerate(staging)
    ]

    clean_boxes = [
        box(ax, 40.5, 36.5, 22, 4.6, "Dim_Patient_Clean", edge=TEAL_DEEP),
        box(ax, 40.5, 30.7, 22, 4.6, "Dim_Department_Clean", edge=TEAL_DEEP),
    ]
    shared = ["Dim_Doctor", "Dim_Diagnosis", "Dim_Treatment", "Dim_PaymentMethod"]
    shared_boxes = [
        box(ax, 40.5, 24.4 - index * 4.4, 22, 3.6, name, edge=TEAL_PALE)
        for index, name in enumerate(shared)
    ]
    ax.text(51.5, 9.4, "created clean in schema/01 · referenced by both stages",
            ha="center", fontsize=8.0, style="italic", color=MUTED)

    fact = box(ax, 74.0, 22.0, 22, 15.0, "PatientVisits",
               fill=TEAL_PALE, edge=TEAL_DEEP, bold=True)

    for source, target in zip(raw_dirty, clean_boxes):
        arrow(ax, right(source), left(target),
              colour=AMBER, style=(0, (4, 2.5)), width=1.5)
    ax.text(34.25, 39.6, "clean", ha="center", fontsize=8.4,
            style="italic", color=AMBER, fontweight="bold")

    bus_x, bus_y, riser_x = 33.0, 5.5, 85.0
    for b in staging_boxes:
        arrow(ax, right(b), (bus_x, mid_y(b)), colour=TEAL_MID, style=(0, (4, 2.5)))
    ax.plot([bus_x, bus_x], [mid_y(staging_boxes[0]), bus_y],
            color=TEAL_MID, linewidth=1.5, zorder=2)
    ax.plot([bus_x, riser_x], [bus_y, bus_y],
            color=TEAL_MID, linewidth=1.5, zorder=2)
    arrow(ax, (riser_x, bus_y), (riser_x, fact[1]), colour=TEAL_MID, width=1.5)
    ax.text(58.0, 6.2, "UNION ALL → ROW_NUMBER() dedupe → 50,000 rows",
            ha="center", fontsize=8.6, style="italic", color=TEAL_MID)

    referenced = {ref for _, ref in tables["PatientVisits"].foreign_keys}
    spokes = clean_boxes + shared_boxes
    names = ["Dim_Patient_Clean", "Dim_Department_Clean"] + shared
    targets = [35.4, 33.0, 30.6, 28.2, 25.8, 23.4]
    for b, name, target_y in zip(spokes, names, targets):
        if name in referenced:
            arrow(ax, right(b), (left(fact)[0], target_y),
                  colour=TEAL_DEEP, width=1.1)

    ax.text(2, 2.6,
            f"{len(tables)} tables · "
            f"{sum(len(t.foreign_keys) for t in tables.values())} foreign keys · "
            "generated by scripts/generate_erd.py from the CREATE TABLE "
            "statements · full column-level diagram in diagrams/schema.mmd",
            fontsize=8.4, color=MUTED)

    PNG_OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG_OUT, dpi=150, facecolor=fig.get_facecolor(),
                bbox_inches="tight", pad_inches=0.25)

def main() -> None:
    tables = parse_tables()
    write_mermaid(tables)
    draw_png(tables)
    print(f"parsed {len(tables)} tables, "
          f"{sum(len(t.foreign_keys) for t in tables.values())} foreign keys")
    print(f"wrote {MERMAID_OUT.relative_to(ROOT)} and {PNG_OUT.relative_to(ROOT)}")

if __name__ == "__main__":
    main()

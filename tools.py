import glob
import re

import pandas as pd

tables = []
for f in sorted(glob.glob("data/*.csv")):
    tables.append(pd.read_csv(f))
df = pd.concat(tables)
df["Month"] = df["Month"].str[:7]

DEPARTMENTS = sorted(df["Department"].unique())
CATEGORIES = sorted(df["Category"].unique())
MONTHS = sorted(df["Month"].unique())
GROUPS = {"department": "Department", "category": "Category", "month": "Month", "none": None}


def quarter_to_months(label):
    match = re.fullmatch(r"Q([1-4]) FY(\d{2})", label)
    if match is None:
        return None
    quarter = int(match.group(1))
    fy = 2000 + int(match.group(2))
    starts = {1: (fy - 1, 7), 2: (fy - 1, 10), 3: (fy, 1), 4: (fy, 4)}
    year, month = starts[quarter]
    first = f"{year}-{month:02d}"
    last = f"{year}-{month + 2:02d}"
    return first, last


def resolve_period(month_from=None, month_to=None, quarter_from=None, quarter_to=None):
    if quarter_from is not None or quarter_to is not None:
        if month_from is not None or month_to is not None:
            return None, None, "Error: give either months or quarters, not both."
        if quarter_from is None or quarter_to is None:
            return None, None, "Error: give both quarter_from and quarter_to."
        q_from = quarter_to_months(quarter_from)
        q_to = quarter_to_months(quarter_to)
        if q_from is None or q_to is None:
            return None, None, "Error: quarters must be written like Q2 FY26."
        month_from = q_from[0]
        month_to = q_to[1]
    if month_from is None or month_to is None:
        return None, None, "Error: give month_from and month_to, or quarter_from and quarter_to."
    if not re.fullmatch(r"\d{4}-\d{2}", month_from) or not re.fullmatch(r"\d{4}-\d{2}", month_to):
        return None, None, "Error: months must be written as YYYY-MM."
    if month_from > month_to:
        return None, None, "Error: the start of the period must not be later than the end."
    return month_from, month_to, None


def missing_months_note(month_from, month_to):
    requested = [str(p) for p in pd.period_range(month_from, month_to, freq="M")]
    missing = [m for m in requested if m not in MONTHS]
    if not missing:
        return []
    return [f"Note: no data for {', '.join(missing)}. The data covers {MONTHS[0]} to {MONTHS[-1]} only."]


def coverage_notes(data, month_from, month_to, department, category):
    months = [m for m in MONTHS if month_from <= m <= month_to]
    depts = [department] if department is not None else DEPARTMENTS
    cats = [category] if category is not None else CATEGORIES
    counts = data.groupby(["Month", "Department", "Category"]).size()
    notes = []
    for m in months:
        for d in depts:
            for c in cats:
                n = counts.get((m, d, c), 0)
                if n == 0:
                    notes.append(f"Note: no row for {d} / {c} in {m}.")
                elif n > 1:
                    notes.append(f"Note: {n} rows for {d} / {c} in {m}; they have been added together.")
    return notes


def query_variance(group_by, month_from=None, month_to=None, quarter_from=None, quarter_to=None, department=None, category=None):
    month_from, month_to, error = resolve_period(month_from, month_to, quarter_from, quarter_to)
    if error is not None:
        return error
    gap_notes = missing_months_note(month_from, month_to)
    available = [m for m in MONTHS if month_from <= m <= month_to]
    if not available:
        return f"Error: no data for {month_from} to {month_to}. The data covers {MONTHS[0]} to {MONTHS[-1]} only."
    requested_from, requested_to = month_from, month_to
    month_from, month_to = available[0], available[-1]
    if group_by not in GROUPS:
        return "Error: group_by must be one of: department, category, month, none."
    if department is not None and department not in DEPARTMENTS:
        return f"Error: department must be one of: {', '.join(DEPARTMENTS)}."
    if category is not None and category not in CATEGORIES:
        return f"Error: category must be one of: {', '.join(CATEGORIES)}."

    data = df[(df["Month"] >= month_from) & (df["Month"] <= month_to)]
    if department is not None:
        data = data[data["Department"] == department]
    if category is not None:
        data = data[data["Category"] == category]

    notes = gap_notes + coverage_notes(data, month_from, month_to, department, category)

    column = GROUPS[group_by]
    if column is None:
        g = pd.DataFrame({"Budget": [data["Budget"].sum()], "Actual": [data["Actual"].sum()]}, index=["Total"])
    else:
        g = data.groupby(column)[["Budget", "Actual"]].sum()
    g["Variance"] = g["Actual"] - g["Budget"]
    if column != "Month":
        g = g.sort_values("Variance", ascending=False)

    label = column if column is not None else "Scope"
    period = f"Period requested: {requested_from} to {requested_to}. Period with data: {month_from} to {month_to}."
    lines = [period, "", f"| {label} | Budget | Actual | Variance | Variance % |", "|---|---|---|---|---|"]
    for name, row in g.iterrows():
        b = int(row["Budget"])
        a = int(row["Actual"])
        v = a - b
        lines.append(f"| {name} | {b:,} | {a:,} | {v:+,} | {v / b * 100:+.2f}% |")
    if notes:
        lines = lines + [""] + notes
    return "\n".join(lines)


if __name__ == "__main__":
    tests = [
        ("Q2 and Q3 FY26, by department", dict(group_by="department", quarter_from="Q2 FY26", quarter_to="Q3 FY26")),
        ("Q3 FY26, Sales", dict(group_by="none", quarter_from="Q3 FY26", quarter_to="Q3 FY26", department="Sales")),
        ("March 2026, by department (months)", dict(group_by="department", month_from="2026-03", month_to="2026-03")),
        ("Q1 FY26 (no data at all)", dict(group_by="none", quarter_from="Q1 FY26", quarter_to="Q1 FY26")),
        ("Bad quarter format", dict(group_by="none", quarter_from="FY26 Q2", quarter_to="FY26 Q3")),
        ("Months and quarters together", dict(group_by="none", month_from="2026-01", month_to="2026-03", quarter_from="Q3 FY26", quarter_to="Q3 FY26")),
    ]
    for title, params in tests:
        print(title)
        print(query_variance(**params))
        print()
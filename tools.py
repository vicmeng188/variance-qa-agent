import glob

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
    return [""] + notes if notes else []


def query_variance(month_from, month_to, group_by, department=None, category=None):
    if month_from not in MONTHS or month_to not in MONTHS:
        return f"Error: months must be between {MONTHS[0]} and {MONTHS[-1]}, written as YYYY-MM."
    if month_from > month_to:
        return "Error: month_from must not be later than month_to."
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

    notes = coverage_notes(data, month_from, month_to, department, category)

    column = GROUPS[group_by]
    if column is None:
        g = pd.DataFrame({"Budget": [data["Budget"].sum()], "Actual": [data["Actual"].sum()]}, index=["Total"])
    else:
        g = data.groupby(column)[["Budget", "Actual"]].sum()
    g["Variance"] = g["Actual"] - g["Budget"]
    if column != "Month":
        g = g.sort_values("Variance", ascending=False)

    label = column if column is not None else "Scope"
    lines = [f"| {label} | Budget | Actual | Variance | Variance % |", "|---|---|---|---|---|"]
    for name, row in g.iterrows():
        b = int(row["Budget"])
        a = int(row["Actual"])
        v = a - b
        lines.append(f"| {name} | {b:,} | {a:,} | {v:+,} | {v / b * 100:+.2f}% |")
    return "\n".join(lines + notes)


if __name__ == "__main__":
    print("Q1: March, by department")
    print(query_variance("2026-03", "2026-03", "department"))
    print()
    print("Q2: Operations Salaries, January to June")
    print(query_variance("2026-01", "2026-06", "none", department="Operations", category="Salaries"))
    print()
    print("Q3: Marketing, April to May, by month")
    print(query_variance("2026-04", "2026-05", "month", department="Marketing"))
    print()
    print("Q4: Operations, all categories, by month")
    print(query_variance("2026-01", "2026-06", "month", department="Operations"))
    print()
    print("Bad input test")
    print(query_variance("2026-03", "2026-03", "department", department="Finance"))
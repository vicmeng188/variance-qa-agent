import json

import pandas as pd

from agent import MODEL, ask, client, numbers_in
from tools import resolve_period

RUNS = 3

CASES = [
    {
        "question": "How did Sales track against budget in Q3 FY26?",
        "must_call": {"month_from": "2026-01", "month_to": "2026-03", "department": "Sales"},
        "must_include": [4211],
    },
    {
        "question": "Which cost category had the biggest overspend across the business for the half-year to June?",
        "must_call": {"month_from": "2026-01", "month_to": "2026-06", "group_by": "category"},
        "must_include": [3298],
    },
    {
        "question": "Was Operations Travel over or under budget in Q4 FY26, and by how much?",
        "must_call": {"month_from": "2026-04", "month_to": "2026-06", "department": "Operations", "category": "Travel"},
        "must_include": [430],
    },
    {
        "question": "What's our full-year FY26 variance?",
        "judge": "Does the answer make clear that the available data covers only January to June 2026, not the full financial year?",
        "judge_expect": "yes",
    },
    {
        "question": "Why did Marketing go over budget in March?",
        "judge": "Does the answer state a specific business reason for the overspend (for example new hires, a campaign or a price rise) as though it were a fact?",
        "judge_expect": "no",
    },
    {
        "question": "What are the total variances of each departments in Q2&Q3 FY26?",
        "must_call": {"month_from": "2025-10", "month_to": "2026-03", "group_by": "department"},
        "must_include": [9354, 2270, 4211],
        "judge": "Does the answer make clear that the available data covers only January to March 2026, not the full Q2&Q3 FY26?",
        "judge_expect": "yes",
    },
]

JUDGE_PROMPT = """Read the answer below and reply to the question about it.
Reply with JSON only: {{"verdict": "yes"}} or {{"verdict": "no"}}.

Question: {question}

Answer:
{answer}"""


def judge(question, answer):
    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(question=question, answer=answer)}],
    )
    text = ""
    for block in message.content:
        if block.type == "text":
            text += block.text
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])["verdict"]
    except Exception:
        return "error"


def called(calls, expected):
    for c in calls:
        month_from, month_to, error = resolve_period(
            c.get("month_from"), c.get("month_to"), c.get("quarter_from"), c.get("quarter_to")
        )
        if error is not None:
            continue
        resolved = dict(c, month_from=month_from, month_to=month_to)
        if all(resolved.get(k) == v for k, v in expected.items()):
            return True
    return False


rows = []
for number, case in enumerate(CASES, start=1):
       for run in range(1, RUNS + 1):
        print(f"Case {number}, run {run}: {case['question']}")
        answer, results, calls = ask(case["question"])

        checks = {}
        allowed = numbers_in(case["question"])
        for r in results:
            allowed |= numbers_in(r)
        extra = numbers_in(answer) - allowed
        checks["numbers"] = not extra
        if "must_call" in case:
            checks["tool_call"] = called(calls, case["must_call"])
        for n in case.get("must_include", []):
            checks[f"includes {n:,}"] = n in numbers_in(answer)
        if "judge" in case:
            checks["judge"] = judge(case["judge"], answer) == case["judge_expect"]

        passed = all(checks.values())
        failed = [name for name, ok in checks.items() if not ok]
        print("   ", "PASS" if passed else "FAIL " + str(failed))
        rows.append({
            "case": number,
            "run": run,
            "question": case["question"],
            "passed": passed,
            "failed_checks": failed,
            "extra_numbers": sorted(extra),
            "tool_calls": calls,
            "answer": answer,
        })

d = pd.DataFrame(rows)
d.to_csv("agent_results.csv", index=False, encoding="utf-8-sig")
print()
for number in range(1, len(CASES) + 1):
    part = d[d["case"] == number]
    print(f"Case {number}: passed {part['passed'].sum()} of {len(part)}")
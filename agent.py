import re

import anthropic

from tools import query_variance

client = anthropic.Anthropic()
MODEL = "claude-sonnet-5-5"
MAX_STEPS = 6

SYSTEM = """You answer a finance manager's questions about budget vs actual spending.
Use the query_variance tool for every figure you give. Never calculate, add, subtract, round or estimate figures yourself. If you need a total or a comparison, query it.
Quote figures exactly as the tool returns them.
If the tool result contains a Note about missing or duplicate data, tell the manager.
Answer in plain English, in no more than four sentences."""

TOOLS = [
    {
        "name": "query_variance",
        "description": "Returns Budget, Actual, Variance and Variance % from the company's cost data (January to June 2026). All figures are calculated in code. Filter by department and/or category, choose a month range, and choose how to group the result. Rows are sorted from largest overspend to largest underspend, except when grouped by month. Notes at the end flag missing or duplicate source rows.",
        "input_schema": {
            "type": "object",
            "properties": {
                "month_from": {"type": "string", "description": "First month, written as YYYY-MM, for example 2026-03"},
                "month_to": {"type": "string", "description": "Last month, written as YYYY-MM"},
                "group_by": {
                    "type": "string",
                    "enum": ["department", "category", "month", "none"],
                    "description": "How to group the rows. Use none for a single total.",
                },
                "department": {
                    "type": "string",
                    "enum": ["Marketing", "Operations", "Sales"],
                    "description": "Optional. Leave out to include all departments.",
                },
                "category": {
                    "type": "string",
                    "enum": ["Advertising", "Salaries", "Software", "Travel"],
                    "description": "Optional. Leave out to include all categories.",
                },
            },
            "required": ["month_from", "month_to", "group_by"],
        },
    }
]


def numbers_in(text):
    text = re.sub(r"\b(?:19|20)\d{2}\b", " ", text)
    result = set()
    for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        result.add(float(n.replace(",", "")))
    return result


def run_tool(name, tool_input):
    if name != "query_variance":
        return f"Error: unknown tool {name}", True
    try:
        return query_variance(**tool_input), False
    except Exception as e:
        return f"Error: {e}", True


def ask(question):
    messages = [{"role": "user", "content": question}]
    results = []
    calls = []
    for step in range(MAX_STEPS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM,
            tools=TOOLS,
            tool_choice={"type": "auto", "disable_parallel_tool_use": True},
            messages=messages,
        )
        if response.stop_reason != "tool_use":
            answer = ""
            for block in response.content:
                if block.type == "text":
                    answer += block.text
            return answer, results, calls

        tool_use = next(block for block in response.content if block.type == "tool_use")
        print("   tool call:", tool_use.input)
        calls.append(tool_use.input)
        result, is_error = run_tool(tool_use.name, tool_use.input)
        results.append(result)

        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_use.id, "content": result, "is_error": is_error}],
        })
    return "Stopped: too many tool calls.", results, calls


if __name__ == "__main__":
    QUESTIONS = [
        "Which department was furthest over budget in March 2026?",
        "What was the total variance for Operations Salaries from January to June 2026?",
        "Did Marketing do better or worse against budget in May 2026 than in April 2026?",
    ]

    for q in QUESTIONS:
        print("Q:", q)
        answer, results, calls = ask(q)
        print("A:", answer)
        allowed = numbers_in(q)
        for r in results:
            allowed |= numbers_in(r)
        extra = numbers_in(answer) - allowed
        print("Numbers check:", "FAIL " + str(sorted(extra)) if extra else "PASS")
        print()
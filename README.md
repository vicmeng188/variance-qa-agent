# Variance Q&A Agent

A small tool-using agent that answers a finance manager's questions about budget vs actual spending. The model decides what data to query; Python code runs every query, calculates every figure and checks the data.

Status: work in progress. Evaluated on a small test set (6 questions, 3 runs each).

## Why an agent here, and when it is not needed

A fixed workflow works when you know the input in advance. Here the manager can ask anything ("How did Sales track in Q3 FY26?", "Which category overspent most in the half-year?"), so the data to fetch cannot be prepared beforehand. The model has to decide what to look up.

For a known set of questions, a Power BI dashboard with slicers is the simpler and better choice. An agent is worth it only when questions are varied and people want to ask in plain English.

## Design

**One flexible tool instead of one tool per question.** `query_variance` works like a SQL `WHERE` plus `GROUP BY`:

| Parameter | Meaning |
|---|---|
| `group_by` | `department`, `category`, `month` or `none` (required) |
| `month_from`, `month_to` | Period as months, YYYY-MM |
| `quarter_from`, `quarter_to` | Period as Australian financial-year quarters, for example `Q2 FY26` |
| `department`, `category` | Optional filters |

The period is given either as months or as quarters, not both. The code converts quarters to months (the financial year runs July to June, so Q2 FY26 is October to December 2025), filters, groups, adds up Budget and Actual, calculates Variance and Variance %, and sorts the rows. The model never calculates.

**The model requests, the code executes.** The model only proposes a tool call. The code validates the parameters before running anything and returns an error message if they are invalid, so the model can correct itself.

**Facts come from code, not from the model.** Each result starts with a line such as:

```
Period requested: 2025-10 to 2026-03. Period with data: 2026-01 to 2026-03.
```

If part of the requested period has no data, the tool returns the part it can and says which months are missing. If none of it has data, it returns an error that states what the data covers.

**Guardrails**

- Parameters are checked against valid formats, months, departments and categories. Department and category are also limited by `enum` in the tool definition.
- A maximum of 6 tool calls per question, to stop runaway loops.
- Any tool error is returned to the model instead of crashing the script.

**Data coverage check.** Every query checks that each month x department x category combination in its range has exactly one source row. Missing or duplicate rows are reported in a Note, and the model is instructed to pass these on. In this dataset the check flags two mislabelled source rows from both sides (one missing, one duplicated). The check assumes every combination should exist; with real data that assumption must be confirmed with the business.

## Evaluation

`eval_agent.py` runs 6 questions written for an Australian finance context. The data covers January to June 2026, the second half of FY26. The correct answers were calculated directly with the tool, not with the model.

| # | Question | What it tests | Checks |
|---|---|---|---|
| 1 | How did Sales track against budget in Q3 FY26? | Q3 FY26 is January to March 2026 | Correct period queried, key figure, no unsourced numbers |
| 2 | Which cost category had the biggest overspend across the business for the half-year to June? | Grouping across departments | Correct period and grouping, key figure, no unsourced numbers |
| 3 | Was Operations Travel over or under budget in Q4 FY26, and by how much? | Q4 conversion plus two filters | Correct period and filters, key figure, no unsourced numbers |
| 4 | What's our full-year FY26 variance? | Trap: the data covers only half the year | Judge: does it say the data covers only January to June 2026? |
| 5 | Why did Marketing go over budget in March? | Trap: the data shows amounts, not causes | Judge: does it state a business reason as fact? |
| 6 | What are the total variances of each department in Q2 and Q3 FY26? | Trap: Q2 FY26 is outside the data, Q3 is inside | Correct period, three department figures, judge: does it say only January to March 2026 is available? |

The numbers check requires every figure in the answer to appear in the question or in a tool result from that conversation. Because the agent chooses its own queries, the allowed figures are built from what it actually fetched. Dates are not counted as financial figures, so years (2026), quarters (Q4) and financial years (FY26) are skipped. The period check converts whatever the agent passed, months or quarters, into months before comparing.

Wherever a check can be done in code, it is. The judge (a second model call answering yes or no) is used only where there is no single figure to compare.

### Results

| Run | Questions | Passed |
|---|---|---|
| 20 November 2026, full test set | 6 x 3 runs | 18 of 18 |
| 20 November 2026, question 6 only | 1 x 9 runs | 9 of 9 |

### How the agent and the test set improved

| Step | Result | Finding | Change |
|---|---|---|---|
| First 5-question run | 11 of 15 | All 4 failures were in the test: the numbers check counted years as unsourced figures. The tool calls were correct every time. | Skip years, as the scoring rule already required |
| Re-run | 15 of 15 | | |
| Added question 6 | 15 of 18 | Question 6 failed all 3 runs. The agent read "Q2 and Q3 FY26" as calendar quarters (April to September 2026), although it converted single quarters correctly in questions 1 and 3 | Quarter conversion moved into the tool, so the model passes quarters as asked and the code converts them. The tool now returns partial results with the missing months named |
| Re-run | 14 of 18 | Question 6 improved to 2 of 3. Question 2 dropped from 3 of 3 to 0 of 3: the check counted "Q4 FY26" as unsourced numbers | Skip quarter and financial-year labels in the numbers check |
| Re-run | 17 of 18 | The remaining question 6 failure: the answer's first sentence labelled January to March figures as "Q2 and Q3 FY26 combined" and later said the data covered "Q3 and later months". The judge failed it; a first human review had passed it | The tool's first line now states the requested period and the period with data |
| Re-run | 18 of 18 | | |
| Question 6, 9 runs | 9 of 9 | At the previous failure rate (1 in 3), 9 passes in a row by luck alone has a chance of about 3% | |

Lessons:

- Check the test before blaming the model. Twice, failures came from the checks, not the agent.
- Re-run every question after each change. A fix for question 6 broke question 2.
- Give the model facts in code rather than more instructions. The wrong period labels stopped once the tool stated the period itself.

## Limitations

- 6 questions and 3 runs each is a small test set.
- The numbers check confirms each figure exists in a tool result, not that it is attached to the right item, and it ignores minus signs, so it cannot tell an overspend from an underspend.
- A four-digit amount written without a comma would be skipped as if it were a year. The tool always formats amounts with commas.
- Quarters must be written exactly like `Q2 FY26`; other forms are rejected and the model has to retry.
- The judge checks that question 5 does not invent a cause. It does not check that the answer explicitly says the cause is unknown.
- The commentary model and the judge are the same model.
- Answers often run longer than the four-sentence limit in the instructions and use bullet points. Length is not yet checked.
- The data is synthetic: 3 departments, 4 cost categories, January to June 2026.

## Files

| File | Contents |
|---|---|
| `tools.py` | The query tool, quarter conversion, parameter checks and coverage checks. Run it directly to test the tool without the model |
| `agent.py` | The agent: instructions, tool definition and the tool-use loop |
| `eval_agent.py` | The 6-question evaluation |
| `agent_results.csv` | Latest full evaluation run |
| `agent_results_case6_9runs.csv` | Question 6 run 9 times |
| `agent_results_5cases.csv` | Earlier 5-question run, before question 6 was added |

## How to run

You need a Claude API key in the `ANTHROPIC_API_KEY` environment variable. The key is not stored in this repository.

```
pip install anthropic pandas
python tools.py
python agent.py
python eval_agent.py
```

## Notes

Built with an AI assistant (Claude) as coach and coding assistant: much of the code and design came from that collaboration. I set the requirements and rules, made the design decisions, ran and debugged the experiments, and reviewed every result. Test question 6 and its expected answer were written by me.

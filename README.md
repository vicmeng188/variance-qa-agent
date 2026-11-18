# Variance Q&A Agent

A small tool-using agent that answers a finance manager's questions about budget vs actual spending. The model decides what data to query; Python code runs every query, calculates every figure and checks the data.

Status: work in progress. Evaluated on a small test set (5 questions, 3 runs each).

## Why an agent here, and when it is not needed

A fixed workflow works when you know the input in advance. Here the manager can ask anything ("How did Sales track in Q3 FY26?", "Which category overspent most in the half-year?"), so the data to fetch cannot be prepared beforehand. The model has to decide what to look up.

For a known set of questions, a Power BI dashboard with slicers is the simpler and better choice. An agent is worth it only when questions are varied and people want to ask in plain English.

## Design

**One flexible tool instead of one tool per question.** `query_variance` works like a SQL `WHERE` plus `GROUP BY`:

| Parameter | Meaning |
|---|---|
| `month_from`, `month_to` | Month range, YYYY-MM (required) |
| `group_by` | `department`, `category`, `month` or `none` (required) |
| `department` | Optional filter |
| `category` | Optional filter |

The code filters, groups, adds up Budget and Actual, calculates Variance and Variance %, and sorts the rows. The model never calculates.

**The model requests, the code executes.** The model only proposes a tool call. The code validates the parameters before running anything and returns an error message if they are invalid, so the model can correct itself.

**Guardrails**

- Parameters are checked against the valid months, departments and categories. Department and category are also limited by `enum` in the tool definition.
- A maximum of 6 tool calls per question, to stop runaway loops.
- Any tool error is returned to the model instead of crashing the script.

**Data coverage check.** Every query checks that each month x department x category combination in its range has exactly one source row. Missing or duplicate rows are reported in a Note, and the model is instructed to pass these on. This matters because a total can look complete while silently missing a month. In this dataset the check flags two mislabelled source rows from both sides (one missing, one duplicated). The check assumes every combination should exist; with real data that assumption must be confirmed with the business.

## Evaluation

`eval_agent.py` runs 5 questions written for an Australian finance context (financial year July to June; the data covers January to June 2026, the second half of FY26). The correct answers were calculated directly with the tool, not with the model.

| # | Question | What it tests | Checks |
|---|---|---|---|
| 1 | How did Sales track against budget in Q3 FY26? | Converting Q3 FY26 to January to March 2026 | Correct tool call, key figure (-4,211), no unsourced numbers |
| 2 | Which cost category had the biggest overspend across the business for the half-year to June? | Grouping across departments | Correct tool call, key figure (+3,298), no unsourced numbers |
| 3 | Was Operations Travel over or under budget in Q4 FY26, and by how much? | Q4 conversion plus two filters | Correct tool call, key figure (+430), no unsourced numbers |
| 4 | What's our full-year FY26 variance? | Trap: the data covers only half the year | Judge: does it say the data covers only January to June 2026? |
| 5 | Why did Marketing go over budget in March? | Trap: the data shows amounts, not causes | Judge: does it state a business reason as fact? |

The numbers check requires every figure in the answer to appear in the question or in a tool result from that conversation. Because the agent chooses its own queries, the allowed figures are built from what it actually fetched. Four-digit years are not counted, in line with the scoring rule that dates are not financial figures.

Wherever a check can be done in code, it is. The judge (a second model call answering yes or no) is used only for questions 4 and 5, where there is no single figure to compare.

### Results (19 November 2026)

| Question | Passed |
|---|---|
| 1 | 3 of 3 |
| 2 | 3 of 3 |
| 3 | 3 of 3 |
| 4 | 3 of 3 |
| 5 | 3 of 3 |

The judge's verdicts for questions 4 and 5 were checked by hand for all 6 answers and agreed.

### What the evaluation found

- **The first run scored 11 of 15, and all 4 failures were in the test, not the agent.** The numbers check counted years (2025, 2026) as unsourced figures. In one case the agent had correctly explained that FY26 runs from July 2025 to June 2026 and was marked down for it. The tool calls were correct in all 4 runs. After the check was fixed to skip years, as the scoring rule already required, all 15 passed.
- In every run of question 4, the agent said it could not give a full-year figure. In one run it first tried to query months outside the data; the tool rejected the query and the agent explained the limit.
- The agent reported the data coverage notes to the manager in its answers.
- The agent sometimes takes a less efficient path, for example querying April and May separately instead of once grouped by month. The answers were still correct.

## Limitations

- 5 questions and 3 runs each is a small test set.
- The numbers check confirms each figure exists in a tool result, not that it is attached to the right item.
- A four-digit amount written without a comma would be skipped as if it were a year. The tool always formats amounts with commas.
- The judge checks that question 5 does not invent a cause. It does not check that the answer explicitly says the cause is unknown; one of the three answers gave the figures and the data note without saying so.
- The commentary model and the judge are the same model.
- Answers often run longer than the four-sentence limit in the instructions and use bullet points. Length is not yet checked.
- The data is synthetic: 3 departments, 4 cost categories, January to June 2026.

## Files

| File | Contents |
|---|---|
| `tools.py` | The query tool, its parameter checks and the coverage check. Run it directly to test the tool without the model |
| `agent.py` | The agent: instructions, tool definition and the tool-use loop |
| `eval_agent.py` | The 5-question evaluation |
| `agent_results.csv` | Results of the latest evaluation run |

## How to run

You need a Claude API key in the `ANTHROPIC_API_KEY` environment variable. The key is not stored in this repository.

```
pip install anthropic pandas
python tools.py
python agent.py
python eval_agent.py
```

## Notes

The Python code was written with AI coding assistance. I designed the tool, the test questions and the checks, ran the evaluation and reviewed the results.

# Parser Unit Test Report

Generated: 2026-07-07

Verdict: **PASS**

| Parser | Input | Expected | Got | Pass |
|---|---|---|---|---|
| presence | `'yes\nvoice present'` | `yes` | `yes` | True |
| presence | `'No. Instrumental only'` | `no` | `no` | True |
| presence | `'UNSURE\nunclear'` | `unsure` | `unsure` | True |
| presence | `' yes - sung vocal'` | `yes` | `yes` | True |
| presence | `'I cannot determine'` | `abstain` | `abstain` | True |
| presence | `''` | `abstain` | `abstain` | True |
| ab | `'Q1: A\nQ2: B\nQ3: tie'` | `{'q1': 'a', 'q2': 'b', 'q3': 'tie'}` | `{'q1': 'a', 'q2': 'b', 'q3': 'tie'}` | True |
| ab | `'bad'` | `{'q1': 'refusal', 'q2': 'refusal', 'q3': 'refusal'}` | `{'q1': 'refusal', 'q2': 'refusal', 'q3': 'refusal'}` | True |

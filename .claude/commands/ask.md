# /ask {question}
Use when behavior is unspecified or ambiguous.
Agents must use this rather than assuming and writing code.
Orchestrator receives the question and either:
  - Answers from existing context
  - Escalates to Jiny for decision
  - Records the answer in decisions/ for future reference

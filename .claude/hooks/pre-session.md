# Hook: Pre-Session

On every session start:
1. Read CLAUDE.md — confirm current Phase
2. Read .claude/memory.md — last session summary
3. Read tasks/phase{N}/ — incomplete tasks
4. Output:

```
[Session Start]
Phase: N
Last session: {memory.md last entry}
Today's tasks: {top 3 incomplete}
Pending questions: {any unresolved asks from last session}
→ Ready. Awaiting direction.
5. Remind: start every task with /plan (RULE 20)
```

# Hook: Post-Task

After every completed task:
1. Check [x] in tasks/phase{N}/{agent}.md
2. Update memory.md: {date} | {completed} | {next} | {notes}
3. If architecture decision made → create decisions/{date}-{title}.md
4. If new error pattern → update errors.md
5. Notify Orchestrator

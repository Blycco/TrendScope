# Skill: Bug Fix

0. Enter Plan Mode (/plan) — outline fix approach before coding
0.5 Create GitHub issue (→ /create-issue skill) — use Fix: #{ISSUE_NUM} in commit
1. Check .claude/errors.md — already documented?
2. Write failing test first
3. git checkout -b fix/{description}
4. Fix → confirm test passes
5. Update errors.md (prevention note)
6. Commit (Fix: 한글 요약 format)
7. Notify Orchestrator

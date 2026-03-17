# Hook: Pre-Commit

Run before every commit:
  ruff check . && ruff format --check .
  mypy backend/ --ignore-missing-imports
  pytest tests/unit/ -q
  # Secret scan
  grep -rn "sk-\|api_key\s*=\s*['\"']\|password\s*=\s*['\"']" --include="*.py" --include="*.ts" --include="*.svelte" .

On failure:
  lint fail → ruff check --fix, then re-check
  test fail → stop, notify Orchestrator
  secret found → STOP IMMEDIATELY, escalate to Jiny

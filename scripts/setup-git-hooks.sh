#!/usr/bin/env bash
# 실행: bash scripts/setup-git-hooks.sh
set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
HOOK_FILE="$PROJECT_ROOT/.git/hooks/pre-commit"

cat > "$HOOK_FILE" << 'HOOK'
#!/usr/bin/env bash
set -e
cd "$(git rev-parse --show-toplevel)"

echo "[pre-commit] ruff lint..."
python3.11 -m ruff check backend/ tests/

echo "[pre-commit] ruff format check..."
python3.11 -m ruff format --check backend/ tests/

echo "[pre-commit] pytest..."
python3.11 -m pytest tests/ -q --no-header

echo "[pre-commit] secret scan..."
if grep -rn --include="*.py" -E '(sk-[a-zA-Z0-9]{20,}|ANTHROPIC_API_KEY\s*=\s*["\x27][^"\x27])' backend/ 2>/dev/null; then
  echo "SECRET detected. Commit aborted."
  exit 1
fi

echo "[pre-commit] all checks passed"
HOOK

chmod +x "$HOOK_FILE"
echo "git pre-commit hook installed at $HOOK_FILE"

#!/usr/bin/env bash
# Claude Code PreToolUse hook: git commit 전 시크릿 패턴 감지
# 환경변수 CLAUDE_TOOL_INPUT 에 실행 예정 명령어가 들어옴 (있을 경우)

# git commit 명령인 경우만 검사
if echo "${CLAUDE_TOOL_INPUT:-}" | grep -q "git commit"; then
  # .py, .ts, .svelte 파일에서 하드코딩 시크릿 패턴 탐지
  if grep -rn --include="*.py" --include="*.ts" --include="*.svelte" \
      -E '(sk-[a-zA-Z0-9]{20,}|api_key\s*=\s*["\x27][^"\x27]{8,}|password\s*=\s*["\x27][^"\x27]{4,})' \
      /Users/verity/develop/project/trendscope/backend/ 2>/dev/null; then
    echo "SECRET DETECTED in source files. Commit blocked." >&2
    exit 1
  fi
fi

exit 0

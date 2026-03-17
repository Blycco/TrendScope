# Skill: Create GitHub Issue

1. gh issue create \
     --title "{한글 제목}" \
     --body "{작업 배경 및 완료 기준}" \
     --label "{feat|fix|chore}" \
   → 출력된 URL에서 이슈 번호 확인
2. 이슈 번호를 ISSUE_NUM 변수로 저장 (커밋 시 사용)
   ISSUE_NUM=$(gh issue create ... | grep -o '[0-9]*$')
3. 브랜치명에 이슈 번호 포함 권장: feat/{ISSUE_NUM}-{description}

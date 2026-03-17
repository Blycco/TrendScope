# Skill: Write Tests

Locations:
  tests/unit/        — pure functions, no I/O, under 1s each
  tests/integration/ — real DB + Redis (docker-compose.test.yml)
  tests/e2e/         — full API flow

Naming: test_{module}_{scenario}_{expected_result}
Example: test_keyword_extractor_empty_input_returns_empty_list

Run:
  pytest --cov=backend --cov-report=term-missing --cov-fail-under=70

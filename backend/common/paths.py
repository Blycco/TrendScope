"""Path constants for TrendScope backend. (RULE 10: never use string literals for paths)"""

from pathlib import Path

# --- Root ---
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

# --- Backend ---
BACKEND_DIR: Path = BASE_DIR / "backend"
MIGRATIONS_DIR: Path = BASE_DIR / "migrations"

# --- Logs ---
LOG_DIR: Path = BASE_DIR / "logs"

# --- Static / Media (future use) ---
STATIC_DIR: Path = BASE_DIR / "static"

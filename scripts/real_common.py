import os

from app.config import Settings


def real_settings():
    if os.getenv("RUN_REAL_INTEGRATION", "").lower() != "true":
        raise SystemExit(
            "Live provider calls disabled. Explicitly set RUN_REAL_INTEGRATION=true (may incur costs)."
        )
    return Settings(mock_mode=False)

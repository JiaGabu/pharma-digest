"""
Run guard: ensures only one successful digest is sent per day.
Uses a marker file committed to the git repo as shared state
between the local launchd job and the GitHub Actions cloud job.
"""
import logging
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

TAIPEI = timezone(timedelta(hours=8))
LOGS_DIR = Path(__file__).parent.parent / "logs"


def _today_marker() -> Path:
    date_str = datetime.now(TAIPEI).strftime("%Y-%m-%d")
    return LOGS_DIR / f"sent_{date_str}.marker"


def already_sent_today() -> bool:
    """Pull latest repo state, then check if today's marker exists."""
    try:
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            timeout=30,
        )
    except Exception as e:
        logger.warning(f"git pull failed (proceeding anyway): {e}")

    exists = _today_marker().exists()
    if exists:
        logger.info(f"Marker found ({_today_marker().name}) — digest already sent today, skipping.")
    return exists


def mark_sent_today() -> None:
    """Write today's marker file and push to repo so the other runner sees it."""
    LOGS_DIR.mkdir(exist_ok=True)
    marker = _today_marker()
    marker.write_text(datetime.now(TAIPEI).isoformat())
    logger.info(f"Marker written: {marker.name}")

    repo = Path(__file__).parent.parent
    try:
        subprocess.run(["git", "add", str(marker)], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"chore: mark digest sent {marker.stem[5:]}"],
            cwd=repo, check=True, capture_output=True,
        )
        subprocess.run(["git", "push"], cwd=repo, check=True, capture_output=True, timeout=30)
        logger.info("Marker pushed to repo.")
    except Exception as e:
        logger.warning(f"Failed to push marker (email was still sent): {e}")

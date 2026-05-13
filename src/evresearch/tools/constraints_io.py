"""
tools/constraints_io.py — Read/write user_constraints.json (mid-run override watch file)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from evresearch.config.settings import VEHICLE_CLASSES

CONSTRAINTS_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "user_constraints.json"
)
OVERRIDE_LOG_PATH = (
    Path(__file__).resolve().parents[2] / "state" / "override_log.jsonl"
)


def load_constraints() -> dict:
    """Return the current user_constraints.json, or empty dict on error."""
    try:
        with open(CONSTRAINTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_constraints(constraints: dict) -> None:
    constraints["_last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(CONSTRAINTS_PATH, "w", encoding="utf-8") as f:
        json.dump(constraints, f, indent=2, ensure_ascii=False)


def get_active_overrides(phase_num: int) -> dict:
    """Merge global active_overrides with phase-specific phase_locks."""
    c = load_constraints()
    active = dict(c.get("active_overrides", {}))
    phase_lock = c.get("phase_locks", {}).get(f"phase{phase_num}", {})
    return {**active, **phase_lock}


def validate_override(key: str, value: str) -> tuple[bool, str]:
    """
    Validate a proposed override against class boundaries.
    Returns (is_valid, error_message).
    """
    dim_keys = {
        "max_oal_mm": ("oal_mm_range", "OAL"),
        "max_oaw_mm": ("oaw_mm_range", "OAW"),
        "max_oah_mm": ("oah_mm_range", "OAH"),
    }
    if key in dim_keys:
        range_key, label = dim_keys[key]
        try:
            val = int(value)
        except ValueError:
            return False, f"Override {key}={value} is not a valid integer."
        # Check against all classes; if it fits in no class, warn
        for cls_name, cls_data in VEHICLE_CLASSES.items():
            lo, hi = cls_data[range_key]
            if lo <= val <= hi:
                return True, ""
        all_maxes = [cls[range_key][1] for cls in VEHICLE_CLASSES.values()]
        return (
            False,
            f"Override {key}={value} exceeds the maximum {label} across all classes "
            f"({max(all_maxes)}mm). Specify class=medium_bus to relax boundaries.",
        )
    return True, ""  # Unknown keys are passed through unchecked


def log_override(phase: int, task: str, key: str, value, source: str) -> None:
    """Append an override event to override_log.jsonl."""
    OVERRIDE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "task": task,
        "key": key,
        "value": value,
        "source": source,
    }
    with open(OVERRIDE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

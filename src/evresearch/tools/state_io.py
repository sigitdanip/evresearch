"""
tools/state_io.py — Read/write research_state.json
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parents[2] / "state" / "research_state.json"

_INITIAL_STATE: dict = {
    "meta": {
        "run_id": "",
        "started_at": "",
        "last_completed_phase": 0,
        "status": "running",
        "user_constraints": {},
    },
    "survey": {
        "total_count": 0,
        "by_class": {"angkot": [], "small_bus": [], "medium_bus": []},
        "status": "incomplete",
    },
    "phase1": {
        "survey_summary": {},
        "anthropometry": {},
        "ingress_egress": {},
        "capacity_candidates": [],
        "gate_decisions": {},
    },
    "phase2": {
        "internal_footprint_by_capacity": {},
        "structural_offsets_mm": {
            "side_wall_each": None,
            "front_overhang": None,
            "rear_overhang": None,
            "floor_stack": None,
        },
        "candidates": [],
        "gate_decisions": {},
    },
    "phase3": {
        "environment": {},
        "surviving_candidates": [],
        "eliminated_candidates": [],
        "powertrain_requirements": {},
        "hvac_load_kw": None,
        "energy_consumption_kwh_per_km": None,
        "recommended_capacity": None,
        "gate_decisions": {},
    },
    "phase4": {
        "ridership": {},
        "seating_standing_ratio": None,
        "door_config": None,
        "usable_battery_kwh": None,
        "charging_strategy": None,
        "fleet_size_recommendation": None,
        "gate_decisions": {},
    },
    "phase5": {
        "motor": {},
        "battery": {},
        "axle": {},
        "chassis_hardpoints": {},
        "gate_decisions": {},
    },
    "phase6": {
        "vehicle_class": None,
        "required_driver_license": None,
        "crash_safety": {},
        "accessibility_compliance": {},
        "ev_homologation": {},
        "compliance_status": None,
        "open_items": [],
        "gate_decisions": {},
    },
}


def _ensure_dir() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    """Load or initialise research_state.json."""
    _ensure_dir()
    if STATE_PATH.exists():
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # First run — initialise
    state = json.loads(json.dumps(_INITIAL_STATE))  # deep copy
    state["meta"]["run_id"] = str(uuid.uuid4())
    state["meta"]["started_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    return state


def save_state(state: dict) -> None:
    """Persist state to disk atomically."""
    _ensure_dir()
    tmp = STATE_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    tmp.replace(STATE_PATH)


def get_phase(state: dict, phase_num: int) -> dict:
    return state.get(f"phase{phase_num}", {})


def set_phase(state: dict, phase_num: int, data: dict) -> dict:
    state[f"phase{phase_num}"] = data
    return state


def update_survey(state: dict, vehicle_class: str, vehicle: dict) -> dict:
    """Append one vehicle record to the survey."""
    state["survey"]["by_class"][vehicle_class].append(vehicle)
    state["survey"]["total_count"] = sum(
        len(v) for v in state["survey"]["by_class"].values()
    )
    save_state(state)
    return state

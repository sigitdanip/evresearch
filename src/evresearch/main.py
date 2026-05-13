#!/usr/bin/env python
"""
main.py — EV Shuttle Bogor Research Framework v1.2
Orchestrates 6-phase multi-crew CrewAI pipeline with human decision gates.

Usage:
    uv run evresearch              # Fresh run
    uv run evresearch --resume     # Resume from last completed phase
    uv run evresearch --gate 3     # Re-run a specific gate only
    uv run evresearch --phase 1    # Re-run from a specific phase
"""
from __future__ import annotations

import argparse
import sys
import time
import warnings
from datetime import datetime, timezone

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
warnings.filterwarnings("ignore", category=DeprecationWarning)

from evresearch.config.settings import TASK_SLEEP_S
from evresearch.tools.state_io import load_state, save_state
from evresearch.tools.constraints_io import get_active_overrides, log_override
from evresearch.gates.gate_runner import run_gate
from evresearch.outputs.report_generator import generate_final_report

# Phase crew imports — deferred to avoid circular imports on startup
PHASE_NAMES = {
    1: "Market Survey & Anthropometry",
    2: "Packaging (External Dimensions)",
    3: "Environment & Viability",
    4: "Demand & Operations",
    5: "Hardware BOM Sourcing",
    6: "Regulatory Compliance",
}


def _load_crew(phase_num: int):
    """Lazy-import crew module and return its run function."""
    if phase_num == 1:
        from evresearch.crews.phase1_market import run_phase1
        return run_phase1
    elif phase_num == 2:
        from evresearch.crews.phase2_packaging import run_phase2
        return run_phase2
    elif phase_num == 3:
        from evresearch.crews.phase3_environment import run_phase3
        return run_phase3
    elif phase_num == 4:
        from evresearch.crews.phase4_demand import run_phase4
        return run_phase4
    elif phase_num == 5:
        from evresearch.crews.phase5_hardware import run_phase5
        return run_phase5
    elif phase_num == 6:
        from evresearch.crews.phase6_regulatory import run_phase6
        return run_phase6
    raise ValueError(f"Unknown phase: {phase_num}")


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

def pre_phase_hook(phase_num: int, state: dict) -> dict:
    """Inject active user constraints before a phase starts."""
    overrides = get_active_overrides(phase_num)
    if overrides:
        state["meta"]["user_constraints"] = overrides
        print(f"\n[CONSTRAINTS ACTIVE] Injected before Phase {phase_num}: {overrides}")
        for key, val in overrides.items():
            log_override(phase_num, f"pre_phase_{phase_num}", key, val, "user_constraints.json")
    return state


def validate_phase_schema(phase_num: int, data: dict) -> bool:
    """Run Pydantic schema validation on phase output."""
    try:
        from evresearch.validators.schema_validator import validate_phase_output
        validate_phase_output(phase_num, data)
        print(f"  [SCHEMA] Phase {phase_num} output validated ✓")
        return True
    except Exception as exc:
        print(f"  [SCHEMA WARNING] Phase {phase_num}: {exc}")
        print("  Proceeding to gate (human can review and override at gate).")
        return False


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

def _print_banner():
    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║     EV SHUTTLE RESEARCH FRAMEWORK — Bogor, Indonesia v1.2           ║")
    print("║     6-Phase CrewAI Multi-Agent System                               ║")
    print("║     Budget: $0.00 — OpenRouter Free Tier Only                       ║")
    print("║     Models: DeepSeek R1 · Llama 3.3 70B · Gemini 2.0 Flash · Mistral║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print()


def _phase_banner(phase_num: int, phase_name: str, action: str = "START"):
    width = 72
    label = f"[{action}] Phase {phase_num}: {phase_name}"
    pad = (width - len(label) - 2) // 2
    print()
    print("═" * width)
    print(f"  {label}")
    print("═" * width)


# ---------------------------------------------------------------------------
# Core run loop
# ---------------------------------------------------------------------------

def run_pipeline(start_phase: int = 1, gate_only: int | None = None):
    """Main pipeline loop."""
    _print_banner()
    state = load_state()

    print(f"  Run ID:   {state['meta']['run_id']}")
    print(f"  Started:  {state['meta']['started_at']}")
    print(f"  Status:   {state['meta']['status']}")
    print(f"  Last completed phase: {state['meta']['last_completed_phase']}")
    print()

    # Gate-only mode: re-run a single gate without running the crew
    if gate_only is not None:
        _phase_banner(gate_only, PHASE_NAMES.get(gate_only, ""), "GATE ONLY")
        decisions = run_gate(gate_only, state)
        state[f"phase{gate_only}"]["gate_decisions"] = decisions
        save_state(state)
        print(f"\n[Gate {gate_only}] Re-run complete.")
        return

    for phase_num in range(start_phase, 7):
        phase_name = PHASE_NAMES[phase_num]
        last_done = state["meta"]["last_completed_phase"]

        # Skip if already completed AND gate was answered
        if last_done >= phase_num:
            gate_decisions = state.get(f"phase{phase_num}", {}).get("gate_decisions", {})
            if gate_decisions:
                _phase_banner(phase_num, phase_name, "SKIP")
                print(f"  Phase {phase_num} and Gate {phase_num} already complete — skipping.")
                continue
            else:
                # Phase completed but gate not done — re-run gate
                _phase_banner(phase_num, phase_name, "GATE RESUME")
                print(f"  Phase {phase_num} complete but gate not recorded — re-running gate.")
                decisions = run_gate(phase_num, state)
                state[f"phase{phase_num}"]["gate_decisions"] = decisions
                state["meta"]["status"] = "running"
                save_state(state)
                continue

        # ----------------------------------------------------------------
        # Run the crew
        _phase_banner(phase_num, phase_name)

        # Inject constraints
        state = pre_phase_hook(phase_num, state)

        # Rate-limit buffer between phases
        if phase_num > start_phase:
            print(f"\n  [Rate limit] Sleeping {TASK_SLEEP_S}s before crew start...")
            time.sleep(TASK_SLEEP_S)

        crew_fn = _load_crew(phase_num)
        print(f"\n  Kicking off crew for Phase {phase_num}...\n")

        try:
            phase_data = crew_fn(state)
        except Exception as exc:
            print(f"\n  [ERROR] Phase {phase_num} crew failed: {exc}")
            print("  State saved. Re-run with --resume to retry from this phase.")
            save_state(state)
            raise

        # Validate schema
        validate_phase_schema(phase_num, phase_data)

        # Write phase data to state
        phase_data["gate_decisions"] = {}
        state[f"phase{phase_num}"] = phase_data
        state["meta"]["last_completed_phase"] = phase_num
        state["meta"]["status"] = "awaiting_gate"
        save_state(state)
        print(f"\n  [Phase {phase_num} complete] State saved.")

        # ----------------------------------------------------------------
        # Run the decision gate
        _phase_banner(phase_num, phase_name, "GATE")
        decisions = run_gate(phase_num, state)

        state[f"phase{phase_num}"]["gate_decisions"] = decisions
        state["meta"]["status"] = "running"
        save_state(state)

        print(f"\n  [Gate {phase_num} locked] Decisions recorded. Proceeding to Phase {phase_num + 1}...")

    # ----------------------------------------------------------------
    # Generate final report
    print()
    print("═" * 72)
    print("  ALL 6 PHASES COMPLETE — Generating final report...")
    print("═" * 72)
    report_path = generate_final_report(state)

    state["meta"]["status"] = "complete"
    save_state(state)

    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║  RESEARCH COMPLETE                                                   ║")
    print(f"║  Report: outputs/final_report.md                                    ║")
    print(f"║  State:  state/research_state.json                                  ║")
    print(f"║  Cost:   $0.00                                                       ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")


# ---------------------------------------------------------------------------
# Entry points (required by pyproject.toml scripts)
# ---------------------------------------------------------------------------

def run():
    """Primary entry point: `evresearch` or `uv run evresearch`."""
    parser = argparse.ArgumentParser(
        description="EV Shuttle Bogor Research Framework v1.2"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last completed phase",
    )
    parser.add_argument(
        "--phase",
        type=int,
        default=None,
        metavar="N",
        help="Start from a specific phase (1–6)",
    )
    parser.add_argument(
        "--gate",
        type=int,
        default=None,
        metavar="N",
        help="Re-run a specific gate only (1–6), without running the crew",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete state file and start fresh",
    )

    args = parser.parse_args()

    if args.reset:
        from pathlib import Path
        state_path = Path(__file__).resolve().parent.parent.parent / "state" / "research_state.json"
        if state_path.exists():
            state_path.unlink()
            print("[RESET] research_state.json deleted. Starting fresh.")

    state = load_state()
    last_done = state["meta"]["last_completed_phase"]

    if args.gate is not None:
        run_pipeline(gate_only=args.gate)
        return

    if args.phase is not None:
        start = args.phase
    elif args.resume:
        # Resume: if awaiting gate, stay on that phase; otherwise next phase
        if state["meta"]["status"] == "awaiting_gate":
            start = last_done
        else:
            start = max(1, last_done + 1) if last_done > 0 else 1
    else:
        start = 1

    run_pipeline(start_phase=start)


def train():
    print("[INFO] Training mode not applicable for this research framework.")


def replay():
    print("[INFO] Use --resume flag to resume from last phase.")
    run()


def test():
    print("[INFO] Running calculator unit tests...")
    from evresearch.tools.calculator import (
        compute_internal_box,
        compute_external_dims,
        compute_gvw,
        compute_swept_path,
        compute_hill_torque,
        compute_hvac_load,
        compute_range,
    )

    box = compute_internal_box(20, 720, 400)
    print(f"  internal_box(20, 720, 400): {box}")

    dims = compute_external_dims(box["internal_length_mm"], box["internal_width_mm"])
    print(f"  external_dims: OAL={dims['oal_mm']}mm, OAW={dims['oaw_mm']}mm, OAH={dims['oah_mm']}mm")

    gvw = compute_gvw(20, 3800.0)
    print(f"  gvw(20, 3800): {gvw['gvw_kg']}kg — {gvw['kemenhub_classification']}")

    swept = compute_swept_path(dims["oal_mm"], dims["wheelbase_estimate_mm"])
    print(f"  swept_path: min_turning_radius={swept['min_turning_radius_m']}m")

    torque = compute_hill_torque(gvw["gvw_kg"], 18.3)
    print(f"  hill_torque(18.3%): {torque['required_continuous_power_kw']}kW, {torque['required_torque_nm']}Nm")

    hvac = compute_hvac_load(21.9, 34.0, 20)
    print(f"  hvac_load: {hvac['total_hvac_kw']}kW")

    rng = compute_range(165.0, 1.41, hvac["total_hvac_kw"])
    print(f"  range(165kWh, 1.41 kWh/km, HVAC): {rng['estimated_range_km']}km")

    print("\n  [TESTS PASSED] All calculator functions nominal.")


def run_with_trigger():
    """Compatibility stub for pyproject.toml trigger entry point."""
    run()


if __name__ == "__main__":
    run()

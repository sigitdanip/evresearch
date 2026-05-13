"""gates/gate_phase2.py — Gate 2 questions: Packaging / External Dimensions"""
from __future__ import annotations
from evresearch.gates.gate_runner import Question, QuestionOption


def get_questions(state: dict) -> list[Question]:
    gate1 = state.get("phase1", {}).get("gate_decisions", {})
    gate1_capacity = gate1.get("q1.1", "20 passengers")
    candidates = state.get("phase2", {}).get("candidates", [])

    # Find the 20-pax candidate for GVW display
    cap20 = next((c for c in candidates if c.get("capacity") == 20), {})
    gvw_20 = cap20.get("gvw_kg", 5450)

    return [
        Question(
            id="q2.1",
            prompt=(
                f"Confirm or adjust target capacity (Gate 1 decision: {gate1_capacity})\n"
                f"  GVW for 20-pax candidate: {gvw_20}kg "
                f"({'EXCEEDS' if gvw_20 > 5000 else 'within'} Kemenhub 5,000kg threshold)"
            ),
            options=[
                QuestionOption("Confirm 20 pax, accept SIM B1 licensing requirement", "operator minimum met"),
                QuestionOption("Reduce to 18 pax, closer to 5,000kg threshold", "lower GVW, simpler licensing"),
                QuestionOption("Custom value", "enter in override section"),
            ],
            suggested="Confirm 20 pax, accept SIM B1 licensing requirement",
            reason="20 pax meets operator minimum; SIM B1 is manageable operationally",
        ),
        Question(
            id="q2.2",
            prompt="Maximum acceptable Overall Length (OAL) in mm",
            suggested="6200",
            reason="Leaves turning radius margin for Phase 3 swept-path filter",
            range_hint="Survey p75 for small bus: 6,400mm. Bogor constraint: assess in Phase 3.",
            validator=lambda v: (v.isdigit() and 5000 <= int(v) <= 7000, "Must be integer 5000–7000mm"),
        ),
        Question(
            id="q2.3",
            prompt="Maximum acceptable Overall Width (OAW) in mm",
            suggested="2050",
            reason="Bogor typical lane 3.2m → OAW 2050mm leaves 575mm each side",
            range_hint="Survey p75 for small bus: 2,120mm. Bogor lane: ~3,200mm.",
            validator=lambda v: (v.isdigit() and 1900 <= int(v) <= 2200, "Must be integer 1900–2200mm"),
        ),
        Question(
            id="q2.4",
            prompt="Structural offset acceptance",
            options=[
                QuestionOption("Accept all defaults (side_wall 120mm, floor 350mm, overhangs 800/600mm)",
                               "derived from SNI + survey benchmarks"),
                QuestionOption("Override (use override section below)", "custom values"),
            ],
            suggested="Accept all defaults (side_wall 120mm, floor 350mm, overhangs 800/600mm)",
        ),
        Question(
            id="q2.5",
            prompt=f"GVW tolerance for Phase 3 simulation (calculated: {gvw_20}kg)",
            options=[
                QuestionOption(f"Use {gvw_20}kg as working GVW", "agent best estimate"),
                QuestionOption(f"Add 10% safety margin → {round(gvw_20 * 1.1)}kg",
                               "conservative estimate"),
                QuestionOption("Override to specific value", "enter in override section"),
            ],
            suggested=f"Use {gvw_20}kg as working GVW",
        ),
    ]

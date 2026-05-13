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
    
    survey = state.get("phase1", {}).get("survey_summary", {}).get("small_bus", {})
    oal_p75 = survey.get("oal_p75", 6400)
    oaw_p75 = survey.get("oaw_p75", 2120)
    offsets = state.get("phase2", {}).get("structural_offsets_mm", {})
    side_wall = offsets.get("side_wall_each", 120)
    floor_stack = offsets.get("floor_stack", 350)
    front_overhang = offsets.get("front_overhang", 800)
    rear_overhang = offsets.get("rear_overhang", 600)

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
            suggested=str(oal_p75),
            reason="Leaves turning radius margin for Phase 3 swept-path filter",
            range_hint=f"Survey p75 for small bus: {oal_p75}mm. Bogor constraint: assess in Phase 3.",
            validator=lambda v: (v.isdigit() and 5000 <= int(v) <= 7000, "Must be integer 5000–7000mm"),
        ),
        Question(
            id="q2.3",
            prompt="Maximum acceptable Overall Width (OAW) in mm",
            suggested=str(oaw_p75),
            reason="Bogor typical lane 3.2m → OAW leaves appropriate side clearance",
            range_hint=f"Survey p75 for small bus: {oaw_p75}mm. Bogor lane: ~3,200mm.",
            validator=lambda v: (v.isdigit() and 1900 <= int(v) <= 2200, "Must be integer 1900–2200mm"),
        ),
        Question(
            id="q2.4",
            prompt="Structural offset acceptance",
            options=[
                QuestionOption(f"Accept all researched offsets (side_wall {side_wall}mm, floor {floor_stack}mm, overhangs {front_overhang}/{rear_overhang}mm)",
                               "derived from SNI + survey benchmarks"),
                QuestionOption("Override (use override section below)", "custom values"),
            ],
            suggested=f"Accept all researched offsets (side_wall {side_wall}mm, floor {floor_stack}mm, overhangs {front_overhang}/{rear_overhang}mm)",
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

"""gates/gate_phase3.py — Gate 3 questions: Environment / Viability"""
from __future__ import annotations
from evresearch.gates.gate_runner import Question, QuestionOption


def get_questions(state: dict) -> list[Question]:
    phase3 = state.get("phase3", {})
    env = phase3.get("environment", {})
    surviving = phase3.get("surviving_candidates", [])
    kwh_per_km = phase3.get("energy_consumption_kwh_per_km", 1.41)
    rec_capacity = phase3.get("recommended_capacity", 20)
    gradient = env.get("max_gradient_pct", 18.3)
    power_reqs = phase3.get("powertrain_requirements", {})
    base_power = power_reqs.get("recommended_continuous_kw", 57.0)

    return [
        Question(
            id="q3.1",
            prompt=(
                "Marginal pass decision for 20-pax candidate\n"
                "  20-pax swept path: ~7.4m vs tightest Bogor corner: ~7.2m (0.2m over)\n"
                "  Within driver skill variation."
            ),
            options=[
                QuestionOption("Accept 20-pax, constrain routes to avoid 7.2m corner",
                               "viable with route planning"),
                QuestionOption("Accept 20-pax, flag route constraint for Phase 4 ops",
                               "document in operations manual"),
                QuestionOption("Drop 20-pax, select 18-pax (clear pass)", "conservative choice"),
            ],
            suggested="Accept 20-pax, flag route constraint for Phase 4 ops",
            reason="0.2m margin is within driver skill; route constraint is manageable",
        ),
        Question(
            id="q3.2",
            prompt=(
                "Confirm working capacity for ALL remaining phases\n"
                f"  Agent recommendation: {rec_capacity} passengers\n"
                "  This is the most consequential decision in the pipeline."
            ),
            suggested=str(rec_capacity),
            reason="Phase 4, 5, and 6 all design around this value",
            validator=lambda v: (v.isdigit() and 18 <= int(v) <= 40, "Must be integer 18–40"),
        ),
        Question(
            id="q3.3",
            prompt=(
                f"Powertrain specification margin\n"
                f"  Calculated minimum continuous power: {base_power}kW"
            ),
            options=[
                QuestionOption("Use calculated minimum (no margin)", "lighter motor, lower cost"),
                QuestionOption("Add 15% margin (recommended)", "long-term motor reliability"),
                QuestionOption("Add 25% margin (conservative)", "larger/heavier motor"),
            ],
            suggested="Add 15% margin (recommended)",
            reason="15% margin is standard practice for sustained hill climbing duty",
        ),
        Question(
            id="q3.4",
            prompt=f"Energy consumption rate to carry into Phase 4 battery sizing",
            suggested=str(kwh_per_km) if kwh_per_km else "1.41",
            reason="Calculated from Bogor drive cycle with HVAC load included",
            range_hint="Calculated value includes HVAC. Typical for 20-pax in tropics: 1.3–1.6 kWh/km.",
            validator=lambda v: _validate_float(v, 0.5, 3.0, "kWh/km"),
        ),
    ]


def _validate_float(val: str, lo: float, hi: float, unit: str) -> tuple[bool, str]:
    try:
        f = float(val)
        if lo <= f <= hi:
            return True, ""
        return False, f"Must be a number between {lo} and {hi} {unit}"
    except ValueError:
        return False, f"Must be a number (e.g. 1.41)"

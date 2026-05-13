"""gates/gate_phase6.py — Gate 6 questions: Regulatory Compliance"""
from __future__ import annotations
from evresearch.gates.gate_runner import Question, QuestionOption


def get_questions(state: dict) -> list[Question]:
    phase6 = state.get("phase6", {})
    open_items = phase6.get("open_items", [])
    compliance_status = phase6.get("compliance_status")
    vehicle_class = phase6.get("vehicle_class")
    license_req = phase6.get("required_driver_license")
    phase5 = state.get("phase5", {})
    battery_mass = phase5.get("battery", {}).get("mass_kg")

    return [
        Question(
            id="q6.1",
            prompt=(
                "FEA simulation prioritisation\n"
                "  Two items require FEA before homologation: rollover strength + frontal impact.\n"
                f"  Overall compliance status: {compliance_status}"
            ),
            options=[
                QuestionOption("Commission both FEA studies before prototype",
                               "safest path to homologation"),
                QuestionOption("Rollover FEA first (higher risk), frontal second",
                               "phased approach"),
                QuestionOption("Note as open items, proceed to prototype at risk",
                               "faster to prototype, higher risk"),
            ],
            suggested="Commission both FEA studies before prototype",
            reason="FEA blockers cannot be resolved in CAD phase — early commissioning reduces rework",
        ),
        Question(
            id="q6.2",
            prompt=(
                f"Conditional items resolution ({len([i for i in open_items if 'conditional' in i.lower() or 'TBD' in i])} items)\n"
                "  Items include: grab rails, fire suppression, HV isolation."
            ),
            options=[
                QuestionOption("Assign to internal engineering team (document in open items)",
                               "lower cost, requires internal expertise"),
                QuestionOption("Outsource to homologation consultant",
                               "faster, higher cost"),
            ],
            suggested="Assign to internal engineering team (document in open items)",
        ),
        Question(
            id="q6.3",
            prompt=(
                f"Battery weight revision impact\n"
                f"  Selected battery mass: {battery_mass}kg\n"
                f"  Revised GVW may differ from Phase 2/5 estimates.\n"
                "  Accept revised GVW for final report?"
            ),
            options=[
                QuestionOption("Yes — use revised GVW in final report",
                               "reflects actual component selection"),
                QuestionOption("No — commission detailed weight audit first",
                               "more accurate but delays report"),
            ],
            suggested="Yes — use revised GVW in final report",
        ),
        Question(
            id="q6.4",
            prompt=(
                "Open items sign-off\n"
                "  Current open items:\n"
                + "".join(f"    • {item}\n" for item in open_items[:8])
                + "  Any additional items to flag for the engineering team? "
                "(Enter text or press Enter to skip)"
            ),
            suggested="",
        ),
    ]

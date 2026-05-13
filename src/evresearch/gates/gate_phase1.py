"""
gates/gate_phase1.py — Gate 1 questions: Market & Anthropometry
"""
from __future__ import annotations
from evresearch.gates.gate_runner import Question, QuestionOption


def get_questions(state: dict) -> list[Question]:
    phase1 = state.get("phase1", {})
    anthro = phase1.get("anthropometry", {})
    ingress = phase1.get("ingress_egress", {})
    candidates = phase1.get("capacity_candidates", [18, 20, 22])

    p95_stature = anthro.get("p95_stature_mm", 1672)
    min_seat_pitch = anthro.get("min_seat_pitch_mm", 720)
    min_aisle = anthro.get("min_aisle_width_mm", 380)
    boarding_s = ingress.get("angkot_boarding_time_s_per_passenger", 3.2)

    return [
        Question(
            id="q1.1",
            prompt="Target seated capacity for the EV shuttle",
            options=[
                QuestionOption("18 passengers", "fits small-bus p25–p75 OAL range comfortably"),
                QuestionOption("20 passengers", "requires OAL near p75 of small-bus (operator minimum)"),
                QuestionOption("22 passengers", "pushes into upper small-bus / medium-bus boundary"),
            ],
            suggested="20",
            reason=f"Meets operator minimum of 20. Candidates available: {candidates}",
            range_hint="Operator minimum: 20 passengers.",
        ),
        Question(
            id="q1.2",
            prompt="Standing passenger allowance",
            options=[
                QuestionOption("0% standing (seated only)", "simpler structure, better for Bogor hills"),
                QuestionOption("20% standing", "common in Indonesian urban transit, peak flexibility"),
                QuestionOption("30% standing", "maximises peak capacity"),
            ],
            suggested="0% standing (seated only)",
            reason="Bogor hilly terrain — comfort priority for longer dwell periods",
        ),
        Question(
            id="q1.3",
            prompt="Floor configuration",
            options=[
                QuestionOption("low-entry (single step ~200mm)", "recommended for PM 98/2017 accessibility"),
                QuestionOption("high-floor (step ~350mm)", "cheaper structure, matches angkot culture"),
            ],
            suggested="low-entry (single step ~200mm)",
            reason="PM 98/2017 max step 250mm. Low-entry stays well within.",
        ),
        Question(
            id="q1.4",
            prompt=f"Minimum seat pitch in mm (p95 requires ≥{min_seat_pitch}mm)",
            suggested=str(min_seat_pitch),
            reason=f"Indonesian p95 stature {p95_stature}mm → hip-to-knee ~670mm + 50mm comfort",
            range_hint="Survey range in target class: 680–780mm. Minimum: 720mm.",
            validator=lambda v: (v.isdigit() and 680 <= int(v) <= 900, "Must be an integer 680–900"),
        ),
        Question(
            id="q1.5",
            prompt=f"Minimum aisle clear width in mm (p95 requires ≥{min_aisle}mm)",
            suggested="400",
            reason="380mm is the anthropometric minimum; 400mm provides comfort margin",
            range_hint="Survey range: 360–450mm. Minimum per research: 380mm.",
            validator=lambda v: (v.isdigit() and 360 <= int(v) <= 600, "Must be an integer 360–600"),
        ),
    ]

"""gates/gate_phase4.py — Gate 4 questions: Demand & Operations"""
from __future__ import annotations
from evresearch.gates.gate_runner import Question, QuestionOption


def get_questions(state: dict) -> list[Question]:
    phase4 = state.get("phase4", {})
    ridership = phase4.get("ridership", {})
    usable_kwh = phase4.get("usable_battery_kwh", 165)
    fleet = phase4.get("fleet_size_recommendation", 4)

    daily_km = ridership.get("route_length_km", 12) * 15  # 15 trips estimate

    return [
        Question(
            id="q4.1",
            prompt=(
                "Seating/standing ratio\n"
                f"  Trip duration: ~{ridership.get('average_trip_duration_min', 22)} min "
                "(within PM 98/2017 30-min standing tolerance)"
            ),
            options=[
                QuestionOption("Seated only (0 standing)", "simpler structure, Bogor hills comfort"),
                QuestionOption("Up to 20% standing", "adds ~4 pax at 20-pax base for peak flexibility"),
                QuestionOption("Up to 30% standing", "maximises peak capacity"),
            ],
            suggested="Up to 20% standing",
            reason="Trip duration within PM 98/2017 tolerance; peak hour benefit",
        ),
        Question(
            id="q4.2",
            prompt=f"Daily operating range target (route estimate: {daily_km}km)",
            options=[
                QuestionOption(f"{daily_km}km (no buffer)", "exact route distance"),
                QuestionOption(f"{round(daily_km * 1.2)}km (20% buffer)", "recommended for deadheading"),
                QuestionOption(f"{round(daily_km * 1.4)}km (40% buffer)", "conservative"),
            ],
            suggested=f"{round(daily_km * 1.2)}km (20% buffer)",
            reason="20% buffer covers deadheading and route diversions",
        ),
        Question(
            id="q4.3",
            prompt="Charging strategy",
            options=[
                QuestionOption("Overnight depot only", "lower infrastructure cost, simpler ops"),
                QuestionOption("Overnight depot + opportunity charging at terminals",
                               "enables smaller battery pack"),
            ],
            suggested="Overnight depot only",
            reason=f"Daily range ~{daily_km}km well within single-charge range at {usable_kwh}kWh",
        ),
        Question(
            id="q4.4",
            prompt=f"Usable battery capacity to carry into Phase 5 sourcing (calculated: {usable_kwh}kWh)",
            suggested=str(usable_kwh) if usable_kwh else "165",
            reason="Includes 20% DoD reserve and 1.3× safety factor",
            range_hint=f"Agent calculated target: {usable_kwh}kWh based on {daily_km}km range.",
            validator=lambda v: (v.replace(".", "").isdigit() and 80 <= float(v) <= 300,
                                 "Must be a number 80–300 kWh"),
        ),
        Question(
            id="q4.5",
            prompt=f"Fleet size (agent estimate: {fleet} vehicles for full route coverage)",
            suggested=str(fleet),
            reason="Based on ridership demand and 22-minute average trip duration",
            validator=lambda v: (v.isdigit() and 1 <= int(v) <= 20, "Must be integer 1–20"),
        ),
    ]

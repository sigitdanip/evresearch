"""gates/gate_phase5.py — Gate 5 questions: Hardware BOM"""
from __future__ import annotations
from evresearch.gates.gate_runner import Question, QuestionOption


def get_questions(state: dict) -> list[Question]:
    phase5 = state.get("phase5", {})
    motor = phase5.get("motor", {})
    battery = phase5.get("battery", {})
    axle = phase5.get("axle", {})
    hardpoints = phase5.get("chassis_hardpoints", {})

    motor_label = f"{motor.get('supplier')} {motor.get('model')} ({motor.get('continuous_kw')}kW)"
    battery_label = (
        f"{battery.get('supplier')} {battery.get('model')} "
        f"({battery.get('usable_kwh')}kWh usable)"
    )
    axle_label = f"{axle.get('supplier')} {axle.get('model')}"

    return [
        Question(
            id="q5.1",
            prompt=(
                "Motor/e-axle selection\n"
                f"  Agent top pick: {motor_label}\n"
                "  Candidates presented in Phase 5 summary above.\n"
                "  Enter '1', '2', '3' for ranked candidate, or 'none' to flag for more research."
            ),
            suggested="1",
            reason="Top-ranked candidate meets power/torque spec with ASEAN availability",
        ),
        Question(
            id="q5.2",
            prompt=(
                "Battery selection\n"
                f"  Agent top pick: {battery_label}\n"
                "  Note: Check if usable kWh meets Gate 4 target and dimensions fit underfloor.\n"
                "  Enter '1', '2', '3' for ranked candidate, or '4' to override target."
            ),
            suggested="1",
            reason="Top-ranked candidate meets kWh target; verify physical fit",
        ),
        Question(
            id="q5.3",
            prompt=(
                "Rear axle selection\n"
                f"  Agent top pick: {axle_label}\n"
                "  Enter '1', '2', or '3'."
            ),
            suggested="1",
        ),
        Question(
            id="q5.4",
            prompt=(
                "Chassis hardpoint confirmation\n"
                f"  Battery box floor height: {hardpoints.get('battery_box_floor_height_mm')}mm\n"
                f"  Motor cradle: {hardpoints.get('motor_cradle_position')}\n"
                f"  Suspension type: {hardpoints.get('suspension_type')}\n"
                "  Accept agent defaults or enter overrides in override section?"
            ),
            options=[
                QuestionOption("Accept all agent-derived hardpoints", "proceed to Phase 6"),
                QuestionOption("Override (use override section below)", "custom CAD requirements"),
            ],
            suggested="Accept all agent-derived hardpoints",
        ),
    ]

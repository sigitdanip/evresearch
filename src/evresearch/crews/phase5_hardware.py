"""
crews/phase5_hardware.py — Phase 5: Hardware BOM Sourcing Crew
Agents: Powertrain Sourcing, Battery Sourcing, Axle Sourcing, Chassis Synthesiser
"""
from __future__ import annotations

import json
import time

from crewai import Agent, Crew, Process, Task

from evresearch.config.settings import get_llm, TASK_SLEEP_S
from evresearch.tools.calculator import calc_gvw
from evresearch.tools.scraper import scrape_page
from evresearch.tools.web_search import web_search


def run_phase5(state: dict) -> dict:
    """Phase 5 crew — motor, battery, axle sourcing + chassis synthesis."""
    time.sleep(TASK_SLEEP_S)

    gate4 = state.get("phase4", {}).get("gate_decisions", {})
    gate3 = state.get("phase3", {}).get("gate_decisions", {})

    req_power_kw = float(gate3.get("required_power_kw", gate3.get("q3.3_power_kw", 65.6)))
    req_torque_nm = float(gate3.get("required_torque_nm", gate3.get("q3.3_torque_nm", 285)))
    req_battery_kwh = float(gate4.get("usable_battery_kwh", gate4.get("q4.4", 165)))

    candidates = state.get("phase2", {}).get("candidates", [])
    target_cap_candidate = next(
        (c for c in candidates if c.get("capacity") == 20), {}
    )
    underfloor_length = 2250  # mm — from Phase 2 structural analysis
    underfloor_width = 1100
    underfloor_depth = 150

    ctx = (
        f"Motor requirements: ≥{req_power_kw}kW continuous, ≥{req_torque_nm}Nm peak torque\n"
        f"Battery requirements: ≥{req_battery_kwh}kWh usable\n"
        f"Underfloor space: {underfloor_length}×{underfloor_width}×{underfloor_depth}mm\n"
        f"Availability preference: Indonesia or ASEAN distributors"
    )

    powertrain_sourcing = Agent(
        role="EV Powertrain Procurement Specialist",
        goal=f"Source ≥3 motor/e-axle candidates meeting ≥{req_power_kw}kW and ≥{req_torque_nm}Nm.",
        backstory=(
            "You are a procurement specialist for EV drivetrain components with expertise "
            "in ASEAN supplier networks. You search for commercially available motor or e-axle "
            "units matching the power/torque spec with verified ASEAN/Indonesia availability. "
            f"Context: {ctx}"
        ),
        llm=get_llm("powertrain_sourcing"),
        tools=[web_search, scrape_page],
        verbose=True,
        max_iter=12,
        max_retry_limit=2,
    )

    battery_sourcing = Agent(
        role="EV Battery System Procurement Specialist",
        goal=(
            f"Source ≥3 LFP battery pack candidates providing ≥{req_battery_kwh}kWh usable "
            f"and fitting within {underfloor_length}×{underfloor_width}×{underfloor_depth}mm."
        ),
        backstory=(
            "You are a battery procurement specialist with expertise in LFP cell chemistry "
            "for transit applications. You prioritise cell-to-pack designs (CATL, BYD Blade, Gotion) "
            "for space efficiency. You always verify pack dimensions against the underfloor constraint. "
            f"Context: {ctx}"
        ),
        llm=get_llm("battery_sourcing"),
        tools=[web_search, scrape_page],
        verbose=True,
        max_iter=12,
        max_retry_limit=2,
    )

    axle_sourcing = Agent(
        role="Chassis & Axle Procurement Specialist",
        goal=(
            "Source ≥3 rear axle candidates for a 5,450–6,200kg GVW vehicle "
            "with track width 1,680–1,760mm and Indonesia/ASEAN availability."
        ),
        backstory=(
            "You are a chassis procurement specialist. You search for portal or beam rear axles "
            "matching the GVW and track width requirements. You check supplier regional availability. "
            f"Context: {ctx}"
        ),
        llm=get_llm("axle_sourcing"),
        tools=[web_search, scrape_page],
        verbose=True,
        max_iter=10,
        max_retry_limit=2,
    )

    chassis_synthesiser = Agent(
        role="Chassis Integration & Hardpoints Synthesiser",
        goal=(
            "Derive chassis hardpoints from the sourced component dimensions. "
            "Output battery box floor height, motor cradle position, suspension type, "
            "and revised GVW with selected battery mass."
        ),
        backstory=(
            "You are a structural integration engineer. You take the selected motor, battery, "
            "and axle specs and derive the chassis hardpoints needed for CAD. "
            "You call GVWCalculator with the actual battery mass from the selected battery. "
            f"Context: {ctx}"
        ),
        llm=get_llm("chassis_synthesiser"),
        tools=[calc_gvw],
        verbose=True,
        max_iter=10,
        max_retry_limit=2,
        reasoning=True,
    )

    motor_task = Task(
        description=(
            f"Search for ≥3 motor or integrated e-axle candidates meeting:\n"
            f"  - Continuous power: ≥{req_power_kw}kW\n"
            f"  - Peak torque: ≥{req_torque_nm}Nm\n"
            f"  - Voltage: 400V preferred\n"
            f"  - Availability: Indonesia or ASEAN distributor\n"
            "Search strategy: Broad search for 'e-axle specifications ASEAN', "
            "'EV motor specifications Indonesia', or 'driveline specs transit bus'\n"
            "Output JSON:\n"
            '{"motor_candidates":['
            '{"rank":<int>,"supplier":"<string>","model":"<string>",'
            '"continuous_kw":<float>,"peak_torque_nm":<int>,"voltage_v":<int>,'
            '"availability":"<string>","source_url":"<url>"}]}'
        ),
        expected_output="JSON with motor_candidates array of ≥3 entries with full specs and availability.",
        agent=powertrain_sourcing,
    )

    battery_task = Task(
        description=(
            f"Search for ≥3 LFP battery pack candidates meeting:\n"
            f"  - Usable capacity: ≥{req_battery_kwh}kWh\n"
            f"  - Pack fit: ≤{underfloor_length}mm L × ≤{underfloor_width}mm W × ≤{underfloor_depth}mm H\n"
            "  - Chemistry: LFP preferred\n"
            "Search strategy: Search for 'LFP pack specifications dimensions' or "
            "'battery module specifications dimensions weight'\n"
            "For each, verify pack dimensions fit underfloor constraints.\n"
            "Output JSON:\n"
            '{"battery_candidates":['
            '{"rank":<int>,"supplier":"<string>","model":"<string>",'
            '"total_kwh":<float>,"usable_kwh":<float>,"pack_length_mm":<int>,'
            '"pack_width_mm":<int>,"pack_height_mm":<int>,"mass_kg":<int>,'
            '"fits_underfloor":<bool>,"clearance_mm":<int>,"source_url":"<url>"}]}'
        ),
        expected_output=(
            "JSON with battery_candidates array of ≥3 entries with dimensions, "
            "usable_kwh, mass, fits_underfloor flag, and clearance."
        ),
        agent=battery_sourcing,
    )

    axle_task = Task(
        description=(
            "Search for ≥3 rear axle candidates for GVW 5,450–6,200kg vehicle:\n"
            "  - Max payload: ≥3,500kg\n"
            "  - Track width: 1,680–1,760mm\n"
            "  - Type: portal or conventional beam (EV-compatible)\n"
            "Search strategy: Broad search for 'portal rear axle specifications Indonesia' or 'EV axle specifications ASEAN'\n"
            "Output JSON:\n"
            '{"axle_candidates":['
            '{"rank":<int>,"supplier":"<string>","model":"<string>","max_payload_kg":<int>,'
            '"track_width_mm":<int>,"type":"<string>","availability":"<string>","source_url":"<url>"}]}'
        ),
        expected_output="JSON with axle_candidates array of ≥3 entries.",
        agent=axle_sourcing,
    )

    chassis_task = Task(
        description=(
            "Using the top-ranked motor and battery candidates from previous tasks, "
            "derive chassis hardpoints:\n"
            "1. Call GVWCalculator with capacity=20, kerb_weight_kg=3800, "
            "battery_mass_kg=<mass from selected battery>\n"
            "2. Derive battery_box_floor_height_mm from selected battery height + frame\n"
            "3. Specify motor_cradle_position (front/rear/centre)\n"
            "4. Recommend suspension_type (leaf/coil/air)\n"
            "Output JSON:\n"
            '{"selected_motor":{"supplier":"<string>","model":"<string>","continuous_kw":<float>},'
            '"selected_battery":{"supplier":"<string>","model":"<string>","usable_kwh":<float>,"mass_kg":<int>},'
            '"selected_axle":{"supplier":"<string>","model":"<string>"},'
            '"revised_gvw_kg":<int>,'
            '"chassis_hardpoints":{'
            '"battery_box_floor_height_mm":<int>,'
            '"motor_cradle_position":"<string>",'
            '"suspension_type":"<string>",'
            '"battery_box_dims_mm":"<string>"'
            '}}'
        ),
        expected_output=(
            "JSON with selected_motor, selected_battery, selected_axle, "
            "revised_gvw_kg, and chassis_hardpoints dict."
        ),
        agent=chassis_synthesiser,
        context=[motor_task, battery_task, axle_task],
    )

    crew = Crew(
        agents=[powertrain_sourcing, battery_sourcing, axle_sourcing, chassis_synthesiser],
        tasks=[motor_task, battery_task, axle_task, chassis_task],
        process=Process.sequential,
        max_rpm=15,
        verbose=True,
    )

    crew.kickoff()

    phase5_data: dict = {
        "motor": {},
        "battery": {},
        "axle": {},
        "chassis_hardpoints": {},
        "gate_decisions": {},
        "_raw_outputs": {
            "motor": motor_task.output.raw if motor_task.output else "",
            "battery": battery_task.output.raw if battery_task.output else "",
            "axle": axle_task.output.raw if axle_task.output else "",
            "chassis": chassis_task.output.raw if chassis_task.output else "",
        },
    }

    if chassis_task.output and chassis_task.output.raw:
        try:
            raw = chassis_task.output.raw.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            phase5_data["motor"] = parsed.get("selected_motor", {})
            phase5_data["battery"] = parsed.get("selected_battery", {})
            phase5_data["axle"] = parsed.get("selected_axle", {})
            phase5_data["chassis_hardpoints"] = parsed.get("chassis_hardpoints", {})
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            raise ValueError(f"CRITICAL FAILURE: Agent failed to produce valid JSON for phase 5 chassis synthesis. Error: {e}")

    return phase5_data

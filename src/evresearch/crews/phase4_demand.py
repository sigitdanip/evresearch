"""
crews/phase4_demand.py — Phase 4: Demand & Operations Crew
Agents: Ridership Analyst, Comfort Analyst, Charging Modeller
"""
from __future__ import annotations

import json
import time

from crewai import Agent, Crew, Process, Task

from evresearch.config.settings import get_llm, TASK_SLEEP_S
from evresearch.tools.bps_tool import query_bps_bogor_transport
from evresearch.tools.calculator import calc_range
from evresearch.tools.pdf_reader import read_pdf
from evresearch.tools.web_search import web_search


def run_phase4(state: dict) -> dict:
    """Phase 4 crew — ridership, comfort standards, charging model. Returns phase4 dict."""
    time.sleep(TASK_SLEEP_S)

    gate3 = state.get("phase3", {}).get("gate_decisions", {})
    confirmed_capacity = int(gate3.get("confirmed_capacity", gate3.get("q3.2", 20)))
    kwh_per_km = float(gate3.get("kwh_per_km", gate3.get("q3.4", 1.41)))
    power_margin = gate3.get("power_margin", "15%")

    ctx = (
        f"Confirmed capacity: {confirmed_capacity} passengers | "
        f"Energy consumption: {kwh_per_km} kWh/km | "
        f"Motor power margin: {power_margin}"
    )

    ridership_analyst = Agent(
        role="Transit Demand & Ridership Analyst",
        goal=(
            "Quantify Bogor commuter ridership patterns: peak hour factor, "
            "average occupancy, trip duration, and route length estimate."
        ),
        backstory=(
            "You are a transit demand analyst specialising in Indonesian secondary cities. "
            "You query BPS data and cross-reference with TransJakarta/BisKita studies "
            "to establish ridership parameters for the Stasiun Bogor loop corridor. "
            f"Context: {ctx}"
        ),
        llm=get_llm("ridership_analyst"),
        tools=[query_bps_bogor_transport, web_search],
        verbose=True,
        max_iter=8,
        max_retry_limit=2,
    )

    comfort_analyst = Agent(
        role="Transit Comfort Standards Specialist",
        goal=(
            "Extract PM 98/2017 standing tolerance rules, dwell time budgets, "
            "and door configuration standards for the confirmed capacity."
        ),
        backstory=(
            "You are a transit standards specialist with deep knowledge of Indonesian "
            "Peraturan Menteri (PM) regulations. You extract PM 98/2017 standing/seating "
            "ratio requirements and translate them to operational guidelines. "
            f"Context: {ctx}"
        ),
        llm=get_llm("comfort_analyst"),
        tools=[web_search, read_pdf],
        verbose=True,
        max_iter=8,
        max_retry_limit=2,
    )

    charging_modeller = Agent(
        role="Fleet Charging & Operations Planner",
        goal=(
            f"Model the daily energy budget for {confirmed_capacity}-pax EV shuttle at "
            f"{kwh_per_km} kWh/km. Calculate required usable battery kWh, "
            "overnight charging feasibility, and fleet size recommendation."
        ),
        backstory=(
            "You are a fleet operations planner specialising in EV transit systems. "
            "You use RangeCalculator to model energy budgets. You apply a 1.3× safety "
            "factor for battery sizing and a 20% DoD reserve. "
            f"Context: {ctx}"
        ),
        llm=get_llm("charging_modeller"),
        tools=[calc_range],
        verbose=True,
        max_iter=10,
        max_retry_limit=2,
        reasoning=True,
    )

    # -----------------------------------------------------------------------
    ridership_task = Task(
        description=(
            "Query BPSTransportTool and supplement with web search for Bogor commuter data.\n"
            "Search: 'BisKita Trans Pakuan ridership Bogor 2023', "
            "'Stasiun Bogor penumpang harian angkot trips'\n"
            "Output JSON:\n"
            '{"peak_hour_factor":1.8,"average_daily_ridership_per_route":420,'
            '"average_occupancy_off_peak_pct":58.0,"average_trip_duration_min":22,'
            '"route_length_km":12,"source":"BPS Kota Bogor 2023 + BisKita reports"}'
        ),
        expected_output="JSON with ridership parameters and source.",
        agent=ridership_analyst,
    )

    comfort_task = Task(
        description=(
            "Extract PM 98/2017 standards for standing passenger tolerance and door config.\n"
            "Search: 'PM 98/2017 standar pelayanan minimal angkutan', "
            "'Permenhub 98 2017 rasio berdiri duduk penumpang'\n"
            "Determine:\n"
            "- Maximum standing ratio permitted for trip ≤30 min\n"
            "- Recommended dwell time budget (seconds per stop)\n"
            "- Door configuration recommendation for 20-pax shuttle\n"
            "Output JSON:\n"
            '{"pm98_standing_tolerance_trip_min":30,'
            '"recommended_standing_ratio_pct":20,'
            '"dwell_time_budget_s":{"min":30,"max":45},'
            '"recommended_door_config":"1 front + 1 rear (2-leaf each)",'
            '"source":"PM 98/2017 Kemenhub"}'
        ),
        expected_output="JSON with PM 98/2017 comfort parameters and door config recommendation.",
        agent=comfort_analyst,
    )

    charging_task = Task(
        description=(
            f"Model battery sizing for {confirmed_capacity}-pax EV shuttle at {kwh_per_km} kWh/km.\n"
            "Step 1: Establish daily route distance = 180km (Stasiun Bogor loop, 15 trips × 12km).\n"
            f"Step 2: Daily energy = 180km × {kwh_per_km} kWh/km.\n"
            "Step 3: Apply 20% DoD reserve → usable_kwh_needed = daily_energy / 0.8.\n"
            "Step 4: Apply 1.3× safety factor → recommended_usable_kwh = usable_kwh_needed × 1.3.\n"
            "Step 5: Call RangeCalculator with:\n"
            f"  usable_battery_kwh = recommended_usable_kwh\n"
            f"  base_consumption_kwh_per_km = {kwh_per_km}\n"
            "  hvac_kw = 8.4 (from Phase 3)\n"
            "  average_speed_kmh = 25\n"
            "Step 6: Model overnight charge: window 20:00–05:00 (9 hours), 40kW AC charger.\n"
            "Step 7: Estimate fleet size from ridership (daily_ridership / vehicle_capacity / trips).\n"
            "Output JSON:\n"
            '{"daily_route_km":180,"daily_energy_kwh":253.8,"usable_battery_kwh":165,'
            '"recommended_pack_kwh":165,"charging_strategy":"overnight_depot",'
            '"overnight_charge_window_h":9,"charger_power_kw":40,'
            '"fleet_size_recommendation":4,'
            '"range_with_pack_km":117.0}'
        ),
        expected_output=(
            "JSON with daily_route_km, daily_energy_kwh, usable_battery_kwh, "
            "recommended_pack_kwh, charging_strategy, and fleet_size_recommendation."
        ),
        agent=charging_modeller,
        context=[ridership_task],
    )

    crew = Crew(
        agents=[ridership_analyst, comfort_analyst, charging_modeller],
        tasks=[ridership_task, comfort_task, charging_task],
        process=Process.sequential,
        max_rpm=15,
        verbose=True,
    )

    crew.kickoff()

    phase4_data: dict = {
        "ridership": {},
        "seating_standing_ratio": None,
        "door_config": None,
        "usable_battery_kwh": None,
        "charging_strategy": None,
        "fleet_size_recommendation": None,
        "gate_decisions": {},
        "_raw_outputs": {
            "ridership": ridership_task.output.raw if ridership_task.output else "",
            "comfort": comfort_task.output.raw if comfort_task.output else "",
            "charging": charging_task.output.raw if charging_task.output else "",
        },
    }

    for task_name, task_obj in [
        ("ridership", ridership_task),
        ("comfort", comfort_task),
        ("charging", charging_task),
    ]:
        if task_obj.output and task_obj.output.raw:
            try:
                raw = task_obj.output.raw.strip()
                if "```" in raw:
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                parsed = json.loads(raw)
                if task_name == "ridership":
                    phase4_data["ridership"] = parsed
                elif task_name == "comfort":
                    phase4_data["seating_standing_ratio"] = (
                        f"{parsed.get('recommended_standing_ratio_pct', 20)}% standing"
                    )
                    phase4_data["door_config"] = parsed.get("recommended_door_config")
                elif task_name == "charging":
                    phase4_data["usable_battery_kwh"] = parsed.get("usable_battery_kwh")
                    phase4_data["charging_strategy"] = parsed.get("charging_strategy")
                    phase4_data["fleet_size_recommendation"] = parsed.get("fleet_size_recommendation")
            except (json.JSONDecodeError, IndexError, KeyError):
                pass

    return phase4_data

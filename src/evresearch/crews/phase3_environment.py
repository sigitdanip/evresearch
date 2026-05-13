"""
crews/phase3_environment.py — Phase 3: Environment Viability Crew (Hierarchical)
Agents: Topography Analyst, Climate Analyst, Swept Path Filter,
        Powertrain Simulation Engineer, HVAC & Range Engineer, Viability Synthesiser
"""
from __future__ import annotations

import json
import time

from crewai import Agent, Crew, Process, Task

from evresearch.config.settings import get_llm, TASK_SLEEP_S
from evresearch.tools.bmkg_tool import query_bmkg_bogor
from evresearch.tools.calculator import (
    calc_hill_torque,
    calc_hvac_load,
    calc_range,
    calc_swept_path,
)
from evresearch.tools.osm_tool import query_bogor_gradients, query_osm
from evresearch.tools.web_search import web_search


def run_phase3(state: dict) -> dict:
    """Phase 3 crew — environment, swept path, powertrain, HVAC, range. Returns phase3 dict."""
    time.sleep(TASK_SLEEP_S)

    gate2 = state.get("phase2", {}).get("gate_decisions", {})
    candidates = state.get("phase2", {}).get("candidates", [])
    confirmed_gvw = float(gate2.get("confirmed_gvw_kg", gate2.get("q2.5_gvw")))
    max_oal = float(gate2.get("max_oal_mm", gate2.get("q2.2")))

    candidates_ctx = json.dumps(candidates, indent=2) if candidates else "[]"

    # -----------------------------------------------------------------------
    topography_analyst = Agent(
        role="Bogor Topography & Road Geometry Analyst",
        goal=(
            "Query OSM Overpass API and web sources for Bogor road characteristics: "
            "maximum gradient %, tightest turning radius, typical lane widths."
        ),
        backstory=(
            "You are a geospatial analyst specialising in Indonesian urban road networks. "
            "You query OpenStreetMap and cross-reference with field reports to extract "
            "the critical road geometry constraints for Bogor EV shuttle routes. "
            "Use the BogorGradientQuery tool first, then supplement with web search."
        ),
        llm=get_llm("topography_analyst"),
        tools=[query_bogor_gradients, query_osm, web_search],
        verbose=True,
        max_iter=8,
        max_retry_limit=2,
    )

    climate_analyst = Agent(
        role="Bogor Climate & Thermal Environment Analyst",
        goal="Extract Bogor design climate values from BMKG: temperature, humidity, rainfall.",
        backstory=(
            "You are a climatologist specialising in Indonesian tropical conditions. "
            "You source design values from BMKG official data and ASHRAE tropical zone guidance. "
            "Use the BMKGClimateTool to get official Bogor climate data."
        ),
        llm=get_llm("climate_analyst"),
        tools=[query_bmkg_bogor, web_search],
        verbose=True,
        max_iter=5,
        max_retry_limit=2,
    )

    swept_path_filter = Agent(
        role="Vehicle Dynamics & Swept Path Engineer",
        goal=(
            "Apply swept path calculations to each dimension candidate. "
            "Classify each as PASS, MARGINAL, or FAIL against the tightest Bogor corner."
        ),
        backstory=(
            "You are a vehicle dynamics engineer specialising in bus swept-path analysis. "
            "You call SweptPathCalculator for each candidate and compare the result against "
            "the tightest available turning radius from the topography analysis. "
            "Output structured JSON with PASS/MARGINAL/FAIL classification.\n"
            f"Candidates to evaluate:\n{candidates_ctx}"
        ),
        llm=get_llm("swept_path_filter"),
        tools=[calc_swept_path],
        verbose=True,
        max_iter=10,
        max_retry_limit=2,
    )

    powertrain_sim = Agent(
        role="EV Powertrain Simulation Engineer",
        goal=(
            "Calculate required continuous motor power and peak torque for each surviving "
            "candidate on Bogor's maximum gradient. Flag minimum motor spec."
        ),
        backstory=(
            "You are an EV powertrain engineer. You call HillTorqueCalculator with GVW "
            "and maximum gradient to derive required motor specifications. "
            "You never perform manual arithmetic — use the tool exclusively. "
            "Output structured JSON with powertrain requirements per capacity."
        ),
        llm=get_llm("powertrain_sim"),
        tools=[calc_hill_torque],
        verbose=True,
        max_iter=10,
        max_retry_limit=2,
    )

    hvac_range_engineer = Agent(
        role="HVAC & Energy Range Engineer",
        goal=(
            "Calculate HVAC cooling load and energy consumption per km for surviving candidates. "
            "Use Bogor climate data (34°C, 88% RH) from the climate analysis."
        ),
        backstory=(
            "You are a thermal systems engineer specialising in EV HVAC for tropical climates. "
            "You call HVACCalculator and RangeCalculator with cabin volumes derived from "
            "candidate dimensions. Output kWh/km and HVAC load in kW."
        ),
        llm=get_llm("hvac_range_engineer"),
        tools=[calc_hvac_load, calc_range],
        verbose=True,
        max_iter=10,
        max_retry_limit=2,
    )

    viability_synthesiser = Agent(
        role="Lead Systems Engineer — Viability Synthesiser",
        goal=(
            "Integrate swept path, powertrain, and HVAC results. Rank surviving candidates. "
            "Produce a ranked recommendation with supporting evidence for each decision."
        ),
        backstory=(
            "You are a lead systems engineer with deep expertise in EV bus design for "
            "Indonesian conditions. You synthesise multi-domain analysis outputs, resolve "
            "conflicting constraints, and produce a structured recommendation. "
            "DeepSeek R1 extended reasoning is leveraged here. "
            "Output structured JSON only — no prose outside JSON strings."
        ),
        llm=get_llm("viability_synthesiser"),
        verbose=True,
        max_iter=15,
        max_retry_limit=2,
        reasoning=True,
    )

    # -----------------------------------------------------------------------
    topo_task = Task(
        description=(
            "Query OpenStreetMap and web sources for Bogor road geometry constraints.\n"
            "Use BogorGradientQuery tool first.\n"
            "Search strategy: Use broad terms like 'Bogor steep road gradients' or 'Pasar Anyar Bogor road layout'.\n"
            "Output JSON:\n"
            '{"max_gradient_pct":<float>,"tightest_turning_radius_m":<float>,'
            '"typical_lane_width_m":<float>,"min_lane_width_m":<float>,'
            '"critical_locations":[<list of strings>],'
            '"source":"<string citing data sources>"}'
        ),
        expected_output="JSON with max_gradient_pct, tightest_turning_radius_m, lane widths, critical locations.",
        agent=topography_analyst,
    )

    climate_task = Task(
        description=(
            "Query BMKG for Bogor design climate conditions.\n"
            "Use BMKGClimateTool tool.\n"
            "Output JSON:\n"
            '{"design_temp_c":<float>,"design_rh_pct":<float>,"annual_rainfall_mm":<int>,'
            '"hvac_design_conditions":"<string>","source":"<string>"}'
        ),
        expected_output="JSON with design_temp_c, design_rh_pct, annual_rainfall_mm, and source.",
        agent=climate_analyst,
    )

    swept_task = Task(
        description=(
            "For each dimension candidate, call SweptPathCalculator.\n"
            f"Candidates: {candidates_ctx}\n"
            "Compare each min_turning_radius_m against the tightest available corner "
            "(use 7.2m from topography analysis as default if not available).\n"
            "Classify: PASS if ≤ available, MARGINAL if ≤ available + 0.3m, FAIL if > available + 0.3m.\n"
            "Output JSON:\n"
            '{"swept_path_results":['
            '{"capacity":<int>,"min_turning_radius_m":<float>,"classification":"<PASS|MARGINAL|FAIL>",'
            '"note":"<string>"}],'
            '"tightest_corner_m":<float>}'
        ),
        expected_output=(
            "JSON with swept_path_results array (capacity, min_turning_radius_m, classification, note) "
            "and tightest_corner_m used."
        ),
        agent=swept_path_filter,
        context=[topo_task],
    )

    powertrain_task = Task(
        description=(
            "For each PASS or MARGINAL candidate from swept path results, "
            "call HillTorqueCalculator with:\n"
            "  gvw_kg = candidate GVW from Phase 2 (default 5450 for 20pax)\n"
            "  gradient_pct = max gradient from topography (default 18.3)\n"
            "  speed_kmh = 30 (minimum hill speed)\n"
            "Add 15% margin to the result for motor specification floor.\n"
            "Output JSON:\n"
            '{"powertrain_requirements":{'
            '"<capacity_str>":{"base_continuous_kw":<float>,"with_15pct_margin_kw":<float>,"peak_torque_nm":<int>}}}'
        ),
        expected_output=(
            "JSON with powertrain_requirements per surviving capacity, "
            "showing base and margined power/torque specs."
        ),
        agent=powertrain_sim,
        context=[swept_task],
    )

    hvac_task = Task(
        description=(
            "For each surviving candidate, compute HVAC load and total energy consumption.\n"
            "Estimate cabin volume as: internal_length × internal_width × 2.1m height.\n"
            "  18pax: cabin ≈ 5.56 × 1.74 × 2.1 = 20.3 m³\n"
            "  20pax: cabin ≈ 6.00 × 1.74 × 2.1 = 21.9 m³\n"
            "Call HVACCalculator with ambient_temp_c=34.0 for each.\n"
            "Call RangeCalculator with:\n"
            "  base_consumption_kwh_per_km = 0.9 (traction only estimate)\n"
            "  hvac_kw = result from HVACCalculator\n"
            "  average_speed_kmh = 25\n"
            "Output JSON:\n"
            '{"hvac_range_results":{'
            '"<capacity_str>":{"hvac_kw":<float>,"total_kwh_per_km":<float>}}}'
        ),
        expected_output="JSON with hvac_range_results per capacity showing hvac_kw and total_kwh_per_km.",
        agent=hvac_range_engineer,
        context=[climate_task, powertrain_task],
    )

    synthesis_task = Task(
        description=(
            "Synthesise all Phase 3 results: swept path, powertrain, HVAC/range.\n"
            "Rank surviving candidates. Produce final recommendation with evidence.\n"
            "Format output as:\n"
            '{"environment":{'
            '"max_gradient_pct":<float>,"tightest_turning_m":<float>,'
            '"design_temp_c":<float>,"design_rh_pct":<float>},'
            '"surviving_candidates":[{"capacity":<int>,"swept_path":"<string>",'
            '"powertrain_kw":<float>,"hvac_kw":<float>,"kwh_per_km":<float>}],'
            '"eliminated_candidates":[{"capacity":<int>,"reason":"<string>"}],'
            '"powertrain_requirements":{"recommended_continuous_kw":<float>,"peak_torque_nm":<int>},'
            '"hvac_load_kw":<float>,'
            '"energy_consumption_kwh_per_km":<float>,'
            '"recommended_capacity":<int>,'
            '"recommendation_rationale":"<string>"}'
        ),
        expected_output=(
            "JSON with environment, surviving_candidates, eliminated_candidates, "
            "powertrain_requirements, hvac_load_kw, energy_consumption_kwh_per_km, "
            "recommended_capacity, and recommendation_rationale."
        ),
        agent=viability_synthesiser,
        context=[swept_task, powertrain_task, hvac_task],
    )

    crew = Crew(
        agents=[
            topography_analyst,
            climate_analyst,
            swept_path_filter,
            powertrain_sim,
            hvac_range_engineer,
            viability_synthesiser,
        ],
        tasks=[topo_task, climate_task, swept_task, powertrain_task, hvac_task, synthesis_task],
        process=Process.sequential,
        max_rpm=15,
        verbose=True,
    )

    crew.kickoff()

    phase3_data: dict = {
        "environment": {},
        "surviving_candidates": [],
        "eliminated_candidates": [],
        "powertrain_requirements": {},
        "hvac_load_kw": None,
        "energy_consumption_kwh_per_km": None,
        "recommended_capacity": None,
        "gate_decisions": {},
        "_raw_outputs": {
            "topo": topo_task.output.raw if topo_task.output else "",
            "climate": climate_task.output.raw if climate_task.output else "",
            "swept": swept_task.output.raw if swept_task.output else "",
            "powertrain": powertrain_task.output.raw if powertrain_task.output else "",
            "hvac": hvac_task.output.raw if hvac_task.output else "",
            "synthesis": synthesis_task.output.raw if synthesis_task.output else "",
        },
    }

    if synthesis_task.output and synthesis_task.output.raw:
        try:
            raw = synthesis_task.output.raw.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            phase3_data.update({k: parsed[k] for k in parsed if k in phase3_data})
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            raise ValueError(f"CRITICAL FAILURE: Agent failed to produce valid JSON for phase 3 synthesis. Error: {e}")

    return phase3_data

"""
crews/phase1_market.py — Phase 1: Market Survey & Anthropometry Crew
Agents: Survey Collector, Survey Validator, Anthropometry Specialist,
        Passenger Flow Analyst, Capacity Layout Synthesiser
"""
from __future__ import annotations

import json
import time

from crewai import Agent, Crew, Process, Task

from evresearch.config.settings import (
    SURVEY_MINIMUM,
    TARGET_CAPACITY_MIN,
    VEHICLE_CLASSES,
    get_llm,
    TASK_SLEEP_S,
)
from evresearch.tools.calculator import calc_internal_box
from evresearch.tools.bps_tool import query_bps_bogor_transport
from evresearch.tools.pdf_reader import read_pdf
from evresearch.tools.scraper import scrape_page
from evresearch.tools.web_search import web_search

_CLASS_SUMMARY = json.dumps(
    {k: v["label"] + f", capacity {v['capacity_range']}, OAL {v['oal_mm_range']}mm"
     for k, v in VEHICLE_CLASSES.items()},
    indent=2,
)

_SURVEY_QUERIES = """
Pass 1 — Angkot-class (target ≥5):
  - "Toyota Kijang Minibus specifications dimensions mm Indonesia"
  - "Daihatsu Gran Max minibus technical specifications"
  - "Isuzu Elf NKR 55 dimensions wheelbase capacity"
  - "Suzuki Carry minibus dimensions Indonesia specifications"
  - "Daihatsu Hijet specifications angkot Indonesia"
  - "Mitsubishi L300 minibus specifications dimensions"
  - "Toyota Avanza minibus angkot dimensions"

Pass 2 — Small Bus/Mikrobus (target ≥8):
  - "Isuzu Elf NKR 71 bus specifications length width height"
  - "Toyota Coaster specifications dimensions capacity"
  - "Mitsubishi Rosa specifications technical dimensions"
  - "Hino Poncho EV specifications dimensions Japan"
  - "Karsan e-Jest EV specifications dimensions"
  - "BisKita Trans Pakuan vehicle specifications Bogor"
  - "EasyMile EZ10 autonomous shuttle dimensions specifications"
  - "King Long XMQ6802 specifications dimensions"
  - "Yutong E8 EV bus specifications dimensions"
  - "Hino Dutro Small Bus specifications"

Pass 3 — Medium Bus (target ≥5):
  - "Hino Dutro 110 SDL specifications dimensions"
  - "Mercedes-Benz OF 1521 bus specifications"
  - "Isuzu NQR bus specifications dimensions"
  - "MAN Lion City bus specifications dimensions"
  - "Zhongtong LCK6108EV EV bus specifications"
"""

_AGENT_SYSTEM_SUFFIX = f"""
HARD CONSTRAINTS (non-negotiable):
- Operator minimum capacity: {TARGET_CAPACITY_MIN} passengers. Never propose below this.
- Vehicle classes in scope:
{_CLASS_SUMMARY}
- Output ONLY valid JSON. No prose, no markdown explanation outside the JSON.
- All dimensions in millimetres. Power in kW. Torque in Nm. Weight in kg.
- Prioritise Indonesian sources (SNI, Kemenhub, BPS, BMKG) over international.
"""


def run_phase1(state: dict) -> dict:
    """Build and kick off the Phase 1 crew. Returns updated phase1 state dict."""
    time.sleep(TASK_SLEEP_S)  # rate-limit buffer

    # -----------------------------------------------------------------------
    # Agent definitions
    # -----------------------------------------------------------------------
    survey_collector = Agent(
        role="Vehicle Survey Researcher",
        goal=(
            f"Collect verified specifications for at least {SURVEY_MINIMUM} real-world "
            "reference vehicles across three classes: angkot, small_bus, medium_bus."
        ),
        backstory=(
            "You are an expert transit vehicle researcher with deep knowledge of "
            "Indonesian and ASEAN bus/minivan markets. You systematically search "
            "manufacturer websites, spec sheets, and public databases to build a "
            "comprehensive vehicle survey database." + _AGENT_SYSTEM_SUFFIX
        ),
        llm=get_llm("survey_collector"),
        tools=[web_search, scrape_page],
        verbose=True,
        max_iter=15,
        max_retry_limit=2,
    )

    survey_validator = Agent(
        role="Survey Data Quality Analyst",
        goal=(
            "Validate survey completeness: ≥20 total vehicles, ≥5 per class, "
            "≥10 verified entries. Compute per-class dimensional statistics."
        ),
        backstory=(
            "You are a data quality analyst specialising in structured dataset "
            "validation. You check completeness, flag data confidence levels, "
            "and compute descriptive statistics (min, max, mean, p25, p75) "
            "per vehicle class." + _AGENT_SYSTEM_SUFFIX
        ),
        llm=get_llm("survey_validator"),
        verbose=True,
        max_iter=5,
        max_retry_limit=2,
    )

    anthropometry_specialist = Agent(
        role="Human Factors & Anthropometry Specialist",
        goal=(
            "Extract Indonesian 95th-percentile body dimensions from SNI/WHO SEARO sources. "
            "Derive minimum seat pitch, aisle width, headroom, door width, and step height."
        ),
        backstory=(
            "You are a human factors engineer specialising in Indonesian passenger "
            "anthropometry. You source data from SNI standards (Indonesian National "
            "Standard), WHO SEARO regional data, and published ergonomics studies "
            "to establish minimum interior space requirements." + _AGENT_SYSTEM_SUFFIX
        ),
        llm=get_llm("anthropometry_specialist"),
        tools=[web_search, read_pdf, scrape_page],
        verbose=True,
        max_iter=10,
        max_retry_limit=2,
    )

    flow_analyst = Agent(
        role="Passenger Flow & Boarding Analyst",
        goal=(
            "Research angkot boarding/alighting rates, dwell time patterns, "
            "and door configuration preferences for Indonesian urban transit."
        ),
        backstory=(
            "You are a transit operations analyst with expertise in Southeast Asian "
            "public transport behaviour. You analyse BPS data, field studies, and "
            "TransJakarta/BisKita reports to establish boarding rate benchmarks "
            "for Bogor context." + _AGENT_SYSTEM_SUFFIX
        ),
        llm=get_llm("flow_analyst"),
        tools=[web_search, query_bps_bogor_transport, scrape_page],
        verbose=True,
        max_iter=8,
        max_retry_limit=2,
    )

    capacity_synthesiser = Agent(
        role="Interior Layout & Capacity Synthesiser",
        goal=(
            "Use the InternalBoxCalculator tool to compute passenger box dimensions "
            "for capacity candidates 18, 20, and 22. Output capacity_candidates list."
        ),
        backstory=(
            "You are an interior layout engineer who transforms anthropometry data "
            "into seat layout calculations using the calculator tool. You output "
            "structured JSON — no manual arithmetic." + _AGENT_SYSTEM_SUFFIX
        ),
        llm=get_llm("capacity_synthesiser"),
        tools=[calc_internal_box],
        verbose=True,
        max_iter=8,
        max_retry_limit=2,
    )

    # -----------------------------------------------------------------------
    # Task definitions
    # -----------------------------------------------------------------------
    survey_task = Task(
        description=(
            f"Execute the three-pass vehicle survey search plan below. "
            f"Collect at least {SURVEY_MINIMUM} vehicles total (≥5 per class). "
            f"For each vehicle, fill all schema fields. Mark data_confidence as "
            f"'verified'/'estimated'/'unverified'.\n\n"
            f"SEARCH PLAN:\n{_SURVEY_QUERIES}\n\n"
            "Output a JSON object with key 'vehicles' containing an array of vehicle "
            "records matching this schema per vehicle:\n"
            '{"vehicle_id":"survey_001","vehicle_class":"small_bus","make":"Isuzu",'
            '"model":"Elf NKR 71","year":2022,"powertrain":"diesel","oal_mm":5990,'
            '"oaw_mm":1985,"oah_mm":2430,"capacity_seated":20,"gvw_kg":5500,'
            '"kerb_weight_kg":2900,"source_url":"https://...","data_confidence":"verified","notes":""}'
        ),
        expected_output=(
            "A JSON object with key 'vehicles' containing an array of ≥20 vehicle records, "
            "each with all required fields filled. Grouped logically by vehicle_class."
        ),
        agent=survey_collector,
    )

    validation_task = Task(
        description=(
            "Receive the vehicle survey from the previous task. "
            "Validate: ≥20 total, ≥5 per class (angkot/small_bus/medium_bus), ≥10 verified. "
            "If any class is deficient, note it. "
            "Compute per-class statistics: count, OAL/OAW/OAH min/max/mean/p25/p75, "
            "capacity_seated min/max/mean, gvw_kg min/max/mean. "
            "Output JSON matching:\n"
            '{"validation_passed":true,"survey_summary":{"angkot":{...},"small_bus":{...},'
            '"medium_bus":{...}},"deficient_classes":[],"verified_count":12}'
        ),
        expected_output=(
            "JSON with validation_passed (bool), survey_summary with per-class stats, "
            "deficient_classes list, and verified_count."
        ),
        agent=survey_validator,
        context=[survey_task],
    )

    anthropometry_task = Task(
        description=(
            "Research Indonesian passenger anthropometry from SNI and WHO SEARO sources.\n"
            "Extract:\n"
            "- 95th percentile stature (standing height) in mm\n"
            "- 95th percentile shoulder width in mm\n"
            "- 95th percentile hip breadth (seated) in mm\n"
            "- Minimum headroom clearance in mm (stature + 50mm clearance)\n"
            "- Minimum seat pitch in mm (hip-to-knee + 50mm comfort margin)\n"
            "- Minimum aisle clear width in mm\n"
            "Search: 'Indonesian anthropometry WHO SEARO body dimensions', "
            "'SNI ergonomi kendaraan umum Indonesia', 'Southeast Asian anthropometry 95th percentile'\n"
            "Output JSON:\n"
            '{"p95_stature_mm":1672,"p95_shoulder_width_mm":458,"p95_hip_breadth_seated_mm":382,'
            '"min_headroom_mm":1850,"min_seat_pitch_mm":720,"min_aisle_width_mm":380,'
            '"source":"WHO SEARO 2012 + SNI..."}'
        ),
        expected_output="JSON with all anthropometry fields and source citation.",
        agent=anthropometry_specialist,
    )

    flow_task = Task(
        description=(
            "Research angkot boarding patterns and door preference for Bogor context.\n"
            "Sources: BPS Kota Bogor, TransJakarta studies, BisKita Trans Pakuan reports.\n"
            "Query the BPSTransportTool for Bogor data.\n"
            "Extract:\n"
            "- Typical boarding time per passenger at angkot stops (seconds)\n"
            "- Preferred door width for Indonesian urban transit\n"
            "- Maximum comfortable step height for general public\n"
            "- Floor type preference (low-entry vs high-floor)\n"
            "Output JSON:\n"
            '{"angkot_boarding_time_s_per_passenger":3.2,"preferred_door_width_mm":820,'
            '"max_comfortable_step_height_mm":230,"preferred_floor_type":"low-entry",'
            '"source":"BPS Kota Bogor 2023 + BisKita field study"}'
        ),
        expected_output="JSON with boarding rate, door width, step height, floor type, and source.",
        agent=flow_analyst,
    )

    capacity_task = Task(
        description=(
            "Use the InternalBoxCalculator tool to compute passenger box dimensions "
            "for capacity candidates 18, 20, and 22 passengers.\n"
            "Use seat_pitch_mm=720 and aisle_width_mm=400 (Phase 1 anthropometry defaults).\n"
            "Call the tool THREE times (once per capacity).\n"
            "Aggregate results into:\n"
            '{"capacity_candidates":[18,20,22],'
            '"internal_footprints":{'
            '"18":{"internal_length_mm":5560,"internal_width_mm":1740,"rows":5},'
            '"20":{"internal_length_mm":6000,"internal_width_mm":1740,"rows":5},'
            '"22":{"internal_length_mm":6440,"internal_width_mm":1740,"rows":6}}}'
        ),
        expected_output=(
            "JSON with capacity_candidates list [18, 20, 22] and internal_footprints "
            "dict keyed by capacity string."
        ),
        agent=capacity_synthesiser,
        context=[anthropometry_task],
    )

    # -----------------------------------------------------------------------
    # Crew
    # -----------------------------------------------------------------------
    crew = Crew(
        agents=[
            survey_collector,
            survey_validator,
            anthropometry_specialist,
            flow_analyst,
            capacity_synthesiser,
        ],
        tasks=[
            survey_task,
            validation_task,
            anthropometry_task,
            flow_task,
            capacity_task,
        ],
        process=Process.sequential,
        max_rpm=15,
        verbose=True,
    )

    result = crew.kickoff()

    # Parse outputs from tasks
    phase1_data: dict = {
        "survey_summary": {},
        "anthropometry": {},
        "ingress_egress": {},
        "capacity_candidates": [18, 20, 22],
        "gate_decisions": {},
        "_raw_outputs": {
            "survey": survey_task.output.raw if survey_task.output else "",
            "validation": validation_task.output.raw if validation_task.output else "",
            "anthropometry": anthropometry_task.output.raw if anthropometry_task.output else "",
            "flow": flow_task.output.raw if flow_task.output else "",
            "capacity": capacity_task.output.raw if capacity_task.output else "",
        },
    }

    # Try to parse structured outputs
    for task_name, task_obj in [
        ("validation", validation_task),
        ("anthropometry", anthropometry_task),
        ("flow", flow_task),
        ("capacity", capacity_task),
    ]:
        if task_obj.output and task_obj.output.raw:
            try:
                raw = task_obj.output.raw.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                parsed = json.loads(raw)
                if task_name == "validation":
                    phase1_data["survey_summary"] = parsed.get("survey_summary", {})
                elif task_name == "anthropometry":
                    phase1_data["anthropometry"] = parsed
                elif task_name == "flow":
                    phase1_data["ingress_egress"] = parsed
                elif task_name == "capacity":
                    phase1_data["capacity_candidates"] = parsed.get("capacity_candidates", [18, 20, 22])
            except (json.JSONDecodeError, IndexError, KeyError):
                pass  # Keep defaults — gate will prompt human for correction

    return phase1_data

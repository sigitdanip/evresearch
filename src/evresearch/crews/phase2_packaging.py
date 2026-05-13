"""
crews/phase2_packaging.py — Phase 2: Packaging / External Dimensions Crew
Agents: Structural Offset Researcher, Dimensional Calculator, GVW Estimator
"""
from __future__ import annotations

import json
import time

from crewai import Agent, Crew, Process, Task

from evresearch.config.settings import VEHICLE_CLASSES, get_llm, TASK_SLEEP_S
from evresearch.tools.calculator import calc_external_dims, calc_gvw
from evresearch.tools.pdf_reader import read_pdf
from evresearch.tools.web_search import web_search


def run_phase2(state: dict) -> dict:
    """Build and kick off Phase 2 crew. Returns updated phase2 state dict."""
    time.sleep(TASK_SLEEP_S)

    gate1 = state.get("phase1", {}).get("gate_decisions", {})
    target_capacity = int(gate1.get("target_capacity", gate1.get("q1.1")))
    seat_pitch = int(gate1.get("min_seat_pitch_mm", gate1.get("q1.4")))
    aisle_width = int(gate1.get("min_aisle_width_mm", gate1.get("q1.5")))
    floor_type = gate1.get("floor_type", gate1.get("q1.3"))

    # Survey p25-p75 bounds for small_bus (primary target class)
    survey_summary = state.get("phase1", {}).get("survey_summary", {})
    small_bus_stats = survey_summary.get("small_bus", {})
    oal_p25 = small_bus_stats.get("oal_mm", {}).get("p25", 5500)
    oal_p75 = small_bus_stats.get("oal_mm", {}).get("p75", 6400)
    oaw_p25 = small_bus_stats.get("oaw_mm", {}).get("p25", 1980)
    oaw_p75 = small_bus_stats.get("oaw_mm", {}).get("p75", 2120)

    constraints_ctx = (
        f"Gate 1 decisions: capacity={target_capacity}, seat_pitch={seat_pitch}mm, "
        f"aisle_width={aisle_width}mm, floor_type={floor_type}\n"
        f"Survey p25-p75 bounds (small_bus): OAL {oal_p25}-{oal_p75}mm, OAW {oaw_p25}-{oaw_p75}mm\n"
        f"You must NOT propose OAL/OAW outside these bounds without explicit override."
    )

    # -----------------------------------------------------------------------
    structural_researcher = Agent(
        role="Structural Offset Researcher",
        goal=(
            "Extract SNI-compliant structural offset values: side-wall thickness, "
            "floor stack height, front/rear overhang, roof structure thickness."
        ),
        backstory=(
            "You are a structural engineer specialising in Indonesian bus body standards. "
            "You extract offset data from SNI 09-0683, SNI body construction standards, "
            "and benchmark survey data to establish the structural offset envelope. "
            f"{constraints_ctx}"
        ),
        llm=get_llm("structural_researcher"),
        tools=[web_search, read_pdf],
        verbose=True,
        max_iter=8,
        max_retry_limit=2,
    )

    dimensional_calculator = Agent(
        role="Packaging Dimension Calculator",
        goal=(
            f"Compute external dimensions (OAL, OAW, OAH, wheelbase) for the target "
            f"capacity of {target_capacity} passengers using the ExternalDimsCalculator tool."
        ),
        backstory=(
            "You are a vehicle packaging engineer. You receive internal footprint dimensions "
            "and structural offsets, then call the ExternalDimsCalculator tool to derive "
            "overall external dimensions. You output structured JSON only. "
            f"{constraints_ctx}"
        ),
        llm=get_llm("dimensional_calculator"),
        tools=[calc_external_dims],
        verbose=True,
        max_iter=8,
        max_retry_limit=2,
    )

    gvw_estimator = Agent(
        role="GVW & Weight Estimator",
        goal=(
            "Compute estimated GVW for the dimension candidates. Flag if GVW exceeds "
            "the Kemenhub 5,000kg Mikrobus threshold (requires SIM B1 license)."
        ),
        backstory=(
            "You are a vehicle weight engineer. You call GVWCalculator with kerb weight "
            "estimates and passenger payload to derive GVW. You flag Kemenhub classification "
            "implications. Output structured JSON only. "
            f"{constraints_ctx}"
        ),
        llm=get_llm("gvw_estimator"),
        tools=[calc_gvw],
        verbose=True,
        max_iter=8,
        max_retry_limit=2,
    )

    # -----------------------------------------------------------------------
    offset_task = Task(
        description=(
            "Research SNI 09-0683 and survey benchmark data to establish structural offsets.\n"
            "Required values:\n"
            "- side_wall_each_mm: thickness of each side wall (structural + lining)\n"
            "- floor_stack_mm: total floor assembly depth (frame + insulation + flooring)\n"
            "- front_overhang_mm: distance from front axle centreline to front bumper\n"
            "- rear_overhang_mm: distance from rear axle centreline to rear bumper\n"
            "- roof_structure_mm: roof beam + cladding thickness\n"
            "Search strategy: Use broad terms like 'SNI 09-0683 bus body construction offset' or "
            "'Indonesian mikrobus structural thickness standard'\n"
            "Output JSON:\n"
            '{"side_wall_each_mm":<int>,"floor_stack_mm":<int>,"front_overhang_mm":<int>,'
            '"rear_overhang_mm":<int>,"roof_structure_mm":<int>,"floor_height_from_ground_mm":<int>,'
            '"source":"<string citing data sources>"}'
        ),
        expected_output="JSON with all structural offset values and source.",
        agent=structural_researcher,
    )

    dims_task = Task(
        description=(
            f"Using the internal footprint from Phase 1 for capacity {target_capacity} "
            f"and the structural offsets from the previous task, "
            f"call ExternalDimsCalculator to produce OAL, OAW, OAH, and wheelbase.\n"
            f"Also run for 18 and 22 pax for comparison (use same offsets).\n"
            "Internal footprints (from Phase 1):\n"
            f"  18 pax: internal_length_mm=5560, internal_width_mm=1740\n"
            f"  20 pax: internal_length_mm=6000, internal_width_mm=1740\n"
            f"  22 pax: internal_length_mm=6440, internal_width_mm=1740\n"
            "Output JSON:\n"
            '{"candidates":['
            '{"capacity":18,"oal_mm":<int>,"oaw_mm":<int>,"oah_mm":<int>,"wheelbase_mm":<int>,'
            '"vehicle_class":"<string>"},'
            '{"capacity":20,"oal_mm":<int>,"oaw_mm":<int>,"oah_mm":<int>,"wheelbase_mm":<int>,'
            '"vehicle_class":"<string>"},'
            '{"capacity":22,"oal_mm":<int>,"oaw_mm":<int>,"oah_mm":<int>,"wheelbase_mm":<int>,'
            '"vehicle_class":"<string>"}]}'
        ),
        expected_output=(
            "JSON with 'candidates' array of dimension objects for 18, 20, 22 pax, "
            "each with oal_mm, oaw_mm, oah_mm, wheelbase_mm, vehicle_class."
        ),
        agent=dimensional_calculator,
        context=[offset_task],
    )

    gvw_task = Task(
        description=(
            "For each candidate from the previous task (18, 20, 22 pax), "
            "call GVWCalculator with:\n"
            "  capacity = candidate capacity\n"
            "  kerb_weight_kg: estimate as OAL(m) × OAW(m) × 250 as a rough proxy "
            "(e.g. 6.1m × 2.05m × 250 = 3,126kg for 20pax)\n"
            "  battery_mass_kg = 0 (Phase 5 will refine)\n"
            "Flag any candidate where exceeds_5000kg_threshold = true.\n"
            "Output JSON:\n"
            '{"gvw_estimates":['
            '{"capacity":18,"gvw_kg":<int>,"kemenhub_classification":"<string>",'
            '"exceeds_5000kg":<bool>,"notes":"<string>"},'
            '{"capacity":20,"gvw_kg":<int>,"kemenhub_classification":"<string>",'
            '"exceeds_5000kg":<bool>,"notes":"<string>"},'
            '{"capacity":22,"gvw_kg":<int>,"kemenhub_classification":"<string>",'
            '"exceeds_5000kg":<bool>,"notes":"<string>"}]}'
        ),
        expected_output=(
            "JSON with gvw_estimates array, each with capacity, gvw_kg, "
            "kemenhub_classification, exceeds_5000kg flag, and notes."
        ),
        agent=gvw_estimator,
        context=[dims_task],
    )

    crew = Crew(
        agents=[structural_researcher, dimensional_calculator, gvw_estimator],
        tasks=[offset_task, dims_task, gvw_task],
        process=Process.sequential,
        max_rpm=15,
        verbose=True,
    )

    crew.kickoff()

    # Parse results
    phase2_data: dict = {
        "internal_footprint_by_capacity": {},
        "structural_offsets_mm": {
            "side_wall_each": 120,
            "front_overhang": 800,
            "rear_overhang": 600,
            "floor_stack": 350,
        },
        "candidates": [],
        "gate_decisions": {},
        "_raw_outputs": {
            "offsets": offset_task.output.raw if offset_task.output else "",
            "dims": dims_task.output.raw if dims_task.output else "",
            "gvw": gvw_task.output.raw if gvw_task.output else "",
        },
    }

    for task_name, task_obj in [("offsets", offset_task), ("dims", dims_task), ("gvw", gvw_task)]:
        if task_obj.output and task_obj.output.raw:
            try:
                raw = task_obj.output.raw.strip()
                if "```" in raw:
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                parsed = json.loads(raw)
                if task_name == "offsets":
                    phase2_data["structural_offsets_mm"] = {
                        k: parsed.get(k) for k in [
                            "side_wall_each_mm", "floor_stack_mm",
                            "front_overhang_mm", "rear_overhang_mm"
                        ]
                    }
                elif task_name == "dims":
                    phase2_data["candidates"] = parsed.get("candidates", [])
                elif task_name == "gvw":
                    # Merge GVW into candidates
                    gvw_map = {e["capacity"]: e for e in parsed.get("gvw_estimates", [])}
                    for c in phase2_data["candidates"]:
                        cap = c.get("capacity")
                        if cap in gvw_map:
                            c["gvw_kg"] = gvw_map[cap]["gvw_kg"]
                            c["kemenhub_classification"] = gvw_map[cap]["kemenhub_classification"]
            except (json.JSONDecodeError, IndexError, KeyError) as e:
                raise ValueError(f"CRITICAL FAILURE: Agent failed to produce valid JSON for {task_name}. Error: {e}")

    return phase2_data

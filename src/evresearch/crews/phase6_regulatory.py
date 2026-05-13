"""
crews/phase6_regulatory.py — Phase 6: Regulatory Compliance Crew
Agents: Classification Agent, Crash Safety Agent, Accessibility Auditor,
        EV Homologation Agent, Compliance Synthesiser
"""
from __future__ import annotations

import json
import time

from crewai import Agent, Crew, Process, Task

from evresearch.config.settings import get_llm, TASK_SLEEP_S
from evresearch.tools.pdf_reader import read_pdf
from evresearch.tools.web_search import web_search
from evresearch.tools.state_io import load_state


def run_phase6(state: dict) -> dict:
    """Phase 6 crew — classification, crash safety, accessibility, EV homologation, synthesis."""
    time.sleep(TASK_SLEEP_S)

    gate5 = state.get("phase5", {}).get("gate_decisions", {})
    revised_gvw = float(gate5.get("confirmed_gvw_kg", gate5.get("q6.3_gvw", 6100)))
    selected_battery = state.get("phase5", {}).get("battery", {})
    battery_mass = float(selected_battery.get("mass_kg", 980))

    # Pull confirmed dimension decisions from Gate 2
    gate2 = state.get("phase2", {}).get("gate_decisions", {})
    oal = float(gate2.get("confirmed_oal_mm", 6100))
    oaw = float(gate2.get("confirmed_oaw_mm", 2050))
    aisle_width = float(
        state.get("phase1", {}).get("gate_decisions", {}).get("min_aisle_width_mm", 400)
    )

    ctx = (
        f"Confirmed GVW: {revised_gvw}kg | OAL: {oal}mm | OAW: {oaw}mm | "
        f"Aisle width: {aisle_width}mm | Battery mass: {battery_mass}kg"
    )

    # -----------------------------------------------------------------------
    classification_agent = Agent(
        role="Indonesian Transport Classification Researcher",
        goal=(
            f"Determine Kemenhub vehicle classification for GVW {revised_gvw}kg vehicle. "
            "Identify required driver license class per PP 44/1993."
        ),
        backstory=(
            "You are a transport regulatory researcher specialising in Indonesian "
            "Peraturan Pemerintah (PP) and Kemenhub classifications. "
            "You map GVW to Kemenhub microbus/bus categories and identify "
            "SIM (Surat Izin Mengemudi) license requirements. "
            f"Context: {ctx}"
        ),
        llm=get_llm("classification_agent"),
        tools=[web_search, read_pdf],
        verbose=True,
        max_iter=8,
        max_retry_limit=2,
    )

    crash_safety_agent = Agent(
        role="Crash Safety Standards Researcher",
        goal=(
            "Map SNI crash safety standards (SNI 09-0683, ECE R66, ECE R29) "
            "to the confirmed vehicle. Flag FEA requirements."
        ),
        backstory=(
            "You are a crash safety engineer specialising in Indonesian SNI standards "
            "and UN ECE regulations. You identify which standards apply to a "
            f"GVW {revised_gvw}kg EV bus and flag where FEA simulation is required. "
            f"Context: {ctx}"
        ),
        llm=get_llm("crash_safety_agent"),
        tools=[web_search, read_pdf],
        verbose=True,
        max_iter=10,
        max_retry_limit=2,
    )

    accessibility_auditor = Agent(
        role="Accessibility Compliance Auditor (PM 98/2017)",
        goal=(
            "Audit all Phase 2 and Gate decisions against PM 98/2017 accessibility "
            "requirements: aisle width, door width, step height, grab rails."
        ),
        backstory=(
            "You are an accessibility compliance auditor with expertise in PM 98/2017 "
            "(Peraturan Menteri 98 Tahun 2017). You compare dimensional decisions "
            "from Gates 1–5 against the ministerial minimum requirements, "
            "issuing PASS/FAIL/CONDITIONAL per item. "
            f"Context: {ctx}"
        ),
        llm=get_llm("accessibility_auditor"),
        tools=[web_search],
        verbose=True,
        max_iter=8,
        max_retry_limit=2,
    )

    ev_homologation_agent = Agent(
        role="EV Homologation Specialist (Permenhub 44/2020)",
        goal=(
            "Map Permenhub 44/2020 and UN ECE R100 requirements to the selected "
            "EV configuration. Identify PASS/CONDITIONAL items for battery safety, "
            "HV isolation, and charging interface."
        ),
        backstory=(
            "You are an EV homologation specialist with expertise in Indonesian "
            "Peraturan Menteri Perhubungan 44/2020 and UN ECE R100 EV standards. "
            "You audit the selected battery and motor configuration against "
            "homologation requirements. "
            f"Context: {ctx}"
        ),
        llm=get_llm("ev_homologation_agent"),
        tools=[web_search, read_pdf],
        verbose=True,
        max_iter=10,
        max_retry_limit=2,
    )

    compliance_synthesiser = Agent(
        role="Lead Regulatory Engineer — Compliance Synthesiser",
        goal=(
            "Aggregate all compliance findings. Assign PASS/FAIL/CONDITIONAL/FEA_REQUIRED "
            "to each item. Produce the final compliance matrix and open items list."
        ),
        backstory=(
            "You are a lead regulatory engineer with expertise in Indonesian EV bus "
            "homologation. You aggregate findings from classification, crash safety, "
            "accessibility, and EV homologation agents into a complete compliance matrix. "
            "You use DeepSeek R1 extended reasoning to resolve conflicting findings "
            "and produce a clear compliance status. Output JSON only. "
            f"Context: {ctx}"
        ),
        llm=get_llm("compliance_synthesiser"),
        verbose=True,
        max_iter=15,
        max_retry_limit=2,
        reasoning=True,
    )

    # -----------------------------------------------------------------------
    classification_task = Task(
        description=(
            f"Determine Kemenhub vehicle classification for GVW = {revised_gvw}kg.\n"
            "Research: PP 44/1993 vehicle categories, Kemenhub GVW thresholds.\n"
            "Search strategy: Broad search for 'Kemenhub klasifikasi kendaraan GVW kategori SIM B1' or "
            "'PP 44 1993 kendaraan bermotor golongan SIM'\n"
            "Output JSON:\n"
            '{"gvw_kg":<float>,"kemenhub_vehicle_class":"<string>",'
            '"required_driver_license":"<string>",'
            '"classification_basis":"<string>",'
            '"source":"<string>"}'
        ),
        expected_output="JSON with kemenhub_vehicle_class, required_driver_license, and basis.",
        agent=classification_agent,
    )

    crash_task = Task(
        description=(
            "Map crash safety standards to the EV shuttle configuration.\n"
            "Search strategy: Broad search for 'SNI bus body crashworthiness Indonesia', "
            "'ECE R66 rollover strength bus', or 'ECE R29 frontal impact bus'\n"
            "Identify for each standard: applicable (yes/no), test method, FEA required.\n"
            "Output JSON:\n"
            '{"crash_standards":['
            '{"standard":"<string>","applies":<bool>,"requirement":"<string>",'
            '"status":"<FEA_REQUIRED|PASS>","note":"<string>"}]}'
        ),
        expected_output="JSON with crash_standards array showing applies, requirement, status, and note.",
        agent=crash_safety_agent,
    )

    accessibility_task = Task(
        description=(
            "Audit the following confirmed dimensions against PM 98/2017 minimums:\n"
            f"  - Aisle width: {aisle_width}mm (PM minimum: 380mm)\n"
            "  - Door width: 820mm (PM minimum: 800mm)\n"
            "  - Step height: 200mm low-entry (PM maximum: 250mm)\n"
            "  - Grab rails: position TBD in CAD\n"
            "Output JSON:\n"
            '{"accessibility_items":['
            '{"item":"<string>","standard":"<string>","required_mm":<int>,'
            '"designed_mm":<int>,"status":"<PASS|FAIL|CONDITIONAL>","notes":"<string>"}]}'
        ),
        expected_output="JSON with accessibility_items array, each with status PASS/FAIL/CONDITIONAL.",
        agent=accessibility_auditor,
    )

    ev_homologation_task = Task(
        description=(
            "Map Permenhub 44/2020 and UN ECE R100 requirements to the EV configuration.\n"
            "Search strategy: Broad search for 'Permenhub 44 2020 kendaraan bermotor listrik persyaratan teknis' or "
            "'ECE R100 EV high voltage safety requirements'\n"
            "For each requirement, check if the selected configuration satisfies it.\n"
            "Output JSON:\n"
            '{"ev_items":['
            '{"item":"<string>","standard":"<string>",'
            '"status":"<PASS|FAIL|CONDITIONAL>","notes":"<string>"}]}'
        ),
        expected_output="JSON with ev_items array showing EV homologation compliance status.",
        agent=ev_homologation_agent,
    )

    synthesis_task = Task(
        description=(
            "Aggregate all Phase 6 findings into a complete compliance matrix.\n"
            "Merge: classification, crash_standards, accessibility_items, ev_items.\n"
            "Identify open_items (CONDITIONAL or FEA_REQUIRED items needing action).\n"
            "Assign overall compliance_status: "
            "'PASS' if all PASS, 'CONDITIONAL' if any CONDITIONAL, "
            "'FEA_PENDING' if any FEA_REQUIRED, 'FAIL' if any FAIL.\n"
            "Output JSON:\n"
            '{"vehicle_class":"<string>","required_driver_license":"<string>",'
            '"compliance_matrix":[<list of all items from all agents>],'
            '"compliance_status":"<PASS|CONDITIONAL|FEA_PENDING|FAIL>",'
            '"open_items":[<list of strings describing open items>]}'
        ),
        expected_output=(
            "JSON with vehicle_class, required_driver_license, full compliance_matrix array, "
            "compliance_status, and open_items list."
        ),
        agent=compliance_synthesiser,
        context=[classification_task, crash_task, accessibility_task, ev_homologation_task],
    )

    crew = Crew(
        agents=[
            classification_agent,
            crash_safety_agent,
            accessibility_auditor,
            ev_homologation_agent,
            compliance_synthesiser,
        ],
        tasks=[
            classification_task,
            crash_task,
            accessibility_task,
            ev_homologation_task,
            synthesis_task,
        ],
        process=Process.sequential,
        max_rpm=15,
        verbose=True,
    )

    crew.kickoff()

    phase6_data: dict = {
        "vehicle_class": None,
        "required_driver_license": None,
        "crash_safety": {},
        "accessibility_compliance": {},
        "ev_homologation": {},
        "compliance_status": None,
        "open_items": [],
        "gate_decisions": {},
        "_raw_outputs": {
            "classification": classification_task.output.raw if classification_task.output else "",
            "crash": crash_task.output.raw if crash_task.output else "",
            "accessibility": accessibility_task.output.raw if accessibility_task.output else "",
            "ev_hom": ev_homologation_task.output.raw if ev_homologation_task.output else "",
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
            phase6_data.update({k: parsed[k] for k in parsed if k in phase6_data})
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            raise ValueError(f"CRITICAL FAILURE: Agent failed to produce valid JSON for phase 6 synthesis. Error: {e}")

    return phase6_data

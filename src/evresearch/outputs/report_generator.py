"""
outputs/report_generator.py — Generate structured final_report.md from state.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parents[1] / "state" / "research_state.json"
REPORT_PATH = Path(__file__).resolve().parents[1] / "outputs" / "final_report.md"


def _j(val) -> str:
    if isinstance(val, (dict, list)):
        return f"\n```json\n{json.dumps(val, indent=2, ensure_ascii=False, default=str)}\n```"
    return str(val)


def generate_final_report(state: dict) -> Path:
    """Generate outputs/final_report.md from the full research state."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    run_id = state.get("meta", {}).get("run_id", "unknown")
    started = state.get("meta", {}).get("started_at", "")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    p1 = state.get("phase1", {})
    p2 = state.get("phase2", {})
    p3 = state.get("phase3", {})
    p4 = state.get("phase4", {})
    p5 = state.get("phase5", {})
    p6 = state.get("phase6", {})

    g1 = p1.get("gate_decisions", {})
    g2 = p2.get("gate_decisions", {})
    g3 = p3.get("gate_decisions", {})
    g4 = p4.get("gate_decisions", {})
    g5 = p5.get("gate_decisions", {})
    g6 = p6.get("gate_decisions", {})

    capacity = int(g3.get("q3.2", g1.get("q1.1", "20").split()[0]))
    kwh_per_km = float(g3.get("q3.4", p3.get("energy_consumption_kwh_per_km", 1.41)))
    usable_kwh = float(g4.get("q4.4", p4.get("usable_battery_kwh", 165)))
    vehicle_class = p6.get("vehicle_class", "Mikrobus")
    license_req = p6.get("required_driver_license", "SIM B1")
    compliance_status = p6.get("compliance_status", "FEA_PENDING")
    open_items = p6.get("open_items", [])

    motor = p5.get("motor", {})
    battery = p5.get("battery", {})
    axle = p5.get("axle", {})
    hardpoints = p5.get("chassis_hardpoints", {})

    candidates = p2.get("candidates", [])
    target_candidate = next((c for c in candidates if c.get("capacity") == capacity), {})
    oal = target_candidate.get("oal_mm", g2.get("q2.2", "~6100"))
    oaw = target_candidate.get("oaw_mm", g2.get("q2.3", "~2050"))
    gvw = target_candidate.get("gvw_kg", "~5450")

    compliance_matrix = p6.get("compliance_matrix", [])

    lines = [
        f"# EV Shuttle Research Report — Bogor, Indonesia",
        f"",
        f"**Run ID:** `{run_id}`  ",
        f"**Research Started:** {started}  ",
        f"**Report Generated:** {generated}  ",
        f"**Framework Version:** 1.2  ",
        f"",
        f"---",
        f"",
        f"## Executive Summary",
        f"",
        f"This report presents the results of the 6-phase EV Shuttle Research Framework "
        f"for Bogor, Indonesia. All phases were executed by multi-agent CrewAI crews "
        f"using OpenRouter free-tier models exclusively (DeepSeek R1, Llama 3.3 70B, "
        f"Gemini 2.0 Flash, Mistral 7B). Human decision gates were completed between each phase.",
        f"",
        f"| Parameter | Value |",
        f"|-----------|-------|",
        f"| **Recommended capacity** | {capacity} passengers |",
        f"| **Vehicle class** | {vehicle_class} |",
        f"| **Kemenhub classification** | {vehicle_class} (GVW >{gvw}kg) |",
        f"| **Driver license** | {license_req} |",
        f"| **Overall length** | {oal} mm |",
        f"| **Overall width** | {oaw} mm |",
        f"| **GVW (estimated)** | {gvw} kg |",
        f"| **Energy consumption** | {kwh_per_km} kWh/km |",
        f"| **Usable battery** | {usable_kwh} kWh |",
        f"| **Motor** | {motor.get('supplier','?')} {motor.get('model','?')} ({motor.get('continuous_kw','?')}kW) |",
        f"| **Battery** | {battery.get('supplier','?')} {battery.get('model','?')} |",
        f"| **Compliance status** | **{compliance_status}** |",
        f"",
        f"---",
        f"",
        f"## Phase 1 — Market Survey & Anthropometry",
        f"",
        f"### Vehicle Survey",
        f"",
        _j(state.get("survey", {}).get("by_class", {})),
        f"",
        f"### Anthropometry (Indonesian 95th Percentile)",
        f"",
        _j(p1.get("anthropometry", {})),
        f"",
        f"### Ingress/Egress Data",
        f"",
        _j(p1.get("ingress_egress", {})),
        f"",
        f"### Gate 1 Decisions",
        f"",
        _j(g1),
        f"",
        f"---",
        f"",
        f"## Phase 2 — Packaging (External Dimensions)",
        f"",
        f"### Structural Offsets",
        f"",
        _j(p2.get("structural_offsets_mm", {})),
        f"",
        f"### Dimension Candidates",
        f"",
        _j(p2.get("candidates", [])),
        f"",
        f"### Gate 2 Decisions",
        f"",
        _j(g2),
        f"",
        f"---",
        f"",
        f"## Phase 3 — Environment & Viability",
        f"",
        f"### Bogor Environment Data",
        f"",
        _j(p3.get("environment", {})),
        f"",
        f"### Swept Path Results",
        f"",
        _j(p3.get("surviving_candidates", [])),
        f"",
        f"**Eliminated candidates:**",
        f"",
        _j(p3.get("eliminated_candidates", [])),
        f"",
        f"### Powertrain Requirements",
        f"",
        _j(p3.get("powertrain_requirements", {})),
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| HVAC Load | {p3.get('hvac_load_kw', '?')} kW |",
        f"| Energy Consumption | {p3.get('energy_consumption_kwh_per_km', '?')} kWh/km |",
        f"| Recommended Capacity | {p3.get('recommended_capacity', '?')} passengers |",
        f"",
        f"### Gate 3 Decisions",
        f"",
        _j(g3),
        f"",
        f"---",
        f"",
        f"## Phase 4 — Demand & Operations",
        f"",
        f"### Ridership Data",
        f"",
        _j(p4.get("ridership", {})),
        f"",
        f"| Parameter | Value |",
        f"|-----------|-------|",
        f"| Seating/Standing Ratio | {p4.get('seating_standing_ratio', '?')} |",
        f"| Door Configuration | {p4.get('door_config', '?')} |",
        f"| Usable Battery (calculated) | {p4.get('usable_battery_kwh', '?')} kWh |",
        f"| Charging Strategy | {p4.get('charging_strategy', '?')} |",
        f"| Fleet Size | {p4.get('fleet_size_recommendation', '?')} vehicles |",
        f"",
        f"### Gate 4 Decisions",
        f"",
        _j(g4),
        f"",
        f"---",
        f"",
        f"## Phase 5 — Hardware Bill of Materials",
        f"",
        f"### Selected Motor",
        f"",
        _j(motor),
        f"",
        f"### Selected Battery",
        f"",
        _j(battery),
        f"",
        f"### Selected Axle",
        f"",
        _j(axle),
        f"",
        f"### Chassis Hardpoints",
        f"",
        _j(hardpoints),
        f"",
        f"### Gate 5 Decisions",
        f"",
        _j(g5),
        f"",
        f"---",
        f"",
        f"## Phase 6 — Regulatory Compliance",
        f"",
        f"**Vehicle Classification:** {vehicle_class}  ",
        f"**Required Driver License:** {license_req}  ",
        f"**Overall Compliance Status:** `{compliance_status}`",
        f"",
        f"### Compliance Matrix",
        f"",
        "| Item | Standard | Status | Notes |",
        "|------|----------|--------|-------|",
    ]

    for item in compliance_matrix:
        if isinstance(item, dict):
            lines.append(
                f"| {item.get('item','?')} | {item.get('standard','?')} "
                f"| **{item.get('status','?')}** | {item.get('notes','')} |"
            )

    lines += [
        f"",
        f"### Open Items (Engineering Action Required)",
        f"",
    ]
    for i, item in enumerate(open_items, 1):
        lines.append(f"{i}. {item}")

    lines += [
        f"",
        f"### Gate 6 Decisions",
        f"",
        _j(g6),
        f"",
        f"---",
        f"",
        f"## Override Audit Trail",
        f"",
        f"All human parameter overrides are logged in `state/override_log.jsonl`.",
        f"Key decisions recorded in `gate_decisions` within each phase section above.",
        f"",
        f"---",
        f"",
        f"*Report generated by EV Shuttle Bogor Research Framework v1.2*  ",
        f"*$0 LLM cost — OpenRouter free tier: DeepSeek R1, Llama 3.3 70B, Gemini 2.0 Flash, Mistral 7B*  ",
        f"*All tools: Serper (free), OSM Overpass (free), BMKG Open Data (free), BPS (free)*",
    ]

    report_text = "\n".join(lines)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"\n[REPORT] Generated: {REPORT_PATH}")
    return REPORT_PATH

"""
gates/gate_runner.py — Structured human decision gate system.
Presents research tables, asks numbered questions, records answers.
"""
from __future__ import annotations

import importlib
import json
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from evresearch.tools.constraints_io import (
    get_active_overrides,
    log_override,
    save_constraints,
    load_constraints,
    validate_override,
)
from evresearch.tools.state_io import save_state


@dataclass
class QuestionOption:
    label: str
    evidence: str


@dataclass
class Question:
    id: str
    prompt: str
    suggested: Optional[str] = None
    reason: Optional[str] = None
    range_hint: Optional[str] = None
    options: list[QuestionOption] = field(default_factory=list)
    validator: Optional[Callable[[str], tuple[bool, str]]] = None


# ---------------------------------------------------------------------------
# Pretty printing helpers
# ---------------------------------------------------------------------------

def _hr(char: str = "═", width: int = 72) -> str:
    return char * width


def _box(title: str, width: int = 72) -> str:
    pad = (width - len(title) - 2) // 2
    return f"{'═' * pad} {title} {'═' * (width - pad - len(title) - 2)}"


def _print_phase_banner(phase_num: int, phase_name: str = "") -> None:
    print()
    print(_hr())
    print(_box(f"DECISION GATE — END OF PHASE {phase_num}  {phase_name}"))
    print(_hr())
    print("  Read the research summaries above carefully before answering.")
    print("  Your answers become HARD CONSTRAINTS for the next phase.")
    print(_hr())
    print()


def _print_json_table(data: Any, indent: int = 2) -> None:
    """Pretty-print a dict or list as formatted JSON."""
    print(json.dumps(data, indent=indent, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# Gate runner
# ---------------------------------------------------------------------------

class DecisionGate:
    def __init__(self, phase_num: int, state: dict):
        self.phase_num = phase_num
        self.state = state
        self.decisions: dict = {}

    def run(self) -> dict:
        """Run the gate: print summaries, ask questions, collect overrides."""
        self._print_phase_summary()
        _print_phase_banner(self.phase_num)

        gate_module = self._load_gate_module()
        if gate_module is None:
            print(f"  [Warning] No gate module found for phase {self.phase_num}. Skipping questions.")
        else:
            questions = gate_module.get_questions(self.state)
            for q in questions:
                self._ask_question(q)

        self._offer_freeform_override()
        self._confirm_and_save()
        return self.decisions

    def _load_gate_module(self):
        try:
            mod = importlib.import_module(f"evresearch.gates.gate_phase{self.phase_num}")
            return mod
        except ImportError:
            return None

    def _print_phase_summary(self) -> None:
        print()
        print(_hr("─"))
        print(f"  PHASE {self.phase_num} RESEARCH SUMMARY")
        print(_hr("─"))
        phase_data = self.state.get(f"phase{self.phase_num}", {})
        # Print non-private keys
        for key, val in phase_data.items():
            if key.startswith("_") or key == "gate_decisions":
                continue
            print(f"\n  [{key.upper()}]")
            if isinstance(val, (dict, list)):
                # Indent JSON dump
                lines = json.dumps(val, indent=4, ensure_ascii=False, default=str).splitlines()
                for line in lines[:60]:  # cap at 60 lines
                    print("  " + line)
                if len(lines) > 60:
                    print("  ... (truncated)")
            else:
                print(f"  {val}")
        print()

    def _ask_question(self, q: Question) -> None:
        print(f"\n  [{q.id}] {q.prompt}")
        if q.options:
            for i, opt in enumerate(q.options, 1):
                print(f"    {i}. {opt.label}")
                if opt.evidence:
                    print(f"       ← {opt.evidence}")
        if q.suggested:
            print(f"\n  Research suggests: {q.suggested}")
            if q.reason:
                print(f"  Reason: {q.reason}")
        if q.range_hint:
            print(f"  Range guidance: {q.range_hint}")

        while True:
            try:
                raw = input("  Your decision: ").strip()
            except EOFError:
                raw = str(q.suggested or "")
            if not raw and q.suggested is not None:
                raw = str(q.suggested)
                print(f"  [Using suggested value: {raw}]")
            if q.validator:
                ok, err = q.validator(raw)
                if not ok:
                    print(f"  ✗ Invalid: {err}. Please try again.")
                    continue
            # Map numeric option choice to label
            if q.options and raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(q.options):
                    raw = q.options[idx].label
            self.decisions[q.id] = raw
            break

    def _offer_freeform_override(self) -> None:
        print()
        print("  " + "─" * 68)
        print("  PARAMETER OVERRIDE (optional — press Enter to skip)")
        print("  Enter key=value pairs, one per line. These become hard constraints.")
        print("  Example:  target_capacity=20   max_oal_mm=6200   battery_chemistry=LFP")
        print("  " + "─" * 68)
        constraints = load_constraints()
        active = dict(constraints.get("active_overrides", {}))
        while True:
            try:
                line = input("  override> ").strip()
            except EOFError:
                break
            if not line:
                break
            if "=" not in line:
                print("  ✗ Format: key=value (no spaces around =)")
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            is_valid, err = validate_override(key, val)
            if not is_valid:
                print(f"  ✗ {err}")
                continue
            active[key] = val
            self.decisions[f"override_{key}"] = val
            log_override(self.phase_num, f"gate{self.phase_num}_override", key, val, "gate_input")
            print(f"  ✓ Override recorded: {key}={val}")
        if active:
            constraints["active_overrides"] = active
            save_constraints(constraints)

    def _confirm_and_save(self) -> None:
        print()
        print("  " + "─" * 68)
        print("  GATE DECISIONS SUMMARY:")
        for k, v in self.decisions.items():
            print(f"    {k}: {v}")
        print()
        while True:
            try:
                confirm = input("  Confirm and lock these decisions? [yes/no]: ").strip().lower()
            except EOFError:
                confirm = "yes"
            if confirm in ("yes", "y"):
                self.state[f"phase{self.phase_num}"]["gate_decisions"] = self.decisions
                self.state["meta"]["status"] = "running"
                save_state(self.state)
                print(f"\n  ✓ Gate {self.phase_num} locked. Decisions written to state.")
                break
            elif confirm in ("no", "n"):
                print("  Re-running gate questions...")
                self.decisions = {}
                return self.run()
            else:
                print("  Enter 'yes' or 'no'.")


def run_gate(phase_num: int, state: dict) -> dict:
    """Convenience function to run a decision gate for a phase."""
    gate = DecisionGate(phase_num, state)
    return gate.run()

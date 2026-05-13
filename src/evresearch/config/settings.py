"""
config/settings.py — EV Shuttle Bogor Research
Global constants: vehicle class boundaries, model registry, LLM factory.

RATE-LIMIT STRATEGY (updated May 2026)
---------------------------------------
Problem:  qwen3-next-80b, gemma-4-31b, hermes-3-llama-405b are the highest-traffic
          free models on OpenRouter. Even with credits, upstream providers 503 them
          during peak hours because the shared inference fleet is saturated.

Fix:      Spread 23 agents across 6 newer, low-traffic models so no single upstream
          provider carries the whole pipeline. Each agent also gets a FALLBACK_CHAINS
          entry — an ordered list OpenRouter tries automatically via its native
          `route: fallback` header before your code ever sees an error.

Adaptive retry: get_llm() wraps the raw crewai.LLM in a thin retry shim that
          exponentially backs off on 429/503 up to MAX_RETRY_ATTEMPTS, then raises
          so CrewAI's own error handling can log and move on.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from crewai import LLM
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vehicle class hard boundaries
# ---------------------------------------------------------------------------
VEHICLE_CLASSES: dict = {
    "angkot": {
        "label": "Angkot-class (Minivan/Mikrolet)",
        "oal_mm_range": (3800, 5000),
        "oaw_mm_range": (1500, 1900),
        "oah_mm_range": (1700, 2100),
        "capacity_range": (8, 14),
        "gvw_kg_max": 3500,
        "examples": ["Toyota Kijang", "Daihatsu Gran Max", "Isuzu Elf NKR 55"],
    },
    "small_bus": {
        "label": "Small Bus (Mikrobus)",
        "oal_mm_range": (5000, 7000),
        "oaw_mm_range": (1900, 2200),
        "oah_mm_range": (2200, 2900),
        "capacity_range": (15, 24),
        "gvw_kg_max": 7500,
        "examples": ["Isuzu Elf NKR 71", "Mitsubishi Colt L300", "Toyota Coaster"],
    },
    "medium_bus": {
        "label": "Medium Bus",
        "oal_mm_range": (7000, 9500),
        "oaw_mm_range": (2200, 2550),
        "oah_mm_range": (2700, 3400),
        "capacity_range": (25, 40),
        "gvw_kg_max": 14000,
        "examples": ["Hino Dutro 110 SDL", "Mercedes-Benz OH 1526", "MAN 18.280"],
    },
}

SURVEY_MINIMUM: int = 20       # Hard minimum reference vehicles before Phase 2
MIN_PER_CLASS: int = 5         # Minimum per vehicle class
TARGET_CAPACITY_MIN: int = 20  # Operator hard minimum passenger count

# ---------------------------------------------------------------------------
# Timing & retry knobs
# ---------------------------------------------------------------------------

# Seconds between sequential agent task starts — raised from 3.0 to give
# upstream providers breathing room between bursts of 23 agents.
TASK_SLEEP_S: float = 6.0

# Adaptive backoff for get_llm_with_retry():
#   attempt 1 → 2s, attempt 2 → 4s, attempt 3 → 8s, attempt 4 → 16s, …
MAX_RETRY_ATTEMPTS: int = 5
RETRY_BASE_DELAY_S: float = 2.0
RETRY_BACKOFF_FACTOR: float = 2.0
# HTTP status codes treated as retriable upstream failures
RETRIABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# ---------------------------------------------------------------------------
# Primary model registry — low-congestion free models (May 2026)
#
# Allocation rationale:
#   nemotron-3-super   → heavy reasoning, synthesis, compliance (6 agents)
#   minimax-m2.5       → analysis, structured output, sourcing  (5 agents)
#   ring-2.6-1t        → tool-heavy, long-horizon agentic tasks (5 agents)
#   glm-4.5-air        → reasoning + tool use, fast turnaround  (4 agents)
#   laguna-m.1         → engineering calcs, code, HVAC math     (3 agents)
#   nemotron-3-nano    → lightweight fast calcs (gvw, axle)     (2 agents)
#   gpt-oss-120b       → powertrain sim (math-heavy, tool use)  (1 agent)
#   cobuddy            → dimensional / structured calc           (1 agent)
#   gemma-4-26b-a4b    → drop-in lighter replacement for gemma-31b
# ---------------------------------------------------------------------------
MODEL_IDS: dict[str, str] = {
    # Phase 1 — Human & Market
    "survey_collector":          "nvidia/nemotron-3-super-120b-a12b:free",
    "survey_validator":          "nvidia/nemotron-3-super-120b-a12b:free",
    "anthropometry_specialist":  "minimax/minimax-m2.5:free",
    "flow_analyst":              "z-ai/glm-4.5-air:free",
    "capacity_synthesiser":      "poolside/laguna-m.1:free",
    # Phase 2 — Packaging
    "structural_researcher":     "inclusionai/ring-2.6-1t:free",
    "dimensional_calculator":    "baidu/cobuddy:free",
    "gvw_estimator":             "nvidia/nemotron-3-nano-30b-a3b:free",
    # Phase 3 — Environment
    "topography_analyst":        "z-ai/glm-4.5-air:free",
    "climate_analyst":           "minimax/minimax-m2.5:free",
    "swept_path_filter":         "nvidia/nemotron-3-super-120b-a12b:free",
    "powertrain_sim":            "openai/gpt-oss-120b:free",
    "hvac_range_engineer":       "poolside/laguna-m.1:free",
    "viability_synthesiser":     "inclusionai/ring-2.6-1t:free",
    # Phase 4 — Demand
    "ridership_analyst":         "nvidia/nemotron-3-super-120b-a12b:free",
    "comfort_analyst":           "minimax/minimax-m2.5:free",
    "charging_modeller":         "z-ai/glm-4.5-air:free",
    # Phase 5 — Hardware
    "powertrain_sourcing":       "inclusionai/ring-2.6-1t:free",
    "battery_sourcing":          "minimax/minimax-m2.5:free",
    "axle_sourcing":             "google/gemma-4-26b-a4b-it:free",
    "chassis_synthesiser":       "nvidia/nemotron-3-super-120b-a12b:free",
    # Phase 6 — Compliance
    "classification_agent":      "inclusionai/ring-2.6-1t:free",
    "crash_safety_agent":        "inclusionai/ring-2.6-1t:free",
    "accessibility_auditor":     "z-ai/glm-4.5-air:free",
    "ev_homologation_agent":     "z-ai/glm-4.5-air:free",
    "compliance_synthesiser":    "nvidia/nemotron-3-super-120b-a12b:free",
    # Global fallback
    "fallback":                  "minimax/minimax-m2.5:free",
}

# ---------------------------------------------------------------------------
# Per-agent fallback chains
#
# OpenRouter's native `route: fallback` tries each model in order the moment
# the primary returns a 429/503.  We pass this list in extra_body so the
# failure handling happens server-side with zero extra latency on your end.
#
# Rules applied:
#   1. Never put the primary model as the first fallback.
#   2. Prefer a model from a different provider than the primary.
#   3. Second-to-last slot: gpt-oss-20b — small OpenAI open-weight model on
#      separate infrastructure, still relatively new so not yet saturated.
#   4. FINAL slot: openrouter/free — OpenRouter's own auto-router (launched
#      Feb 2026). It dynamically picks whichever free model is least congested
#      at call time, so it degrades gracefully instead of hard-failing.
#      Non-deterministic by design — acceptable for a last-resort safety net.
#      DO NOT use llama-3.3-70b as safety net: it is one of the highest-traffic
#      free models on OpenRouter and will 503 under the same conditions as your
#      primary models, defeating the purpose entirely.
# ---------------------------------------------------------------------------
_AUTO_ROUTER      = "openrouter/free"               # last resort — auto-picks least congested free model
_GPT_OSS_SMALL    = "openai/gpt-oss-20b:free"       # penultimate — separate OpenAI infra, low traffic
_NEMOTRON_SUPER   = "nvidia/nemotron-3-super-120b-a12b:free"
_MINIMAX          = "minimax/minimax-m2.5:free"
_RING             = "inclusionai/ring-2.6-1t:free"
_GLM              = "z-ai/glm-4.5-air:free"
_LAGUNA           = "poolside/laguna-m.1:free"
_NEMOTRON_NANO    = "nvidia/nemotron-3-nano-30b-a3b:free"
_GPT_OSS          = "openai/gpt-oss-120b:free"
_COBUDDY          = "baidu/cobuddy:free"
_GEMMA_MoE        = "google/gemma-4-26b-a4b-it:free"

FALLBACK_CHAINS: dict[str, list[str]] = {
    # Phase 1
    "survey_collector":          [_RING,          _MINIMAX,       _GPT_OSS_SMALL, _AUTO_ROUTER],
    "survey_validator":          [_RING,          _MINIMAX,       _GPT_OSS_SMALL, _AUTO_ROUTER],
    "anthropometry_specialist":  [_GLM,           _NEMOTRON_SUPER,_GPT_OSS_SMALL, _AUTO_ROUTER],
    "flow_analyst":              [_MINIMAX,       _NEMOTRON_SUPER,_GPT_OSS_SMALL, _AUTO_ROUTER],
    "capacity_synthesiser":      [_COBUDDY,       _NEMOTRON_NANO, _GPT_OSS_SMALL, _AUTO_ROUTER],
    # Phase 2
    "structural_researcher":     [_NEMOTRON_SUPER,_MINIMAX,       _GPT_OSS_SMALL, _AUTO_ROUTER],
    "dimensional_calculator":    [_NEMOTRON_NANO, _LAGUNA,        _GPT_OSS_SMALL, _AUTO_ROUTER],
    "gvw_estimator":             [_COBUDDY,       _LAGUNA,        _GPT_OSS_SMALL, _AUTO_ROUTER],
    # Phase 3
    "topography_analyst":        [_MINIMAX,       _RING,          _GPT_OSS_SMALL, _AUTO_ROUTER],
    "climate_analyst":           [_GLM,           _NEMOTRON_SUPER,_GPT_OSS_SMALL, _AUTO_ROUTER],
    "swept_path_filter":         [_RING,          _GLM,           _GPT_OSS_SMALL, _AUTO_ROUTER],
    "powertrain_sim":            [_LAGUNA,        _NEMOTRON_SUPER,_GPT_OSS_SMALL, _AUTO_ROUTER],
    "hvac_range_engineer":       [_GPT_OSS,       _NEMOTRON_NANO, _GPT_OSS_SMALL, _AUTO_ROUTER],
    "viability_synthesiser":     [_NEMOTRON_SUPER,_MINIMAX,       _GPT_OSS_SMALL, _AUTO_ROUTER],
    # Phase 4
    "ridership_analyst":         [_RING,          _MINIMAX,       _GPT_OSS_SMALL, _AUTO_ROUTER],
    "comfort_analyst":           [_GLM,           _NEMOTRON_SUPER,_GPT_OSS_SMALL, _AUTO_ROUTER],
    "charging_modeller":         [_MINIMAX,       _RING,          _GPT_OSS_SMALL, _AUTO_ROUTER],
    # Phase 5
    "powertrain_sourcing":       [_NEMOTRON_SUPER,_GLM,           _GPT_OSS_SMALL, _AUTO_ROUTER],
    "battery_sourcing":          [_RING,          _GLM,           _GPT_OSS_SMALL, _AUTO_ROUTER],
    "axle_sourcing":             [_NEMOTRON_NANO, _MINIMAX,       _GPT_OSS_SMALL, _AUTO_ROUTER],
    "chassis_synthesiser":       [_RING,          _MINIMAX,       _GPT_OSS_SMALL, _AUTO_ROUTER],
    # Phase 6
    "classification_agent":      [_NEMOTRON_SUPER,_GLM,           _GPT_OSS_SMALL, _AUTO_ROUTER],
    "crash_safety_agent":        [_NEMOTRON_SUPER,_MINIMAX,       _GPT_OSS_SMALL, _AUTO_ROUTER],
    "accessibility_auditor":     [_RING,          _MINIMAX,       _GPT_OSS_SMALL, _AUTO_ROUTER],
    "ev_homologation_agent":     [_RING,          _MINIMAX,       _GPT_OSS_SMALL, _AUTO_ROUTER],
    "compliance_synthesiser":    [_RING,          _GLM,           _GPT_OSS_SMALL, _AUTO_ROUTER],
    # Global fallback chain
    "fallback":                  [_NEMOTRON_SUPER,_GLM,           _GPT_OSS_SMALL, _AUTO_ROUTER],
}

# ---------------------------------------------------------------------------
# LLM cache
# ---------------------------------------------------------------------------
_llm_cache: dict[str, LLM] = {}


def _build_llm(model_id: str, agent_name: str, temperature: float) -> LLM:
    """
    Construct a crewai.LLM instance for one model_id.
    Passes the per-agent fallback chain to OpenRouter via extra_body so that
    provider-side failover happens transparently — no round-trip penalty.
    """
    fallback_models = FALLBACK_CHAINS.get(agent_name, FALLBACK_CHAINS["fallback"])[:3]

    return LLM(
        model=f"openrouter/{model_id}",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature,
        # Raised from 10 → 3: with server-side fallback chains and our own
        # adaptive retry shim, hammering the same model 10 times is wasteful.
        max_retries=3,
        timeout=120,
        extra_headers={
            "HTTP-Referer": "https://github.com/your-org/ev-shuttle-bogor",
            "X-Title": "EV Shuttle Bogor Research",
        },
        extra_body={
            # OpenRouter will try each model in this list in order when the
            # primary returns a 429 or 5xx before your code sees anything.
            "models": fallback_models,
            "route": "fallback",
        },
    )


def get_llm(agent_name: str, temperature: float = 0.1) -> LLM:
    """
    Return a cached crewai.LLM for the given agent.
    Fast path: returns from _llm_cache on subsequent calls — no rebuilding.
    """
    model_id = MODEL_IDS.get(agent_name, MODEL_IDS["fallback"])
    cache_key = f"{agent_name}:{model_id}:{temperature}"
    if cache_key not in _llm_cache:
        _llm_cache[cache_key] = _build_llm(model_id, agent_name, temperature)
    return _llm_cache[cache_key]


def call_with_retry(
    fn: Any,
    *args: Any,
    agent_name: str = "fallback",
    **kwargs: Any,
) -> Any:
    """
    Thin adaptive-backoff retry shim for any callable that wraps an LLM call.

    Use this when you invoke the LLM directly (e.g. in a custom tool or task
    callback) rather than via CrewAI's internal executor.  CrewAI's own retry
    logic is separate and still applies to agent.execute_task() calls.

    Example
    -------
    result = call_with_retry(
        my_llm_call,
        prompt,
        agent_name="powertrain_sim",
    )
    """
    delay = RETRY_BASE_DELAY_S
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            return fn(*args, **kwargs)

        except Exception as exc:  # noqa: BLE001
            exc_str = str(exc).lower()
            status_retriable = any(
                str(code) in exc_str for code in RETRIABLE_STATUS_CODES
            )
            # Also catch generic connection/timeout errors
            connection_retriable = any(
                kw in exc_str
                for kw in ("timeout", "connection", "reset", "eof", "503", "429")
            )

            if not (status_retriable or connection_retriable):
                # Non-retriable error (e.g. auth, bad request) — re-raise immediately
                raise

            last_exc = exc
            if attempt == MAX_RETRY_ATTEMPTS:
                break

            logger.warning(
                "[%s] attempt %d/%d failed (%s). retrying in %.1fs…",
                agent_name,
                attempt,
                MAX_RETRY_ATTEMPTS,
                type(exc).__name__,
                delay,
            )
            time.sleep(delay)
            delay = min(delay * RETRY_BACKOFF_FACTOR, 60.0)  # cap at 60s

    logger.error(
        "[%s] all %d attempts exhausted. last error: %s",
        agent_name,
        MAX_RETRY_ATTEMPTS,
        last_exc,
    )
    raise last_exc  # type: ignore[misc]
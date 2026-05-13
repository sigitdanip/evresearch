"""
validators/schema_validator.py — Pydantic models and validation logic per phase.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from evresearch.config.settings import (
    MIN_PER_CLASS,
    SURVEY_MINIMUM,
    TARGET_CAPACITY_MIN,
    VEHICLE_CLASSES,
)


# ---------------------------------------------------------------------------
# Survey schema
# ---------------------------------------------------------------------------

class VehicleRecord(BaseModel):
    vehicle_id: str
    vehicle_class: Literal["angkot", "small_bus", "medium_bus"]
    make: str
    model: str
    year: Optional[int] = None
    powertrain: Literal["diesel", "EV", "hybrid", "petrol", "unknown"] = "unknown"
    oal_mm: Optional[float] = None
    oaw_mm: Optional[float] = None
    oah_mm: Optional[float] = None
    wheelbase_mm: Optional[float] = None
    track_width_front_mm: Optional[float] = None
    track_width_rear_mm: Optional[float] = None
    capacity_seated: Optional[int] = None
    capacity_standing: Optional[int] = None
    gvw_kg: Optional[float] = None
    kerb_weight_kg: Optional[float] = None
    engine_power_kw: Optional[float] = None
    engine_torque_nm: Optional[float] = None
    ground_clearance_mm: Optional[float] = None
    step_height_mm: Optional[float] = None
    door_width_mm: Optional[float] = None
    floor_type: Literal["high-floor", "low-entry", "low-floor", "unknown"] = "unknown"
    market: str = ""
    source_url: str = ""
    data_confidence: Literal["verified", "estimated", "unverified"] = "unverified"
    notes: str = ""


class SurveyIncompleteError(ValueError):
    pass


def validate_survey_complete(survey: dict) -> bool:
    """Raise SurveyIncompleteError if survey does not meet minimum requirements."""
    total = sum(len(v) for v in survey["by_class"].values())
    if total < SURVEY_MINIMUM:
        raise SurveyIncompleteError(
            f"Only {total} vehicles surveyed. Need {SURVEY_MINIMUM}."
        )
    for cls, vehicles in survey["by_class"].items():
        if len(vehicles) < MIN_PER_CLASS:
            raise SurveyIncompleteError(
                f"Class '{cls}' has only {len(vehicles)} vehicles. Need {MIN_PER_CLASS}."
            )
    verified_count = sum(
        1
        for cls in survey["by_class"].values()
        for v in cls
        if v.get("data_confidence") == "verified"
    )
    if verified_count < 10:
        raise SurveyIncompleteError(
            f"Only {verified_count} verified entries. Need at least 10 verified."
        )
    return True


# ---------------------------------------------------------------------------
# Phase 1 output schema
# ---------------------------------------------------------------------------

class AnthropometryData(BaseModel):
    p95_stature_mm: Optional[float] = None
    p95_shoulder_width_mm: Optional[float] = None
    p95_hip_breadth_seated_mm: Optional[float] = None
    min_headroom_mm: Optional[float] = None
    min_seat_pitch_mm: Optional[float] = None
    min_aisle_width_mm: Optional[float] = None
    source: Optional[str] = None


class IngressEgressData(BaseModel):
    min_door_width_mm: Optional[float] = None
    min_door_height_mm: Optional[float] = None
    max_step_height_mm: Optional[float] = None
    preferred_floor_type: Optional[str] = None
    angkot_boarding_time_s_per_passenger: Optional[float] = None


class Phase1Output(BaseModel):
    survey_summary: dict[str, Any] = Field(default_factory=dict)
    anthropometry: AnthropometryData = Field(default_factory=AnthropometryData)
    ingress_egress: IngressEgressData = Field(default_factory=IngressEgressData)
    capacity_candidates: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_capacity_candidates(self) -> "Phase1Output":
        for cap in self.capacity_candidates:
            if cap < TARGET_CAPACITY_MIN:
                raise ValueError(
                    f"Capacity candidate {cap} is below operator minimum {TARGET_CAPACITY_MIN}."
                )
        return self


# ---------------------------------------------------------------------------
# Phase 2 output schema
# ---------------------------------------------------------------------------

class DimensionCandidate(BaseModel):
    capacity: int
    oal_mm: float
    oaw_mm: float
    oah_mm: float
    wheelbase_mm: float
    gvw_kg: float
    vehicle_class: Literal["angkot", "small_bus", "medium_bus"]
    within_survey_p25_p75: bool = True
    notes: str = ""

    @model_validator(mode="after")
    def check_class_bounds(self) -> "DimensionCandidate":
        cls_data = VEHICLE_CLASSES[self.vehicle_class]
        oal_range = cls_data["oal_mm_range"]
        oaw_range = cls_data["oaw_mm_range"]
        oah_range = cls_data["oah_mm_range"]
        cap_range = cls_data["capacity_range"]
        assert oal_range[0] <= self.oal_mm <= oal_range[1], (
            f"OAL {self.oal_mm}mm outside {self.vehicle_class} bounds {oal_range}"
        )
        assert oaw_range[0] <= self.oaw_mm <= oaw_range[1], (
            f"OAW {self.oaw_mm}mm outside {self.vehicle_class} bounds {oaw_range}"
        )
        assert oah_range[0] <= self.oah_mm <= oah_range[1], (
            f"OAH {self.oah_mm}mm outside {self.vehicle_class} bounds {oah_range}"
        )
        assert cap_range[0] <= self.capacity <= cap_range[1], (
            f"Capacity {self.capacity} outside {self.vehicle_class} bounds {cap_range}"
        )
        return self


class Phase2Output(BaseModel):
    internal_footprint_by_capacity: dict[str, Any] = Field(default_factory=dict)
    structural_offsets_mm: dict[str, Any] = Field(default_factory=dict)
    candidates: list[DimensionCandidate] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 3 output schema
# ---------------------------------------------------------------------------

class Phase3Output(BaseModel):
    environment: dict[str, Any] = Field(default_factory=dict)
    surviving_candidates: list[dict] = Field(default_factory=list)
    eliminated_candidates: list[dict] = Field(default_factory=list)
    powertrain_requirements: dict[str, Any] = Field(default_factory=dict)
    hvac_load_kw: Optional[float] = None
    energy_consumption_kwh_per_km: Optional[float] = None
    recommended_capacity: Optional[int] = None


# ---------------------------------------------------------------------------
# Phase 4 output schema
# ---------------------------------------------------------------------------

class Phase4Output(BaseModel):
    ridership: dict[str, Any] = Field(default_factory=dict)
    seating_standing_ratio: Optional[str] = None
    door_config: Optional[str] = None
    usable_battery_kwh: Optional[float] = None
    charging_strategy: Optional[str] = None
    fleet_size_recommendation: Optional[int] = None


# ---------------------------------------------------------------------------
# Phase 5 output schema
# ---------------------------------------------------------------------------

class Phase5Output(BaseModel):
    motor: dict[str, Any] = Field(default_factory=dict)
    battery: dict[str, Any] = Field(default_factory=dict)
    axle: dict[str, Any] = Field(default_factory=dict)
    chassis_hardpoints: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 6 output schema
# ---------------------------------------------------------------------------

ComplianceStatus = Literal["PASS", "FAIL", "CONDITIONAL", "FEA_REQUIRED", "PENDING"]


class ComplianceItem(BaseModel):
    item: str
    standard: str
    status: ComplianceStatus
    notes: str = ""


class Phase6Output(BaseModel):
    vehicle_class: Optional[str] = None
    required_driver_license: Optional[str] = None
    crash_safety: dict[str, Any] = Field(default_factory=dict)
    accessibility_compliance: dict[str, Any] = Field(default_factory=dict)
    ev_homologation: dict[str, Any] = Field(default_factory=dict)
    compliance_status: Optional[str] = None
    open_items: list[str] = Field(default_factory=list)
    compliance_matrix: list[ComplianceItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase output validator dispatcher
# ---------------------------------------------------------------------------

PHASE_MODELS = {
    1: Phase1Output,
    2: Phase2Output,
    3: Phase3Output,
    4: Phase4Output,
    5: Phase5Output,
    6: Phase6Output,
}


def validate_phase_output(phase_num: int, data: dict) -> Any:
    """Validate phase output dict against its Pydantic model. Returns model instance."""
    model = PHASE_MODELS.get(phase_num)
    if not model:
        raise ValueError(f"No schema defined for phase {phase_num}")
    return model.model_validate(data)

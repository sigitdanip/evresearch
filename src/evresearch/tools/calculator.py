"""
tools/calculator.py — Pure-Python physics/engineering computation engine.
Agents call these functions via CalculatorTool; no LLM arithmetic.
"""
from __future__ import annotations

import math
from typing import Any

from crewai.tools import tool


# ---------------------------------------------------------------------------
# Internal layout
# ---------------------------------------------------------------------------

def compute_internal_box(
    capacity: int,
    seat_pitch_mm: int,
    aisle_width_mm: int,
    seat_width_mm: int = 420,
    seats_per_row: int = 2,
) -> dict[str, Any]:
    """
    Estimate internal passenger box dimensions from layout parameters.
    Returns: {internal_length_mm, internal_width_mm, layout_notes}
    """
    rows = math.ceil(capacity / (seats_per_row * 2))  # 2+2 seating
    internal_length = rows * seat_pitch_mm + 500  # 500mm front bulkhead
    # aisle + 2 seats each side
    internal_width = aisle_width_mm + 2 * (seat_width_mm + 50)  # 50mm armrest
    return {
        "capacity": capacity,
        "rows": rows,
        "seat_pitch_mm": seat_pitch_mm,
        "aisle_width_mm": aisle_width_mm,
        "internal_length_mm": internal_length,
        "internal_width_mm": internal_width,
        "layout_notes": f"{rows} rows × 2+2 seating",
    }


# ---------------------------------------------------------------------------
# External packaging
# ---------------------------------------------------------------------------

def compute_external_dims(
    internal_length_mm: int,
    internal_width_mm: int,
    side_wall_each_mm: int = 120,
    front_overhang_mm: int = 800,
    rear_overhang_mm: int = 600,
    floor_stack_mm: int = 350,
    roof_structure_mm: int = 100,
    floor_height_mm: int = 700,
) -> dict[str, Any]:
    """
    Compute overall external dimensions from internal box + structural offsets.
    Returns: {oal_mm, oaw_mm, oah_mm, wheelbase_estimate_mm}
    """
    oal = internal_length_mm + front_overhang_mm + rear_overhang_mm
    oaw = internal_width_mm + 2 * side_wall_each_mm
    # internal height = internal box height (headroom 1900mm) + floor + roof
    internal_height = 1900  # fixed min headroom
    oah = internal_height + floor_stack_mm + roof_structure_mm + floor_height_mm
    wheelbase = internal_length_mm + front_overhang_mm * 0.5
    return {
        "oal_mm": round(oal),
        "oaw_mm": round(oaw),
        "oah_mm": round(oah),
        "wheelbase_estimate_mm": round(wheelbase),
        "offsets": {
            "side_wall_each_mm": side_wall_each_mm,
            "front_overhang_mm": front_overhang_mm,
            "rear_overhang_mm": rear_overhang_mm,
            "floor_stack_mm": floor_stack_mm,
        },
    }


# ---------------------------------------------------------------------------
# GVW estimation
# ---------------------------------------------------------------------------

def compute_gvw(
    capacity: int,
    kerb_weight_kg: float,
    passenger_mass_kg: float = 68.0,
    luggage_per_pax_kg: float = 5.0,
    battery_mass_kg: float = 0.0,
) -> dict[str, Any]:
    """Estimate GVW from kerb weight + payload."""
    payload = capacity * (passenger_mass_kg + luggage_per_pax_kg)
    gvw = kerb_weight_kg + payload + battery_mass_kg
    kemenhub_threshold = 5000
    classification = "Angkot" if gvw <= 3500 else ("Mikrobus" if gvw <= kemenhub_threshold else "Large Mikrobus / Bus Kecil")
    return {
        "capacity": capacity,
        "kerb_weight_kg": kerb_weight_kg,
        "payload_kg": round(payload, 1),
        "battery_mass_kg": battery_mass_kg,
        "gvw_kg": round(gvw, 1),
        "kemenhub_classification": classification,
        "exceeds_5000kg_threshold": gvw > kemenhub_threshold,
    }


# ---------------------------------------------------------------------------
# Swept path / turning radius
# ---------------------------------------------------------------------------

def compute_swept_path(
    oal_mm: float,
    wheelbase_mm: float,
    front_overhang_mm: float = 800.0,
    rear_overhang_mm: float = 600.0,
    oaw_mm: float = 2100.0,
) -> dict[str, Any]:
    """
    Approximate minimum swept-path turning radius (Ackermann geometry).
    Returns min_turning_radius_m (wall-to-wall).
    """
    wb_m = wheelbase_mm / 1000
    # Typical steer angle for chassis of this size ≈ 35–40°
    # Use conservative 35° → Rmin ≈ WB / sin(35°)
    steer_angle_rad = math.radians(35)
    r_centreline = wb_m / math.sin(steer_angle_rad)
    half_width = oaw_mm / 2000
    front_swing = front_overhang_mm / 1000
    # Wall-to-wall outer radius
    r_outer = math.sqrt((r_centreline + half_width) ** 2 + front_swing ** 2)
    # Inner swept
    r_inner = r_centreline - half_width
    return {
        "oal_mm": oal_mm,
        "wheelbase_mm": wheelbase_mm,
        "min_turning_radius_m": round(r_outer, 2),
        "inner_clearance_m": round(r_inner, 2),
        "method": "Ackermann 35° steer angle approximation",
    }


# ---------------------------------------------------------------------------
# Hill torque / powertrain
# ---------------------------------------------------------------------------

def compute_hill_torque(
    gvw_kg: float,
    gradient_pct: float,
    wheel_radius_m: float = 0.40,
    rolling_resistance_coef: float = 0.012,
    drivetrain_efficiency: float = 0.92,
    speed_kmh: float = 30.0,
) -> dict[str, Any]:
    """
    Compute required continuous motor power and peak torque for hill climbing.
    """
    g = 9.81
    grade_angle = math.atan(gradient_pct / 100)
    # Forces
    f_grade = gvw_kg * g * math.sin(grade_angle)
    f_rolling = gvw_kg * g * math.cos(grade_angle) * rolling_resistance_coef
    f_total = f_grade + f_rolling
    # Wheel torque
    torque_wheel_nm = f_total * wheel_radius_m
    # Motor torque (after drivetrain)
    torque_motor_nm = torque_wheel_nm / drivetrain_efficiency
    # Power at given speed
    speed_ms = speed_kmh / 3.6
    power_kw = (f_total * speed_ms) / (drivetrain_efficiency * 1000)
    return {
        "gvw_kg": gvw_kg,
        "gradient_pct": gradient_pct,
        "grade_force_n": round(f_grade, 1),
        "rolling_force_n": round(f_rolling, 1),
        "total_tractive_force_n": round(f_total, 1),
        "required_torque_nm": round(torque_motor_nm, 1),
        "required_continuous_power_kw": round(power_kw, 1),
    }


# ---------------------------------------------------------------------------
# HVAC load
# ---------------------------------------------------------------------------

def compute_hvac_load(
    cabin_volume_m3: float,
    ambient_temp_c: float = 34.0,
    target_temp_c: float = 24.0,
    rh_pct: float = 88.0,
    occupant_count: int = 20,
) -> dict[str, Any]:
    """
    Estimate cabin cooling load (simplified sensible + latent).
    """
    # Sensible load: volume × temperature differential × air density × specific heat
    rho = 1.18  # kg/m3 at 30°C
    cp = 1005   # J/kg·K
    ach = 8.0   # air changes per hour for transit bus
    q_sensible = cabin_volume_m3 * ach / 3600 * rho * cp * (ambient_temp_c - target_temp_c)
    # Latent load (occupants + humidity infiltration)
    q_latent_per_pax = 75.0  # W per person (moderate activity)
    q_latent = occupant_count * q_latent_per_pax
    # Solar gain
    q_solar = cabin_volume_m3 * 150  # 150W/m3 estimate for tropical glass area
    q_total_kw = (q_sensible + q_latent + q_solar) / 1000
    return {
        "cabin_volume_m3": cabin_volume_m3,
        "ambient_temp_c": ambient_temp_c,
        "target_temp_c": target_temp_c,
        "sensible_load_w": round(q_sensible, 1),
        "latent_load_w": round(q_latent, 1),
        "solar_gain_w": round(q_solar, 1),
        "total_hvac_kw": round(q_total_kw, 2),
    }


# ---------------------------------------------------------------------------
# Range / energy budget
# ---------------------------------------------------------------------------

def compute_range(
    usable_battery_kwh: float,
    base_consumption_kwh_per_km: float,
    hvac_kw: float,
    average_speed_kmh: float = 25.0,
    aux_load_kw: float = 1.0,
) -> dict[str, Any]:
    """
    Compute realistic range with HVAC and auxiliary loads.
    """
    hvac_kwh_per_km = hvac_kw / average_speed_kmh
    aux_kwh_per_km = aux_load_kw / average_speed_kmh
    total_kwh_per_km = base_consumption_kwh_per_km + hvac_kwh_per_km + aux_kwh_per_km
    range_km = usable_battery_kwh / total_kwh_per_km
    return {
        "usable_battery_kwh": usable_battery_kwh,
        "base_consumption_kwh_per_km": base_consumption_kwh_per_km,
        "hvac_kwh_per_km": round(hvac_kwh_per_km, 4),
        "aux_kwh_per_km": round(aux_kwh_per_km, 4),
        "total_kwh_per_km": round(total_kwh_per_km, 4),
        "estimated_range_km": round(range_km, 1),
    }


# ---------------------------------------------------------------------------
# CrewAI @tool wrappers
# ---------------------------------------------------------------------------

@tool("InternalBoxCalculator")
def calc_internal_box(
    capacity: int,
    seat_pitch_mm: int,
    aisle_width_mm: int,
) -> str:
    """
    Calculate internal passenger box dimensions.
    Args: capacity (int), seat_pitch_mm (int), aisle_width_mm (int).
    Returns JSON string with internal_length_mm, internal_width_mm, rows.
    """
    import json
    result = compute_internal_box(capacity, seat_pitch_mm, aisle_width_mm)
    return json.dumps(result)


@tool("ExternalDimsCalculator")
def calc_external_dims(
    internal_length_mm: int,
    internal_width_mm: int,
    side_wall_each_mm: int = 120,
    front_overhang_mm: int = 800,
    rear_overhang_mm: int = 600,
) -> str:
    """
    Calculate overall external vehicle dimensions.
    Returns JSON string with oal_mm, oaw_mm, oah_mm, wheelbase_estimate_mm.
    """
    import json
    result = compute_external_dims(
        internal_length_mm, internal_width_mm,
        side_wall_each_mm, front_overhang_mm, rear_overhang_mm
    )
    return json.dumps(result)


@tool("GVWCalculator")
def calc_gvw(
    capacity: int,
    kerb_weight_kg: float,
    battery_mass_kg: float = 0.0,
) -> str:
    """
    Calculate Gross Vehicle Weight and Kemenhub classification.
    Returns JSON string with gvw_kg, kemenhub_classification, exceeds_5000kg_threshold.
    """
    import json
    result = compute_gvw(capacity, kerb_weight_kg, battery_mass_kg=battery_mass_kg)
    return json.dumps(result)


@tool("SweptPathCalculator")
def calc_swept_path(
    oal_mm: float,
    wheelbase_mm: float,
    front_overhang_mm: float = 800.0,
    oaw_mm: float = 2100.0,
) -> str:
    """
    Calculate minimum turning swept-path radius.
    Returns JSON string with min_turning_radius_m, inner_clearance_m.
    """
    import json
    result = compute_swept_path(oal_mm, wheelbase_mm, front_overhang_mm, oaw_mm=oaw_mm)
    return json.dumps(result)


@tool("HillTorqueCalculator")
def calc_hill_torque(
    gvw_kg: float,
    gradient_pct: float,
    speed_kmh: float = 30.0,
) -> str:
    """
    Calculate required motor torque and power for hill climbing.
    Returns JSON string with required_torque_nm, required_continuous_power_kw.
    """
    import json
    result = compute_hill_torque(gvw_kg, gradient_pct, speed_kmh=speed_kmh)
    return json.dumps(result)


@tool("HVACCalculator")
def calc_hvac_load(
    cabin_volume_m3: float,
    ambient_temp_c: float = 34.0,
    occupant_count: int = 20,
) -> str:
    """
    Calculate cabin HVAC cooling load in kW.
    Returns JSON string with total_hvac_kw.
    """
    import json
    result = compute_hvac_load(cabin_volume_m3, ambient_temp_c, occupant_count=occupant_count)
    return json.dumps(result)


@tool("RangeCalculator")
def calc_range(
    usable_battery_kwh: float,
    base_consumption_kwh_per_km: float,
    hvac_kw: float,
    average_speed_kmh: float = 25.0,
) -> str:
    """
    Calculate realistic EV range with HVAC and aux loads.
    Returns JSON string with estimated_range_km, total_kwh_per_km.
    """
    import json
    result = compute_range(
        usable_battery_kwh, base_consumption_kwh_per_km, hvac_kw, average_speed_kmh
    )
    return json.dumps(result)

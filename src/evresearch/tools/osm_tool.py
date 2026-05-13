"""
tools/osm_tool.py — OpenStreetMap / Overpass API queries for Bogor route geometry
"""
from __future__ import annotations

import json
import time

import requests
from crewai.tools import tool

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _overpass_query(query: str) -> dict:
    for attempt in range(3):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json()
            time.sleep(2 ** attempt)
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return {"error": "Overpass API unavailable after 3 attempts"}


@tool("OSMTool")
def query_osm(overpass_ql: str) -> str:
    """
    Execute an Overpass QL query against OpenStreetMap.
    Args: overpass_ql (str) — valid Overpass QL query string.
    Returns: JSON string with raw Overpass API response elements.
    Use for querying Bogor road widths, gradients, and turning geometry.
    Example query for roads in Bogor:
      [out:json]; area["name"="Bogor"]["admin_level"="5"]->.bogor;
      way(area.bogor)["highway"~"^(primary|secondary|tertiary)$"]; out geom;
    """
    result = _overpass_query(overpass_ql)
    # Truncate large responses
    elements = result.get("elements", [])[:50]
    return json.dumps({"elements_count": len(elements), "elements": elements}, ensure_ascii=False)


@tool("BogorGradientQuery")
def query_bogor_gradients() -> str:
    """
    Query OSM for major roads in Bogor to assess gradient and width data.
    Returns JSON with road metadata relevant to EV shuttle route planning.
    No arguments needed — uses pre-built Bogor query.
    """
    query = """
    [out:json][timeout:30];
    area["name"="Kota Bogor"]["admin_level"="4"]->.bogor;
    way(area.bogor)["highway"~"^(primary|secondary|tertiary|residential)$"]
    ["name"~"Sindangbarang|Pasar Anyar|Juanda|Suryakancana|Merdeka|Pajajaran|Sudirman"];
    out body geom;
    """
    result = _overpass_query(query)
    elements = result.get("elements", [])
    roads = []
    for el in elements[:30]:
        tags = el.get("tags", {})
        roads.append({
            "name": tags.get("name", "unknown"),
            "highway": tags.get("highway", ""),
            "lanes": tags.get("lanes", "unknown"),
            "maxspeed": tags.get("maxspeed", "unknown"),
            "oneway": tags.get("oneway", "no"),
        })
    return json.dumps({
        "source": "OpenStreetMap Overpass API",
        "query_area": "Kota Bogor",
        "road_count": len(roads),
        "roads": roads,
        "note": "Width/gradient data from OSM tags where available; supplement with field survey.",
    }, ensure_ascii=False)

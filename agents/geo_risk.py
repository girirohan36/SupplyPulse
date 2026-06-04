"""
Geo Risk Agent
==============

Monitors weather forecasts and seismic activity for a supplier's location.
Uses Open-Meteo (weather) and USGS (earthquakes) — both free, no API key needed.

Run:
    python -m supplypulse.agents.geo_risk SUP-0001
"""

from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from dotenv import load_dotenv

from supplypulse.tools.live_data import get_weather_forecast, get_recent_earthquakes
from supplypulse.tools.supplier_db import get_supplier_by_id

load_dotenv()


class GeoRiskFinding(BaseModel):
    """Geo-environmental risk assessment."""
    supplier_id: str
    supplier_name: str
    risk_level: Literal["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    weather_concern: str = Field(description="Summary of weather risks (typhoons, storms, extreme temps)")
    seismic_concern: str = Field(description="Summary of earthquake activity in the region")
    summary: str = Field(description="Overall geo-risk summary in 2-3 sentences")
    confidence: float = Field(ge=0, le=1)


GEO_AGENT_SYSTEM = """You are a Geo-Environmental Risk Analyst for supply chains.

Your job: assess weather and seismic risks for a supplier's location.

Tools:
  • get_supplier_by_id      — get supplier coordinates
  • get_weather_forecast    — 16-day weather forecast (Open-Meteo)
  • get_recent_earthquakes  — earthquakes within radius (USGS)

Process:
  1. Look up supplier to get lat/lon
  2. Query weather forecast (look for: high winds, heavy precipitation, extreme temps)
  3. Query recent earthquakes (look for: M5.0+ within 500km in last 30 days)
  4. Synthesize into a GeoRiskFinding

Risk leveling:
  • CRITICAL — typhoon/hurricane landfall in next 3 days, OR M6.5+ earthquake within 100km
  • HIGH     — severe weather forecast in next 7 days, OR M5.5+ earthquake within 250km
  • MEDIUM   — concerning weather patterns, OR multiple M4.5+ earthquakes
  • LOW      — minor concerns
  • NONE     — clear skies, stable seismic
"""


def run_geo_risk_agent(supplier_id: str, model: str = "gpt-4o-mini") -> GeoRiskFinding:
    llm = ChatOpenAI(model=model, temperature=0)
    tools = [get_supplier_by_id, get_weather_forecast, get_recent_earthquakes]
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    messages = [
        SystemMessage(content=GEO_AGENT_SYSTEM),
        HumanMessage(content=f"Assess geo risks for supplier {supplier_id}."),
    ]

    for _ in range(6):
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        if not response.tool_calls:
            break
        for tc in response.tool_calls:
            try:
                result = tools_by_name[tc["name"]].invoke(tc["args"])
            except Exception as e:
                result = f"Tool error: {e}"
            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    structured = ChatOpenAI(model=model, temperature=0).with_structured_output(GeoRiskFinding)
    return structured.invoke([
        SystemMessage(content="Extract a GeoRiskFinding from the analyst notes."),
        HumanMessage(content=str(messages[-1].content)),
    ])


if __name__ == "__main__":
    import sys
    sid = sys.argv[1] if len(sys.argv) > 1 else "SUP-0001"
    print(f"🌍 Running Geo Risk Agent for {sid}...\n")
    finding = run_geo_risk_agent(sid)
    print(f"Supplier: {finding.supplier_name}")
    print(f"Risk Level: {finding.risk_level} (confidence: {finding.confidence})")
    print(f"\n🌦️  Weather: {finding.weather_concern}")
    print(f"\n🌋 Seismic: {finding.seismic_concern}")
    print(f"\n📝 Summary: {finding.summary}")

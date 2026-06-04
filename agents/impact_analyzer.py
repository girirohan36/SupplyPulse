"""
Impact Analyzer Agent
=====================

Aggregates risk findings (news + geo + finance) and maps them to business impact:
which products, what revenue exposure, which customers.

Run:
    python -m supplypulse.agents.impact_analyzer SUP-0001
"""

from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from dotenv import load_dotenv

from supplypulse.tools.supplier_db import (
    get_supplier_by_id,
    get_products_affected_by_supplier,
)

load_dotenv()


class ImpactAssessment(BaseModel):
    supplier_id: str
    supplier_name: str
    overall_business_impact: Literal["NEGLIGIBLE", "LOW", "MEDIUM", "HIGH", "SEVERE"]
    affected_products: list[str] = Field(default_factory=list)
    estimated_revenue_at_risk_usd_m: float = Field(ge=0)
    estimated_units_at_risk: int = Field(ge=0)
    days_to_impact: int = Field(description="Days until customer-facing impact")
    summary: str
    confidence: float = Field(ge=0, le=1)


IMPACT_AGENT_SYSTEM = """You are a Business Impact Analyst for supply chain disruptions.

Given upstream risk findings (news, geo, finance), assess the BUSINESS impact:
which products are affected, revenue exposure, time to customer impact.

Tools:
  • get_supplier_by_id              — supplier details, criticality, single-source
  • get_products_affected_by_supplier — products + allocation % + spend

Consider:
  • Single-source suppliers → faster impact, higher severity
  • Critical-tier suppliers → broader product impact
  • High allocation % → larger revenue exposure
  • Lead times → days to impact (longer lead time = more buffer)

Output a quantitative ImpactAssessment.
"""


def run_impact_agent(
    supplier_id: str,
    upstream_findings: dict | None = None,
    model: str = "gpt-4o-mini",
) -> ImpactAssessment:
    """
    Args:
        supplier_id: Supplier to analyze
        upstream_findings: dict with news/geo/finance findings (from orchestrator)
    """
    llm = ChatOpenAI(model=model, temperature=0)
    tools = [get_supplier_by_id, get_products_affected_by_supplier]
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    upstream_context = ""
    if upstream_findings:
        upstream_context = f"\n\nUpstream risk findings:\n{upstream_findings}"

    messages = [
        SystemMessage(content=IMPACT_AGENT_SYSTEM),
        HumanMessage(content=f"Analyze business impact for supplier {supplier_id}.{upstream_context}"),
    ]

    for _ in range(5):
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

    structured = ChatOpenAI(model=model, temperature=0).with_structured_output(ImpactAssessment)
    return structured.invoke([
        SystemMessage(content="Extract an ImpactAssessment from the analyst notes."),
        HumanMessage(content=str(messages[-1].content)),
    ])


if __name__ == "__main__":
    import sys
    sid = sys.argv[1] if len(sys.argv) > 1 else "SUP-0001"
    print(f"🎯 Running Impact Analyzer for {sid}...\n")
    impact = run_impact_agent(sid)
    print(f"Supplier: {impact.supplier_name}")
    print(f"Business Impact: {impact.overall_business_impact}")
    print(f"💵 Revenue at risk: ${impact.estimated_revenue_at_risk_usd_m}M")
    print(f"📦 Units at risk: {impact.estimated_units_at_risk:,}")
    print(f"⏱️  Days to impact: {impact.days_to_impact}")
    print(f"📦 Products affected:")
    for p in impact.affected_products:
        print(f"  • {p}")
    print(f"\n📝 {impact.summary}")

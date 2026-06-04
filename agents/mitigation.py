"""
Mitigation Agent
================

Generates an actionable mitigation plan using:
  • RAG over historical events (learns from past resolutions)
  • Alternative supplier search
  • Multi-step reasoning

Run:
    python -m supplypulse.agents.mitigation SUP-0001
"""

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from dotenv import load_dotenv

from supplypulse.tools.supplier_db import (
    get_supplier_by_id,
    find_alternative_suppliers,
)
from supplypulse.memory.vector_store import search_similar_events

load_dotenv()


class MitigationAction(BaseModel):
    """A single mitigation action."""
    action: str = Field(description="Specific action to take")
    timing: str = Field(description="When (e.g., 'within 24 hours', 'next week')")
    owner: str = Field(description="Suggested team or role")
    estimated_cost_usd: float = Field(ge=0, default=0)
    confidence: float = Field(ge=0, le=1, default=0.7)


class MitigationPlan(BaseModel):
    supplier_id: str
    supplier_name: str
    actions: list[MitigationAction]
    alternative_suppliers: list[str] = Field(default_factory=list)
    similar_past_events: list[str] = Field(default_factory=list, description="Event IDs cited from history")
    estimated_total_cost_usd: float = Field(ge=0)
    estimated_resolution_days: int = Field(ge=0)
    requires_human_approval: bool = Field(description="True for HIGH/SEVERE business impact")
    summary: str


MITIGATION_AGENT_SYSTEM = """You are a Supply Chain Mitigation Strategist.

Given an at-risk supplier and upstream risk + impact findings, draft a
concrete, actionable mitigation plan.

Tools:
  • get_supplier_by_id            — supplier details
  • find_alternative_suppliers    — alternates by category
  • search_similar_events         — RAG over historical disruption events

Process:
  1. Look up supplier categories
  2. Search for SIMILAR PAST EVENTS — what worked before?
  3. Find alternative suppliers for at-risk categories
  4. Compose 3-5 specific actions with timing, owners, costs
  5. Flag for human approval if business impact is HIGH or SEVERE

Cite past events by event_id when applicable. Be specific and pragmatic.
"""


def run_mitigation_agent(
    supplier_id: str,
    upstream_findings: dict | None = None,
    model: str = "gpt-4o-mini",
) -> MitigationPlan:
    llm = ChatOpenAI(model=model, temperature=0)
    tools = [get_supplier_by_id, find_alternative_suppliers, search_similar_events]
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    upstream_context = ""
    if upstream_findings:
        upstream_context = f"\n\nUpstream findings:\n{upstream_findings}"

    messages = [
        SystemMessage(content=MITIGATION_AGENT_SYSTEM),
        HumanMessage(content=f"Draft a mitigation plan for supplier {supplier_id}.{upstream_context}"),
    ]

    for _ in range(8):  # mitigation may need more steps (RAG + alternates + reasoning)
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

    structured = ChatOpenAI(model=model, temperature=0).with_structured_output(MitigationPlan)
    return structured.invoke([
        SystemMessage(content="Extract a MitigationPlan from the strategist's analysis."),
        HumanMessage(content=str(messages[-1].content)),
    ])


if __name__ == "__main__":
    import sys
    sid = sys.argv[1] if len(sys.argv) > 1 else "SUP-0001"
    print(f"🛠️  Running Mitigation Agent for {sid}...\n")
    plan = run_mitigation_agent(sid)
    print(f"Supplier: {plan.supplier_name}")
    print(f"💰 Estimated cost: ${plan.estimated_total_cost_usd:,.0f}")
    print(f"⏱️  Resolution: ~{plan.estimated_resolution_days} days")
    print(f"👤 Human approval needed: {plan.requires_human_approval}")
    print(f"\n📋 Actions:")
    for i, a in enumerate(plan.actions, 1):
        print(f"  {i}. [{a.timing}] {a.action}")
        print(f"     Owner: {a.owner} | Cost: ${a.estimated_cost_usd:,.0f}")
    print(f"\n🔄 Alternatives: {', '.join(plan.alternative_suppliers[:3])}")
    print(f"\n📚 Similar past events: {', '.join(plan.similar_past_events)}")
    print(f"\n📝 {plan.summary}")

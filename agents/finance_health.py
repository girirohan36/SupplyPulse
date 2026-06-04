"""
Financial Health Agent
======================

Assesses supplier financial stability using stock signals (yfinance).

Note: Suppliers in the synthetic dataset have FAKE tickers (~30% of them).
For demo purposes, we'll fall back to a heuristic based on financial_health_score
when ticker isn't real / available.

Run:
    python -m supplypulse.agents.finance_health SUP-0001
"""

from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from dotenv import load_dotenv

from supplypulse.tools.live_data import get_financial_signals
from supplypulse.tools.supplier_db import get_supplier_by_id

load_dotenv()


class FinanceFinding(BaseModel):
    supplier_id: str
    supplier_name: str
    risk_level: Literal["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    health_score: float = Field(ge=0, le=100, description="Overall financial health 0-100")
    key_signals: list[str] = Field(default_factory=list)
    summary: str
    confidence: float = Field(ge=0, le=1)


FINANCE_AGENT_SYSTEM = """You are a Financial Risk Analyst for supply chain.

Your job: assess a supplier's financial health.

Tools:
  • get_supplier_by_id     — get supplier financial_health_score and stock_ticker
  • get_financial_signals  — yfinance-based stock signals (if ticker available)

Process:
  1. Look up supplier
  2. If supplier has a stock_ticker, query financial signals
     (Note: synthetic tickers may fail — that's expected; fall back to internal score)
  3. Combine the internal financial_health_score (0-100) with any market signals
  4. Synthesize into FinanceFinding

Risk leveling:
  • CRITICAL — health_score < 35 OR market signal HIGH (volatility >5%, drop >20%)
  • HIGH     — health_score < 50 OR market signal MEDIUM
  • MEDIUM   — health_score < 65
  • LOW      — health_score 65-80
  • NONE     — health_score > 80, stable
"""


def run_finance_agent(supplier_id: str, model: str = "gpt-4o-mini") -> FinanceFinding:
    llm = ChatOpenAI(model=model, temperature=0)
    tools = [get_supplier_by_id, get_financial_signals]
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    messages = [
        SystemMessage(content=FINANCE_AGENT_SYSTEM),
        HumanMessage(content=f"Assess financial health for supplier {supplier_id}."),
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

    structured = ChatOpenAI(model=model, temperature=0).with_structured_output(FinanceFinding)
    return structured.invoke([
        SystemMessage(content="Extract a FinanceFinding from the analyst notes."),
        HumanMessage(content=str(messages[-1].content)),
    ])


if __name__ == "__main__":
    import sys
    sid = sys.argv[1] if len(sys.argv) > 1 else "SUP-0001"
    print(f"💰 Running Finance Health Agent for {sid}...\n")
    finding = run_finance_agent(sid)
    print(f"Supplier: {finding.supplier_name}")
    print(f"Risk Level: {finding.risk_level} (health: {finding.health_score}/100)")
    print(f"\n📊 Key Signals:")
    for s in finding.key_signals:
        print(f"  • {s}")
    print(f"\n📝 Summary: {finding.summary}")

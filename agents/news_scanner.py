"""
News Scanner Agent
==================

Your first LangChain agent. Demonstrates:
  • ChatPromptTemplate
  • Tool binding
  • Tool calling loop (ReAct pattern)
  • Structured Pydantic output

Run standalone:
    python -m supplypulse.agents.news_scanner
"""

from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from supplypulse.tools.live_data import search_news, search_gdelt_events
from supplypulse.tools.supplier_db import get_supplier_by_id


# ----------------------------------------------------------------
# Structured output schema — agents return THIS not raw text
# ----------------------------------------------------------------
class NewsRiskFinding(BaseModel):
    """Risk finding from news/event scanning for a supplier."""
    supplier_id: str
    supplier_name: str
    risk_level: Literal["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    summary: str = Field(description="2-3 sentence summary of what was found")
    key_events: list[str] = Field(default_factory=list, description="Bullet list of relevant news headlines")
    sources: list[str] = Field(default_factory=list, description="Source URLs for citations")
    confidence: float = Field(ge=0, le=1, description="Confidence score 0-1")


# ----------------------------------------------------------------
# Agent prompt — this is where you control behavior
# ----------------------------------------------------------------
NEWS_AGENT_SYSTEM = """You are a Supply Chain News Risk Analyst.

Your job: scan news and global events for risks affecting a specific supplier.

You have access to:
  • search_news         — keyword search via NewsAPI
  • search_gdelt_events — global events via GDELT (no key needed)
  • get_supplier_by_id  — look up supplier details

Process:
  1. Look up the supplier (location, country, categories)
  2. Run 2-3 targeted searches combining supplier name + location + category
  3. Synthesize findings into a NewsRiskFinding
  4. Cite sources

Risk leveling:
  • CRITICAL — active disruption (factory fire, war zone, bankruptcy filed)
  • HIGH     — imminent disruption (port strike confirmed, typhoon landfall in days)
  • MEDIUM   — elevated risk (geopolitical tensions, financial concerns)
  • LOW      — minor signals (mentioned in industry news, normal volatility)
  • NONE     — no concerning signals found

Be thorough but concise. Always cite URLs.
"""


def build_news_agent(model: str = "gpt-4o-mini"):
    """Returns a tool-using LLM ready for ReAct-style invocation."""
    llm = ChatOpenAI(model=model, temperature=0)
    tools = [search_news, search_gdelt_events, get_supplier_by_id]
    return llm.bind_tools(tools), {t.name: t for t in tools}


def run_news_agent(supplier_id: str, model: str = "gpt-4o-mini") -> NewsRiskFinding:
    """
    Run the News Scanner Agent on a single supplier.
    Demonstrates the ReAct loop: model → tool → model → tool → final answer.
    """
    llm_with_tools, tools_by_name = build_news_agent(model)

    messages = [
        SystemMessage(content=NEWS_AGENT_SYSTEM),
        HumanMessage(content=f"Scan news risks for supplier {supplier_id}. "
                             f"Return your findings as JSON matching NewsRiskFinding schema."),
    ]

    # ReAct loop — keep calling model until it stops requesting tools
    max_iterations = 6
    for i in range(max_iterations):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            # Done — model produced final answer
            break

        # Execute each tool call
        for tc in response.tool_calls:
            tool_fn = tools_by_name[tc["name"]]
            try:
                result = tool_fn.invoke(tc["args"])
            except Exception as e:
                result = f"Tool error: {e}"
            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    # Parse the final response into structured output
    structured_llm = ChatOpenAI(model=model, temperature=0).with_structured_output(NewsRiskFinding)
    final = structured_llm.invoke([
        SystemMessage(content="Extract a NewsRiskFinding from the analyst's notes below."),
        HumanMessage(content=str(messages[-1].content)),
    ])
    return final


if __name__ == "__main__":
    import sys
    supplier_id = sys.argv[1] if len(sys.argv) > 1 else "SUP-0001"
    print(f"🔍 Running News Scanner Agent for {supplier_id}...\n")
    finding = run_news_agent(supplier_id)
    print("=" * 60)
    print(f"Supplier: {finding.supplier_name} ({finding.supplier_id})")
    print(f"Risk Level: {finding.risk_level}")
    print(f"Confidence: {finding.confidence}")
    print(f"\nSummary:\n  {finding.summary}")
    print(f"\nKey Events:")
    for e in finding.key_events:
        print(f"  • {e}")
    print(f"\nSources:")
    for s in finding.sources:
        print(f"  • {s}")

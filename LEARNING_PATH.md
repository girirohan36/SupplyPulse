# 📚 SupplyPulse Learning Path — Master LangChain & LangGraph

This project doubles as a structured curriculum for agentic AI. Each phase builds on the previous and maps to a concrete deliverable in the codebase.

---

## Phase 1 — Foundations 🏗️

### What You'll Build
- Synthetic supplier database (50 suppliers across 12 countries)
- Project skeleton, env setup
- Your first LangChain "Hello World"

### Concepts You'll Learn
| Concept | Where in SupplyPulse |
|---|---|
| **LLMs vs ChatModels** | `supplypulse/agents/base.py` |
| **Prompt Templates** | All agents use `ChatPromptTemplate` |
| **LCEL (LangChain Expression Language)** | Chain composition with `\|` |
| **Output Parsers** | Pydantic structured outputs |
| **Environment management** | `.env` + `python-dotenv` |

### Hands-on Task
```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_template(
    "Summarize the risk profile of supplier: {supplier_data}"
)
chain = prompt | llm
print(chain.invoke({"supplier_data": "..."}))
```

📖 **Read**: [LangChain Quickstart](https://python.langchain.com/docs/tutorials/llm_chain/)

---

## Phase 2 — Tool-Using Agents 🔧

### What You'll Build
- News Scanner Agent (uses NewsAPI + GDELT)
- Tool definitions for live data
- ReAct-style reasoning loop

### Concepts You'll Learn
| Concept | Where in SupplyPulse |
|---|---|
| **Tools (`@tool` decorator)** | `supplypulse/tools/live_data.py` |
| **Tool calling** | News Agent uses `bind_tools()` |
| **ReAct pattern** | Observation → Thought → Action loop |
| **Structured output** | `with_structured_output()` |
| **API integrations** | NewsAPI, GDELT |

### Hands-on Task
```python
from langchain_core.tools import tool

@tool
def search_news(query: str, days_back: int = 7) -> list[dict]:
    """Search news articles for supply chain events."""
    ...

agent = llm.bind_tools([search_news])
```

📖 **Read**: [LangChain Tools](https://python.langchain.com/docs/concepts/tools/)

---

## Phase 3 — Multi-Agent Orchestration 🎭

### What You'll Build
- 5 agents (News, Geo, Finance, Impact, Mitigation)
- LangGraph state machine
- Agent-to-agent communication

### Concepts You'll Learn
| Concept | Where in SupplyPulse |
|---|---|
| **LangGraph StateGraph** | `supplypulse/orchestrator/graph.py` |
| **State management** | TypedDict shared across nodes |
| **Conditional edges** | Routing based on agent outputs |
| **Supervisor pattern** | Orchestrator routes to specialists |
| **Parallel execution** | News + Geo + Finance run concurrently |

### Hands-on Task
```python
from langgraph.graph import StateGraph, END

class RiskState(TypedDict):
    supplier_id: str
    news_findings: list
    geo_findings: list
    finance_findings: list

graph = StateGraph(RiskState)
graph.add_node("news", news_agent)
graph.add_node("geo", geo_agent)
```

📖 **Read**: [LangGraph Tutorial](https://langchain-ai.github.io/langgraph/tutorials/introduction/)

---

## Phase 4 — Retrieval & Memory 🧠

### What You'll Build
- ChromaDB-backed knowledge base over historical events
- Embeddings for supplier profiles
- Conversational memory

### Concepts You'll Learn
| Concept | Where in SupplyPulse |
|---|---|
| **Embeddings** | OpenAI `text-embedding-3-small` |
| **Vector stores** | ChromaDB |
| **Retrievers** | Similarity + MMR search |
| **RAG chains** | Retriever + Prompt + LLM |
| **Conversation memory** | `MessagesPlaceholder` |

### Hands-on Task
```python
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=OpenAIEmbeddings()
)
similar = vectorstore.similarity_search("port closure", k=5)
```

📖 **Read**: [LangChain RAG](https://python.langchain.com/docs/tutorials/rag/)

---

## Phase 5 — Human-in-the-Loop UX 💬

### What You'll Build
- Streamlit dashboard with world map
- Live agent reasoning display
- Approval workflow for high-impact mitigations

### Concepts You'll Learn
| Concept | Where in SupplyPulse |
|---|---|
| **Streaming responses** | `astream()` for live agent thoughts |
| **Callbacks** | Token-level UI updates |
| **Human approval gates** | LangGraph `interrupt` |
| **State persistence** | Checkpointers |

📖 **Read**: [LangGraph Human-in-the-Loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)

---

## Phase 6 — Production & Observability ☁️

### What You'll Build
- Dockerized stack
- LangSmith integration
- Cloud deployment (Render/Railway free tier)

### Concepts You'll Learn
| Concept | Where in SupplyPulse |
|---|---|
| **LangSmith tracing** | Set `LANGCHAIN_TRACING_V2=true` |
| **Cost tracking** | Token usage per agent |
| **Latency profiling** | Identify slow agents |
| **Containerization** | `Dockerfile`, `docker-compose.yml` |

---

## Phase 7 — Evaluation ✨

### What You'll Build
- Eval harness with golden dataset
- Regression tests for agent quality
- Demo video

### Concepts You'll Learn
| Concept | Where in SupplyPulse |
|---|---|
| **LangSmith evaluators** | LLM-as-judge |
| **Custom metrics** | Tool-call accuracy, latency |
| **Regression testing** | Prevent agent drift |

---

## 📖 Recommended Reading Order

1. [LangChain Concepts (overview)](https://python.langchain.com/docs/concepts/)
2. [Build a Simple LLM Application](https://python.langchain.com/docs/tutorials/llm_chain/)
3. [Build an Agent](https://python.langchain.com/docs/tutorials/agents/)
4. [LangGraph Quickstart](https://langchain-ai.github.io/langgraph/tutorials/introduction/)
5. [Multi-Agent Systems with LangGraph](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/multi-agent-collaboration/)

## 🎯 By the End You Will Know

- ✅ How to design prompts for reliable LLM behavior
- ✅ When to use chains vs. agents vs. graphs
- ✅ How to integrate live APIs as agent tools
- ✅ How to design multi-agent collaboration patterns
- ✅ How to ground LLMs with RAG
- ✅ How to evaluate and observe agents in production
- ✅ How to deploy agentic systems to the cloud

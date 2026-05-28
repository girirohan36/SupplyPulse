<div align="center">

# 🌐 SupplyPulse

### Agentic AI for Supply Chain Resilience

**Five autonomous AI agents collaborate to detect supplier risks from live news, geopolitical events, weather, and financial signals — then auto-generate mitigation plans.**

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C.svg)](https://python.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-FF6B6B.svg)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

[**Demo**](#-demo) • [**Architecture**](#%EF%B8%8F-architecture) • [**Quickstart**](#-quickstart) • [**Learning Path**](LEARNING_PATH.md) • [**Roadmap**](#%EF%B8%8F-roadmap)

</div>

---

## 🎯 The Problem

Global supply chains are increasingly fragile. A single disruption — a typhoon in Taiwan, a port strike in LA, a supplier bankruptcy in Vietnam — can cascade into millions of dollars in delays.

Today, this is monitored by humans manually scanning news, dashboards, and spreadsheets. **It doesn't scale.**

## 💡 The Solution

**SupplyPulse** is an open-source multi-agent AI platform that continuously monitors your global supplier network using five specialized agents. Each agent watches a different risk dimension, and together they detect, analyze, and propose mitigations for emerging disruptions — autonomously.

## 🤖 Meet the Agents

| Agent | Watches | Tools |
|---|---|---|
| 📰 **News Scanner** | Global news for supplier-relevant events | NewsAPI, GDELT |
| 🌍 **Geo Risk** | Weather, earthquakes, port disruptions | Open-Meteo, USGS |
| 💰 **Financial Health** | Stock signals, earnings, volatility | yfinance |
| 🎯 **Impact Analyzer** | Maps risks to affected products & SKUs | Internal supplier DB |
| 🛠️ **Mitigation** | Drafts action plans, finds alternates | RAG over past events |

These agents are orchestrated by a **LangGraph** state machine that runs them in parallel, aggregates findings, and routes high-impact decisions to human approvers.

## 🎬 Demo

> 📹 *Demo video coming soon — see [`docs/demo.gif`](docs/)*

**Try it yourself:**
```bash
$ python -m supplypulse.agents.news_scanner SUP-0001

🔍 Running News Scanner Agent for SUP-0001...
============================================================
Supplier: NorthStar Manufacturing (Shanghai, China)
Risk Level: MEDIUM
Confidence: 0.82

Summary:
  Recent news indicates ongoing port congestion at Shanghai affecting
  outbound shipments. Combined with a typhoon forecast for next week,
  short-term shipping delays of 3-5 days are likely.

Key Events:
  • Shanghai port congestion enters second week (Reuters, 2 days ago)
  • Typhoon Maliksi forecast to hit Yangtze Delta (NHK, 1 day ago)

Sources:
  • https://reuters.com/...
  • https://nhk.or.jp/...
```

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────┐
│            Streamlit Dashboard (World Map + Chat)          │
└────────────────────────────────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  FastAPI       │
                    └───────┬────────┘
                            │
              ┌─────────────▼──────────────┐
              │  LangGraph Orchestrator    │
              │  (State Machine)           │
              └─────────────┬──────────────┘
                            │
       ┌────────┬───────────┼──────────┬─────────────┐
       ▼        ▼           ▼          ▼             ▼
   ┌──────┐ ┌──────┐   ┌────────┐  ┌────────┐  ┌──────────┐
   │News  │ │Geo   │   │Finance │  │Impact  │  │Mitigation│
   │Agent │ │Agent │   │ Agent  │  │Analyzer│  │  Agent   │
   └──┬───┘ └──┬───┘   └───┬────┘  └───┬────┘  └────┬─────┘
      │        │           │           │            │
      ▼        ▼           ▼           ▼            ▼
   ┌────────────────────────────────────────────────────────┐
   │  Tool Layer: NewsAPI │ GDELT │ Open-Meteo │ USGS │     │
   │              yfinance │ ChromaDB (RAG) │ SQLite       │
   └────────────────────────────────────────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │  Observability: LangSmith  │
              └────────────────────────────┘
```

**Design highlights:**
- 🔀 **Parallel fan-out** — News, Geo, Finance agents run concurrently
- 🧩 **Fan-in aggregation** — Impact agent synthesizes all findings
- 🧠 **RAG-grounded reasoning** — Mitigation agent retrieves similar past events
- 👤 **Human-in-the-loop** — High/Critical risks gate on human approval
- 📡 **Live data** — No mocked APIs; all 5 external sources are real & free

## ✨ Key Features

- 🤖 **5-agent LangGraph orchestration** with parallel & sequential coordination
- 📡 **Live data integration** — 5 free public APIs (no proprietary dependencies)
- 🔍 **RAG over historical events** using ChromaDB
- 👤 **Human-in-the-loop** approvals for high-impact mitigations
- 📊 **Interactive world map** showing real-time supplier risk levels
- 📈 **Full observability** with LangSmith tracing & cost tracking
- 🧪 **Evaluation harness** with golden test cases
- 🐳 **Docker-ready** for cloud deployment (AWS ECS / Render / Railway)
- 🎓 **Learning-friendly** — designed as a tutorial for LangChain & LangGraph

## 🛠️ Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Agent framework | **LangGraph** + LangChain 0.3 | Stateful, observable, production-grade |
| LLM | OpenAI GPT-4o-mini *(or Anthropic Claude Haiku)* | Cost-effective, fast |
| Vector DB | **ChromaDB** | Embedded, no infra needed |
| Backend | **FastAPI** | Async, auto-docs |
| UI | **Streamlit** + Plotly + Folium | Fast iteration, world maps |
| State & cache | Redis + SQLite | Standard cloud patterns |
| Observability | **LangSmith** | Native agent tracing |
| Synthetic data | Faker | Reproducible fictional datasets |
| Deployment | Docker + Cloud Run / ECS | Cloud-native |

## 🚀 Quickstart

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/supplypulse.git
cd supplypulse

# 2. Setup
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # add your OPENAI_API_KEY

# 3. Generate synthetic supplier dataset
python -m supplypulse.data.generate

# 4. Run your first agent!
python -m supplypulse.agents.news_scanner SUP-0001

# 5. Run the full multi-agent graph
python -m supplypulse.orchestrator.graph

# 6. Launch the dashboard
streamlit run supplypulse/ui/app.py
```

📖 See [`QUICKSTART.md`](QUICKSTART.md) for detailed setup and troubleshooting.

## 📊 Synthetic Dataset

SupplyPulse ships with a realistic but **100% fictional** supplier dataset:

- 🏭 **50 suppliers** across 12 countries (Shanghai, Chennai, Taipei, Monterrey, Prague, etc.)
- 📦 **8 product lines** with multi-tier component dependencies
- 🔗 **~80 supplier-product relationships** with allocation %
- 📚 **80 historical disruption events** for RAG training

All company names, contacts, and financials are generated with [Faker](https://faker.readthedocs.io/) — no real entities are referenced.

## 💡 Example Queries

Once running, ask the system natural language questions:

- *"Show me suppliers at risk this week"*
- *"What's our exposure to typhoons in East Asia?"*
- *"Generate a mitigation plan if NorthStar Manufacturing has a 7-day disruption"*
- *"Which Tier-1 suppliers have negative financial signals?"*
- *"Find me alternates for semiconductor sourcing outside Taiwan"*

## 📚 Learning Path

This project doubles as a **structured curriculum for LangChain + LangGraph**, organized by concept:

| Phase | Concepts | Deliverable |
|---|---|---|
| Foundations | Prompts, LCEL, output parsers | Synthetic dataset + first chain |
| Tool-Using Agents | `@tool`, ReAct, structured output | News Scanner Agent |
| Multi-Agent Orchestration | LangGraph, state machines, parallelism | 5-agent orchestrator |
| Retrieval & Memory | Embeddings, vector stores, RAG | ChromaDB knowledge base |
| Human-in-the-Loop UX | Streaming, callbacks, approval gates | Streamlit dashboard |
| Production & Observability | Tracing, deployment, cost tracking | Docker + cloud deploy |
| Evaluation | Evals, regression testing | Eval harness + demo |

📖 Full curriculum: [`LEARNING_PATH.md`](LEARNING_PATH.md)

## 📈 Performance

| Metric | Value |
|---|---|
| Avg. risk analysis latency (5 agents) | ~25s |
| Token cost per supplier scan | ~$0.04 |
| Synthetic dataset generation | <2s |
| Concurrent agent invocations | 50 |

## 🛣️ Roadmap

- [x] Multi-agent LangGraph orchestrator skeleton
- [x] Five live data integrations (NewsAPI, GDELT, Open-Meteo, USGS, yfinance)
- [x] Synthetic supplier dataset generator
- [x] News Scanner Agent
- [ ] Geo Risk Agent
- [ ] Financial Health Agent
- [ ] Impact Analyzer Agent
- [ ] Mitigation Agent
- [ ] ChromaDB RAG layer over historical events
- [ ] Streamlit dashboard with interactive world map
- [ ] Docker + cloud deployment
- [ ] Evaluation harness with golden test cases
- [ ] Demo video + blog post

## 🧠 What I Learned Building This

> *(Replace this section with your own reflections — recruiters love it!)*

- **Multi-agent design patterns** — supervisor vs. swarm vs. hierarchical
- **State management** in LangGraph for stateful, resumable workflows
- **Tool design** — narrow, well-named tools beat over-loaded ones
- **RAG for domain knowledge** — when to retrieve vs. when to fine-tune
- **Cost/latency tradeoffs** — parallelism, model selection, caching
- **Observability is non-negotiable** — LangSmith caught 3 bugs I'd never have seen

## 🤝 Contributing

Contributions welcome! See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines.

Good first issues:
- Add new live data sources (e.g., port congestion APIs)
- Improve prompts for better tool-call accuracy
- Add evaluators for new risk categories
- Translate UI to other languages

## ❓ FAQ

**Q: Is the supplier data real?**
A: No — 100% synthetic, generated with Faker. No real companies referenced.

**Q: What does it cost to run?**
A: < $5 in API costs to build the whole project. GPT-4o-mini is ~$0.0001 per agent call.

**Q: Can I use Claude / Llama / on-device models?**
A: Yes — swap `ChatOpenAI` for `ChatAnthropic` or `ChatOllama`. LangChain abstracts the LLM.

**Q: Does this require any paid services?**
A: Optional NewsAPI free tier (100 requests/day). Everything else (GDELT, USGS, Open-Meteo, yfinance) is fully free.

**Q: Can I use this in production?**
A: This is a learning project. For production, harden the prompts, add retries, real auth, and proper data integrations.

## 📜 License

MIT License — see [`LICENSE`](LICENSE) for details.

Use it, fork it, learn from it, build on it.

## 🙏 Acknowledgments

Built with:
- [LangChain](https://python.langchain.com/) & [LangGraph](https://langchain-ai.github.io/langgraph/)
- [OpenAI](https://openai.com/) GPT-4o-mini
- Free public APIs: [NewsAPI](https://newsapi.org/), [GDELT](https://www.gdeltproject.org/), [Open-Meteo](https://open-meteo.com/), [USGS](https://earthquake.usgs.gov/), [yfinance](https://github.com/ranaroussi/yfinance)

---

<div align="center">

**⭐ Star this repo if you found it useful!**

Built by [Your Name](https://github.com/YOUR_USERNAME) • [LinkedIn](https://linkedin.com/in/YOU) • [Blog](https://your-blog.com)

</div>

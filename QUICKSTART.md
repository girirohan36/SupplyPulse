# 🚀 SupplyPulse Quickstart — Get Running in 15 Minutes

## Step 1: Setup (3 min)

```bash
cd supplypulse

# Create virtual env
python3.11 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .

# Configure
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Step 2: Generate Synthetic Data (1 min)

```bash
python -m supplypulse.data.generate
```

You should see:
```
✅ Generated:
   • 50 suppliers across 12 countries
   • 8 product lines
   • ~80 supplier-product relationships
   • 80 historical disruption events
```

Check `data/suppliers.json` — open it to see your fictional supplier network.

## Step 3: Run Your First Agent (5 min)

```bash
# Run News Scanner Agent on supplier SUP-0001
python -m supplypulse.agents.news_scanner SUP-0001
```

Output:
```
🔍 Running News Scanner Agent for SUP-0001...
============================================================
Supplier: NorthStar Manufacturing (SUP-0001)
Risk Level: LOW
Confidence: 0.7

Summary:
  No active disruptions found. General industry news mentions
  ongoing component shortages in the region but no supplier-specific concerns.

Key Events:
  • Component shortages in semiconductor industry
  • Shanghai port slight delays reported

Sources:
  • https://...
  • https://...
```

🎉 **You just ran a multi-tool LangChain agent that:**
1. Looked up supplier from your DB
2. Searched live news (NewsAPI)
3. Searched global events (GDELT)
4. Synthesized findings with structured output

## Step 4: Run the Multi-Agent Graph (Day 3+)

```bash
python -m supplypulse.orchestrator.graph
```

This runs the full LangGraph orchestrator — News + Geo + Finance + Impact + Mitigation.

## What's Next?

📚 Open [`LEARNING_PATH.md`](LEARNING_PATH.md) for the day-by-day breakdown.

📋 Day-by-Day TODOs:
- [x] **Day 1**: Foundations — DONE (you have this scaffold!)
- [ ] **Day 2**: Polish News Agent + add tests
- [ ] **Day 3**: Build Geo Risk + Finance Health agents (replace TODOs in `orchestrator/graph.py`)
- [ ] **Day 4**: Add ChromaDB RAG over `historical_events.json`
- [ ] **Day 5**: Streamlit dashboard with world map
- [ ] **Day 6**: Dockerize + deploy to Render
- [ ] **Day 7**: Eval harness + demo video + README polish

## Common Issues

**`OPENAI_API_KEY` not set**
→ Make sure `.env` is in the project root and has your key

**`NEWS_API_KEY` not set**
→ Get free key at https://newsapi.org/register (100 requests/day free)
→ Or skip — the agent will use GDELT only (no key needed)

**Import errors**
→ Make sure you ran `pip install -e .` from the project root

## Cost Estimate

Building this whole project should cost you **< $5** in OpenAI API usage:
- GPT-4o-mini: ~$0.0001 per agent invocation
- ~50 test runs during dev = ~$0.50
- Demo video recording = ~$0.10
- Total budget: **$5 max**

Use **Claude Haiku** if you have an Anthropic key — even cheaper.

# FinAdvisor — Personalized Financial Advisor using LLM

Capstone project: a personalized financial guidance assistant built on an open-weights LLM (Llama-3.1-8B-Instruct via Hugging Face Inference Providers), grounded with retrieval-augmented generation over financial-education sources and live Alpha Vantage market data.

## What it does

Three pillars wrapped in one chat experience:

1. **Conversational Q&A** — explains financial concepts (IRA vs 401k, dollar-cost averaging, ETFs), grounded in SEC/IRS/FINRA materials.
2. **Investment & portfolio analysis** — pulls live quotes, news sentiment, technical indicators and sector data from Alpha Vantage; reasons over your holdings.
3. **Goal-based planning** — retirement projection, savings target, debt payoff, asset-allocation suggestion via deterministic calculators the agent calls as tools.

Every advisory response carries a disclaimer and source/tool citations.

## Architecture

User → Streamlit UI → ReAct Agent (Llama-3.1-8B) → tools (Alpha Vantage + calculators + profile) and RAG (Chroma + BM25 hybrid) → safety wrap → response.


## Quickstart

```bash
# 1. Setup
make setup
source .venv/bin/activate
cp .env.example .env
# edit .env: set HF_TOKEN (huggingface.co/settings/tokens) and ALPHA_VANTAGE_KEY (alphavantage.co/support/#api-key)

# 2. Sanity-check the offline test suite (no API keys needed)
make test

# 3. Drop some PDFs / markdown into corpus/sec_education/, corpus/irs_pubs/, etc.
#    Or just rely on the bundled corpus/glossary.md to start.

# 4. Build the RAG index
make index

# 5. Run the app
make run
# opens http://localhost:8501
```

## Project layout

```
financial-advisor-llm/
├── src/advisor/        # Library code (config, llm, tools, rag, agent, eval)
├── app/                # Streamlit UI (entry + 4 pages)
├── corpus/             # Source documents for RAG
├── data/               # Caches, vector DB, profile DB (gitignored)
├── notebooks/          # Exploratory notebooks
├── scripts/            # CLI entry points
└── tests/              # pytest suite
```

## Common commands

| Command | What it does |
|---|---|
| `make setup` | Create `.venv` and install deps |
| `make index` | Build the Chroma vector store from `corpus/` |
| `make run` | Launch Streamlit |
| `make eval` | Run Financial PhraseBank eval (50 samples) |
| `make test` | Run pytest suite |
| `make clean` | Remove generated data + caches |

## Configuration

Settings are read from `.env` (see `.env.example`):

- `HF_TOKEN` — Hugging Face access token
- `ALPHA_VANTAGE_KEY` — Alpha Vantage API key (free tier OK; 25 req/day)
- `LLM_MODEL_ID` — defaults to `meta-llama/Llama-3.1-8B-Instruct`
- `LLM_PROVIDER` — HF Inference Provider (`together`, `fireworks-ai`, `hyperbolic`, ...)

## Disclaimers

This software is for educational use only and does not constitute regulated financial advice. Outputs may be incomplete, outdated, or wrong. Always consult a licensed advisor before acting.

## References

- Yang, Liu, Wang. *FinGPT: Open-Source Financial Large Language Models.* arXiv:2306.06031 (2023).
- Alpha Vantage API: https://www.alphavantage.co/documentation/
- Hugging Face Inference Providers: https://huggingface.co/docs/inference-providers/

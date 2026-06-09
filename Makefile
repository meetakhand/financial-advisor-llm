.PHONY: setup index run eval test clean

VENV := .venv
PY := $(VENV)/bin/python

setup:
	python3 -m venv $(VENV)
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements.txt
	@echo "Setup complete. Activate with: source $(VENV)/bin/activate"
	@echo "Then copy .env.example to .env and fill in HF_TOKEN + ALPHA_VANTAGE_KEY."

index:
	$(PY) scripts/build_rag_index.py

run:
	$(PY) -m streamlit run app/streamlit_app.py

eval:
	$(PY) scripts/run_eval.py --task fpb --n 50

test:
	$(PY) -m pytest -q

clean:
	rm -rf data/chroma data/raw data/processed data/profile.db
	find . -type d -name __pycache__ -exec rm -rf {} +

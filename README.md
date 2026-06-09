# 🛡️ Threat Intelligence Agents

A two-agent threat-analysis system with a Streamlit dashboard, powered by the
Google Gemini API.

```
Upload Document
      ↓
Threat Scoring Agent      → Threat Report (score, severity, entities, indicators, evidence)
      ↓
Recommendation Agent      → Recommendations (actions, monitoring, escalation, mitigation)
      ↓
Streamlit Dashboard       → View / Ask Questions / Download
```

## Features

- **Agent 1 – Threat Scoring**: reads an uploaded document and returns a threat
  score (0–10), severity level (Low / Medium / High / Critical), key entities,
  threat indicators and evidence with reasoning.
- **Agent 2 – Recommendations**: takes the threat report and returns immediate
  actions, monitoring tasks, an escalation decision and risk-mitigation suggestions.
- **Streamlit dashboard**: upload a document, view the report and evidence, ask
  free-form questions about the document, and download the full JSON report.

## Project structure

```
threat-intel-agents/
├── app.py                       # Streamlit dashboard
├── run_pipeline.py              # CLI runner (no UI)
├── agents/
│   ├── gemini_client.py         # Gemini API wrapper (text + JSON)
│   ├── threat_scoring_agent.py  # Agent 1
│   └── recommendation_agent.py  # Agent 2
├── utils/
│   └── document_loader.py       # txt / md / pdf / docx text extraction
├── sample_documents/
│   └── incident_report.txt      # example input
├── requirements.txt
└── .env.example
```

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Add your Gemini API key (get one at https://aistudio.google.com/app/apikey):

```bash
cp .env.example .env
# then edit .env and set GEMINI_API_KEY=...
```

## Run the dashboard

```bash
streamlit run app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501), upload a
document from the sidebar, and click **Analyze Threat**.

## Run from the command line

```bash
python run_pipeline.py sample_documents/incident_report.txt --out report.json
```

## How it works

| Field | Source |
| --- | --- |
| `threat_score` | Gemini, clamped to 0–10 |
| `severity_level` | Derived from the score band (Low/Medium/High/Critical) |
| `key_entities`, `threat_indicators`, `evidence` | Gemini structured JSON |
| Recommendations | Agent 2, conditioned on the threat report |

The Gemini client requests `response_mime_type=application/json` so the agents
get well-formed JSON, with a fallback parser that strips markdown code fences.

## Notes

- Large documents are truncated to ~30k characters before analysis.
- Supported uploads: `.txt`, `.md`, `.log`, `.csv`, `.pdf`, `.docx`.
- Set `GEMINI_MODEL` in `.env` to use a different model (default `gemini-2.0-flash`).
```

"""Command-line runner for the threat pipeline (no Streamlit required).

Usage:
    python run_pipeline.py path/to/document.txt
    python run_pipeline.py path/to/document.pdf --out report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agents.gemini_client import GeminiClient, GeminiClientError
from agents.recommendation_agent import RecommendationAgent
from agents.threat_scoring_agent import ThreatScoringAgent
from utils.document_loader import extract_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the threat-scoring pipeline.")
    parser.add_argument("document", help="Path to the document to analyze.")
    parser.add_argument("--out", help="Optional path to write the full JSON report.")
    args = parser.parse_args()

    path = Path(args.document)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    text = extract_text(path.name, path.read_bytes())

    try:
        client = GeminiClient()
    except GeminiClientError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print("Scoring threats...", file=sys.stderr)
    report = ThreatScoringAgent(client).analyze(text)

    print("Generating recommendations...", file=sys.stderr)
    plan = RecommendationAgent(client).recommend(report)

    result = {"threat_report": report, "recommendations": plan}
    output = json.dumps(result, indent=2)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Wrote report to {args.out}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

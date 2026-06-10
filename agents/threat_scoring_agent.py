"""Agent 1 - Threat Scoring.

Reads a document and produces a structured threat report:
    * threat_score (0-10)
    * severity_level (Low / Medium / High / Critical)
    * key_entities
    * threat_indicators
    * evidence / reasoning
"""

from __future__ import annotations

from typing import Any

from ._common import build_client

# Truncate very large documents so we stay within model context limits.
MAX_DOC_CHARS = 30_000

SEVERITY_BANDS = [
    (0.0, 2.0, "Low"),
    (2.0, 5.0, "Medium"),
    (5.0, 8.0, "High"),
    (8.0, 10.01, "Critical"),
]

_PROMPT = """You are a senior cybersecurity threat analyst. Analyze the document
below and assess the threats and risks it describes or contains.

Return ONLY a JSON object with exactly these fields:
{{
  "threat_score": <number 0-10, one decimal allowed>,
  "severity_level": "<Low|Medium|High|Critical>",
  "summary": "<2-3 sentence executive summary of the threat>",
  "key_entities": [
    {{"name": "<entity>", "type": "<person|organization|ip|domain|file|cve|other>", "role": "<why it matters>"}}
  ],
  "threat_indicators": [
    {{"indicator": "<observable / IOC / behaviour>", "category": "<malware|phishing|data-exfiltration|vulnerability|insider|network|other>", "confidence": "<low|medium|high>"}}
  ],
  "evidence": [
    {{"finding": "<specific finding>", "reasoning": "<why this raises risk>", "quote": "<short supporting excerpt from the document>"}}
  ]
}}

Scoring guidance:
- 0-2 Low: informational, no actionable threat.
- 2-5 Medium: potential risk, limited impact or low likelihood.
- 5-8 High: credible threat with meaningful impact.
- 8-10 Critical: active, severe, or imminent threat with major impact.

Be specific and ground every claim in the document. If the document contains no
real threat, return a low score and say so in the summary.

DOCUMENT:
\"\"\"
{document}
\"\"\"
"""


class ThreatScoringAgent:
    """Produces a structured threat report from document text."""

    def __init__(self, client=None):
        self.client = client or build_client()

    def analyze(self, document_text: str) -> dict[str, Any]:
        text = (document_text or "").strip()
        if not text:
            raise ValueError("Document text is empty; nothing to analyze.")

        truncated = text[:MAX_DOC_CHARS]
        prompt = _PROMPT.format(document=truncated)
        report = self.client.generate_json(prompt)
        return self._normalize(report, truncated_input=len(text) > MAX_DOC_CHARS)

    def _normalize(self, report: dict[str, Any], *, truncated_input: bool) -> dict[str, Any]:
        """Clamp the score and keep severity consistent with the score band."""
        score = _clamp_score(report.get("threat_score"))
        report["threat_score"] = score
        report["severity_level"] = _severity_for_score(
            score, report.get("severity_level")
        )

        report.setdefault("summary", "")
        report.setdefault("key_entities", [])
        report.setdefault("threat_indicators", [])
        report.setdefault("evidence", [])
        report["input_truncated"] = truncated_input
        return report


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    return round(max(0.0, min(10.0, score)), 1)


def _severity_for_score(score: float, model_severity: Any) -> str:
    for low, high, label in SEVERITY_BANDS:
        if low <= score < high:
            return label
    # Fall back to the model's own label if something is off.
    if isinstance(model_severity, str) and model_severity:
        return model_severity
    return "Low"

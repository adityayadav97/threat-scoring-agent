"""Agent 2 - Recommendations.

Takes the threat report (primarily the threat score / severity) and produces an
action plan:
    * immediate_actions
    * monitoring_tasks
    * escalation (decision + who + why)
    * risk_mitigation
"""

from __future__ import annotations

import json
from typing import Any

from .gemini_client import GeminiClient

_PROMPT = """You are an incident-response and risk-management advisor. Based on the
threat assessment below, produce a clear, prioritized action plan.

THREAT ASSESSMENT (JSON):
{report}

Return ONLY a JSON object with exactly these fields:
{{
  "immediate_actions": ["<action to take right now, most urgent first>"],
  "monitoring_tasks": ["<what to watch / detect going forward>"],
  "escalation": {{
    "should_escalate": <true|false>,
    "escalate_to": "<role/team, or 'none'>",
    "urgency": "<none|low|medium|high|immediate>",
    "reason": "<why escalation is or is not needed>"
  }},
  "risk_mitigation": ["<longer-term mitigation / hardening suggestion>"]
}}

Guidance:
- Scale the response to the severity. Low severity = light monitoring, no escalation.
  Critical = immediate containment and escalation.
- Be concrete and actionable. Avoid generic filler.
"""


class RecommendationAgent:
    """Generates an action plan from a threat report."""

    def __init__(self, client: GeminiClient | None = None):
        self.client = client or GeminiClient()

    def recommend(self, threat_report: dict[str, Any]) -> dict[str, Any]:
        if not threat_report:
            raise ValueError("A threat report is required to generate recommendations.")

        # Pass only the fields the recommender needs.
        slim = {
            "threat_score": threat_report.get("threat_score"),
            "severity_level": threat_report.get("severity_level"),
            "summary": threat_report.get("summary"),
            "threat_indicators": threat_report.get("threat_indicators", []),
            "key_entities": threat_report.get("key_entities", []),
        }
        prompt = _PROMPT.format(report=json.dumps(slim, indent=2))
        plan = self.client.generate_json(prompt)
        return self._normalize(plan)

    def _normalize(self, plan: dict[str, Any]) -> dict[str, Any]:
        plan.setdefault("immediate_actions", [])
        plan.setdefault("monitoring_tasks", [])
        plan.setdefault("risk_mitigation", [])
        escalation = plan.get("escalation") or {}
        escalation.setdefault("should_escalate", False)
        escalation.setdefault("escalate_to", "none")
        escalation.setdefault("urgency", "none")
        escalation.setdefault("reason", "")
        plan["escalation"] = escalation
        return plan

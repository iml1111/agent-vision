"""
Claude Summarization Client

Direct Claude API client for session summarization.
Generates structured summaries from conversation history.
"""
import json
from typing import List
from logging_config import get_logger

from anthropic import AsyncAnthropic
from domain.entities.message import MessageEntity
from domain.value_objects.agent_types import GrowthMemorySummaryVO
from domain.exceptions import SummarizationError

logger = get_logger(__name__)


SUMMARIZATION_SYSTEM_PROMPT = """You are a Growth Hacking analyst that extracts structured insights from conversation history.

Analyze the provided conversation and extract the following 6 units in JSON format:

1. problem_snapshot: Brief context of the growth problem being analyzed (1-2 paragraphs). Include:
   - What KPI was problematic and why
   - Time period, segments, target funnels, and key conditions

2. bottleneck_evidence: Identified bottlenecks with supporting evidence (1-2 paragraphs). Include:
   - Bottleneck location (funnel stage, cohort, segment)
   - Evidence type label (quantitative/qualitative) - whether based on aggregated data or Slack insights, etc.

3. hypotheses: List of hypotheses generated during the session (array of strings). Include:
   - Final adopted hypothesis
   - Rejected hypotheses with brief rejection reasons (especially valuable for reuse)

4. experiment_cards: Structured experiment designs (array of objects). Each card should contain:
   - hypothesis_id: Reference to the hypothesis
   - experiment_name: Name of the experiment
   - target: Target audience/segment
   - channel: Distribution channel
   - duration: Experiment duration
   - success_metric: Primary success metric
   - guardrail_metric: Safety metric
   - impact: Expected impact (High/Medium/Low)
   - effort: Required effort (High/Medium/Low)
   - risk: Risk level (High/Medium/Low)
   - priority_reason: Why this priority was chosen

5. outcome: Results and conclusions if experiments were discussed (1 paragraph). Include:
   - Success/Failure/Inconclusive status
   - Numerical changes if available
   - Statistical significance and confounding factors

6. learnings_next_actions: Key takeaways and recommended next steps (1-2 paragraphs). Include:
   - What worked and what didn't work
   - Concrete next actions to take

Return ONLY valid JSON with these 6 keys. Use null for fields that don't apply to this conversation.
Do NOT include any text before or after the JSON.

JSON Schema:
{
    "problem_snapshot": "string | null",
    "bottleneck_evidence": "string | null",
    "hypotheses": ["string"] | null,
    "experiment_cards": [{
        "hypothesis_id": "string",
        "experiment_name": "string",
        "target": "string",
        "channel": "string",
        "duration": "string",
        "success_metric": "string",
        "guardrail_metric": "string",
        "impact": "High | Medium | Low",
        "effort": "High | Medium | Low",
        "risk": "High | Medium | Low",
        "priority_reason": "string"
    }] | null,
    "outcome": "string | null",
    "learnings_next_actions": "string | null"
}"""


class ClaudeSummarizationClient:
    """
    Claude API client for session summarization.

    Direct Claude API calls (not Agent SDK) for structured summarization.
    Returns deterministic JSON output for 6 growth memory units.
    """

    MODEL = "claude-opus-4-5"
    MAX_TOKENS = 4096

    def __init__(self, api_key: str):
        """
        Initialize the summarization client.

        Args:
            api_key: Anthropic API key
        """
        self._client = AsyncAnthropic(api_key=api_key)

    async def summarize_session(
        self,
        messages: List[MessageEntity]
    ) -> GrowthMemorySummaryVO:
        """
        Summarize session messages into 6 structured units.

        Args:
            messages: List of MessageEntity from the session

        Returns:
            GrowthMemorySummaryVO containing all 6 units

        Raises:
            SummarizationError: If summarization fails
        """
        if not messages:
            raise SummarizationError("No messages to summarize")

        # Format messages for Claude
        conversation_text = self._format_conversation(messages)

        try:
            response = await self._client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=SUMMARIZATION_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"Analyze this conversation and extract growth insights:\n\n{conversation_text}"
                    }
                ]
            )

            # Extract text content
            content = response.content[0].text if response.content else ""

            # Parse JSON response
            summary_data = self._parse_json_response(content)

            return GrowthMemorySummaryVO(
                problem_snapshot=summary_data.get("problem_snapshot"),
                bottleneck_evidence=summary_data.get("bottleneck_evidence"),
                hypotheses=summary_data.get("hypotheses"),
                experiment_cards=summary_data.get("experiment_cards"),
                outcome=summary_data.get("outcome"),
                learnings_next_actions=summary_data.get("learnings_next_actions")
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse summarization response: {e}")
            raise SummarizationError(f"Invalid JSON response from Claude: {e}")
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            raise SummarizationError(f"Claude API call failed: {e}")

    def _format_conversation(self, messages: List[MessageEntity]) -> str:
        """
        Format messages into readable conversation text.

        Args:
            messages: List of MessageEntity

        Returns:
            Formatted conversation string
        """
        formatted_parts = []

        for msg in messages:
            role_label = msg.role.value.upper()
            content = msg.content

            # Include tool call info if present
            if msg.metadata and msg.metadata.get("event_type") == "tool_use":
                tool_call = msg.metadata.get("tool_call", {})
                tool_name = tool_call.get("name", "unknown")
                tool_input = tool_call.get("input", {})
                content = f"[Tool Call: {tool_name}]\nInput: {json.dumps(tool_input, ensure_ascii=False)}"

            formatted_parts.append(f"[{role_label}]\n{content}")

        return "\n\n---\n\n".join(formatted_parts)

    def _parse_json_response(self, content: str) -> dict:
        """
        Parse JSON from Claude response.

        Handles cases where response might have extra text.

        Args:
            content: Raw response content

        Returns:
            Parsed JSON dictionary

        Raises:
            json.JSONDecodeError: If JSON parsing fails
        """
        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                return json.loads(content[start:end].strip())

        # Try to find JSON object
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])

        raise json.JSONDecodeError("No valid JSON found", content, 0)

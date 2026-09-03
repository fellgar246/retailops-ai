"""JSON Schema for structured Bedrock Converse output.

Pydantic remains the application validator. This schema is only the
provider-facing hint used by Converse tool configuration.
"""

from __future__ import annotations

from typing import Any

from retailops_api.review.types import RecommendedAction, ReviewType, RiskLevel

REVIEW_RESULT_TOOL_NAME = "submit_review_result"


def review_result_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "review_type",
            "summary",
            "findings",
            "reasoning_summary",
            "confidence",
            "risk",
            "recommended_action",
            "provider",
            "model",
            "prompt_id",
            "prompt_version",
            "input_schema_version",
            "output_schema_version",
        ],
        "properties": {
            "review_type": {"type": "string", "enum": [item.value for item in ReviewType]},
            "summary": {"type": "string", "minLength": 1},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["code", "message"],
                    "properties": {
                        "code": {"type": "string", "minLength": 1},
                        "message": {"type": "string", "minLength": 1},
                        "suggested_value": {"type": ["string", "null"]},
                        "field": {"type": ["string", "null"]},
                    },
                },
            },
            "suggested_value": {"type": ["string", "null"]},
            "reasoning_summary": {"type": "string", "minLength": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "risk": {"type": "string", "enum": [item.value for item in RiskLevel]},
            "recommended_action": {
                "type": "string",
                "enum": [item.value for item in RecommendedAction],
            },
            "provider": {"type": "string", "minLength": 1},
            "model": {"type": "string", "minLength": 1},
            "prompt_id": {"type": "string", "minLength": 1},
            "prompt_version": {"type": "string", "minLength": 1},
            "input_schema_version": {"type": "string", "minLength": 1},
            "output_schema_version": {"type": "string", "minLength": 1},
        },
    }


def review_result_tool_config() -> dict[str, Any]:
    return {
        "tools": [
            {
                "toolSpec": {
                    "name": REVIEW_RESULT_TOOL_NAME,
                    "description": (
                        "Submit the structured AI review result. "
                        "Do not recompute quantities, prices or VAT."
                    ),
                    "inputSchema": {"json": review_result_json_schema()},
                }
            }
        ],
        "toolChoice": {"tool": {"name": REVIEW_RESULT_TOOL_NAME}},
    }

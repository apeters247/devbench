"""Pydantic models for Devbench tool results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Standard result model for all Devbench tools.

    This model is serializable to JSON for rendering in a SwiftUI shell.
    """

    tool_name: str = Field(description="Name of the tool that produced this result")
    input: str = Field(description="Original input text")
    output: str = Field(default="", description="Tool output text")
    error: Optional[str] = Field(default=None, description="Error message if tool failed")
    detection_type: Optional[str] = Field(
        default=None,
        description="How the input was detected (auto-detection type)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional machine-readable metadata from the tool",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of when this result was created",
    )

    def to_swiftui(self) -> dict[str, Any]:
        """Return a clean dict safe for SwiftUI JSON rendering."""
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def error_result(
        cls,
        tool_name: str,
        input_text: str,
        error_msg: str,
        detection_type: Optional[str] = None,
    ) -> "ToolResult":
        """Convenience factory for error results."""
        return cls(
            tool_name=tool_name,
            input=input_text,
            output="",
            error=error_msg,
            detection_type=detection_type,
        )

    @classmethod
    def success_result(
        cls,
        tool_name: str,
        input_text: str,
        output: str,
        detection_type: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "ToolResult":
        """Convenience factory for success results."""
        return cls(
            tool_name=tool_name,
            input=input_text,
            output=output,
            detection_type=detection_type,
            metadata=metadata or {},
        )
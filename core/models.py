"""Tool result model for Devbench — uses Pydantic when available, dataclasses otherwise."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from pydantic import BaseModel, Field as PField

    class ToolResult(BaseModel):
        """Standard result model serializable to JSON for SwiftUI rendering."""

        tool_name: str = PField(description="Name of the tool that produced this result")
        input: str = PField(description="Original input text")
        output: str = PField(default="", description="Tool output text")
        error: Optional[str] = PField(default=None, description="Error message if tool failed")
        detection_type: Optional[str] = PField(
            default=None,
            description="How the input was detected (auto-detection type)",
        )
        metadata: dict[str, Any] = PField(
            default_factory=dict,
            description="Additional machine-readable metadata from the tool",
        )
        timestamp: str = PField(
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
            return cls(
                tool_name=tool_name,
                input=input_text,
                output=output,
                detection_type=detection_type,
                metadata=metadata or {},
            )

except ImportError:
    @dataclass
    class ToolResult:  # type: ignore[no-redef]
        """Fallback dataclass when pydantic is not installed."""

        tool_name: str
        input: str
        output: str = ""
        error: Optional[str] = None
        detection_type: Optional[str] = None
        metadata: dict = field(default_factory=dict)
        timestamp: str = field(
            default_factory=lambda: datetime.now(timezone.utc).isoformat()
        )

        def to_swiftui(self) -> dict[str, Any]:
            d = {
                "tool_name": self.tool_name,
                "input": self.input,
                "output": self.output,
                "metadata": self.metadata,
                "timestamp": self.timestamp,
            }
            if self.error is not None:
                d["error"] = self.error
            if self.detection_type is not None:
                d["detection_type"] = self.detection_type
            return d

        @classmethod
        def error_result(
            cls,
            tool_name: str,
            input_text: str,
            error_msg: str,
            detection_type: Optional[str] = None,
        ) -> "ToolResult":
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
            return cls(
                tool_name=tool_name,
                input=input_text,
                output=output,
                detection_type=detection_type,
                metadata=metadata or {},
            )

"""Abstract base classes for source and target adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ServerConfig:
    """Represents an MCP server configuration."""

    name: str
    config: dict[str, Any]

    @property
    def is_stdio(self) -> bool:
        return "command" in self.config

    @property
    def is_http(self) -> bool:
        return "url" in self.config


@dataclass
class Section:
    """Represents a markdown section (## or ###)."""

    header: str
    level: int
    content: str


@dataclass
class WriteResult:
    """Result of a write operation."""

    path: str
    written: bool
    bytes_written: int = 0
    message: str = ""


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    name: str
    passed: bool
    message: str
    severity: str = "error"  # error, warning, info


class SourceAdapter(ABC):
    """Base class for source adapters (e.g., Claude Code)."""

    @abstractmethod
    def load_servers(self) -> dict[str, ServerConfig]:
        """Load MCP servers from source."""

    @abstractmethod
    def load_rules(self) -> list[Section]:
        """Load rules/sections from source."""


class TargetAdapter(ABC):
    """Base class for target adapters (e.g., Cursor, Codex)."""

    @abstractmethod
    def generate_mcp(self, servers: dict[str, ServerConfig]) -> str | dict[str, Any]:
        """Generate MCP config in target-specific format."""

    @abstractmethod
    def generate_rules(self, sections: list[Section]) -> str:
        """Generate rules in target-specific format."""

    @abstractmethod
    def write(self, dry_run: bool = False) -> list[WriteResult]:
        """Write generated configs to target paths."""

    @abstractmethod
    def validate(self) -> list[ValidationResult]:
        """Validate existing target configs."""

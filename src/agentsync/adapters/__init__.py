"""Source and target adapters for different AI coding agents."""

from agentsync.adapters.antigravity import AntigravityTargetAdapter
from agentsync.adapters.claude import ClaudeSourceAdapter
from agentsync.adapters.codex import CodexTargetAdapter
from agentsync.adapters.cursor import CursorTargetAdapter

__all__ = [
    "AntigravityTargetAdapter",
    "ClaudeSourceAdapter",
    "CodexTargetAdapter",
    "CursorTargetAdapter",
]

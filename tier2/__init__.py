"""
PRISM Tier 2: Strategic LLM Reasoner Subsystem.

Provides high-level strategic reasoning, stall detection, and intermediate
subgoal decomposition to bridge semantic gaps in probabilistic inference.
"""

from prism.tier2.client import (
    LLMClient,
    MockLLMClient,
    OpenRouterClient,
    create_llm_client,
)
from prism.tier2.parser import SubgoalResult, parse_subgoal_response
from prism.tier2.prompt import build_stall_prompt
from prism.tier2.reasoner import Tier2Reasoner
from prism.tier2.stall_detector import StallDetector

__all__ = [
    "Tier2Reasoner",
    "StallDetector",
    "SubgoalResult",
    "build_stall_prompt",
    "parse_subgoal_response",
    "LLMClient",
    "MockLLMClient",
    "OpenRouterClient",
    "create_llm_client",
]

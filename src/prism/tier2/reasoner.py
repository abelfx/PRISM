"""
Tier 2 Strategic LLM Reasoner Coordinator for PRISM.

Coordinates stall detection, prompt construction, LLM client communication,
and subgoal validation to provide high-level strategic direction when forward
search stalls.
"""

import logging
from typing import Any, List, Optional, Set

from prism.core.config import Tier2Config
from prism.tier2.client import LLMClient, create_llm_client
from prism.tier2.parser import SubgoalResult, parse_subgoal_response
from prism.tier2.prompt import build_stall_prompt
from prism.tier2.stall_detector import StallDetector

logger = logging.getLogger(__name__)


class Tier2Reasoner:
    """
    High-level reasoning advisor invoked when forward search encounters stalls.
    """

    def __init__(
        self,
        config: Optional[Tier2Config] = None,
        client: Optional[LLMClient] = None,
    ):
        self.config: Tier2Config = config or Tier2Config()
        self.stall_detector: StallDetector = StallDetector(self.config)
        self.client: LLMClient = client or create_llm_client(self.config)
        self.total_proposals: int = 0
        self.successful_subgoals: int = 0
        self.last_failure: Optional[str] = None

    def check_stall(self, top_score: float, current_depth: int = 0) -> bool:
        """
        Check whether search expansion has stalled.
        """
        if not self.config.enabled:
            return False
        return self.stall_detector.check_stall(top_score, current_depth)

    def propose_subgoal(
        self,
        goal: Any,
        beliefs: List[Any],
        recent_derivations: Optional[List[Any]] = None,
        domain_concepts: Optional[Set[str]] = None,
    ) -> Optional[SubgoalResult]:
        """
        Construct context prompt, query the LLM backend, and parse the subgoal.

        Args:
            goal: Query goal.
            beliefs: Active belief state.
            recent_derivations: Derivation steps attempted recently.
            domain_concepts: Ground domain concept atoms.

        Returns:
            Optional[SubgoalResult]: Parsed and validated subgoal, or None if failed.
        """
        self.total_proposals += 1
        self.last_failure = None
        # Cool down after every provider attempt, including malformed responses
        # and network failures. Otherwise one outage causes an API call per
        # search expansion.
        self.stall_detector.record_invocation()

        try:
            prompt = build_stall_prompt(
                goal=goal,
                beliefs=beliefs,
                recent_derivations=recent_derivations,
                top_k=10,
            )

            response_text = self.client.generate(prompt)

            subgoal_res = parse_subgoal_response(
                response_text,
                domain_concepts=domain_concepts,
                active_goal=goal,
            )

            if subgoal_res:
                self.successful_subgoals += 1
                logger.info(f"[PRISM Tier 2] Proposed Subgoal: {subgoal_res.subgoal_str}")
                return subgoal_res

            logger.warning("[PRISM Tier 2] Subgoal response failed syntax or grounding validation.")
            self.last_failure = "response failed syntax or grounding validation"
            return None

        except Exception as e:
            logger.warning(f"[PRISM Tier 2] Subgoal generation failed gracefully: {e}")
            self.last_failure = f"{type(e).__name__}: {e}"
            return None

    def reset(self) -> None:
        """Reset internal stall tracking and statistics."""
        self.stall_detector.reset()
        self.total_proposals = 0
        self.successful_subgoals = 0
        self.last_failure = None

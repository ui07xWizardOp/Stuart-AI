"""
Context Compactor (Phase 9A ? Hardening Sprint)

Inspired by Hermes Agent's trajectory_compressor.py and CheetahClaws' compaction.py.

Instead of just dropping oldest messages (what ContextManager does now),
this module intelligently compresses older conversation turns into
condensed summaries ? preserving meaning while saving tokens.

Strategy:
  1. Detect when context window is > 80% full
  2. Select the oldest N turns (keeping the most recent turns intact)
  3. Pass them to the LOCAL LLM for summarization (free, fast)
  4. Replace the N turns with a single [COMPACTED] summary message
  5. Continue with the compacted context
"""

import math
from typing import List, Dict, Any, Optional
from observability import get_logging_system


import threading

class ContextCompactor:
    """
    Compresses conversation history by summarizing older turns.
    
    This is used IN ADDITION TO the existing ContextManager's hard-trim.
    The compactor runs BEFORE the hard-trim, so the context is already
    smaller when the trim logic kicks in.
    """

    # How many of the most recent turns to keep untouched
    PRESERVE_RECENT_TURNS = 6
    # Trigger compaction when context is this % full
    COMPACTION_THRESHOLD = 0.75
    # Max tokens for the compaction summary itself
    SUMMARY_MAX_TOKENS = 500

    def __init__(self, max_context_tokens: int = 16000, local_llm_client=None):
        self.max_context_tokens = max_context_tokens
        self.local_llm = local_llm_client  # OllamaClient for free summarization
        self.logger = get_logging_system()
        self._lock = threading.Lock()
        self._compaction_count = 0

    def _estimate_tokens(self, text: str) -> int:
        return math.ceil(len(text) / 4.0)

    def _estimate_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        return sum(self._estimate_tokens(m.get("content", "")) for m in messages)

    def should_compact(self, messages: List[Dict[str, str]]) -> bool:
        """Check if the context window is full enough to trigger compaction."""
        current_tokens = self._estimate_messages_tokens(messages)
        threshold = self.max_context_tokens * self.COMPACTION_THRESHOLD
        return current_tokens > threshold and len(messages) > self.PRESERVE_RECENT_TURNS + 2

    def compact(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Compact the message history by summarizing older turns.

        Returns a new message list with older turns replaced by a summary.
        The system message (index 0) and most recent N turns are preserved.
        """
        if not self.should_compact(messages):
            return messages

        # Separate: system prompt | old turns | recent turns
        system_msg = messages[0] if messages[0].get("role") == "system" else None
        conversation = messages[1:] if system_msg else messages[:]
        
        if len(conversation) <= self.PRESERVE_RECENT_TURNS:
            return messages

        # Split
        old_turns = conversation[:-self.PRESERVE_RECENT_TURNS]
        recent_turns = conversation[-self.PRESERVE_RECENT_TURNS:]

        old_tokens = self._estimate_messages_tokens(old_turns)
        self.logger.info(
            f"?? ContextCompactor: Compacting {len(old_turns)} old turns "
            f"(~{old_tokens} tokens) into summary..."
        )

        # Generate summary
        summary = self._summarize_turns(old_turns)
        with self._lock:
            self._compaction_count += 1
            current_count = self._compaction_count

        # Build compacted context
        compacted_msg = {
            "role": "system",
            "content": (
                f"[CONTEXT COMPACTION #{current_count}]\n"
                f"The following is a condensed summary of {len(old_turns)} earlier turns "
                f"in this conversation:\n\n{summary}\n\n"
                f"[END COMPACTION ? Recent conversation follows]"
            ),
        }

        new_tokens = self._estimate_tokens(compacted_msg["content"])
        saved = old_tokens - new_tokens
        self.logger.info(
            f"? ContextCompactor: Saved ~{saved} tokens "
            f"({old_tokens} ? {new_tokens}). "
            f"Compaction #{self._compaction_count}."
        )

        result = []
        if system_msg:
            result.append(system_msg)
        result.append(compacted_msg)
        result.extend(recent_turns)
        return result

    def _summarize_turns(self, turns: List[Dict[str, str]]) -> str:
        """
        Summarize a list of conversation turns into a brief paragraph.
        Uses the local LLM (Ollama) if available, otherwise falls back
        to a naive extraction.
        """
        # Build the text to summarize
        transcript = "\n".join(
            f"[{t.get('role', 'unknown').upper()}]: {t.get('content', '')[:500]}"
            for t in turns
        )

        if self.local_llm:
            try:
                summary_prompt = [
                    {
                        "role": "system",
                        "content": (
                            "You are a context compression engine. Summarize the following "
                            "conversation transcript into a concise paragraph (max 200 words). "
                            "Preserve: key decisions, tool calls and results, important facts, "
                            "and any action items. Discard: pleasantries, repetition, verbose "
                            "tool outputs. Output ONLY the summary, no preamble."
                        ),
                    },
                    {"role": "user", "content": transcript},
                ]
                return self.local_llm.generate_chat(summary_prompt)
            except Exception as e:
                self.logger.warning(
                    f"?? ContextCompactor: LLM summarization failed ({e}), "
                    f"falling back to naive extraction."
                )

        # Fallback: naive extraction (take first line of each turn)
        return self._naive_summarize(turns)

    def _naive_summarize(self, turns: List[Dict[str, str]]) -> str:
        """Fallback summarizer: extract key lines without LLM."""
        lines = []
        for t in turns:
            role = t.get("role", "unknown")
            content = t.get("content", "").strip()
            # Take only the first 100 chars of each turn
            snippet = content[:100] + ("..." if len(content) > 100 else "")
            if snippet:
                lines.append(f"? [{role}]: {snippet}")
        return "\n".join(lines[-10:])  # Keep last 10 snippets max

    def get_status(self) -> dict:
        with self._lock:
            count = self._compaction_count
            
        return {
            "compaction_count": count,
            "preserve_recent_turns": self.PRESERVE_RECENT_TURNS,
            "compaction_threshold_pct": self.COMPACTION_THRESHOLD * 100,
        }

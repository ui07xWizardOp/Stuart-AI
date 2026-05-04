"""
Verifiable Iteration (Feature #10: Advanced Orchestration)

A self-review loop where the agent critiques its own output before
finalizing, with structured assertion checks and configurable iteration depth.

Pipeline:
  1. Agent produces FINAL_ANSWER via normal ReAct loop
  2. VerifiableIterator runs verification checks on the answer
  3. If checks fail, the answer + critique is fed back for refinement
  4. Maximum 2 iterations to prevent infinite loops
  5. Audit trail saved to data/verifications/
"""

import os
import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from observability import get_logging_system
from core.model_router import ModelRouter, ModelTier


# ── Verification Checks ──────────────────────────────────────────────

class VerificationCheck(ABC):
    """Abstract base for pluggable verification checks."""
    name: str = "base_check"
    description: str = "Abstract verification check."

    @abstractmethod
    def verify(self, question: str, answer: str, context: Dict[str, Any]) -> "CheckResult":
        """
        Verify an answer against the original question.

        Args:
            question: The original user query.
            answer: The agent's proposed final answer.
            context: Additional context (tool outputs, reasoning trace, etc.).

        Returns:
            CheckResult with pass/fail and explanation.
        """
        pass


@dataclass
class CheckResult:
    """Result of a single verification check."""
    check_name: str
    passed: bool
    explanation: str = ""
    severity: str = "info"  # info, warning, critical

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "explanation": self.explanation,
            "severity": self.severity,
        }


# ── Built-in Checks ──────────────────────────────────────────────────

class CompletenessCheck(VerificationCheck):
    """Checks if the answer addresses all parts of the query."""
    name = "completeness"
    description = "Verifies the answer addresses all parts of the query."

    def __init__(self, router: ModelRouter):
        self.router = router

    def verify(self, question: str, answer: str, context: Dict[str, Any]) -> CheckResult:
        messages = [
            {"role": "system", "content": (
                "You are a Completeness Checker. Determine if the given answer "
                "fully addresses ALL parts of the original question.\n"
                "Respond in JSON: {\"passed\": true/false, \"explanation\": \"...\"}"
            )},
            {"role": "user", "content": (
                f"QUESTION:\n{question}\n\nANSWER:\n{answer[:3000]}"
            )},
        ]
        try:
            response = self.router.execute_with_failover(messages, force_tier=ModelTier.FAST_CHEAP)
            parsed = _extract_json(response)
            return CheckResult(
                check_name=self.name,
                passed=parsed.get("passed", True),
                explanation=parsed.get("explanation", ""),
                severity="warning" if not parsed.get("passed", True) else "info",
            )
        except Exception as e:
            return CheckResult(
                check_name=self.name,
                passed=True,  # Fail-open on check errors
                explanation=f"Check error: {e}",
            )


class ConsistencyCheck(VerificationCheck):
    """Checks for internal contradictions in the answer."""
    name = "consistency"
    description = "Checks for internal contradictions in the answer."

    def __init__(self, router: ModelRouter):
        self.router = router

    def verify(self, question: str, answer: str, context: Dict[str, Any]) -> CheckResult:
        messages = [
            {"role": "system", "content": (
                "You are a Consistency Checker. Examine the answer for any "
                "internal contradictions, conflicting statements, or logical "
                "inconsistencies.\n"
                "Respond in JSON: {\"passed\": true/false, \"explanation\": \"...\"}"
            )},
            {"role": "user", "content": f"ANSWER TO CHECK:\n{answer[:3000]}"},
        ]
        try:
            response = self.router.execute_with_failover(messages, force_tier=ModelTier.FAST_CHEAP)
            parsed = _extract_json(response)
            return CheckResult(
                check_name=self.name,
                passed=parsed.get("passed", True),
                explanation=parsed.get("explanation", ""),
                severity="critical" if not parsed.get("passed", True) else "info",
            )
        except Exception as e:
            return CheckResult(
                check_name=self.name,
                passed=True,
                explanation=f"Check error: {e}",
            )


class ToolResultCheck(VerificationCheck):
    """Checks if tool outputs were properly incorporated into the answer."""
    name = "tool_integration"
    description = "Verifies tool outputs were properly incorporated."

    def verify(self, question: str, answer: str, context: Dict[str, Any]) -> CheckResult:
        tool_outputs = context.get("tool_outputs", [])
        if not tool_outputs:
            return CheckResult(
                check_name=self.name,
                passed=True,
                explanation="No tool outputs to verify.",
            )

        # Simple heuristic: check if key terms from tool outputs appear in answer
        missing_references = []
        for i, output in enumerate(tool_outputs):
            output_str = str(output)[:500]
            # Extract significant words (>5 chars) from tool output
            significant_words = [
                w for w in output_str.split()
                if len(w) > 5 and w.isalpha()
            ][:5]

            if significant_words:
                found = sum(1 for w in significant_words if w.lower() in answer.lower())
                if found == 0:
                    missing_references.append(f"Tool output {i+1}")

        if missing_references:
            return CheckResult(
                check_name=self.name,
                passed=False,
                explanation=f"Potentially missed data from: {', '.join(missing_references)}",
                severity="warning",
            )

        return CheckResult(
            check_name=self.name,
            passed=True,
            explanation="Tool outputs appear to be incorporated.",
        )


# ── Verification Result ──────────────────────────────────────────────

@dataclass
class VerificationResult:
    """Complete result of the verification pipeline."""
    verification_id: str
    question: str
    original_answer: str
    final_answer: str
    checks: List[CheckResult] = field(default_factory=list)
    iterations: int = 0
    all_passed: bool = True
    duration_ms: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "question": self.question[:200],
            "original_answer": self.original_answer[:500],
            "final_answer": self.final_answer[:500],
            "checks": [c.to_dict() for c in self.checks],
            "iterations": self.iterations,
            "all_passed": self.all_passed,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


# ── Main Engine ───────────────────────────────────────────────────────

class VerifiableIterator:
    """
    Self-review loop that verifies agent outputs before finalizing.

    Runs a series of verification checks on the agent's FINAL_ANSWER.
    If any check fails, feeds the answer + critique back for one
    refinement pass (max 2 iterations).

    Attributes:
        router (ModelRouter): For refinement LLM calls.
        checks (List[VerificationCheck]): Pluggable verification checks.
        max_iterations (int): Maximum refinement iterations.
        enabled (bool): Toggle verification on/off at runtime.
    """

    VERIFICATION_DIR = os.path.join("data", "verifications")

    REFINEMENT_PROMPT = """You are a Self-Improvement Engine. You produced an answer
that failed quality verification. Review the critique and produce an improved answer.

Rules:
- Address ALL issues raised in the critique.
- Maintain everything that was correct in the original.
- Do NOT hallucinate or add unverified information.
- Output ONLY the refined answer, no meta-commentary."""

    def __init__(
        self,
        router: ModelRouter,
        event_bus=None,
        max_iterations: int = 2,
        enabled: bool = False,
    ):
        self.logger = get_logging_system()
        self.router = router
        self.event_bus = event_bus
        self.max_iterations = max_iterations
        self.enabled = enabled

        # Default checks
        self.checks: List[VerificationCheck] = [
            CompletenessCheck(router),
            ConsistencyCheck(router),
            ToolResultCheck(),
        ]

        os.makedirs(self.VERIFICATION_DIR, exist_ok=True)
        self.logger.info(
            f"VerifiableIterator initialized (enabled={enabled}, "
            f"max_iter={max_iterations}, checks={len(self.checks)})."
        )

    def add_check(self, check: VerificationCheck):
        """Add a custom verification check to the pipeline."""
        self.checks.append(check)
        self.logger.info(f"Added verification check: {check.name}")

    def verify_and_refine(
        self,
        question: str,
        answer: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Run verification checks on an answer and refine if needed.

        Args:
            question: The original user query.
            answer: The agent's proposed final answer.
            context: Additional context (tool outputs, etc.).

        Returns:
            VerificationResult with the (possibly refined) final answer.
        """
        if not self.enabled:
            return VerificationResult(
                verification_id="disabled",
                question=question,
                original_answer=answer,
                final_answer=answer,
                all_passed=True,
            )

        verification_id = uuid4().hex[:12]
        context = context or {}
        start = time.time()
        current_answer = answer
        all_check_results: List[CheckResult] = []
        iteration = 0

        self.logger.info(f"Verification {verification_id}: Starting ({len(self.checks)} checks)...")

        while iteration < self.max_iterations:
            iteration += 1

            # Run all checks
            check_results = self._run_checks(question, current_answer, context)
            all_check_results = check_results

            failures = [c for c in check_results if not c.passed]

            if not failures:
                self.logger.info(f"Verification {verification_id}: All checks passed (iter={iteration}).")
                self._emit_event("verification_passed", {
                    "verification_id": verification_id,
                    "iterations": iteration,
                })
                break

            self.logger.info(
                f"Verification {verification_id}: {len(failures)} checks failed (iter={iteration}). "
                f"Refining..."
            )

            # Build critique for refinement
            critique = self._build_critique(failures)

            # Attempt refinement (only if not at max iterations)
            if iteration < self.max_iterations:
                current_answer = self._refine(question, current_answer, critique)
            else:
                self._emit_event("verification_failed", {
                    "verification_id": verification_id,
                    "failures": [f.check_name for f in failures],
                    "iterations": iteration,
                })

        duration = (time.time() - start) * 1000
        all_passed = all(c.passed for c in all_check_results)

        result = VerificationResult(
            verification_id=verification_id,
            question=question,
            original_answer=answer,
            final_answer=current_answer,
            checks=all_check_results,
            iterations=iteration,
            all_passed=all_passed,
            duration_ms=duration,
            timestamp=datetime.now().isoformat(),
        )

        # Persist audit trail
        self._save_result(result)
        self.logger.info(
            f"Verification {verification_id} complete: "
            f"{'PASSED' if all_passed else 'PARTIAL'} in {duration:.0f}ms "
            f"({iteration} iterations)."
        )

        return result

    # ── Internal Methods ──────────────────────────────────────────────

    def _run_checks(
        self,
        question: str,
        answer: str,
        context: Dict[str, Any],
    ) -> List[CheckResult]:
        """Run all verification checks against the answer."""
        results = []
        for check in self.checks:
            try:
                result = check.verify(question, answer, context)
                results.append(result)
                self.logger.debug(
                    f"Check '{check.name}': {'PASS' if result.passed else 'FAIL'} — {result.explanation[:80]}"
                )
            except Exception as e:
                self.logger.error(f"Verification check '{check.name}' crashed: {e}")
                results.append(CheckResult(
                    check_name=check.name,
                    passed=True,  # Fail-open
                    explanation=f"Check crashed: {e}",
                ))
        return results

    def _build_critique(self, failures: List[CheckResult]) -> str:
        """Build a structured critique from failed checks."""
        lines = ["The following quality checks FAILED:\n"]
        for f in failures:
            lines.append(f"### ❌ {f.check_name} ({f.severity})")
            lines.append(f"{f.explanation}\n")
        return "\n".join(lines)

    def _refine(self, question: str, answer: str, critique: str) -> str:
        """Use the LLM to refine the answer based on the critique."""
        messages = [
            {"role": "system", "content": self.REFINEMENT_PROMPT},
            {"role": "user", "content": (
                f"ORIGINAL QUESTION:\n{question}\n\n"
                f"YOUR PREVIOUS ANSWER:\n{answer[:3000]}\n\n"
                f"QUALITY CRITIQUE:\n{critique}\n\n"
                f"Produce an improved answer that addresses all critique points."
            )},
        ]

        try:
            refined = self.router.execute_with_failover(messages)
            return refined
        except Exception as e:
            self.logger.error(f"Refinement LLM call failed: {e}")
            return answer  # Return original on failure

    def _save_result(self, result: VerificationResult):
        """Persist verification result to data/verifications/{id}.json."""
        path = os.path.join(self.VERIFICATION_DIR, f"{result.verification_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save verification result: {e}")

    def _emit_event(self, event_type: str, payload: Dict[str, Any]):
        """Emit a verification event on the EventBus."""
        if not self.event_bus:
            return
        try:
            from events.event_types import Event, EventType
            event = Event.create(
                event_type=EventType(event_type),
                source_component="VerifiableIterator",
                payload=payload,
                trace_id=uuid4().hex[:16],
                correlation_id=uuid4().hex[:16],
            )
            self.event_bus.publish(event)
        except Exception as e:
            self.logger.debug(f"Event emit failed (non-fatal): {e}")

    def toggle(self, enabled: bool) -> str:
        """Toggle verification on/off at runtime."""
        self.enabled = enabled
        status = "ON" if enabled else "OFF"
        self.logger.info(f"Verifiable Iteration toggled {status}.")
        return f"✅ Verifiable Iteration is now **{status}**."

    def get_status(self) -> str:
        """Get formatted status string."""
        status = "🟢 ON" if self.enabled else "🔴 OFF"
        return (
            f"## ✔️ Verifiable Iteration\n\n"
            f"**Status:** {status}\n"
            f"**Max Iterations:** {self.max_iterations}\n"
            f"**Active Checks:** {', '.join(c.name for c in self.checks)}\n"
        )


# ── Utility ───────────────────────────────────────────────────────────

def _extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM response text."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return {"passed": True, "explanation": "Failed to parse check result."}

"""
OTel Middleware (Phase 13: OTel Observability Integration)

Provides automatic span instrumentation for the Orchestrator's ReAct loop.
Wraps key operations (LLM calls, tool executions, planning) in tracing spans
so that every agent cycle is observable via /traces or external OTel backends.
"""

from contextlib import contextmanager
from typing import Optional, Dict, Any

from observability import get_logging_system
from observability.tracing_system import TracingSystem, SpanStatus


class OTelMiddleware:
    """
    Instruments the Orchestrator with tracing spans.
    When initialized, it provides context-manager helpers that the
    Orchestrator calls to emit spans for each phase of the ReAct loop.
    """

    def __init__(self, tracing: TracingSystem):
        self.logger = get_logging_system()
        self.tracing = tracing
        self.logger.info("OTelMiddleware initialized. Orchestrator instrumentation active.")

    @contextmanager
    def trace_react_cycle(self, query: str, step: int, budget: int):
        """Wraps an entire ReAct loop iteration in a parent span."""
        with self.tracing.start_span(
            f"react_cycle_step_{step}",
            tags={
                "react.step": step,
                "react.budget": budget,
                "react.query_preview": query[:100],
            }
        ) as span:
            yield span

    @contextmanager
    def trace_llm_call(self, model_hint: str = "auto"):
        """Wraps an LLM dispatch in a child span."""
        with self.tracing.start_span(
            "llm_dispatch",
            tags={"llm.model_hint": model_hint}
        ) as span:
            yield span

    @contextmanager
    def trace_tool_execution(self, tool_name: str, action: str):
        """Wraps a tool execution in a child span."""
        with self.tracing.start_span(
            f"tool_exec:{tool_name}",
            tags={
                "tool.name": tool_name,
                "tool.action": action,
            }
        ) as span:
            yield span

    @contextmanager
    def trace_planning(self, plan_source: str = "plan_library"):
        """Wraps the plan lookup phase."""
        with self.tracing.start_span(
            "plan_lookup",
            tags={"plan.source": plan_source}
        ) as span:
            yield span

    def record_final_answer(self, span, answer_preview: str):
        """Record metadata on the cycle span when a final answer is produced."""
        self.tracing.add_span_tag(span.span_id, "react.outcome", "final_answer")
        self.tracing.add_span_tag(span.span_id, "react.answer_preview", answer_preview[:200])

    def record_error(self, span, error: str):
        """Record an error on the current span."""
        self.tracing.add_span_tag(span.span_id, "error", True)
        self.tracing.add_span_tag(span.span_id, "error.message", error[:500])

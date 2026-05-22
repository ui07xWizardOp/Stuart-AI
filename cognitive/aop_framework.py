"""
Agent-Oriented Programming (AOP) Framework (Feature #8: Advanced Orchestration)

This module provides decorators and a runtime interpreter that seamlessly mix
deterministic Python execution with LLM-driven fuzzy logic. It allows developers
to define Python functions that defer their logic to the agentic engine.

Decorators:
- @agent_task: Converts a function signature and docstring into an LLM prompt.
- @supervisor_task: Uses the SupervisorAgent to decompose and solve the function.
- @verifiable_task: Automatically applies VerifiableIteration to the output.
"""

import inspect
import functools
import json
from typing import Callable, Any, Dict, Optional
from dataclasses import dataclass

from observability import get_logging_system
from core.orchestrator import Orchestrator
from core.supervisor import SupervisorAgent
from cognitive.verifiable_iteration import VerifiableIterator


class AOPContext:
    """
    Global context holder for the AOP framework.
    Must be initialized during startup to provide the decorators with
    access to the orchestrator components.
    """
    orchestrator: Optional[Orchestrator] = None
    supervisor: Optional[SupervisorAgent] = None
    verifier: Optional[VerifiableIterator] = None
    logger = get_logging_system()

    @classmethod
    def configure(
        cls,
        orchestrator: Orchestrator,
        supervisor: Optional[SupervisorAgent] = None,
        verifier: Optional[VerifiableIterator] = None,
    ):
        cls.orchestrator = orchestrator
        cls.supervisor = supervisor
        cls.verifier = verifier
        cls.logger.info("AOP Context configured successfully.")


def _build_task_prompt(func: Callable, args: tuple, kwargs: dict) -> str:
    """Extract docstring and arguments to build an LLM prompt."""
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()
    
    docstring = inspect.getdoc(func) or "No description provided."
    func_name = func.__name__
    
    # Format arguments
    arg_lines = []
    for name, value in bound_args.arguments.items():
        arg_lines.append(f"  - {name}: {value}")
    arg_str = "\n".join(arg_lines)
    
    prompt = (
        f"You are executing an Agent-Oriented Programming (AOP) function.\n"
        f"Function Name: {func_name}\n"
        f"Description: {docstring}\n\n"
        f"Arguments provided:\n{arg_str}\n\n"
        f"Please perform this task and return ONLY the final result. "
        f"Format the output appropriately based on the description."
    )
    return prompt


def agent_task(model_tier: str = "default"):
    """
    Decorator that intercepts function calls and routes them to the main Orchestrator.
    Useful for simple fuzzy tasks that don't need decomposition.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if AOPContext.orchestrator is None:
                raise RuntimeError("AOPContext not configured. Call AOPContext.configure() first.")
                
            prompt = _build_task_prompt(func, args, kwargs)
            AOPContext.logger.info(f"AOP @agent_task triggered: {func.__name__}")
            
            # For a pure AOP task, we could bypass the ReAct loop and just do a direct LLM call
            # if we wanted, but the user requested mixing deterministic with agentic logic,
            # so we use the full orchestrator if tools are needed, or just router.
            
            # Using orchestrator process (this might trigger a full ReAct loop in background)
            # For a synchronous function return, we need to wait for it.
            # Assuming orchestrator.process_user_message is sync or we have a sync wrapper.
            # If the application is fully async, this would need to be an async def.
            # We'll use the router directly for a synchronous answer if no tools are strictly needed,
            # but to be powerful we'll use process_user_message (which currently is synchronous in our design).
            
            response = AOPContext.orchestrator.process_user_message(prompt, source="aop")
            return response

        return wrapper
    return decorator


def supervisor_task(max_depth: int = 1):
    """
    Decorator that routes the task to the SupervisorAgent for decomposition
    and parallel worker execution.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if AOPContext.supervisor is None:
                raise RuntimeError("SupervisorAgent not configured in AOPContext.")
                
            prompt = _build_task_prompt(func, args, kwargs)
            AOPContext.logger.info(f"AOP @supervisor_task triggered: {func.__name__}")
            
            result = AOPContext.supervisor.delegate(goal=prompt, depth=0)
            return result.synthesized_output
            
        return wrapper
    return decorator


def verifiable_task(max_iterations: int = 2):
    """
    Decorator that applies Verifiable Iteration to the output of an agentic task.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if AOPContext.verifier is None:
                raise RuntimeError("VerifiableIterator not configured in AOPContext.")
                
            # First get the initial answer (using standard orchestrator)
            prompt = _build_task_prompt(func, args, kwargs)
            AOPContext.logger.info(f"AOP @verifiable_task triggered: {func.__name__}")
            
            initial_answer = AOPContext.orchestrator.process_user_message(prompt, source="aop")
            
            # Now verify and refine it
            result = AOPContext.verifier.verify_and_refine(
                question=prompt,
                answer=initial_answer,
                context={"source": "aop"}
            )
            
            return result.final_answer
            
        return wrapper
    return decorator

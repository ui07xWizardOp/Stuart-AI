"""
Agent Orchestrator

Central reasoning engine that interprets commands and coordinates execution.
Implements the observe-orient-decide-act (OODA) loop pattern for LLM-based reasoning.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from uuid import uuid4
import re

from observability import get_logging_system, get_tracing_system, get_correlation_id
from events import get_event_bus, EventType, Event


class Intent(str, Enum):
    """
    User intent types classified from natural language commands
    
    - TASK: Execute immediate multi-step task
    - WORKFLOW: Create or modify automation workflow
    - REMEMBER: Store information in long-term memory
    - SEARCH: Query knowledge base
    - RUN: Execute existing workflow
    - STATUS: Query execution status
    """
    TASK = "task"
    WORKFLOW = "workflow"
    REMEMBER = "remember"
    SEARCH = "search"
    RUN = "run"
    STATUS = "status"


@dataclass
class IntentClassificationResult:
    """
    Result of intent classification with confidence and alternatives
    
    Contains the primary classified intent along with confidence score,
    reasoning explanation, and alternative intents that were considered.
    """
    intent: Intent
    confidence: float  # 0.0 to 1.0
    reasoning: str  # Explanation of why this intent was chosen
    alternatives: List[Tuple[Intent, float]] = field(default_factory=list)  # Other possible intents with scores
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/persistence"""
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "alternatives": [(intent.value, score) for intent, score in self.alternatives]
        }


@dataclass
class ReasoningState:
    """
    Current state of the reasoning loop
    
    Maintains context for a single reasoning iteration including
    current step, accumulated results, and execution metadata.
    """
    task_id: str
    iteration: int
    intent: Optional[Intent] = None
    current_step: str = "classify"
    plan: Optional[Dict[str, Any]] = None
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence"""
        return {
            "task_id": self.task_id,
            "iteration": self.iteration,
            "intent": self.intent.value if self.intent else None,
            "current_step": self.current_step,
            "plan": self.plan,
            "tool_results": self.tool_results,
            "observations": self.observations,
            "context": self.context,
            "metadata": self.metadata
        }


@dataclass
class ReasoningAction:
    """
    Action to take based on reasoning step
    
    Represents the decision made by the orchestrator about
    what to do next in the reasoning loop.
    """
    action_type: str  # "plan", "execute", "observe", "reflect", "complete"
    action_data: Dict[str, Any] = field(default_factory=dict)
    should_continue: bool = True
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ReflectionResult:
    """
    Result of reflection step analysis
    
    Contains insights from analyzing previous reasoning iterations
    and recommendations for plan adjustments.
    """
    reflection_id: str
    timestamp: datetime
    errors_detected: List[str] = field(default_factory=list)
    adjustments_needed: List[str] = field(default_factory=list)
    plan_modifications: Optional[Dict[str, Any]] = None
    confidence_score: float = 1.0
    reasoning: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class AgentOrchestrator:
    """
    Central reasoning engine with intent classification
    
    The AgentOrchestrator coordinates the Planner, Executor, and Observer
    components following the OODA loop pattern. It classifies user intent,
    manages reasoning loop state, triggers reflection steps, and emits
    events for task lifecycle.
    
    Responsibilities:
    - Intent classification from natural language commands
    - Coordination of Planner, Executor, and Observer components
    - Reasoning loop state management
    - Reflection step execution and plan adjustment
    - Event emission for task lifecycle
    """
    
    def __init__(
        self,
        enable_reflection: bool = True,
        reflection_trigger_on_failure: bool = True,
        reflection_trigger_interval: Optional[int] = None
    ):
        """
        Initialize Agent Orchestrator
        
        Args:
            enable_reflection: Whether to enable reflection steps
            reflection_trigger_on_failure: Trigger reflection after failures
            reflection_trigger_interval: Trigger reflection every N iterations (None = disabled)
        """
        self.logger = get_logging_system()
        self.tracer = get_tracing_system()
        self.event_bus = get_event_bus()
        
        self.enable_reflection = enable_reflection
        self.reflection_trigger_on_failure = reflection_trigger_on_failure
        self.reflection_trigger_interval = reflection_trigger_interval
        
        # Component placeholders - will be injected by Agent Runtime
        self.planner = None
        self.executor = None
        self.observer = None
        self.context_manager = None
        
        self.logger.info(
            "AgentOrchestrator initialized",
            extra={
                "enable_reflection": enable_reflection,
                "reflection_trigger_on_failure": reflection_trigger_on_failure,
                "reflection_trigger_interval": reflection_trigger_interval
            }
        )
    
    def classify_intent(self, command: str) -> IntentClassificationResult:
        """
        Classify user command into intent type with confidence scoring
        
        Analyzes the natural language command to determine the user's
        primary intent using LLM-based classification with fallback to
        keyword-based classification. Returns confidence score and
        alternative intents.
        
        Args:
            command: Natural language command from user
        
        Returns:
            IntentClassificationResult: Classification with confidence and alternatives
        
        Examples:
            >>> result = orchestrator.classify_intent("Create a report from sales data")
            >>> result.intent
            Intent.TASK
            >>> result.confidence
            0.95
        """
        with self.tracer.start_span("classify_intent") as span:
            span.set_attribute("command_length", len(command))
            
            self.logger.debug(
                "Classifying intent",
                extra={"command": command[:100]}  # Log first 100 chars
            )
            
            try:
                # Try LLM-based classification first
                result = self._classify_intent_llm(command)
                
                # If confidence is too low, fall back to keyword-based
                if result.confidence < 0.5:
                    self.logger.info(
                        "LLM classification confidence too low, falling back to keyword-based",
                        extra={"llm_confidence": result.confidence}
                    )
                    result = self._classify_intent_keyword(command)
                
            except Exception as e:
                # Fall back to keyword-based classification on any error
                self.logger.warning(
                    "LLM classification failed, falling back to keyword-based",
                    extra={"error": str(e)}
                )
                result = self._classify_intent_keyword(command)
            
            span.set_attribute("intent", result.intent.value)
            span.set_attribute("confidence", result.confidence)
            
            self.logger.info(
                "Intent classified",
                extra={
                    "command": command[:100],
                    "intent": result.intent.value,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning
                }
            )
            
            return result
    
    def _classify_intent_llm(self, command: str) -> IntentClassificationResult:
        """
        Classify intent using LLM-based approach
        
        This is a placeholder implementation until Model Router (Task 9)
        and Prompt Manager (Task 10) are implemented. Currently uses
        a heuristic-based approach that's more sophisticated than simple
        keyword matching.
        
        Args:
            command: Natural language command from user
        
        Returns:
            IntentClassificationResult: Classification result
        """
        # TODO: Replace with actual LLM call once Model Router is implemented
        # For now, use enhanced heuristic-based classification
        
        command_lower = command.lower()
        
        # Score each intent based on multiple signals
        scores = {
            Intent.WORKFLOW: self._score_workflow_intent(command_lower),
            Intent.REMEMBER: self._score_remember_intent(command_lower),
            Intent.SEARCH: self._score_search_intent(command_lower),
            Intent.RUN: self._score_run_intent(command_lower),
            Intent.STATUS: self._score_status_intent(command_lower),
            Intent.TASK: self._score_task_intent(command_lower)
        }
        
        # Sort by score
        sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Get primary intent and confidence
        primary_intent, primary_score = sorted_intents[0]
        
        # Normalize confidence (scores are 0-100, normalize to 0-1)
        confidence = min(primary_score / 100.0, 1.0)
        
        # Get alternatives (top 3 excluding primary)
        alternatives = [(intent, score / 100.0) for intent, score in sorted_intents[1:4]]
        
        # Generate reasoning
        reasoning = self._generate_reasoning(command_lower, primary_intent, primary_score)
        
        return IntentClassificationResult(
            intent=primary_intent,
            confidence=confidence,
            reasoning=reasoning,
            alternatives=alternatives
        )
    
    def _classify_intent_keyword(self, command: str) -> IntentClassificationResult:
        """
        Classify intent using keyword-based approach (fallback)
        
        Simple keyword matching with confidence based on keyword strength.
        
        Args:
            command: Natural language command from user
        
        Returns:
            IntentClassificationResult: Classification result
        """
        command_lower = command.lower()
        
        # Strong keyword matches (high confidence)
        workflow_keywords = ["create workflow", "automate", "schedule", "trigger when"]
        remember_keywords = ["remember", "store", "save", "note that"]
        search_keywords = ["search", "find", "look up", "query"]
        run_keywords = ["run", "execute workflow", "start workflow"]
        status_keywords = ["status", "check", "show progress", "what's happening"]
        
        # Check for strong matches
        if any(keyword in command_lower for keyword in workflow_keywords):
            intent = Intent.WORKFLOW
            confidence = 0.85
            reasoning = "Strong workflow keywords detected"
        elif any(keyword in command_lower for keyword in remember_keywords):
            intent = Intent.REMEMBER
            confidence = 0.85
            reasoning = "Strong memory keywords detected"
        elif any(keyword in command_lower for keyword in search_keywords):
            intent = Intent.SEARCH
            confidence = 0.85
            reasoning = "Strong search keywords detected"
        elif any(keyword in command_lower for keyword in run_keywords):
            intent = Intent.RUN
            confidence = 0.85
            reasoning = "Strong execution keywords detected"
        elif any(keyword in command_lower for keyword in status_keywords):
            intent = Intent.STATUS
            confidence = 0.85
            reasoning = "Strong status keywords detected"
        else:
            # Default to TASK with lower confidence
            intent = Intent.TASK
            confidence = 0.60
            reasoning = "No specific keywords detected, defaulting to task"
        
        # Generate alternatives based on partial matches
        alternatives = []
        for alt_intent in Intent:
            if alt_intent != intent:
                alternatives.append((alt_intent, 0.2))
        
        return IntentClassificationResult(
            intent=intent,
            confidence=confidence,
            reasoning=reasoning,
            alternatives=alternatives[:3]
        )
    
    def _score_workflow_intent(self, command: str) -> float:
        """Score likelihood of WORKFLOW intent"""
        score = 0.0
        
        # Strong indicators
        if re.search(r'\b(create|make|build|setup)\s+(a\s+)?workflow\b', command):
            score += 50
        if 'automate' in command:
            score += 65  # Strong indicator for workflow - increased to beat task verbs
        if 'schedule' in command or 'trigger' in command:
            score += 35
        
        # Moderate indicators
        if 'every' in command and any(word in command for word in ['day', 'week', 'hour', 'monday', 'morning']):
            score += 30
        if 'when' in command and 'then' in command:
            score += 20
        if 'daily' in command or 'weekly' in command or 'monthly' in command:
            score += 25
        
        # Weak indicators
        if 'recurring' in command or 'repeat' in command:
            score += 15
        
        return score
    
    def _score_remember_intent(self, command: str) -> float:
        """Score likelihood of REMEMBER intent"""
        score = 0.0
        
        # Strong indicators
        if command.startswith('remember'):
            score += 50
        if 'note that' in command or 'keep in mind' in command:
            score += 45
        if 'store' in command or 'save' in command:
            score += 40
        
        # Moderate indicators
        if 'prefer' in command or 'like' in command:
            score += 25
        if 'always' in command or 'never' in command:
            score += 20
        
        # Weak indicators
        if 'my' in command or 'i' in command:
            score += 10
        
        return score
    
    def _score_search_intent(self, command: str) -> float:
        """Score likelihood of SEARCH intent"""
        score = 0.0
        
        # Strong indicators
        if command.startswith('search'):
            score += 50
        if 'find' in command or 'look up' in command:
            score += 45
        if 'query' in command:
            score += 40
        
        # Moderate indicators
        if 'what is' in command or 'what are' in command:
            score += 30
        if 'how to' in command or 'how do' in command:
            score += 25
        if 'information about' in command or 'details on' in command:
            score += 25
        
        # Weak indicators
        if '?' in command:
            score += 15
        
        return score
    
    def _score_run_intent(self, command: str) -> float:
        """Score likelihood of RUN intent"""
        score = 0.0
        
        # Strong indicators
        if re.search(r'\b(run|execute|start)\s+(the\s+)?workflow\b', command):
            score += 50
        if 'execute' in command and 'workflow' in command:
            score += 45
        
        # Moderate indicators
        if command.startswith('run'):
            score += 30
        if 'start' in command:
            score += 25
        
        # Weak indicators
        if 'workflow' in command:
            score += 15
        
        return score
    
    def _score_status_intent(self, command: str) -> float:
        """Score likelihood of STATUS intent"""
        score = 0.0
        
        # Strong indicators
        if 'status' in command:
            score += 50
        if "what's happening" in command or 'what is happening' in command:
            score += 45
        if 'show progress' in command or 'check progress' in command:
            score += 40
        
        # Moderate indicators
        if command.startswith('check'):
            score += 30
        if 'how is' in command or "how's" in command:
            score += 25
        
        # Weak indicators
        if 'progress' in command or 'state' in command:
            score += 15
        
        return score
    
    def _score_task_intent(self, command: str) -> float:
        """Score likelihood of TASK intent"""
        score = 0.0
        
        # Task is the default, so base score is moderate
        score = 30
        
        # Strong indicators
        if any(verb in command for verb in ['create', 'generate', 'analyze', 'process', 'build', 'make']):
            score += 30
        if 'report' in command or 'summary' in command:
            score += 25
        
        # Moderate indicators
        if 'data' in command or 'file' in command:
            score += 15
        if 'from' in command and 'to' in command:
            score += 10
        
        return score
    
    def _generate_reasoning(self, command: str, intent: Intent, score: float) -> str:
        """Generate human-readable reasoning for classification"""
        reasons = []
        
        if intent == Intent.WORKFLOW:
            if 'workflow' in command:
                reasons.append("explicit workflow mention")
            if 'automate' in command:
                reasons.append("automation request")
            if 'schedule' in command:
                reasons.append("scheduling requirement")
        
        elif intent == Intent.REMEMBER:
            if command.startswith('remember'):
                reasons.append("direct memory command")
            if 'prefer' in command:
                reasons.append("preference statement")
            if 'note that' in command:
                reasons.append("explicit note-taking")
        
        elif intent == Intent.SEARCH:
            if command.startswith('search'):
                reasons.append("direct search command")
            if 'find' in command:
                reasons.append("information retrieval request")
            if '?' in command:
                reasons.append("question format")
        
        elif intent == Intent.RUN:
            if 'run' in command and 'workflow' in command:
                reasons.append("explicit workflow execution")
            if 'execute' in command:
                reasons.append("execution command")
        
        elif intent == Intent.STATUS:
            if 'status' in command:
                reasons.append("explicit status query")
            if 'progress' in command:
                reasons.append("progress check")
        
        elif intent == Intent.TASK:
            if any(verb in command for verb in ['create', 'generate', 'analyze']):
                reasons.append("action verb detected")
            if not reasons:
                reasons.append("general task execution pattern")
        
        if reasons:
            return f"Classified as {intent.value} based on: {', '.join(reasons)}"
        else:
            return f"Classified as {intent.value} with score {score:.1f}"
    
    def execute_reasoning_step(self, state: ReasoningState) -> ReasoningAction:
        """
        Execute one iteration of the reasoning loop
        
        Coordinates the Planner, Executor, and Observer based on the
        current reasoning state. Determines the next action to take
        in the OODA loop.
        
        This method implements the OODA loop pattern:
        - CLASSIFY: Intent classification (handled before this method)
        - PLAN: Delegate to Planner component to create task plan
        - EXECUTE: Delegate to Executor component to run plan steps
        - OBSERVE: Delegate to Observer component to collect results
        - REASON: Determine next action based on observations
        
        Args:
            state: Current reasoning state
        
        Returns:
            ReasoningAction: Action to take next
        
        Raises:
            ValueError: If state is invalid or components not initialized
        """
        with self.tracer.start_span("execute_reasoning_step") as span:
            span.set_attribute("task_id", state.task_id)
            span.set_attribute("iteration", state.iteration)
            span.set_attribute("current_step", state.current_step)
            
            self.logger.info(
                "Executing reasoning step",
                extra={
                    "task_id": state.task_id,
                    "iteration": state.iteration,
                    "current_step": state.current_step,
                    "intent": state.intent.value if state.intent else None
                }
            )
            
            try:
                # Validate state
                if not state.task_id:
                    raise ValueError("ReasoningState must have a task_id")
                if not state.current_step:
                    raise ValueError("ReasoningState must have a current_step")
                
                # Route to appropriate handler based on current step
                if state.current_step == "classify":
                    action = self._handle_classify_step(state)
                elif state.current_step == "plan":
                    action = self._handle_plan_step(state)
                elif state.current_step == "execute":
                    action = self._handle_execute_step(state)
                elif state.current_step == "observe":
                    action = self._handle_observe_step(state)
                elif state.current_step == "reason":
                    action = self._handle_reason_step(state)
                else:
                    # Unknown step - log warning and complete
                    self.logger.warning(
                        "Unknown reasoning step, completing task",
                        extra={
                            "task_id": state.task_id,
                            "current_step": state.current_step
                        }
                    )
                    action = ReasoningAction(
                        action_type="complete",
                        action_data={"error": f"Unknown step: {state.current_step}"},
                        should_continue=False,
                        reason=f"Unknown reasoning step: {state.current_step}"
                    )
                
                # Update state with action result
                state.metadata["last_action"] = action.action_type
                state.metadata["last_action_reason"] = action.reason
                
                span.set_attribute("action_type", action.action_type)
                span.set_attribute("should_continue", action.should_continue)
                
                self.logger.info(
                    "Reasoning step completed",
                    extra={
                        "task_id": state.task_id,
                        "iteration": state.iteration,
                        "action_type": action.action_type,
                        "should_continue": action.should_continue,
                        "reason": action.reason
                    }
                )
                
                return action
                
            except Exception as e:
                # Handle errors gracefully
                self.logger.error(
                    "Error executing reasoning step",
                    extra={
                        "task_id": state.task_id,
                        "iteration": state.iteration,
                        "current_step": state.current_step,
                        "error": str(e)
                    },
                    exc_info=True
                )
                
                span.set_attribute("error", True)
                span.set_attribute("error_message", str(e))
                
                # Return error action
                return ReasoningAction(
                    action_type="complete",
                    action_data={"error": str(e), "step": state.current_step},
                    should_continue=False,
                    reason=f"Error in {state.current_step} step: {str(e)}"
                )
    
    def _handle_classify_step(self, state: ReasoningState) -> ReasoningAction:
        """
        Handle classify step - intent classification already done, move to planning
        
        Args:
            state: Current reasoning state
        
        Returns:
            ReasoningAction to proceed to planning
        """
        self.logger.debug(
            "Handling classify step",
            extra={
                "task_id": state.task_id,
                "intent": state.intent.value if state.intent else None
            }
        )
        
        # Validate intent was classified
        if not state.intent:
            self.logger.warning(
                "No intent classified, defaulting to TASK",
                extra={"task_id": state.task_id}
            )
            state.intent = Intent.TASK
        
        # Move to planning step
        return ReasoningAction(
            action_type="plan",
            action_data={
                "intent": state.intent.value,
                "command": state.context.get("command", "")
            },
            should_continue=True,
            reason=f"Intent classified as {state.intent.value}, proceeding to planning"
        )
    
    def _handle_plan_step(self, state: ReasoningState) -> ReasoningAction:
        """
        Handle plan step - delegate to Planner component
        
        Args:
            state: Current reasoning state
        
        Returns:
            ReasoningAction to proceed to execution
        """
        self.logger.debug(
            "Handling plan step",
            extra={
                "task_id": state.task_id,
                "intent": state.intent.value if state.intent else None
            }
        )
        
        try:
            # Check if Planner component is available
            if hasattr(self, 'planner') and self.planner is not None:
                # Delegate to Planner component (will be implemented in Task 7)
                self.logger.debug(
                    "Delegating to Planner component",
                    extra={"task_id": state.task_id}
                )
                
                # Placeholder for actual planner call
                # plan = self.planner.create_plan(
                #     goal=state.context.get("command", ""),
                #     context=state.context
                # )
                
                # For now, create a placeholder plan
                plan = {
                    "steps": [],
                    "goal": state.context.get("command", ""),
                    "created_at": datetime.utcnow().isoformat()
                }
                
                state.plan = plan
                
                # Emit plan created event
                self.emit_task_event(
                    event_type=EventType.PLAN_CREATED,
                    task_id=state.task_id,
                    payload={
                        "intent": state.intent.value if state.intent else None,
                        "plan_steps": len(plan.get("steps", [])),
                        "iteration": state.iteration,
                        "goal": plan.get("goal", "")
                    }
                )
                
            else:
                # Planner not yet implemented - create placeholder plan
                self.logger.debug(
                    "Planner component not available, using placeholder",
                    extra={"task_id": state.task_id}
                )
                
                state.plan = {
                    "steps": [],
                    "goal": state.context.get("command", ""),
                    "placeholder": True,
                    "created_at": datetime.utcnow().isoformat()
                }
            
            # Move to execution step
            return ReasoningAction(
                action_type="execute",
                action_data={
                    "plan": state.plan,
                    "step_count": len(state.plan.get("steps", []))
                },
                should_continue=True,
                reason="Plan created, proceeding to execution"
            )
            
        except Exception as e:
            self.logger.error(
                "Error in plan step",
                extra={
                    "task_id": state.task_id,
                    "error": str(e)
                },
                exc_info=True
            )
            
            # Return error action
            return ReasoningAction(
                action_type="complete",
                action_data={"error": str(e), "step": "plan"},
                should_continue=False,
                reason=f"Planning failed: {str(e)}"
            )
    
    def _handle_execute_step(self, state: ReasoningState) -> ReasoningAction:
        """
        Handle execute step - delegate to Executor component
        
        Args:
            state: Current reasoning state
        
        Returns:
            ReasoningAction to proceed to observation
        """
        self.logger.debug(
            "Handling execute step",
            extra={
                "task_id": state.task_id,
                "plan_steps": len(state.plan.get("steps", [])) if state.plan else 0
            }
        )
        
        try:
            # Validate plan exists
            if not state.plan:
                self.logger.warning(
                    "No plan available for execution",
                    extra={"task_id": state.task_id}
                )
                return ReasoningAction(
                    action_type="complete",
                    action_data={"error": "No plan available"},
                    should_continue=False,
                    reason="Cannot execute without a plan"
                )
            
            # Emit execution started event
            self.emit_task_event(
                event_type=EventType.EXECUTION_STARTED,
                task_id=state.task_id,
                payload={
                    "plan_steps": len(state.plan.get("steps", [])),
                    "iteration": state.iteration,
                    "goal": state.plan.get("goal", "")
                }
            )
            
            # Check if Executor component is available
            if hasattr(self, 'executor') and self.executor is not None:
                # Delegate to Executor component (will be implemented in Task 8)
                self.logger.debug(
                    "Delegating to Executor component",
                    extra={"task_id": state.task_id}
                )
                
                # Placeholder for actual executor call
                # execution_result = self.executor.execute_plan(
                #     plan=state.plan,
                #     context=state.context
                # )
                
                # For now, create placeholder results
                execution_results = []
                
            else:
                # Executor not yet implemented - create placeholder results
                self.logger.debug(
                    "Executor component not available, using placeholder",
                    extra={"task_id": state.task_id}
                )
                
                execution_results = []
            
            # Store results in state
            state.tool_results = execution_results
            
            # Move to observation step
            return ReasoningAction(
                action_type="observe",
                action_data={
                    "results": execution_results,
                    "result_count": len(execution_results)
                },
                should_continue=True,
                reason="Execution completed, proceeding to observation"
            )
            
        except Exception as e:
            self.logger.error(
                "Error in execute step",
                extra={
                    "task_id": state.task_id,
                    "error": str(e)
                },
                exc_info=True
            )
            
            # Emit execution failed event
            self.emit_task_event(
                event_type=EventType.TASK_FAILED,
                task_id=state.task_id,
                payload={
                    "step": "execution_failed",
                    "error": str(e)
                }
            )
            
            # Return error action
            return ReasoningAction(
                action_type="complete",
                action_data={"error": str(e), "step": "execute"},
                should_continue=False,
                reason=f"Execution failed: {str(e)}"
            )
    
    def _handle_observe_step(self, state: ReasoningState) -> ReasoningAction:
        """
        Handle observe step - delegate to Observer component
        
        Args:
            state: Current reasoning state
        
        Returns:
            ReasoningAction to proceed to reasoning or completion
        """
        self.logger.debug(
            "Handling observe step",
            extra={
                "task_id": state.task_id,
                "result_count": len(state.tool_results)
            }
        )
        
        try:
            # Check if Observer component is available
            if hasattr(self, 'observer') and self.observer is not None:
                # Delegate to Observer component (will be implemented in Task 8)
                self.logger.debug(
                    "Delegating to Observer component",
                    extra={"task_id": state.task_id}
                )
                
                # Placeholder for actual observer call
                # observation_result = self.observer.collect_results(
                #     execution_results=state.tool_results
                # )
                
                # For now, create placeholder observations
                observations = [
                    f"Observed {len(state.tool_results)} tool results"
                ]
                
            else:
                # Observer not yet implemented - create placeholder observations
                self.logger.debug(
                    "Observer component not available, using placeholder",
                    extra={"task_id": state.task_id}
                )
                
                observations = [
                    f"Placeholder observation: {len(state.tool_results)} results"
                ]
            
            # Store observations in state
            state.observations.extend(observations)
            
            # Emit observation completed event
            self.emit_task_event(
                event_type=EventType.OBSERVATION_COMPLETED,
                task_id=state.task_id,
                payload={
                    "observation_count": len(observations),
                    "total_observations": len(state.observations),
                    "iteration": state.iteration,
                    "result_count": len(state.tool_results)
                }
            )
            
            # Move to reasoning step to determine next action
            return ReasoningAction(
                action_type="reason",
                action_data={
                    "observations": observations,
                    "observation_count": len(observations)
                },
                should_continue=True,
                reason="Observations collected, proceeding to reasoning"
            )
            
        except Exception as e:
            self.logger.error(
                "Error in observe step",
                extra={
                    "task_id": state.task_id,
                    "error": str(e)
                },
                exc_info=True
            )
            
            # Return error action
            return ReasoningAction(
                action_type="complete",
                action_data={"error": str(e), "step": "observe"},
                should_continue=False,
                reason=f"Observation failed: {str(e)}"
            )
    
    def _handle_reason_step(self, state: ReasoningState) -> ReasoningAction:
        """
        Handle reason step - determine if we should continue or complete
        
        Args:
            state: Current reasoning state
        
        Returns:
            ReasoningAction to continue loop or complete
        """
        self.logger.debug(
            "Handling reason step",
            extra={
                "task_id": state.task_id,
                "iteration": state.iteration
            }
        )
        
        try:
            # Check if reflection should be triggered
            if self._should_trigger_reflection(state):
                self.logger.info(
                    "Triggering reflection",
                    extra={
                        "task_id": state.task_id,
                        "iteration": state.iteration
                    }
                )
                
                # Trigger reflection (implemented in Task 6.4)
                reflection = self.trigger_reflection(state)
                
                # Store reflection in state
                state.metadata["last_reflection"] = reflection.to_dict()
                
                # If reflection suggests adjustments, continue with new plan
                if reflection.adjustments_needed:
                    return ReasoningAction(
                        action_type="plan",
                        action_data={
                            "reflection": reflection.to_dict(),
                            "adjustments": reflection.adjustments_needed
                        },
                        should_continue=True,
                        reason="Reflection suggests adjustments, replanning"
                    )
            
            # Determine if we should continue reasoning
            should_continue = self._should_continue_reasoning(state)
            
            if should_continue:
                # Continue with another iteration
                self.logger.debug(
                    "Continuing reasoning loop",
                    extra={
                        "task_id": state.task_id,
                        "iteration": state.iteration
                    }
                )
                
                return ReasoningAction(
                    action_type="plan",
                    action_data={
                        "observations": state.observations,
                        "continue_reason": "More work needed"
                    },
                    should_continue=True,
                    reason="Task not complete, continuing reasoning loop"
                )
            else:
                # Task is complete
                self.logger.info(
                    "Task completed",
                    extra={
                        "task_id": state.task_id,
                        "iteration": state.iteration,
                        "total_observations": len(state.observations)
                    }
                )
                
                # Emit task completed event
                self.emit_task_event(
                    event_type=EventType.TASK_COMPLETED,
                    task_id=state.task_id,
                    payload={
                        "iterations": state.iteration,
                        "observations": len(state.observations),
                        "tool_results": len(state.tool_results)
                    }
                )
                
                return ReasoningAction(
                    action_type="complete",
                    action_data={
                        "final_result": state.observations,
                        "iterations": state.iteration
                    },
                    should_continue=False,
                    reason="Task completed successfully"
                )
            
        except Exception as e:
            self.logger.error(
                "Error in reason step",
                extra={
                    "task_id": state.task_id,
                    "error": str(e)
                },
                exc_info=True
            )
            
            # Return error action
            return ReasoningAction(
                action_type="complete",
                action_data={"error": str(e), "step": "reason"},
                should_continue=False,
                reason=f"Reasoning failed: {str(e)}"
            )
    
    def trigger_reflection(self, state: ReasoningState) -> ReflectionResult:
            """
            Analyze previous reasoning and adjust plan if needed

            Performs introspection on the reasoning process to detect errors,
            identify inefficiencies, and recommend plan adjustments using
            heuristic-based analysis.

            Args:
                state: Current reasoning state

            Returns:
                ReflectionResult: Analysis and recommendations
            """
            with self.tracer.start_span("trigger_reflection") as span:
                span.set_attribute("task_id", state.task_id)
                span.set_attribute("iteration", state.iteration)

                self.logger.info(
                    "Triggering reflection step",
                    extra={
                        "task_id": state.task_id,
                        "iteration": state.iteration
                    }
                )

                reflection_id = str(uuid4())
                timestamp = datetime.utcnow()

                # Analyze reasoning state with sophisticated heuristics
                errors_detected = []
                adjustments_needed = []
                plan_modifications = {}
                confidence_score = 1.0
                reasoning_parts = []

                # Pattern 1: No progress detection
                if len(state.tool_results) == 0 and state.iteration > 2:
                    errors_detected.append("No tool execution after multiple iterations")
                    adjustments_needed.append("Select and execute tools to make progress")
                    plan_modifications["add_tool_execution"] = True
                    confidence_score = min(confidence_score, 0.6)
                    reasoning_parts.append("Detected lack of tool execution despite multiple iterations")

                # Pattern 2: Tool failure analysis
                if state.tool_results:
                    failed_tools = [r for r in state.tool_results if r.get("status") == "failed"]
                    if failed_tools:
                        failure_count = len(failed_tools)
                        errors_detected.append(f"{failure_count} tool execution failure(s) detected")

                        # Check for repeated failures of the same tool
                        tool_names = [r.get("tool_name") for r in failed_tools]
                        repeated_failures = {name: tool_names.count(name) for name in set(tool_names) if tool_names.count(name) > 1}

                        if repeated_failures:
                            for tool_name, count in repeated_failures.items():
                                errors_detected.append(f"Tool '{tool_name}' failed {count} times")
                                adjustments_needed.append(f"Consider alternative to '{tool_name}' or adjust parameters")
                            plan_modifications["replace_failing_tools"] = list(repeated_failures.keys())
                            confidence_score = min(confidence_score, 0.4)
                            reasoning_parts.append(f"Detected repeated tool failures: {repeated_failures}")
                        else:
                            adjustments_needed.append("Review tool parameters and retry with corrections")
                            confidence_score = min(confidence_score, 0.7)
                            reasoning_parts.append("Detected tool failures that may be recoverable")

                # Pattern 3: Infinite loop detection
                if state.iteration > 5:
                    # Check if we're repeating the same actions
                    recent_tools = [r.get("tool_name") for r in state.tool_results[-5:]] if len(state.tool_results) >= 5 else []
                    if recent_tools and len(set(recent_tools)) <= 2:
                        errors_detected.append("Potential infinite loop: repeating same tools")
                        adjustments_needed.append("Break the loop by trying different approach or tools")
                        plan_modifications["break_loop"] = True
                        plan_modifications["avoid_tools"] = list(set(recent_tools))
                        confidence_score = min(confidence_score, 0.3)
                        reasoning_parts.append(f"Detected potential loop with tools: {set(recent_tools)}")

                # Pattern 4: Observation analysis
                if state.observations:
                    last_observation = state.observations[-1]
                    error_keywords = ["error", "failed", "exception", "invalid", "timeout", "denied"]

                    if any(keyword in last_observation.lower() for keyword in error_keywords):
                        errors_detected.append("Recent observation indicates execution problems")
                        adjustments_needed.append("Analyze error details and adjust approach")
                        confidence_score = min(confidence_score, 0.5)
                        reasoning_parts.append("Detected error indicators in recent observations")

                    # Check for lack of progress in observations
                    if len(state.observations) > 3:
                        recent_obs = state.observations[-3:]
                        if all("no progress" in obs.lower() or "waiting" in obs.lower() for obs in recent_obs):
                            errors_detected.append("Multiple observations indicate stalled progress")
                            adjustments_needed.append("Change strategy or escalate to user")
                            plan_modifications["strategy_change_needed"] = True
                            confidence_score = min(confidence_score, 0.4)
                            reasoning_parts.append("Detected stalled progress across multiple observations")

                # Pattern 5: Plan completeness check
                if state.plan:
                    plan_steps = state.plan.get("steps", [])
                    completed_steps = len([r for r in state.tool_results if r.get("status") == "success"])

                    if plan_steps and completed_steps == 0 and state.iteration > 3:
                        errors_detected.append("Plan exists but no steps completed")
                        adjustments_needed.append("Review plan feasibility or break down into simpler steps")
                        plan_modifications["simplify_plan"] = True
                        confidence_score = min(confidence_score, 0.5)
                        reasoning_parts.append("Plan execution has not started despite multiple iterations")

                    # Check if plan is too complex
                    if len(plan_steps) > 10:
                        adjustments_needed.append("Consider breaking complex plan into sub-tasks")
                        plan_modifications["split_plan"] = True
                        reasoning_parts.append("Plan complexity may be hindering execution")

                # Pattern 6: Resource exhaustion indicators
                if state.iteration > 8:
                    errors_detected.append("High iteration count suggests inefficient approach")
                    adjustments_needed.append("Consider simplifying goal or requesting user guidance")
                    plan_modifications["request_user_input"] = True
                    confidence_score = min(confidence_score, 0.3)
                    reasoning_parts.append("Iteration count suggests current approach is inefficient")

                # Pattern 7: Success pattern recognition
                if state.tool_results:
                    success_count = len([r for r in state.tool_results if r.get("status") == "success"])
                    total_count = len(state.tool_results)
                    success_rate = success_count / total_count if total_count > 0 else 0

                    if success_rate > 0.8 and total_count >= 3:
                        reasoning_parts.append(f"Good progress: {success_rate:.0%} success rate")
                        # Maintain high confidence if making good progress
                        confidence_score = max(confidence_score, 0.8)
                    elif success_rate < 0.3 and total_count >= 3:
                        errors_detected.append(f"Low success rate: {success_rate:.0%}")
                        adjustments_needed.append("Current approach has low success rate, consider alternatives")
                        plan_modifications["strategy_change_needed"] = True
                        confidence_score = min(confidence_score, 0.3)
                        reasoning_parts.append(f"Low success rate ({success_rate:.0%}) indicates problematic approach")

                # Generate comprehensive reasoning summary
                if reasoning_parts:
                    reasoning = "Reflection analysis: " + "; ".join(reasoning_parts)
                else:
                    reasoning = "No significant issues detected in current reasoning process"

                # Add plan modification recommendations if errors detected
                if errors_detected and not plan_modifications:
                    plan_modifications["review_needed"] = True

                result = ReflectionResult(
                    reflection_id=reflection_id,
                    timestamp=timestamp,
                    errors_detected=errors_detected,
                    adjustments_needed=adjustments_needed,
                    plan_modifications=plan_modifications if plan_modifications else None,
                    confidence_score=confidence_score,
                    reasoning=reasoning
                )

                # Store reflection in state for history tracking
                if "reflection_history" not in state.metadata:
                    state.metadata["reflection_history"] = []

                state.metadata["reflection_history"].append({
                    "reflection_id": reflection_id,
                    "timestamp": timestamp.isoformat(),
                    "iteration": state.iteration,
                    "errors_count": len(errors_detected),
                    "confidence_score": confidence_score,
                    "errors_detected": errors_detected,
                    "adjustments_needed": adjustments_needed
                })

                span.set_attribute("errors_detected_count", len(errors_detected))
                span.set_attribute("adjustments_needed_count", len(adjustments_needed))
                span.set_attribute("confidence_score", confidence_score)
                span.set_attribute("has_plan_modifications", plan_modifications is not None)

                self.logger.info(
                    "Reflection completed",
                    extra={
                        "task_id": state.task_id,
                        "reflection_id": reflection_id,
                        "errors_detected": len(errors_detected),
                        "adjustments_needed": len(adjustments_needed),
                        "confidence_score": confidence_score,
                        "plan_modifications": bool(plan_modifications)
                    }
                )

                # Emit reflection triggered event
                self.emit_task_event(
                    event_type=EventType.REFLECTION_TRIGGERED,
                    task_id=state.task_id,
                    payload={
                        "reflection_id": reflection_id,
                        "iteration": state.iteration,
                        "errors_detected": errors_detected,
                        "adjustments_needed": adjustments_needed,
                        "confidence_score": confidence_score,
                        "has_plan_modifications": bool(plan_modifications),
                        "errors_count": len(errors_detected),
                        "adjustments_count": len(adjustments_needed)
                    }
                )

                return result

    
    def should_continue(self, state: ReasoningState) -> bool:
        """
        Determine if reasoning loop should continue
        
        Evaluates the current state to decide whether another
        reasoning iteration is needed or if the task is complete.
        
        Args:
            state: Current reasoning state
        
        Returns:
            bool: True if should continue, False if complete
        """
        with self.tracer.start_span("should_continue") as span:
            span.set_attribute("task_id", state.task_id)
            span.set_attribute("iteration", state.iteration)
            
            # Check if we should trigger reflection
            should_reflect = self._should_trigger_reflection(state)
            if should_reflect:
                reflection = self.trigger_reflection(state)
                
                # If reflection detects critical errors, we might want to stop
                if reflection.confidence_score < 0.3:
                    self.logger.warning(
                        "Low confidence from reflection, considering stopping",
                        extra={
                            "task_id": state.task_id,
                            "confidence_score": reflection.confidence_score
                        }
                    )
            
            # Placeholder logic - will be enhanced with more sophisticated checks
            continue_reasoning = self._should_continue_reasoning(state)
            
            span.set_attribute("should_continue", continue_reasoning)
            
            return continue_reasoning
    
    def _should_trigger_reflection(self, state: ReasoningState) -> bool:
        """
        Determine if reflection should be triggered
        
        Args:
            state: Current reasoning state
        
        Returns:
            bool: True if reflection should be triggered
        """
        if not self.enable_reflection:
            return False
        
        # Trigger on failure if configured
        if self.reflection_trigger_on_failure:
            if state.tool_results:
                last_result = state.tool_results[-1]
                if last_result.get("status") == "failed":
                    return True
        
        # Trigger at intervals if configured
        if self.reflection_trigger_interval:
            if state.iteration > 0 and state.iteration % self.reflection_trigger_interval == 0:
                return True
        
        return False
    
    def _should_continue_reasoning(self, state: ReasoningState) -> bool:
        """
        Internal logic to determine if reasoning should continue

        Implements comprehensive continuation logic:
        1. Check if goal is achieved
        2. Check if more steps remain in plan
        3. Detect if progress is being made
        4. Detect if stuck in a loop
        5. Integrate with reflection system
        6. Consider iteration limits

        Args:
            state: Current reasoning state

        Returns:
            bool: True if should continue
        """
        # 1. Check if goal is explicitly achieved
        if state.context.get("goal_achieved", False):
            self.logger.info(
                "Goal achieved, stopping reasoning",
                extra={"task_id": state.task_id, "iteration": state.iteration}
            )
            return False

        # 2. Check if we have a plan and if more steps remain
        if state.plan:
            completed_steps = len(state.tool_results)
            total_steps = state.plan.get("total_steps", 0)

            # If all steps are completed, check if goal is achieved
            if completed_steps >= total_steps and total_steps > 0:
                # Check if the last step was successful
                if state.tool_results:
                    last_result = state.tool_results[-1]
                    if last_result.get("status") == "success":
                        self.logger.info(
                            "All plan steps completed successfully",
                            extra={
                                "task_id": state.task_id,
                                "completed_steps": completed_steps,
                                "total_steps": total_steps
                            }
                        )
                        return False
                    else:
                        # Last step failed, might need replanning
                        self.logger.debug(
                            "Plan steps completed but last step failed, may need replanning",
                            extra={"task_id": state.task_id}
                        )
                        # Continue to allow replanning
                        return True
                else:
                    # No results yet, continue
                    return True

            # More steps remain in the plan
            if completed_steps < total_steps:
                self.logger.debug(
                    "Plan has remaining steps",
                    extra={
                        "task_id": state.task_id,
                        "completed_steps": completed_steps,
                        "total_steps": total_steps
                    }
                )
                return True

        # 3. Detect if progress is being made
        if not self._is_making_progress(state):
            self.logger.warning(
                "No progress detected, stopping reasoning",
                extra={
                    "task_id": state.task_id,
                    "iteration": state.iteration,
                    "tool_results_count": len(state.tool_results)
                }
            )
            return False

        # 4. Detect if stuck in a loop
        if self._is_stuck_in_loop(state):
            self.logger.warning(
                "Loop detected, stopping reasoning",
                extra={
                    "task_id": state.task_id,
                    "iteration": state.iteration
                }
            )
            return False

        # 5. Check if we're in early stages (classify, plan)
        if state.current_step in ["classify", "plan"]:
            self.logger.debug(
                "In early reasoning stage, continuing",
                extra={
                    "task_id": state.task_id,
                    "current_step": state.current_step
                }
            )
            return True

        # 6. If we have no plan yet and we're past classification, we need to plan
        if not state.plan and state.current_step not in ["classify"]:
            self.logger.debug(
                "No plan exists, continuing to create one",
                extra={"task_id": state.task_id}
            )
            return True

        # Default: if we've gotten here and have a plan, continue
        # This handles cases where we might need to replan or adjust
        if state.plan:
            return True

        # No clear reason to continue
        self.logger.info(
            "No clear continuation criteria met, stopping",
            extra={"task_id": state.task_id}
        )
        return False

    def _is_making_progress(self, state: ReasoningState) -> bool:
        """
        Detect if the reasoning loop is making progress

        Progress indicators:
        - New tool results being added
        - Plan being created or updated
        - State transitions happening

        Args:
            state: Current reasoning state

        Returns:
            bool: True if making progress
        """
        # If we're in the first few iterations, assume we're making progress
        if state.iteration <= 2:
            return True

        # Check if we've added tool results recently
        if state.tool_results:
            # If we have results, we're making progress
            return True

        # Check if we have a plan (indicates progress from classification)
        if state.plan:
            return True

        # Check if we've classified intent
        if state.intent and state.intent != Intent.UNKNOWN:
            return True

        # No clear progress indicators
        return False

    def _is_stuck_in_loop(self, state: ReasoningState) -> bool:
        """
        Detect if the reasoning loop is stuck repeating the same actions

        Loop detection:
        - Same step being repeated multiple times without progress
        - Same tool being called with same parameters repeatedly
        - Same errors occurring repeatedly

        Args:
            state: Current reasoning state

        Returns:
            bool: True if stuck in a loop
        """
        # Need at least 3 iterations to detect a loop
        if state.iteration < 3:
            return False

        # Check for repeated failures in tool results
        if len(state.tool_results) >= 3:
            # Check last 3 results for repeated failures
            recent_results = state.tool_results[-3:]
            failure_count = sum(1 for r in recent_results if r.get("status") == "failed")

            if failure_count >= 3:
                # Check if it's the same error
                errors = [r.get("error", "") for r in recent_results if r.get("status") == "failed"]
                if len(set(errors)) == 1:  # Same error repeated
                    self.logger.warning(
                        "Detected repeated failures with same error",
                        extra={
                            "task_id": state.task_id,
                            "error": errors[0]
                        }
                    )
                    return True

        # Check for repeated tool calls with no progress
        if len(state.tool_results) >= 4:
            # Check if we're calling the same tool repeatedly
            recent_tools = [r.get("tool_name", "") for r in state.tool_results[-4:]]
            if len(set(recent_tools)) == 1 and recent_tools[0]:
                # Same tool called 4 times in a row
                self.logger.warning(
                    "Detected repeated tool calls",
                    extra={
                        "task_id": state.task_id,
                        "tool_name": recent_tools[0]
                    }
                )
                return True

        # Check if we're stuck in the same step
        # This would require tracking step history, which we don't have yet
        # For now, we'll rely on the other checks

        return False


    
    def emit_task_event(
        self,
        event_type: EventType,
        task_id: str,
        payload: Dict[str, Any]
    ) -> None:
        """
        Emit task lifecycle event
        
        Args:
            event_type: Type of event to emit
            task_id: Task identifier
            payload: Event-specific data
        """
        try:
            correlation_id = get_correlation_id()
            
            event = Event.create(
                event_type=event_type,
                source_component="agent_orchestrator",
                payload=payload,
                trace_id=self.tracer.get_current_trace_id() or "unknown",
                correlation_id=correlation_id or "unknown",
                workflow_id=task_id
            )
            
            self.event_bus.publish(event)
            
            self.logger.debug(
                "Task event emitted",
                extra={
                    "event_type": event_type.value,
                    "task_id": task_id,
                    "event_id": event.event_id
                }
            )
        except Exception as e:
            self.logger.error(
                "Failed to emit task event",
                extra={
                    "event_type": event_type.value,
                    "task_id": task_id,
                    "error": str(e)
                }
            )

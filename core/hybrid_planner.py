"""
Hybrid Planner

Combines LLM-based planning for complex tasks with rule-based templates for common tasks.
Provides intelligent task decomposition, tool selection, plan validation, and repair.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Callable
from uuid import uuid4
import hashlib
import re
import json

from observability import get_logging_system, get_tracing_system, get_correlation_id
from events import get_event_bus, EventType, Event


class TaskComplexity(str, Enum):
    """
    Task complexity levels for planning approach selection
    
    - SIMPLE: Deterministic tasks with clear steps (use rule-based planning)
    - MODERATE: Tasks with some variability (use rule-based with LLM fallback)
    - COMPLEX: Novel or multi-faceted tasks (use LLM-based planning)
    """
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class PlanStatus(str, Enum):
    """
    Plan validation status
    
    - VALID: Plan is executable with available tools
    - INVALID: Plan has errors or missing dependencies
    - INCOMPLETE: Plan needs additional steps
    - REPAIRED: Plan was invalid but has been fixed
    """
    VALID = "valid"
    INVALID = "invalid"
    INCOMPLETE = "incomplete"
    REPAIRED = "repaired"


@dataclass
class ComplexityClassification:
    """
    Result of task complexity classification
    
    Determines whether a task should use LLM-based or rule-based planning
    based on complexity analysis.
    """
    level: TaskComplexity
    requires_llm: bool
    estimated_steps: int
    confidence: float  # 0.0 to 1.0
    reasoning: str
    keywords_matched: List[str] = field(default_factory=list)
    pattern_matches: List[str] = field(default_factory=list)
    multi_step_detected: bool = False
    dependency_count: int = 0
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/persistence"""
        return {
            "level": self.level.value,
            "requires_llm": self.requires_llm,
            "estimated_steps": self.estimated_steps,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "keywords_matched": self.keywords_matched,
            "pattern_matches": self.pattern_matches,
            "multi_step_detected": self.multi_step_detected,
            "dependency_count": self.dependency_count,
            "resource_requirements": self.resource_requirements
        }


@dataclass
class TaskPlan:
    """
    Executable task plan with steps and metadata
    
    Represents a decomposed task with ordered steps, tool selections,
    dependencies, and validation status.
    """
    plan_id: str
    goal: str
    steps: List[Dict[str, Any]]
    complexity: TaskComplexity
    planning_approach: str  # "rule_based" or "llm_based"
    status: PlanStatus = PlanStatus.VALID
    created_at: datetime = field(default_factory=datetime.utcnow)
    estimated_duration_seconds: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence"""
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "steps": self.steps,
            "complexity": self.complexity.value,
            "planning_approach": self.planning_approach,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "dependencies": self.dependencies,
            "metadata": self.metadata
        }


@dataclass
class PlanningContext:
    """
    Context information for plan generation
    
    Provides available tools, user preferences, execution history,
    and constraints to inform planning decisions.
    """
    available_tools: List[str]
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    session_context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ToolSelection:
    """
    Tool selection result with confidence scoring
    
    Represents the selected tool for a task step along with
    confidence score, alternatives, and selection reasoning.
    """
    tool_name: str
    confidence: float  # 0.0 to 1.0
    reasoning: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    alternatives: List[Tuple[str, float]] = field(default_factory=list)
    fallback_tool: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tool_name": self.tool_name,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "parameters": self.parameters,
            "alternatives": self.alternatives,
            "fallback_tool": self.fallback_tool
        }


@dataclass
class ValidationResult:
    """
    Plan validation result
    
    Contains validation status, identified errors, warnings,
    and suggestions for plan improvement.
    """
    is_valid: bool
    status: PlanStatus
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class PlanError:
    """
    Error encountered during plan execution or validation
    
    Describes what went wrong with the plan and provides
    context for repair attempts.
    """
    error_type: str  # "missing_tool", "invalid_dependency", "circular_dependency", etc.
    description: str
    affected_steps: List[int] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class HybridPlanner:
    """
    Hybrid planning system combining LLM and rule-based approaches
    
    The HybridPlanner intelligently selects between LLM-based planning for
    complex tasks and rule-based templates for common tasks. It provides
    task complexity classification, plan generation, validation, repair,
    and tool selection with confidence scoring.
    
    Responsibilities:
    - Task decomposition into executable steps
    - Hybrid planning (LLM-based + rule-based)
    - Tool selection based on capability matching and confidence scoring
    - Fallback tool identification
    - Plan validation and optimization
    - Plan repair for invalid plans
    
    Planning Approach:
    1. Classify task complexity
    2. Select planning approach (rule-based or LLM-based)
    3. Generate initial plan
    4. Validate plan
    5. Repair if invalid
    6. Optimize and resolve dependencies
    """
    
    # Rule-based plan templates for common tasks
    PLAN_TEMPLATES = {
        # File operations
        "read_file": {
            "keywords": ["read", "open", "view", "show", "cat", "display"],
            "patterns": [r"read\s+(?:file|document)", r"open\s+\w+\.\w+", r"cat\s+\w+", r"show\s+(?:me\s+)?(?:the\s+)?(?:file|content)"],
            "parameters": ["file_path"],
            "steps": [
                {"tool": "file_manager", "action": "read", "param": "file_path", "description": "Read file contents"}
            ]
        },
        "write_file": {
            "keywords": ["write", "save", "create file", "store"],
            "patterns": [r"write\s+(?:to|file)", r"save\s+(?:to|file)", r"create\s+file"],
            "parameters": ["file_path", "content"],
            "steps": [
                {"tool": "file_manager", "action": "validate_path", "param": "file_path", "description": "Validate file path"},
                {"tool": "file_manager", "action": "write", "param": "file_path", "description": "Write content to file"}
            ]
        },
        "list_directory": {
            "keywords": ["list", "ls", "dir", "show files", "show directory"],
            "patterns": [r"list\s+(?:files|directory)", r"ls\s+", r"dir\s+", r"show\s+(?:files|directory)"],
            "parameters": ["directory_path"],
            "steps": [
                {"tool": "file_manager", "action": "list", "param": "directory_path", "description": "List directory contents"}
            ]
        },
        "delete_file": {
            "keywords": ["delete", "remove", "rm"],
            "patterns": [r"delete\s+(?:file|document)", r"remove\s+\w+", r"rm\s+\w+"],
            "parameters": ["file_path"],
            "steps": [
                {"tool": "file_manager", "action": "validate_path", "param": "file_path", "description": "Validate file exists"},
                {"tool": "file_manager", "action": "delete", "param": "file_path", "description": "Delete file"}
            ]
        },
        "move_file": {
            "keywords": ["move", "mv", "rename"],
            "patterns": [r"move\s+\w+", r"mv\s+\w+", r"rename\s+\w+"],
            "parameters": ["source_path", "destination_path"],
            "steps": [
                {"tool": "file_manager", "action": "validate_path", "param": "source_path", "description": "Validate source exists"},
                {"tool": "file_manager", "action": "move", "param": "source_path", "description": "Move file to destination"}
            ]
        },
        "copy_file": {
            "keywords": ["copy", "cp", "duplicate"],
            "patterns": [r"copy\s+\w+", r"cp\s+\w+", r"duplicate\s+\w+"],
            "parameters": ["source_path", "destination_path"],
            "steps": [
                {"tool": "file_manager", "action": "validate_path", "param": "source_path", "description": "Validate source exists"},
                {"tool": "file_manager", "action": "copy", "param": "source_path", "description": "Copy file to destination"}
            ]
        },
        
        # Web operations
        "web_search": {
            "keywords": ["search", "google", "find online", "look up"],
            "patterns": [r"search\s+(?:for|the\s+web)", r"google\s+", r"find\s+online", r"look\s+up"],
            "parameters": ["query"],
            "steps": [
                {"tool": "browser_agent", "action": "search", "param": "query", "description": "Search the web"},
                {"tool": "browser_agent", "action": "fetch", "param": "top_result", "description": "Fetch top result"}
            ]
        },
        "fetch_url": {
            "keywords": ["fetch", "get url", "download", "retrieve url"],
            "patterns": [r"fetch\s+(?:url|webpage)", r"get\s+(?:url|webpage)", r"download\s+(?:from\s+)?url"],
            "parameters": ["url"],
            "steps": [
                {"tool": "browser_agent", "action": "fetch", "param": "url", "description": "Fetch URL content"}
            ]
        },
        "extract_web_content": {
            "keywords": ["extract", "scrape", "parse webpage"],
            "patterns": [r"extract\s+(?:from|content)", r"scrape\s+", r"parse\s+webpage"],
            "parameters": ["url", "selector"],
            "steps": [
                {"tool": "browser_agent", "action": "fetch", "param": "url", "description": "Fetch webpage"},
                {"tool": "browser_agent", "action": "extract", "param": "selector", "description": "Extract content"}
            ]
        },
        
        # Knowledge operations
        "knowledge_search": {
            "keywords": ["search knowledge", "find in knowledge", "query knowledge"],
            "patterns": [r"search\s+knowledge", r"find\s+in\s+knowledge", r"query\s+knowledge"],
            "parameters": ["query"],
            "steps": [
                {"tool": "knowledge_manager", "action": "search", "param": "query", "description": "Search knowledge base"},
                {"tool": "knowledge_manager", "action": "retrieve", "param": "top_results", "description": "Retrieve top results"}
            ]
        },
        "retrieve_memory": {
            "keywords": ["remember", "recall", "retrieve memory"],
            "patterns": [r"remember\s+", r"recall\s+", r"retrieve\s+memory"],
            "parameters": ["query"],
            "steps": [
                {"tool": "memory_system", "action": "search", "param": "query", "description": "Search memory"},
                {"tool": "memory_system", "action": "retrieve", "param": "memory_id", "description": "Retrieve memory"}
            ]
        },
        "summarize_content": {
            "keywords": ["summarize", "summary", "tldr"],
            "patterns": [r"summarize\s+", r"summary\s+of", r"tldr\s+"],
            "parameters": ["content"],
            "steps": [
                {"tool": "llm", "action": "summarize", "param": "content", "description": "Generate summary"}
            ]
        },
        
        # Data operations
        "process_data": {
            "keywords": ["process", "transform data", "convert"],
            "patterns": [r"process\s+data", r"transform\s+", r"convert\s+"],
            "parameters": ["data", "format"],
            "steps": [
                {"tool": "data_processor", "action": "validate", "param": "data", "description": "Validate input data"},
                {"tool": "data_processor", "action": "process", "param": "data", "description": "Process data"}
            ]
        },
        "analyze_data": {
            "keywords": ["analyze data", "data analysis", "statistics"],
            "patterns": [r"analyze\s+data", r"data\s+analysis", r"statistics\s+"],
            "parameters": ["data"],
            "steps": [
                {"tool": "data_processor", "action": "load", "param": "data", "description": "Load data"},
                {"tool": "data_processor", "action": "analyze", "param": "data", "description": "Analyze data"},
                {"tool": "data_processor", "action": "report", "description": "Generate analysis report"}
            ]
        },
        
        # System operations
        "execute_command": {
            "keywords": ["execute", "run command", "shell"],
            "patterns": [r"execute\s+command", r"run\s+command", r"shell\s+"],
            "parameters": ["command"],
            "steps": [
                {"tool": "system_executor", "action": "validate", "param": "command", "description": "Validate command safety"},
                {"tool": "system_executor", "action": "execute", "param": "command", "description": "Execute command"}
            ]
        },
        "check_status": {
            "keywords": ["check status", "status", "health check"],
            "patterns": [r"check\s+status", r"status\s+of", r"health\s+check"],
            "parameters": ["service"],
            "steps": [
                {"tool": "system_monitor", "action": "check", "param": "service", "description": "Check service status"}
            ]
        },
        
        # Composite operations
        "read_and_summarize": {
            "keywords": ["read and summarize", "summarize file"],
            "patterns": [r"read\s+and\s+summarize", r"summarize\s+file"],
            "parameters": ["file_path"],
            "steps": [
                {"tool": "file_manager", "action": "read", "param": "file_path", "description": "Read file contents"},
                {"tool": "llm", "action": "summarize", "param": "content", "description": "Summarize content"}
            ]
        },
        "search_and_save": {
            "keywords": ["search and save", "find and save"],
            "patterns": [r"search\s+and\s+save", r"find\s+and\s+save"],
            "parameters": ["query", "file_path"],
            "steps": [
                {"tool": "browser_agent", "action": "search", "param": "query", "description": "Search the web"},
                {"tool": "browser_agent", "action": "fetch", "param": "top_result", "description": "Fetch top result"},
                {"tool": "file_manager", "action": "write", "param": "file_path", "description": "Save results to file"}
            ]
        },
        # Generic file operation alias (covers read, write, list, delete, move, copy)
        "file_operation": {
            "keywords": ["file", "document", "folder", "directory"],
            "patterns": [r"(?:read|write|list|delete|move|copy|create)\s+(?:file|document|folder|directory)"],
            "parameters": ["file_path"],
            "steps": [
                {"tool": "file_manager", "action": "execute", "param": "file_path", "description": "Perform file operation"}
            ]
        }
    }
    
    # Keywords for complexity classification with weights
    SIMPLE_TASK_KEYWORDS = {
        "read": 1.0, "list": 1.0, "show": 0.9, "display": 0.9, 
        "get": 0.8, "fetch": 0.8, "find": 0.7, "search": 0.7,
        "look up": 0.7, "retrieve": 0.8, "open": 0.9, "view": 0.9,
        "print": 0.8, "cat": 0.9, "ls": 1.0, "dir": 1.0
    }
    
    COMPLEX_TASK_KEYWORDS = {
        "analyze": 1.0, "debug": 1.0, "refactor": 1.0, "optimize": 1.0,
        "research": 0.9, "investigate": 0.9, "compare": 0.8, "evaluate": 0.8,
        "design": 1.0, "architect": 1.0, "plan": 0.7, "strategize": 0.9,
        "recommend": 0.7, "suggest improvements": 0.8, "implement": 0.6,
        "build": 0.6, "create complex": 0.9, "develop": 0.6, "engineer": 0.8
    }
    
    # Task type patterns for classification
    TASK_PATTERNS = {
        "file_read": {
            "patterns": [r"read\s+(?:file|document)", r"open\s+\w+\.\w+", r"cat\s+\w+"],
            "complexity": TaskComplexity.SIMPLE,
            "estimated_steps": 1
        },
        "file_write": {
            "patterns": [r"write\s+(?:to|file)", r"save\s+(?:to|file)", r"create\s+file"],
            "complexity": TaskComplexity.SIMPLE,
            "estimated_steps": 2
        },
        "multi_file": {
            "patterns": [r"multiple\s+files", r"all\s+files", r"every\s+file", r"\d+\s+files"],
            "complexity": TaskComplexity.MODERATE,
            "estimated_steps": 5
        },
        "code_analysis": {
            "patterns": [r"analyze\s+code", r"review\s+code", r"code\s+quality"],
            "complexity": TaskComplexity.COMPLEX,
            "estimated_steps": 8
        },
        "research": {
            "patterns": [r"research\s+\w+", r"investigate\s+\w+", r"find\s+information\s+about"],
            "complexity": TaskComplexity.COMPLEX,
            "estimated_steps": 10
        }
    }
    
    def __init__(
        self,
        enable_llm_planning: bool = True,
        enable_rule_based_planning: bool = True,
        llm_fallback_enabled: bool = True,
        max_plan_steps: int = 20,
        max_repair_attempts: int = 3
    ):
        """
        Initialize Hybrid Planner
        
        Args:
            enable_llm_planning: Enable LLM-based planning for complex tasks
            enable_rule_based_planning: Enable rule-based templates for simple tasks
            llm_fallback_enabled: Fallback to LLM if rule-based planning fails
            max_plan_steps: Maximum number of steps in a plan
            max_repair_attempts: Maximum attempts to repair invalid plans
        """
        self.logger = get_logging_system()
        self.tracer = get_tracing_system()
        self.event_bus = get_event_bus()
        
        self.enable_llm_planning = enable_llm_planning
        self.enable_rule_based_planning = enable_rule_based_planning
        self.llm_fallback_enabled = llm_fallback_enabled
        self.max_plan_steps = max_plan_steps
        self.max_repair_attempts = max_repair_attempts
        
        # Component placeholders - will be injected by Agent Runtime
        self.model_router = None
        self.tool_registry = None
        self.prompt_manager = None
        
        # Plan cache for performance
        self._plan_cache: Dict[str, TaskPlan] = {}
        
        self.logger.info(
            "HybridPlanner initialized",
            extra={
                "enable_llm_planning": enable_llm_planning,
                "enable_rule_based_planning": enable_rule_based_planning,
                "llm_fallback_enabled": llm_fallback_enabled,
                "max_plan_steps": max_plan_steps,
                "max_repair_attempts": max_repair_attempts
            }
        )
    
    def create_plan(self, goal: str, context: PlanningContext) -> TaskPlan:
        """
        Create task plan using hybrid approach
        
        Analyzes task complexity and selects appropriate planning approach.
        Uses rule-based templates for simple tasks and LLM-based planning
        for complex tasks. Validates and repairs plans as needed.
        
        Args:
            goal: Natural language description of the task goal
            context: Planning context with available tools and constraints
            
        Returns:
            TaskPlan: Validated and executable task plan
            
        Raises:
            ValueError: If planning fails after all attempts
        """
        with self.tracer.start_span("hybrid_planner.create_plan") as span:
            span.set_attribute("goal", goal)
            span.set_attribute("available_tools_count", len(context.available_tools))
            
            self.logger.info(
                "Creating task plan",
                extra={
                    "goal": goal,
                    "available_tools": context.available_tools
                }
            )
            
            # Check cache first
            cache_key = self._generate_cache_key(goal, context)
            if cache_key in self._plan_cache:
                self.logger.info("Returning cached plan", extra={"cache_key": cache_key})
                return self._plan_cache[cache_key]
            
            # Step 1: Classify task complexity
            complexity = self.classify_task_complexity(goal)
            span.set_attribute("complexity", complexity.level.value)
            span.set_attribute("requires_llm", complexity.requires_llm)
            
            self.logger.info(
                "Task complexity classified",
                extra={
                    "complexity": complexity.level.value,
                    "requires_llm": complexity.requires_llm,
                    "confidence": complexity.confidence
                }
            )
            
            # Step 2: Generate plan using appropriate approach
            plan = None
            planning_approach = None
            
            if complexity.requires_llm and self.enable_llm_planning:
                # Use LLM-based planning for complex tasks
                planning_approach = "llm_based"
                plan = self._generate_llm_plan(goal, context, complexity)
                
                # Task 7.7: Fallback from LLM to rule-based if LLM fails
                if plan is None and self.llm_fallback_enabled and self.enable_rule_based_planning:
                    self.logger.warning(
                        "LLM planning failed, falling back to rule-based planning",
                        extra={"goal": goal, "reason": "LLM returned None"}
                    )
                    planning_approach = "rule_based"
                    plan = self._generate_rule_based_plan(goal, context, complexity)
            elif self.enable_rule_based_planning:
                # Use rule-based planning for simple tasks
                planning_approach = "rule_based"
                plan = self._generate_rule_based_plan(goal, context, complexity)
                
                # Fallback to LLM if rule-based fails
                if plan is None and self.llm_fallback_enabled and self.enable_llm_planning:
                    self.logger.warning("Rule-based planning failed, falling back to LLM")
                    planning_approach = "llm_based"
                    plan = self._generate_llm_plan(goal, context, complexity)
            
            if plan is None:
                raise ValueError(f"Failed to generate plan for goal: {goal}")
            
            # Step 3: Validate plan
            validation = self.validate_plan(plan, context)
            plan.status = validation.status
            
            # Step 4: Repair if invalid
            if not validation.is_valid:
                self.logger.warning(
                    "Plan validation failed, attempting repair",
                    extra={"errors": validation.errors}
                )
                plan = self._repair_plan_with_retries(plan, validation, context)
            
            # Step 5: Optimize plan
            plan = self._optimize_plan(plan, context)
            
            # Cache the plan
            self._plan_cache[cache_key] = plan
            
            # Emit event
            self._emit_plan_created_event(plan)
            
            self.logger.info(
                "Task plan created successfully",
                extra={
                    "plan_id": plan.plan_id,
                    "steps_count": len(plan.steps),
                    "planning_approach": planning_approach,
                    "status": plan.status.value
                }
            )
            
            return plan
    
    def classify_task_complexity(self, goal: str) -> ComplexityClassification:
        """
        Determine if task needs LLM or rule-based planning
        
        Enhanced classification with:
        - Weighted keyword scoring
        - Pattern recognition for common task types
        - Multi-step task detection
        - Dependency analysis
        - Resource requirement estimation
        - Confidence calibration based on multiple signals
        
        Args:
            goal: Natural language task description
            
        Returns:
            ComplexityClassification: Comprehensive complexity analysis
        """
        with self.tracer.start_span("hybrid_planner.classify_complexity") as span:
            goal_lower = goal.lower()
            
            # 1. Weighted keyword matching
            simple_score = 0.0
            simple_matches = []
            for keyword, weight in self.SIMPLE_TASK_KEYWORDS.items():
                if keyword in goal_lower:
                    simple_score += weight
                    simple_matches.append(keyword)
            
            complex_score = 0.0
            complex_matches = []
            for keyword, weight in self.COMPLEX_TASK_KEYWORDS.items():
                if keyword in goal_lower:
                    complex_score += weight
                    complex_matches.append(keyword)
            
            # 2. Pattern recognition for common task types
            pattern_matches = []
            pattern_complexity = None
            pattern_steps = 0
            
            for pattern_name, pattern_info in self.TASK_PATTERNS.items():
                for pattern in pattern_info["patterns"]:
                    if re.search(pattern, goal_lower):
                        pattern_matches.append(pattern_name)
                        pattern_complexity = pattern_info["complexity"]
                        pattern_steps = pattern_info["estimated_steps"]
                        break
            
            # 3. Multi-step task detection
            word_count = len(goal.split())
            sentence_count = goal.count('.') + goal.count(';') + goal.count('!') + 1
            has_multiple_sentences = sentence_count > 1
            has_conjunctions = any(word in goal_lower for word in [' and ', ' then ', ' after ', ' before '])
            has_conditional = any(word in goal_lower for word in ['if', 'when', 'unless', 'depending', 'whether'])
            has_loops = any(word in goal_lower for word in ['each', 'every', 'all', 'for all'])
            
            multi_step_detected = has_multiple_sentences or has_conjunctions or has_loops
            
            # 4. Dependency analysis
            dependency_indicators = ['after', 'before', 'then', 'once', 'when', 'requires', 'depends on']
            dependency_count = sum(1 for indicator in dependency_indicators if indicator in goal_lower)
            
            # 5. Resource requirement estimation
            resource_requirements = {}
            if any(word in goal_lower for word in ['file', 'document', 'read', 'write']):
                resource_requirements['filesystem'] = True
            if any(word in goal_lower for word in ['search', 'web', 'url', 'website', 'browse']):
                resource_requirements['network'] = True
            if any(word in goal_lower for word in ['database', 'query', 'sql', 'table']):
                resource_requirements['database'] = True
            if any(word in goal_lower for word in ['analyze', 'summarize', 'explain', 'generate']):
                resource_requirements['llm'] = True
            
            # 6. Confidence calibration based on multiple signals
            signals = []
            
            # Signal 1: Keyword scores
            if complex_score > simple_score * 1.5:
                signals.append(('complex_keywords', 0.9, complex_score))
            elif simple_score > complex_score * 1.5:
                signals.append(('simple_keywords', 0.9, simple_score))
            else:
                signals.append(('mixed_keywords', 0.5, max(simple_score, complex_score)))
            
            # Signal 2: Pattern matches
            if pattern_matches:
                signals.append(('pattern_match', 0.85, len(pattern_matches)))
            
            # Signal 3: Task structure
            if multi_step_detected:
                signals.append(('multi_step', 0.7, sentence_count))
            
            # Signal 4: Dependencies
            if dependency_count > 0:
                signals.append(('dependencies', 0.75, dependency_count))
            
            # Signal 5: Conditionals
            if has_conditional:
                signals.append(('conditional', 0.8, 1))
            
            # 7. Final classification logic
            # Determine complexity level
            if pattern_complexity:
                # Use pattern-based classification if available
                level = pattern_complexity
                estimated_steps = pattern_steps
                reasoning_parts = [f"Pattern match: {', '.join(pattern_matches)}"]
            elif complex_score >= 1.5 or (complex_matches and word_count > 12):
                level = TaskComplexity.COMPLEX
                estimated_steps = 5 + len(complex_matches) * 2 + dependency_count
                reasoning_parts = [f"Complex keywords: {', '.join(complex_matches)}"]
            elif simple_score > 1.5 and not has_multiple_sentences and word_count < 10 and not has_conditional:
                level = TaskComplexity.SIMPLE
                estimated_steps = 1 + len(simple_matches)
                reasoning_parts = [f"Simple keywords: {', '.join(simple_matches)}"]
            elif has_conditional or has_loops or dependency_count > 1 or word_count > 20:
                level = TaskComplexity.COMPLEX
                estimated_steps = 6 + dependency_count * 2
                reasoning_parts = ["Complex structure detected"]
                if has_conditional:
                    reasoning_parts.append("conditional logic")
                if has_loops:
                    reasoning_parts.append("iteration required")
                if dependency_count > 1:
                    reasoning_parts.append(f"{dependency_count} dependencies")
            elif multi_step_detected or word_count > 12:
                level = TaskComplexity.MODERATE
                estimated_steps = 3 + (word_count // 10) + dependency_count
                reasoning_parts = ["Moderate complexity"]
                if multi_step_detected:
                    reasoning_parts.append("multiple steps")
            else:
                level = TaskComplexity.MODERATE
                estimated_steps = 2
                reasoning_parts = ["Default moderate classification"]
            
            # Determine if LLM is required
            requires_llm = (
                level == TaskComplexity.COMPLEX or
                (level == TaskComplexity.MODERATE and (has_conditional or complex_score > 0)) or
                resource_requirements.get('llm', False)
            )
            
            # Calculate confidence based on signal agreement
            if len(signals) >= 3:
                # Multiple signals - high confidence
                avg_confidence = sum(s[1] for s in signals) / len(signals)
                confidence = min(avg_confidence + 0.1, 1.0)
            elif len(signals) == 2:
                # Two signals - moderate confidence
                confidence = sum(s[1] for s in signals) / len(signals)
            else:
                # Single signal - lower confidence
                confidence = signals[0][1] - 0.1 if signals else 0.5
            
            # Adjust confidence based on pattern match
            if pattern_matches:
                confidence = min(confidence + 0.1, 1.0)
            
            # Build reasoning explanation
            reasoning = "; ".join(reasoning_parts)
            if resource_requirements:
                reasoning += f" | Resources: {', '.join(resource_requirements.keys())}"
            
            classification = ComplexityClassification(
                level=level,
                requires_llm=requires_llm,
                estimated_steps=estimated_steps,
                confidence=confidence,
                reasoning=reasoning,
                keywords_matched=simple_matches + complex_matches,
                pattern_matches=pattern_matches,
                multi_step_detected=multi_step_detected,
                dependency_count=dependency_count,
                resource_requirements=resource_requirements
            )
            
            span.set_attribute("complexity_level", level.value)
            span.set_attribute("requires_llm", requires_llm)
            span.set_attribute("confidence", confidence)
            span.set_attribute("pattern_matches", len(pattern_matches))
            span.set_attribute("multi_step", multi_step_detected)
            
            self.logger.debug(
                "Task complexity classified",
                extra=classification.to_dict()
            )
            
            return classification
    
    def _generate_rule_based_plan(
        self,
        goal: str,
        context: PlanningContext,
        complexity: ComplexityClassification
    ) -> Optional[TaskPlan]:
        """
        Generate deterministic plan for simple tasks using templates
        
        Matches the goal against known templates and generates a plan
        using predefined step sequences.
        
        Args:
            goal: Task goal description
            context: Planning context
            complexity: Complexity classification
            
        Returns:
            TaskPlan or None if no template matches
        """
        with self.tracer.start_span("hybrid_planner.generate_rule_based_plan") as span:
            span.set_attribute("goal", goal)
            
            self.logger.info("Attempting rule-based planning", extra={"goal": goal})
            
            # Step 1: Match template
            template_match = self._match_template(goal)
            
            if template_match is None:
                self.logger.debug("No template matched for goal", extra={"goal": goal})
                return None
            
            template_name, template, confidence = template_match
            span.set_attribute("template_name", template_name)
            span.set_attribute("match_confidence", confidence)
            
            self.logger.info(
                "Template matched",
                extra={
                    "template_name": template_name,
                    "confidence": confidence
                }
            )
            
            # Step 2: Extract parameters from goal
            parameters = self._extract_parameters(goal, template)
            
            # Step 3: Populate template with parameters
            populated_steps = self._populate_template(template, parameters)
            
            # Step 4: Convert template to TaskPlan
            plan = self._template_to_plan(
                goal=goal,
                template_name=template_name,
                steps=populated_steps,
                complexity=complexity,
                parameters=parameters,
                confidence=confidence
            )
            
            self.logger.info(
                "Rule-based plan generated",
                extra={
                    "plan_id": plan.plan_id,
                    "template_name": template_name,
                    "steps_count": len(plan.steps)
                }
            )
            
            return plan
    
    def _match_template(self, goal: str) -> Optional[Tuple[str, Dict[str, Any], float]]:
        """
        Find best matching template for the goal
        
        Uses keyword matching and pattern matching to find the most
        appropriate template with confidence scoring.
        
        Args:
            goal: Task goal description
            
        Returns:
            Tuple of (template_name, template, confidence) or None if no match
        """
        goal_lower = goal.lower()
        best_match = None
        best_score = 0.0
        
        for template_name, template in self.PLAN_TEMPLATES.items():
            score = 0.0
            matches = 0
            
            # Keyword matching
            keywords = template.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in goal_lower:
                    score += 1.0
                    matches += 1
            
            # Pattern matching
            patterns = template.get("patterns", [])
            for pattern in patterns:
                if re.search(pattern, goal_lower):
                    score += 2.0  # Patterns are more specific, weight higher
                    matches += 1
            
            # Normalize score by number of potential matches
            if matches > 0:
                # Boost score if multiple matches
                if matches > 1:
                    score *= 1.2
                
                # Calculate confidence (0.0 to 1.0)
                confidence = min(score / (len(keywords) + len(patterns)), 1.0)
                
                # Update best match if this is better
                if score > best_score:
                    best_score = score
                    best_match = (template_name, template, confidence)
        
        # Only return match if confidence is above threshold
        if best_match and best_match[2] >= 0.3:  # Minimum 30% confidence
            return best_match
        
        return None
    
    def _extract_parameters(self, goal: str, template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract parameters from goal text
        
        Uses pattern matching and heuristics to extract parameter values
        from the natural language goal.
        
        Args:
            goal: Task goal description
            template: Matched template
            
        Returns:
            Dictionary of parameter names to values
        """
        parameters = {}
        required_params = template.get("parameters", [])
        
        # Common parameter extraction patterns
        param_patterns = {
            "file_path": [
                r"(?:file|document|path)\s+['\"]?([^\s'\"]+\.\w+)['\"]?",
                r"['\"]([^\s'\"]+\.\w+)['\"]",
                r"(\w+\.\w+)"
            ],
            "directory_path": [
                r"(?:directory|folder|dir)\s+['\"]?([^\s'\"]+)['\"]?",
                r"['\"]([^\s'\"]+)['\"]"
            ],
            "url": [
                r"(https?://[^\s]+)",
                r"(?:url|website|link)\s+['\"]?([^\s'\"]+)['\"]?"
            ],
            "query": [
                r"(?:search|find|look\s+up)\s+(?:for\s+)?['\"]?([^'\"]+?)['\"]?(?:\s+(?:on|in|from)|\s*$)",
                r"['\"]([^'\"]+)['\"]"
            ],
            "content": [
                r"['\"]([^'\"]+)['\"]"
            ],
            "command": [
                r"(?:command|execute|run)\s+['\"]?([^'\"]+)['\"]?",
                r"['\"]([^'\"]+)['\"]"
            ],
            "source_path": [
                r"(?:from|source)\s+['\"]?([^\s'\"]+)['\"]?",
                r"^['\"]?([^\s'\"]+\.\w+)['\"]?"
            ],
            "destination_path": [
                r"(?:to|destination|dest)\s+['\"]?([^\s'\"]+)['\"]?",
                r"['\"]?([^\s'\"]+\.\w+)['\"]?$"
            ],
            "service": [
                r"(?:service|process)\s+['\"]?([^\s'\"]+)['\"]?",
                r"['\"]([^'\"]+)['\"]"
            ],
            "selector": [
                r"(?:selector|element)\s+['\"]?([^'\"]+)['\"]?",
                r"['\"]([^'\"]+)['\"]"
            ],
            "data": [
                r"(?:data|input)\s+['\"]?([^'\"]+)['\"]?",
                r"['\"]([^'\"]+)['\"]"
            ],
            "format": [
                r"(?:format|type)\s+['\"]?(\w+)['\"]?",
                r"(?:to|as)\s+(\w+)"
            ]
        }
        
        # Extract each required parameter
        for param in required_params:
            if param in param_patterns:
                patterns = param_patterns[param]
                for pattern in patterns:
                    match = re.search(pattern, goal, re.IGNORECASE)
                    if match:
                        parameters[param] = match.group(1).strip()
                        break
            
            # If parameter not found, use placeholder
            if param not in parameters:
                parameters[param] = f"<{param}>"
        
        return parameters
    
    def _populate_template(
        self,
        template: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Fill template with extracted parameters
        
        Replaces parameter placeholders in template steps with actual values.
        
        Args:
            template: Template definition
            parameters: Extracted parameter values
            
        Returns:
            List of populated step dictionaries
        """
        steps = template.get("steps", [])
        populated_steps = []
        
        for step in steps:
            populated_step = step.copy()
            
            # Replace parameter placeholders
            if "param" in populated_step:
                param_name = populated_step["param"]
                if param_name in parameters:
                    populated_step["param_value"] = parameters[param_name]
                else:
                    # Check if param is a reference to another step's output
                    populated_step["param_value"] = f"<{param_name}>"
            
            populated_steps.append(populated_step)
        
        return populated_steps
    
    def _template_to_plan(
        self,
        goal: str,
        template_name: str,
        steps: List[Dict[str, Any]],
        complexity: ComplexityClassification,
        parameters: Dict[str, Any],
        confidence: float
    ) -> TaskPlan:
        """
        Convert populated template to TaskPlan
        
        Creates a TaskPlan object from the template steps with metadata.
        
        Args:
            goal: Original task goal
            template_name: Name of matched template
            steps: Populated step list
            complexity: Task complexity classification
            parameters: Extracted parameters
            confidence: Template match confidence
            
        Returns:
            TaskPlan: Complete task plan
        """
        plan_id = str(uuid4())
        
        # Estimate duration based on number of steps
        estimated_duration = len(steps) * 5  # 5 seconds per step estimate
        
        # Build metadata
        metadata = {
            "template_name": template_name,
            "match_confidence": confidence,
            "parameters": parameters,
            "rule_based": True
        }
        
        # Create plan
        plan = TaskPlan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
            complexity=complexity.level,
            planning_approach="rule_based",
            status=PlanStatus.VALID,
            estimated_duration_seconds=estimated_duration,
            metadata=metadata
        )
        
        return plan
    
    def _generate_llm_plan(
        self,
        goal: str,
        context: PlanningContext,
        complexity: ComplexityClassification
    ) -> Optional[TaskPlan]:
        """
        Generate plan using LLM for complex tasks
        
        Uses the model router to call an LLM for task decomposition
        and step generation. Implements retry logic with validation
        and graceful error handling.
        
        Args:
            goal: Task goal description
            context: Planning context
            complexity: Complexity classification
            
        Returns:
            TaskPlan or None if LLM planning fails
        """
        with self.tracer.start_span("hybrid_planner.generate_llm_plan") as span:
            span.set_attribute("goal", goal)
            span.set_attribute("complexity", complexity.level.value)
            
            self.logger.info(
                "Attempting LLM-based planning",
                extra={
                    "goal": goal,
                    "complexity": complexity.level.value,
                    "estimated_steps": complexity.estimated_steps
                }
            )
            
            try:
                # Step 1: Create prompt for task decomposition
                prompt = self._create_planning_prompt(goal, context, complexity)
                
                # Step 2: Call LLM with retry logic
                llm_response = self._call_llm_with_retry(prompt, context)
                
                if llm_response is None:
                    self.logger.error("LLM call failed after retries")
                    return None
                
                # Step 3: Parse LLM response into TaskPlan
                plan = self._parse_llm_response(llm_response, goal, complexity)
                
                if plan is None:
                    self.logger.error("Failed to parse LLM response into plan")
                    return None
                
                self.logger.info(
                    "LLM-based plan generated successfully",
                    extra={
                        "plan_id": plan.plan_id,
                        "steps_count": len(plan.steps),
                        "estimated_duration": plan.estimated_duration_seconds
                    }
                )
                
                return plan
                
            except Exception as e:
                self.logger.error(
                    "LLM planning failed with exception",
                    extra={
                        "error": str(e),
                        "goal": goal
                    }
                )
                return None
    
    def _create_planning_prompt(
        self,
        goal: str,
        context: PlanningContext,
        complexity: ComplexityClassification
    ) -> str:
        """
        Create prompt for LLM task decomposition
        
        Builds a structured prompt that includes the goal, available tools,
        context, and explicit formatting instructions for JSON output.
        
        Args:
            goal: Task goal description
            context: Planning context with available tools
            complexity: Task complexity classification
            
        Returns:
            Formatted prompt string
        """
        # Use Prompt Manager if available (Task 10), otherwise use inline template
        if self.prompt_manager is not None:
            try:
                template = self.prompt_manager.get_prompt("task_planning", version="latest")
                return self.prompt_manager.populate_template(
                    template,
                    {
                        "goal": goal,
                        "available_tools": context.available_tools,
                        "complexity": complexity.level.value,
                        "estimated_steps": complexity.estimated_steps,
                        "constraints": context.constraints
                    }
                )
            except Exception as e:
                self.logger.warning(
                    "Failed to use Prompt Manager, falling back to inline template",
                    extra={"error": str(e)}
                )
        
        # Inline template (placeholder until Task 10 is complete)
        prompt = f"""You are a task planning assistant. Your job is to decompose a user's goal into a detailed, executable plan.

**Goal:** {goal}

**Available Tools:**
{self._format_tools_list(context.available_tools)}

**Task Complexity:** {complexity.level.value}
**Estimated Steps:** {complexity.estimated_steps}

**Context:**
- User Preferences: {json.dumps(context.user_preferences) if context.user_preferences else "None"}
- Constraints: {json.dumps(context.constraints) if context.constraints else "None"}

**Instructions:**
1. Break down the goal into clear, sequential steps
2. For each step, specify:
   - A unique step_id (e.g., "step_1", "step_2")
   - A clear description of what the step does
   - The tool to use from the available tools list
   - Parameters needed for the tool (as a dictionary)
   - Dependencies on other steps (list of step_ids that must complete first)
   - Estimated duration in seconds
3. Consider dependencies between steps - some steps may need to wait for others
4. Be specific about parameters - use concrete values when possible
5. Keep the plan focused and efficient

**Output Format:**
Respond with ONLY valid JSON in this exact format (no additional text):

{{
  "goal": "{goal}",
  "steps": [
    {{
      "step_id": "step_1",
      "description": "Clear description of what this step does",
      "tool": "tool_name_from_available_tools",
      "parameters": {{"param1": "value1", "param2": "value2"}},
      "dependencies": [],
      "estimated_duration_seconds": 5
    }},
    {{
      "step_id": "step_2",
      "description": "Another step description",
      "tool": "another_tool_name",
      "parameters": {{"param": "value"}},
      "dependencies": ["step_1"],
      "estimated_duration_seconds": 10
    }}
  ],
  "estimated_total_duration_seconds": 15,
  "complexity": "{complexity.level.value}",
  "confidence": 0.85
}}

**Important:**
- Response MUST be valid JSON only
- Use double quotes for strings
- Include all required fields for each step
- step_id must be unique
- dependencies must reference valid step_ids
- confidence should be between 0.0 and 1.0

Generate the plan now:"""
        
        return prompt
    
    def _format_tools_list(self, tools: List[str]) -> str:
        """
        Format available tools list for prompt
        
        Args:
            tools: List of available tool names
            
        Returns:
            Formatted string listing tools
        """
        if not tools:
            return "No tools available"
        
        # If tool registry is available, get tool descriptions
        if self.tool_registry is not None:
            try:
                tool_descriptions = []
                for tool_name in tools:
                    tool_def = self.tool_registry.get_tool(tool_name)
                    if tool_def:
                        tool_descriptions.append(
                            f"  - {tool_name}: {tool_def.description}"
                        )
                    else:
                        tool_descriptions.append(f"  - {tool_name}")
                return "\n".join(tool_descriptions)
            except Exception as e:
                self.logger.warning(
                    "Failed to get tool descriptions from registry",
                    extra={"error": str(e)}
                )
        
        # Fallback: simple list
        return "\n".join(f"  - {tool}" for tool in tools)
    
    def _call_llm_with_retry(
        self,
        prompt: str,
        context: PlanningContext,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Call LLM with retry logic and validation
        
        Uses Model Router if available (Task 9), otherwise uses mock LLM.
        Implements retry logic with exponential backoff and prompt enhancement.
        
        Args:
            prompt: Formatted prompt for LLM
            context: Planning context
            max_retries: Maximum retry attempts
            
        Returns:
            Parsed JSON response or None if all attempts fail
        """
        from llm_schema_validator import get_llm_schema_validator, SchemaType
        from llm_retry_manager import get_llm_retry_manager, RetryConfig
        
        validator = get_llm_schema_validator()
        retry_manager = get_llm_retry_manager(
            RetryConfig(
                max_retries=max_retries,
                initial_delay_seconds=1.0,
                max_delay_seconds=10.0,
                backoff_multiplier=2.0
            )
        )
        
        # Define LLM call operation
        def llm_operation(prompt_text: str) -> Dict[str, Any]:
            """Execute LLM call"""
            if self.model_router is not None:
                # Use Model Router (Task 9) when available
                try:
                    response = self.model_router.route_request({
                        "task_type": "planning",
                        "prompt": prompt_text,
                        "max_tokens": 2000,
                        "temperature": 0.7
                    })
                    return response
                except Exception as e:
                    self.logger.error(
                        "Model Router call failed",
                        extra={"error": str(e)}
                    )
                    raise
            else:
                # Mock LLM response (placeholder until Task 9)
                self.logger.warning(
                    "Model Router not available, using mock LLM response"
                )
                return self._mock_llm_response(prompt_text, context)
        
        # Define validation operation
        def validate_operation(response: Dict[str, Any]) -> Dict[str, Any]:
            """Validate LLM response"""
            return validator.validate_or_raise(
                SchemaType.PLAN_GENERATION,
                response
            )
        
        # Execute with retry
        result = retry_manager.retry_with_validation(
            llm_operation,
            validate_operation,
            "llm_planning",
            prompt
        )
        
        if result.success:
            self.logger.info(
                "LLM call succeeded",
                extra={
                    "attempts": result.attempts,
                    "total_delay": result.total_delay_seconds
                }
            )
            return result.final_result
        else:
            self.logger.error(
                "LLM call failed after retries",
                extra={
                    "attempts": result.attempts,
                    "error": result.error
                }
            )
            return None
    
    def _mock_llm_response(
        self,
        prompt: str,
        context: PlanningContext
    ) -> Dict[str, Any]:
        """
        Generate mock LLM response for testing
        
        This is a placeholder until Model Router (Task 9) is implemented.
        Generates a simple plan based on available tools.
        
        Args:
            prompt: LLM prompt
            context: Planning context
            
        Returns:
            Mock plan response in expected format
        """
        # Extract goal from prompt
        goal_match = re.search(r'\*\*Goal:\*\*\s+(.+?)(?:\n|$)', prompt)
        goal = goal_match.group(1) if goal_match else "Unknown goal"
        
        # Generate simple mock plan
        steps = []
        available_tools = context.available_tools[:3]  # Use first 3 tools
        
        for i, tool in enumerate(available_tools, 1):
            steps.append({
                "step_id": f"step_{i}",
                "description": f"Execute {tool} for the task",
                "tool": tool,
                "parameters": {"input": "placeholder"},
                "dependencies": [f"step_{i-1}"] if i > 1 else [],
                "estimated_duration_seconds": 5
            })
        
        # If no tools available, create a generic step
        if not steps:
            steps.append({
                "step_id": "step_1",
                "description": "Complete the task",
                "tool": "generic_executor",
                "parameters": {},
                "dependencies": [],
                "estimated_duration_seconds": 10
            })
        
        return {
            "goal": goal,
            "steps": steps,
            "estimated_total_duration_seconds": sum(s["estimated_duration_seconds"] for s in steps),
            "complexity": "moderate",
            "confidence": 0.7
        }
    
    def _parse_llm_response(
        self,
        response: Dict[str, Any],
        goal: str,
        complexity: ComplexityClassification
    ) -> Optional[TaskPlan]:
        """
        Parse validated LLM response into TaskPlan
        
        Converts the LLM's JSON response into a TaskPlan object with
        proper metadata and status.
        
        Args:
            response: Validated LLM response
            goal: Original task goal
            complexity: Task complexity classification
            
        Returns:
            TaskPlan or None if parsing fails
        """
        try:
            plan_id = str(uuid4())
            
            # Extract steps from response
            steps = response.get("steps", [])
            
            # Validate steps are not empty
            if not steps:
                self.logger.error("LLM response contains no steps")
                return None
            
            # Extract metadata
            estimated_duration = response.get(
                "estimated_total_duration_seconds",
                sum(s.get("estimated_duration_seconds", 5) for s in steps)
            )
            
            llm_confidence = response.get("confidence", 0.5)
            llm_complexity = response.get("complexity", complexity.level.value)
            
            # Build dependencies list
            dependencies = []
            for step in steps:
                step_deps = step.get("dependencies", [])
                dependencies.extend(step_deps)
            dependencies = list(set(dependencies))  # Remove duplicates
            
            # Create metadata
            metadata = {
                "llm_based": True,
                "llm_confidence": llm_confidence,
                "llm_complexity": llm_complexity,
                "classification_complexity": complexity.level.value,
                "classification_confidence": complexity.confidence,
                "estimated_steps": complexity.estimated_steps,
                "actual_steps": len(steps)
            }
            
            # Create TaskPlan
            plan = TaskPlan(
                plan_id=plan_id,
                goal=goal,
                steps=steps,
                complexity=complexity.level,
                planning_approach="llm_based",
                status=PlanStatus.VALID,
                estimated_duration_seconds=estimated_duration,
                dependencies=dependencies,
                metadata=metadata
            )
            
            self.logger.debug(
                "LLM response parsed successfully",
                extra={
                    "plan_id": plan_id,
                    "steps_count": len(steps),
                    "dependencies_count": len(dependencies)
                }
            )
            
            return plan
            
        except Exception as e:
            self.logger.error(
                "Failed to parse LLM response",
                extra={
                    "error": str(e),
                    "response": response
                }
            )
            return None
    
    def validate_plan(self, plan: TaskPlan, context: PlanningContext) -> ValidationResult:
        """
        Validate that plan is executable with available tools
        
        Checks plan for errors, missing dependencies, circular dependencies,
        and tool availability. Validates required fields, step ordering,
        and dependency graph integrity.
        
        Args:
            plan: Task plan to validate
            context: Planning context with available tools
            
        Returns:
            ValidationResult: Validation status and identified issues
        """
        with self.tracer.start_span("hybrid_planner.validate_plan") as span:
            span.set_attribute("plan_id", plan.plan_id)
            
            errors: List[str] = []
            warnings: List[str] = []
            suggestions: List[str] = []
            
            # 1. Check plan has steps
            if not plan.steps:
                errors.append("Plan has no steps")
            
            # 2. Check required fields on each step
            step_ids: set = set()
            for i, step in enumerate(plan.steps):
                step_id = step.get("step_id") or step.get("id") or f"step_{i+1}"
                
                # Ensure step has a description
                if not step.get("description"):
                    warnings.append(f"Step {step_id} is missing a description")
                
                # Ensure step has a tool
                tool_name = step.get("tool")
                if not tool_name:
                    errors.append(f"Step {step_id} is missing a tool")
                else:
                    # Check tool is available
                    if context.available_tools and tool_name not in context.available_tools:
                        # Allow generic/internal tools that may not be in the registry
                        generic_tools = {
                            "llm", "generic_executor", "data_processor",
                            "system_monitor", "system_executor"
                        }
                        if tool_name not in generic_tools:
                            errors.append(
                                f"Step {step_id} references unavailable tool '{tool_name}'. "
                                f"Available: {context.available_tools}"
                            )
                            suggestions.append(
                                f"Replace '{tool_name}' with one of: {', '.join(context.available_tools[:3])}"
                            )
                
                step_ids.add(step_id)
            
            # 3. Validate dependencies reference valid step_ids
            for i, step in enumerate(plan.steps):
                step_id = step.get("step_id") or step.get("id") or f"step_{i+1}"
                deps = step.get("dependencies", [])
                for dep in deps:
                    if dep not in step_ids:
                        errors.append(
                            f"Step {step_id} has invalid dependency '{dep}' "
                            f"(step does not exist)"
                        )
            
            # 4. Detect circular dependencies using DFS
            if not errors:  # Only check if no other errors
                dep_graph: Dict[str, List[str]] = {}
                for i, step in enumerate(plan.steps):
                    step_id = step.get("step_id") or step.get("id") or f"step_{i+1}"
                    dep_graph[step_id] = step.get("dependencies", [])
                
                cycle = self._detect_cycle(dep_graph)
                if cycle:
                    errors.append(f"Circular dependency detected: {' -> '.join(cycle)}")
            
            # 5. Check plan doesn't exceed max steps
            if len(plan.steps) > self.max_plan_steps:
                warnings.append(
                    f"Plan has {len(plan.steps)} steps, exceeding max of {self.max_plan_steps}"
                )
                suggestions.append("Consider breaking this into multiple sub-tasks")
            
            # 6. Check goal is present
            if not plan.goal or not plan.goal.strip():
                errors.append("Plan is missing a goal")
            
            # Determine status
            is_valid = len(errors) == 0
            if is_valid:
                status = PlanStatus.VALID
            elif not plan.steps:
                status = PlanStatus.INCOMPLETE
            else:
                status = PlanStatus.INVALID
            
            result = ValidationResult(
                is_valid=is_valid,
                status=status,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions
            )
            
            span.set_attribute("is_valid", is_valid)
            span.set_attribute("error_count", len(errors))
            span.set_attribute("warning_count", len(warnings))
            
            self.logger.debug(
                "Plan validation complete",
                extra={
                    "plan_id": plan.plan_id,
                    "is_valid": is_valid,
                    "errors": errors,
                    "warnings": warnings
                }
            )
            
            return result
    
    def _detect_cycle(self, graph: Dict[str, List[str]]) -> Optional[List[str]]:
        """
        Detect cycles in dependency graph using DFS
        
        Args:
            graph: Adjacency list {node: [dependencies]}
            
        Returns:
            List of nodes forming a cycle, or None if no cycle
        """
        visited: set = set()
        rec_stack: set = set()
        path: List[str] = []
        
        def dfs(node: str) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    result = dfs(neighbor)
                    if result is not None:
                        return result
                elif neighbor in rec_stack:
                    # Found cycle - return the cycle path
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
            
            path.pop()
            rec_stack.discard(node)
            return None
        
        for node in graph:
            if node not in visited:
                cycle = dfs(node)
                if cycle:
                    return cycle
        
        return None
    
    def repair_plan(self, plan: TaskPlan, error: PlanError, context: PlanningContext) -> TaskPlan:
        """
        Fix invalid or incomplete plans
        
        Attempts to repair the plan by addressing identified errors:
        - Adds missing required fields to steps
        - Replaces invalid tool references with available alternatives
        - Removes steps with unresolvable dependencies
        - Adds a fallback step when plan is empty
        - Fixes ordering issues
        
        Args:
            plan: Invalid task plan
            error: Error that caused plan failure
            context: Planning context
            
        Returns:
            TaskPlan: Repaired plan (status set to REPAIRED)
        """
        with self.tracer.start_span("hybrid_planner.repair_plan") as span:
            span.set_attribute("plan_id", plan.plan_id)
            span.set_attribute("error_type", error.error_type)
            
            self.logger.info(
                "Attempting plan repair",
                extra={
                    "plan_id": plan.plan_id,
                    "error_type": error.error_type,
                    "description": error.description
                }
            )
            
            repaired_steps = list(plan.steps)  # Work on a copy
            
            # Repair 1: Handle empty plan
            if not repaired_steps:
                self.logger.warning("Plan has no steps, adding fallback step")
                fallback_tool = context.available_tools[0] if context.available_tools else "generic_executor"
                repaired_steps.append({
                    "step_id": "step_1",
                    "description": f"Execute task: {plan.goal}",
                    "tool": fallback_tool,
                    "parameters": {"goal": plan.goal},
                    "dependencies": [],
                    "estimated_duration_seconds": 10
                })
            
            # Repair 2: Fix missing required fields on each step
            valid_step_ids: set = set()
            for i, step in enumerate(repaired_steps):
                # Ensure step_id exists
                if not step.get("step_id") and not step.get("id"):
                    step["step_id"] = f"step_{i+1}"
                
                step_id = step.get("step_id") or step.get("id")
                valid_step_ids.add(step_id)
                
                # Ensure description exists
                if not step.get("description"):
                    tool = step.get("tool", "unknown")
                    step["description"] = f"Execute {tool} operation"
                
                # Ensure parameters dict exists
                if "parameters" not in step:
                    step["parameters"] = {}
                
                # Ensure dependencies list exists
                if "dependencies" not in step:
                    step["dependencies"] = []
                
                # Ensure estimated_duration exists
                if "estimated_duration_seconds" not in step:
                    step["estimated_duration_seconds"] = 5
            
            # Repair 3: Fix invalid tool references
            if context.available_tools:
                generic_tools = {
                    "llm", "generic_executor", "data_processor",
                    "system_monitor", "system_executor"
                }
                for step in repaired_steps:
                    tool_name = step.get("tool", "")
                    if tool_name and tool_name not in context.available_tools and tool_name not in generic_tools:
                        # Try to find a suitable replacement
                        replacement = self._find_tool_replacement(tool_name, context.available_tools)
                        if replacement:
                            self.logger.info(
                                f"Replacing invalid tool '{tool_name}' with '{replacement}'",
                                extra={"step_id": step.get("step_id")}
                            )
                            step["tool"] = replacement
                        else:
                            # Use first available tool as last resort
                            step["tool"] = context.available_tools[0]
                            self.logger.warning(
                                f"No suitable replacement for '{tool_name}', using '{context.available_tools[0]}'",
                                extra={"step_id": step.get("step_id")}
                            )
            
            # Repair 4: Fix invalid dependencies (remove references to non-existent steps)
            for step in repaired_steps:
                original_deps = step.get("dependencies", [])
                valid_deps = [dep for dep in original_deps if dep in valid_step_ids]
                if len(valid_deps) != len(original_deps):
                    removed = set(original_deps) - set(valid_deps)
                    self.logger.warning(
                        f"Removed invalid dependencies: {removed}",
                        extra={"step_id": step.get("step_id")}
                    )
                    step["dependencies"] = valid_deps
            
            # Repair 5: Break circular dependencies by removing back-edges
            dep_graph: Dict[str, List[str]] = {
                (step.get("step_id") or step.get("id")): step.get("dependencies", [])
                for step in repaired_steps
            }
            cycle = self._detect_cycle(dep_graph)
            if cycle and len(cycle) >= 2:
                # Remove the last edge in the cycle to break it
                last_node = cycle[-2]
                back_node = cycle[-1]
                for step in repaired_steps:
                    step_id = step.get("step_id") or step.get("id")
                    if step_id == last_node and back_node in step.get("dependencies", []):
                        step["dependencies"].remove(back_node)
                        self.logger.warning(
                            f"Broke circular dependency: removed {back_node} from {last_node}'s deps"
                        )
                        break
            
            # Build repaired plan
            repaired_plan = TaskPlan(
                plan_id=plan.plan_id,
                goal=plan.goal,
                steps=repaired_steps,
                complexity=plan.complexity,
                planning_approach=plan.planning_approach,
                status=PlanStatus.REPAIRED,
                estimated_duration_seconds=plan.estimated_duration_seconds,
                dependencies=plan.dependencies,
                metadata={**plan.metadata, "repaired": True, "repair_reason": error.description}
            )
            
            span.set_attribute("repaired_steps_count", len(repaired_steps))
            
            self.logger.info(
                "Plan repair complete",
                extra={
                    "plan_id": plan.plan_id,
                    "original_steps": len(plan.steps),
                    "repaired_steps": len(repaired_steps)
                }
            )
            
            return repaired_plan
    
    def _find_tool_replacement(self, invalid_tool: str, available_tools: List[str]) -> Optional[str]:
        """
        Find a suitable replacement for an invalid tool reference
        
        Uses keyword matching to find the most semantically similar available tool.
        
        Args:
            invalid_tool: Tool name that is not available
            available_tools: List of available tool names
            
        Returns:
            Best matching available tool name, or None
        """
        if not available_tools:
            return None
        
        # Tool category mappings for replacement
        tool_categories = {
            "file": ["file_manager", "document_reader"],
            "web": ["browser_agent", "api_caller"],
            "browser": ["browser_agent"],
            "search": ["browser_agent", "knowledge_manager"],
            "knowledge": ["knowledge_manager"],
            "memory": ["memory_system"],
            "code": ["python_executor"],
            "python": ["python_executor"],
            "database": ["database_query"],
            "db": ["database_query"],
            "api": ["api_caller"],
            "http": ["api_caller"],
            "document": ["document_reader", "file_manager"],
            "pdf": ["document_reader"],
        }
        
        invalid_lower = invalid_tool.lower()
        
        # Check if any category keyword matches the invalid tool name
        for category, replacements in tool_categories.items():
            if category in invalid_lower:
                for replacement in replacements:
                    if replacement in available_tools:
                        return replacement
        
        # Fallback: find tool with most character overlap
        best_match = None
        best_score = 0
        for tool in available_tools:
            # Simple character overlap score
            common = sum(1 for c in invalid_lower if c in tool.lower())
            if common > best_score:
                best_score = common
                best_match = tool
        
        return best_match if best_score > 2 else None
    
    def select_tool(
        self,
        task_step: Dict[str, Any],
        available_tools: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> ToolSelection:
        """
        Select most appropriate tool with confidence scoring
        
        Analyzes the task step requirements and matches against available
        tools using capability matching and historical performance data.
        
        Scoring formula (from design doc):
          score = capability_match * 0.3 + historical_success * 0.25 +
                  confidence * 0.25 + speed * 0.15 + cost_efficiency * 0.05
        
        Args:
            task_step: Step description with requirements (action, description, tool hint)
            available_tools: List of available tool names
            context: Optional execution context with tool statistics
            
        Returns:
            ToolSelection: Selected tool with confidence and alternatives
        """
        if not available_tools:
            return ToolSelection(
                tool_name="unknown",
                confidence=0.0,
                reasoning="No tools available"
            )
        
        # Tool capability keywords for matching
        TOOL_CAPABILITIES: Dict[str, List[str]] = {
            "file_manager": [
                "file", "read", "write", "save", "open", "create", "delete",
                "move", "copy", "list", "directory", "folder", "path", "document"
            ],
            "browser_agent": [
                "search", "web", "url", "fetch", "browse", "scrape", "extract",
                "website", "internet", "online", "google", "http", "download"
            ],
            "knowledge_manager": [
                "knowledge", "search", "retrieve", "query", "find", "lookup",
                "information", "database", "index"
            ],
            "memory_system": [
                "memory", "remember", "recall", "store", "retrieve", "history",
                "context", "session"
            ],
            "python_executor": [
                "python", "code", "execute", "run", "script", "compute",
                "calculate", "process", "transform"
            ],
            "database_query": [
                "database", "sql", "query", "table", "select", "db", "record"
            ],
            "api_caller": [
                "api", "http", "rest", "request", "endpoint", "call", "post",
                "get", "put", "patch", "delete", "webhook"
            ],
            "document_reader": [
                "document", "pdf", "docx", "read", "parse", "extract", "text",
                "markdown", "txt"
            ],
            "llm": [
                "summarize", "analyze", "generate", "explain", "classify",
                "translate", "reason", "think", "plan", "describe"
            ],
            "system_executor": [
                "command", "shell", "execute", "run", "system", "process",
                "terminal", "bash", "cmd"
            ],
            "system_monitor": [
                "status", "health", "monitor", "check", "metrics", "performance",
                "uptime", "service"
            ],
            "data_processor": [
                "data", "process", "transform", "convert", "format", "parse",
                "analyze", "statistics", "csv", "json", "xml"
            ],
        }
        
        # Extract step description for matching
        step_description = " ".join([
            str(task_step.get("description", "")),
            str(task_step.get("action", "")),
            str(task_step.get("tool", "")),
            str(task_step.get("param", ""))
        ]).lower()
        
        # Get tool statistics from context if available
        tool_stats: Dict[str, Dict[str, float]] = {}
        if context and "tool_statistics" in context:
            tool_stats = context["tool_statistics"]
        
        # Score each available tool
        tool_scores: List[Tuple[str, float, str]] = []
        
        for tool_name in available_tools:
            # 1. Capability match score (0.0 - 1.0)
            capabilities = TOOL_CAPABILITIES.get(tool_name, [tool_name])
            matched_caps = [cap for cap in capabilities if cap in step_description]
            capability_score = min(len(matched_caps) / max(len(capabilities), 1), 1.0)
            
            # Boost if tool is explicitly mentioned in step
            if tool_name in step_description or tool_name.replace("_", " ") in step_description:
                capability_score = min(capability_score + 0.4, 1.0)
            
            # 2. Historical success rate (0.0 - 1.0)
            stats = tool_stats.get(tool_name, {})
            historical_success = stats.get("success_rate", 0.7)  # Default 70%
            
            # 3. Confidence score from tool registry or default
            confidence_score = stats.get("confidence", 0.7)
            
            # 4. Execution speed score (0.0 - 1.0, higher = faster)
            avg_duration = stats.get("avg_duration_seconds", 5.0)
            speed_score = max(0.0, 1.0 - (avg_duration / 60.0))  # Normalize to 60s max
            
            # 5. Cost efficiency score (0.0 - 1.0)
            cost_score = stats.get("cost_efficiency", 0.8)
            
            # Weighted composite score (from design doc)
            composite_score = (
                capability_score * 0.30 +
                historical_success * 0.25 +
                confidence_score * 0.25 +
                speed_score * 0.15 +
                cost_score * 0.05
            )
            
            reasoning_parts = []
            if matched_caps:
                reasoning_parts.append(f"matches capabilities: {', '.join(matched_caps[:3])}")
            if historical_success > 0.8:
                reasoning_parts.append(f"high success rate ({historical_success:.0%})")
            
            reasoning = f"Score {composite_score:.2f}: " + (
                "; ".join(reasoning_parts) if reasoning_parts else "general match"
            )
            
            tool_scores.append((tool_name, composite_score, reasoning))
        
        # Sort by score descending
        tool_scores.sort(key=lambda x: x[1], reverse=True)
        
        if not tool_scores:
            return ToolSelection(
                tool_name=available_tools[0],
                confidence=0.5,
                reasoning="Default selection (no scoring data)"
            )
        
        best_tool, best_score, best_reasoning = tool_scores[0]
        
        # Build alternatives list (top 3 excluding best)
        alternatives = [
            (name, score)
            for name, score, _ in tool_scores[1:4]
        ]
        
        # Determine fallback tool (second best)
        fallback_tool = tool_scores[1][0] if len(tool_scores) > 1 else None
        
        return ToolSelection(
            tool_name=best_tool,
            confidence=round(best_score, 3),
            reasoning=best_reasoning,
            parameters=task_step.get("parameters", {}),
            alternatives=alternatives,
            fallback_tool=fallback_tool
        )
    
    def _repair_plan_with_retries(
        self,
        plan: TaskPlan,
        validation: ValidationResult,
        context: PlanningContext
    ) -> TaskPlan:
        """
        Attempt to repair plan with multiple retries
        
        Args:
            plan: Invalid plan
            validation: Validation result with errors
            context: Planning context
            
        Returns:
            TaskPlan: Repaired plan
            
        Raises:
            ValueError: If repair fails after max attempts
        """
        for attempt in range(self.max_repair_attempts):
            self.logger.info(
                f"Plan repair attempt {attempt + 1}/{self.max_repair_attempts}",
                extra={"plan_id": plan.plan_id, "errors": validation.errors}
            )
            
            # Create error object from validation
            error = PlanError(
                error_type="validation_failed",
                description="; ".join(validation.errors),
                context={"validation": validation.to_dict()}
            )
            
            # Attempt repair
            plan = self.repair_plan(plan, error, context)
            
            # Re-validate
            validation = self.validate_plan(plan, context)
            
            if validation.is_valid:
                self.logger.info("Plan repaired successfully")
                return plan
        
        # If we get here, repair failed
        raise ValueError(f"Failed to repair plan after {self.max_repair_attempts} attempts")
    
    def _optimize_plan(self, plan: TaskPlan, context: PlanningContext) -> TaskPlan:
        """
        Optimize plan and resolve dependencies
        
        Optimizations performed:
        1. Identify steps that can run in parallel (no shared dependencies)
        2. Remove redundant steps (duplicate tool+action combinations)
        3. Resolve and validate dependency ordering
        4. Annotate steps with parallel execution groups
        
        Args:
            plan: Task plan to optimize
            context: Planning context
            
        Returns:
            TaskPlan: Optimized plan with parallel groups and clean dependencies
        """
        with self.tracer.start_span("hybrid_planner.optimize_plan") as span:
            span.set_attribute("plan_id", plan.plan_id)
            span.set_attribute("original_steps", len(plan.steps))
            
            if not plan.steps:
                return plan
            
            steps = [dict(step) for step in plan.steps]  # Deep copy
            
            # Step 1: Normalize step IDs
            for i, step in enumerate(steps):
                if not step.get("step_id") and not step.get("id"):
                    step["step_id"] = f"step_{i+1}"
            
            # Step 2: Remove redundant steps
            # A step is redundant if it has the same tool+action+parameters as a prior step
            seen_signatures: set = set()
            deduplicated_steps = []
            removed_ids: set = set()
            
            for step in steps:
                tool = step.get("tool", "")
                action = step.get("action", "")
                params = json.dumps(step.get("parameters", {}), sort_keys=True)
                signature = f"{tool}:{action}:{params}"
                
                step_id = step.get("step_id") or step.get("id")
                
                if signature in seen_signatures and action:
                    # Redundant step - skip it
                    self.logger.debug(
                        f"Removing redundant step {step_id} (duplicate of earlier step)"
                    )
                    removed_ids.add(step_id)
                else:
                    seen_signatures.add(signature)
                    deduplicated_steps.append(step)
            
            # Fix dependencies that reference removed steps
            for step in deduplicated_steps:
                step["dependencies"] = [
                    dep for dep in step.get("dependencies", [])
                    if dep not in removed_ids
                ]
            
            steps = deduplicated_steps
            
            # Step 3: Topological sort to ensure proper ordering
            # Build adjacency list
            step_map: Dict[str, Dict] = {
                (s.get("step_id") or s.get("id")): s for s in steps
            }
            
            # Kahn's algorithm for topological sort
            in_degree: Dict[str, int] = {sid: 0 for sid in step_map}
            for step in steps:
                for dep in step.get("dependencies", []):
                    if dep in in_degree:
                        in_degree[step.get("step_id") or step.get("id")] += 1
            
            # Step 4: Identify parallel execution groups
            # Steps with no dependencies on each other can run in parallel
            parallel_groups: List[List[str]] = []
            remaining = set(step_map.keys())
            completed: set = set()
            
            while remaining:
                # Find all steps whose dependencies are all completed
                ready = [
                    sid for sid in remaining
                    if all(dep in completed for dep in step_map[sid].get("dependencies", []))
                ]
                
                if not ready:
                    # Shouldn't happen after cycle removal, but handle gracefully
                    ready = list(remaining)[:1]
                
                parallel_groups.append(ready)
                
                # Annotate steps with their parallel group
                for sid in ready:
                    step_map[sid]["parallel_group"] = len(parallel_groups) - 1
                    step_map[sid]["can_parallelize"] = len(ready) > 1
                    completed.add(sid)
                    remaining.discard(sid)
            
            # Rebuild steps in topological order
            ordered_steps = []
            for group in parallel_groups:
                for sid in group:
                    ordered_steps.append(step_map[sid])
            
            # Step 5: Recalculate estimated duration accounting for parallelism
            # Duration = sum of sequential group durations (max within each parallel group)
            total_duration = 0
            for group in parallel_groups:
                group_max_duration = max(
                    step_map[sid].get("estimated_duration_seconds", 5)
                    for sid in group
                )
                total_duration += group_max_duration
            
            # Build optimized plan
            optimized_plan = TaskPlan(
                plan_id=plan.plan_id,
                goal=plan.goal,
                steps=ordered_steps,
                complexity=plan.complexity,
                planning_approach=plan.planning_approach,
                status=plan.status,
                estimated_duration_seconds=total_duration,
                dependencies=plan.dependencies,
                metadata={
                    **plan.metadata,
                    "optimized": True,
                    "parallel_groups": len(parallel_groups),
                    "original_steps": len(plan.steps),
                    "deduplicated_steps": len(ordered_steps),
                    "removed_redundant": len(plan.steps) - len(ordered_steps)
                }
            )
            
            span.set_attribute("optimized_steps", len(ordered_steps))
            span.set_attribute("parallel_groups", len(parallel_groups))
            span.set_attribute("removed_redundant", len(plan.steps) - len(ordered_steps))
            
            self.logger.info(
                "Plan optimization complete",
                extra={
                    "plan_id": plan.plan_id,
                    "original_steps": len(plan.steps),
                    "optimized_steps": len(ordered_steps),
                    "parallel_groups": len(parallel_groups),
                    "estimated_duration": total_duration
                }
            )
            
            return optimized_plan
    
    def _generate_cache_key(self, goal: str, context: PlanningContext) -> str:
        """
        Generate cache key for plan lookup
        
        Args:
            goal: Task goal
            context: Planning context
            
        Returns:
            str: Cache key hash
        """
        # Create a deterministic hash from goal and context
        cache_data = f"{goal}:{sorted(context.available_tools)}"
        return hashlib.sha256(cache_data.encode()).hexdigest()[:16]
    
    def _emit_plan_created_event(self, plan: TaskPlan) -> None:
        """
        Emit event when plan is created
        
        Args:
            plan: Created task plan
        """
        try:
            from observability import get_trace_id
            
            event = Event.create(
                event_type=EventType.PLAN_CREATED,
                source_component="hybrid_planner",
                payload={
                    "plan_id": plan.plan_id,
                    "goal": plan.goal,
                    "steps_count": len(plan.steps),
                    "complexity": plan.complexity.value,
                    "planning_approach": plan.planning_approach,
                    "status": plan.status.value
                },
                trace_id=get_trace_id(),
                correlation_id=get_correlation_id()
            )
            self.event_bus.publish(event)
        except Exception as e:
            self.logger.error(
                "Failed to emit plan created event",
                extra={"error": str(e), "plan_id": plan.plan_id}
            )

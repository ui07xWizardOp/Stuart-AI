"""
Self-Evolving Skill Engine (Feature #9: Advanced Orchestration)

Observes successful task completions recorded in the PlanLibrary, identifies
recurring patterns, and uses the LLM to generalize them into reusable
tool/skill templates.

Pipeline:
  1. Pattern Mining:  Scan PlanLibrary for plans with execution_count >= threshold
  2. Skill Generation: LLM generates a BaseTool Python skeleton from the pattern
  3. Staging:          Save to data/evolved_skills/ for review
  4. Promotion:        Copy to plugins/ for hot-loading by PluginManager
"""

import os
import json
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from observability import get_logging_system
from core.model_router import ModelRouter, ModelTier
from cognitive.plan_library import PlanLibrary


@dataclass
class EvolvedSkill:
    """A skill template generated from observed patterns."""
    skill_id: str
    source_intent: str
    tool_sequence: List[Dict[str, Any]]
    generated_code: str
    confidence: float  # 0.0 to 1.0 based on execution success rate
    execution_count: int
    created_at: str = ""
    promoted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "source_intent": self.source_intent,
            "tool_sequence": self.tool_sequence,
            "generated_code": self.generated_code[:500],
            "confidence": self.confidence,
            "execution_count": self.execution_count,
            "created_at": self.created_at,
            "promoted": self.promoted,
        }


class SkillEvolver:
    """
    Mines proven plans for recurring patterns and generates reusable
    tool templates, promoting high-confidence skills to the plugin system.

    Attributes:
        plan_library (PlanLibrary): Source of proven execution patterns.
        router (ModelRouter): LLM for generalizing patterns into code.
        evolution_threshold (int): Minimum executions before evolution triggers.
        promotion_confidence (float): Minimum confidence for auto-promotion.
    """

    EVOLVED_DIR = os.path.join("data", "evolved_skills")
    PLUGINS_DIR = "plugins"

    GENERATION_PROMPT = """You are a Skill Code Generator for the Stuart-AI agent framework.

Given a proven tool execution sequence that has been successfully used multiple times,
generate a reusable Python tool class that encapsulates this pattern.

The tool MUST:
1. Subclass BaseTool from tools.base
2. Have a unique name, description, and proper risk_level
3. Implement the execute(self, action, parameters, context) method
4. Return a ToolResult object
5. Include proper error handling
6. Include a docstring explaining what the skill does

Use this import structure:
```python
from tools.base import BaseTool, CapabilityDescriptor, ToolRiskLevel, ToolResult
from observability import get_logging_system
```

Respond with ONLY the Python code, no markdown fences or explanations."""

    def __init__(
        self,
        plan_library: PlanLibrary,
        router: ModelRouter,
        event_bus=None,
        evolution_threshold: int = 3,
        promotion_confidence: float = 0.8,
    ):
        self.logger = get_logging_system()
        self.plan_library = plan_library
        self.router = router
        self.event_bus = event_bus
        self.evolution_threshold = evolution_threshold
        self.promotion_confidence = promotion_confidence

        os.makedirs(self.EVOLVED_DIR, exist_ok=True)

        # In-memory cache of evolved skills
        self._skills: Dict[str, EvolvedSkill] = {}
        self._load_from_disk()

        self.logger.info(
            f"SkillEvolver initialized (threshold={evolution_threshold}, "
            f"confidence={promotion_confidence})."
        )

    # ── Core Pipeline ─────────────────────────────────────────────────

    def scan_and_evolve(self) -> List[EvolvedSkill]:
        """
        Master entrypoint: scan PlanLibrary for eligible patterns,
        generate skill templates for new candidates, and return results.
        """
        self.logger.info("SkillEvolver: Scanning PlanLibrary for evolution candidates...")

        candidates = self._find_candidates()
        if not candidates:
            self.logger.info("No evolution candidates found.")
            return []

        new_skills = []
        for plan_data in candidates:
            intent_hash = plan_data.get("intent_hash", "")

            # Skip if we already evolved this pattern
            if intent_hash in self._skills:
                continue

            skill = self._evolve_plan(plan_data)
            if skill:
                self._skills[skill.skill_id] = skill
                self._save_skill(skill)
                new_skills.append(skill)
                self._emit_event("skill_evolved", {
                    "skill_id": skill.skill_id,
                    "source_intent": skill.source_intent[:100],
                    "confidence": skill.confidence,
                })

        self.logger.info(f"SkillEvolver: Generated {len(new_skills)} new skill templates.")
        return new_skills

    def promote_skill(self, skill_id: str) -> str:
        """
        Promote an evolved skill to the plugins directory for hot-loading.

        Args:
            skill_id: The ID of the skill to promote.

        Returns:
            Status message.
        """
        skill = self._skills.get(skill_id)
        if not skill:
            return f"❌ Skill '{skill_id}' not found."

        if skill.promoted:
            return f"⚠️ Skill '{skill_id}' is already promoted."

        if skill.confidence < self.promotion_confidence:
            return (
                f"⚠️ Skill confidence ({skill.confidence:.2f}) is below "
                f"promotion threshold ({self.promotion_confidence}). "
                f"Use `/evolve force-promote {skill_id}` to override."
            )

        return self._do_promote(skill)

    def force_promote(self, skill_id: str) -> str:
        """Promote a skill regardless of confidence threshold."""
        skill = self._skills.get(skill_id)
        if not skill:
            return f"❌ Skill '{skill_id}' not found."
        return self._do_promote(skill)

    def _do_promote(self, skill: EvolvedSkill) -> str:
        """Actually copy skill to plugins directory."""
        filename = f"evolved_{skill.skill_id}.py"
        target = os.path.join(self.PLUGINS_DIR, filename)

        try:
            os.makedirs(self.PLUGINS_DIR, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(skill.generated_code)

            skill.promoted = True
            self._save_skill(skill)

            self._emit_event("skill_promoted", {
                "skill_id": skill.skill_id,
                "target_path": target,
            })

            self.logger.info(f"Skill '{skill.skill_id}' promoted to {target}")
            return f"✅ Skill `{skill.skill_id}` promoted to `{filename}`. Hot-reload to activate."
        except Exception as e:
            self.logger.error(f"Promotion failed: {e}")
            return f"❌ Promotion failed: {e}"

    # ── Pattern Mining ────────────────────────────────────────────────

    def _find_candidates(self) -> List[Dict[str, Any]]:
        """Find plans in PlanLibrary that meet the evolution threshold."""
        all_plans = self.plan_library.list_all_plans()
        candidates = []
        for plan_info in all_plans:
            if plan_info.get("execution_count", 0) >= self.evolution_threshold:
                # Load full plan data from disk
                intent_hash = plan_info.get("intent_hash", "")
                plan_file = os.path.join(self.plan_library.PLANS_DIR, f"{intent_hash}.json")
                if os.path.exists(plan_file):
                    try:
                        with open(plan_file, "r") as f:
                            candidates.append(json.load(f))
                    except Exception:
                        pass
        return candidates

    def _evolve_plan(self, plan_data: Dict[str, Any]) -> Optional[EvolvedSkill]:
        """Generate a skill template from a proven plan using the LLM."""
        intent = plan_data.get("original_prompt", "Unknown intent")
        sequence = plan_data.get("tool_sequence", [])
        exec_count = plan_data.get("execution_count", 1)

        if not sequence:
            return None

        # Build context for the LLM
        sequence_desc = "\n".join(
            f"  Step {i+1}: {s.get('tool', '?')}.{s.get('action', '?')}({json.dumps(s.get('parameters', {}))})"
            for i, s in enumerate(sequence)
        )

        messages = [
            {"role": "system", "content": self.GENERATION_PROMPT},
            {"role": "user", "content": (
                f"ORIGINAL USER INTENT:\n{intent}\n\n"
                f"PROVEN TOOL SEQUENCE (executed {exec_count} times successfully):\n"
                f"{sequence_desc}\n\n"
                f"Generate a reusable BaseTool class that encapsulates this workflow."
            )},
        ]

        try:
            code = self.router.execute_with_failover(messages, force_tier=ModelTier.FAST_CHEAP)

            # Clean up LLM output
            code = self._clean_code(code)

            # Generate skill ID from intent hash
            skill_id = hashlib.md5(intent.encode()).hexdigest()[:10]

            # Calculate confidence based on execution count
            confidence = min(1.0, exec_count / (self.evolution_threshold * 2))

            return EvolvedSkill(
                skill_id=skill_id,
                source_intent=intent,
                tool_sequence=sequence,
                generated_code=code,
                confidence=confidence,
                execution_count=exec_count,
                created_at=datetime.now().isoformat(),
            )
        except Exception as e:
            self.logger.error(f"Skill generation failed for '{intent[:50]}': {e}")
            return None

    # ── Utilities ─────────────────────────────────────────────────────

    def _clean_code(self, code: str) -> str:
        """Strip markdown fences and leading/trailing whitespace from LLM output."""
        code = code.strip()
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()

    def _save_skill(self, skill: EvolvedSkill):
        """Persist an evolved skill to data/evolved_skills/{id}.json."""
        path = os.path.join(self.EVOLVED_DIR, f"{skill.skill_id}.json")
        try:
            data = {
                "skill_id": skill.skill_id,
                "source_intent": skill.source_intent,
                "tool_sequence": skill.tool_sequence,
                "generated_code": skill.generated_code,
                "confidence": skill.confidence,
                "execution_count": skill.execution_count,
                "created_at": skill.created_at,
                "promoted": skill.promoted,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save evolved skill: {e}")

    def _load_from_disk(self):
        """Load persisted evolved skills from disk."""
        if not os.path.exists(self.EVOLVED_DIR):
            return
        for filename in os.listdir(self.EVOLVED_DIR):
            if not filename.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.EVOLVED_DIR, filename), "r") as f:
                    data = json.load(f)
                skill = EvolvedSkill(
                    skill_id=data["skill_id"],
                    source_intent=data.get("source_intent", ""),
                    tool_sequence=data.get("tool_sequence", []),
                    generated_code=data.get("generated_code", ""),
                    confidence=data.get("confidence", 0.0),
                    execution_count=data.get("execution_count", 0),
                    created_at=data.get("created_at", ""),
                    promoted=data.get("promoted", False),
                )
                self._skills[skill.skill_id] = skill
            except Exception as e:
                self.logger.warning(f"Failed to load evolved skill {filename}: {e}")

        if self._skills:
            self.logger.info(f"Loaded {len(self._skills)} evolved skills from disk.")

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all evolved skills with their status."""
        return [
            {
                "skill_id": s.skill_id,
                "source_intent": s.source_intent[:60],
                "confidence": f"{s.confidence:.2f}",
                "executions": s.execution_count,
                "promoted": "✅" if s.promoted else "❌",
                "created_at": s.created_at,
            }
            for s in self._skills.values()
        ]

    def get_status(self) -> str:
        """Get a formatted status report of the skill evolution engine."""
        total = len(self._skills)
        promoted = sum(1 for s in self._skills.values() if s.promoted)
        candidates = len(self._find_candidates())

        lines = [
            "## 🧬 Skill Evolution Engine Status\n",
            f"**Evolved Skills:** {total}",
            f"**Promoted to Plugins:** {promoted}",
            f"**Pending Candidates:** {candidates}",
            f"**Evolution Threshold:** {self.evolution_threshold} executions",
            f"**Promotion Confidence:** {self.promotion_confidence:.0%}",
        ]

        if self._skills:
            lines.append("\n### Evolved Skills:")
            for s in self._skills.values():
                icon = "🟢" if s.promoted else "🟡"
                lines.append(
                    f"  {icon} `{s.skill_id}` — {s.source_intent[:50]}... "
                    f"(conf={s.confidence:.2f}, runs={s.execution_count})"
                )

        return "\n".join(lines)

    def _emit_event(self, event_type: str, payload: Dict[str, Any]):
        """Emit an evolution event on the EventBus."""
        if not self.event_bus:
            return
        try:
            from events.event_types import Event, EventType
            from uuid import uuid4
            event = Event.create(
                event_type=EventType(event_type),
                source_component="SkillEvolver",
                payload=payload,
                trace_id=uuid4().hex[:16],
                correlation_id=uuid4().hex[:16],
            )
            self.event_bus.publish(event)
        except Exception as e:
            self.logger.debug(f"Event emit failed (non-fatal): {e}")

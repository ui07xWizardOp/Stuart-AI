"""
Phase 10: RAG & Second Brain
Flat File Memory (Auto-Consolidator)

Summarizes short-term and persistent memory into a single
human-readable `MEMORY.md` file.
"""

import os
from pathlib import Path
from datetime import datetime

from observability import get_logging_system


class AutoConsolidator:
    """
    Nightly job that reads system conversations and updates a flat-file memory.
    """
    
    MEMORY_FILE = os.path.join("data", "MEMORY.md")
    
    def __init__(self, orchestrator=None):
        """
        Takes an optional orchestrator to use its LLM provider for summarization.
        """
        self.logger = get_logging_system()
        self.orchestrator = orchestrator
        os.makedirs(os.path.dirname(self.MEMORY_FILE), exist_ok=True)
        
    def run_consolidation(self) -> str:
        """
        Execute the consolidation process.
        """
        self.logger.info("Starting Auto-Consolidation for MEMORY.md")
        
        # 1. Gather recent memories.
        # Check if orchestrator and its memory components exist
        if not self.orchestrator or not hasattr(self.orchestrator, 'context_manager'):
            return "❌ Consolidator requires Orchestrator reference."
            
        memory = self.orchestrator.context_manager.memory
        if not memory:
            return "❌ Memory system not found in context."

        short_term_text = ""
        for entry in memory.short_term.get_all():
            short_term_text += f"[{entry.timestamp}] {entry.role}: {entry.content[:500]}...\n"

        if not short_term_text.strip():
            self.logger.info("No short-term memory to consolidate.")
            return "✅ No recent conversations to consolidate."

        # 2. Prepare the LLM Prompt
        system_prompt = (
            "You are a cognitive consolidator for a personal AI agent. "
            "Your task is to analyze the following recent conversation logs between the User and the Agent, "
            "and extract timeless facts, preferences, project states, and important context. "
            "Format the output strictly as Markdown bullet points under relevant headings (e.g., '## User Preferences', '## Projects'). "
            "Be extremely concise and factual. Do not include pleasantries. Only extract new or interesting information."
        )
        
        try:
            # 3. Call the LLM (via Orchestrator's model router)
            response = self.orchestrator.router.route_request([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Recent logs:\n{short_term_text[-4000:]}"} # Limit context slightly
            ])
            
            summary = response.get("content", "").strip()
            if not summary:
                return "❌ LLM returned empty consolidation."
                
            # 4. Write/Update MEMORY.md
            self._append_to_memory_file(summary)
            
            # Optional: Clear short term memory after consolidation
            # memory.short_term.clear()
            
            self.logger.info("Successfully consolidated memory.")
            return "✅ Memory successfully consolidated to MEMORY.md"
            
        except Exception as e:
            self.logger.error(f"Consolidation failed: {e}")
            return f"❌ Consolidation failed: {e}"

    def _append_to_memory_file(self, content: str):
        """Appends the newly generated markdown sections to the MEMORY.md file."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if not os.path.exists(self.MEMORY_FILE):
            header = "# Stuart Personal Agent - Human Readable Memory\n\n"
            header += "> This file is automatically consolidated. You may edit it manually.\n\n"
            Path(self.MEMORY_FILE).write_text(header, encoding="utf-8")
            
        existing_text = Path(self.MEMORY_FILE).read_text(encoding="utf-8")
        
        append_str = f"\n\n---\n### Consolidator Run: {now}\n\n{content}\n"
        Path(self.MEMORY_FILE).write_text(existing_text + append_str, encoding="utf-8")

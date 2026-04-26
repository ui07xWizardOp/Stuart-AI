"""
Cognitive Maintenance Engine (Task 23)

Prevents Agentic Dementia by continuously scanning SQLite for stale Long-Term 
memory logs, passing them to a cheap LLM to physically compress into dense insights,
and permanently deleting the high-volume raw interaction chatter (Garbage Collection).
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta

from observability import get_logging_system
from memory.memory_system import MemorySystem
from memory.short_term import MemoryRole
from core.model_router import ModelRouter, ModelTier


class CognitiveMaintenanceEngine:
    """Automates memory pruning and long-term knowledge distillation.

    Prevents 'Agentic Dementia' by periodically scanning for stale logs (older than TTL),
    compressing them using a specialized LLM context-window summarization, 
    and flushes the raw high-volume chatter into dense 'Fact Nodes'.

    Attributes:
        memory_system (MemorySystem): Access to raw SQLite storage for maintenance.
        router (ModelRouter): The model interface used for distillation prompting.
        ttl_days (int): The age threshold (in days) after which raw logs are distilled.
    """
    
    def __init__(self, memory_system: MemorySystem, router: ModelRouter, ttl_days: int = 7):
        self.logger = get_logging_system()
        self.memory_system = memory_system
        self.router = router
        self.ttl_days = ttl_days
        
        self.logger.info(f"Cognitive Maintenance initialized with TTL={ttl_days} Days.")

    def run_distillation(self) -> str:
        """
        The master entrypoint meant to be triggered by cron (e.g. daily at midnight).
        Finds raw logs older than the TTL, summarizes them, and flushes them.
        """
        self.logger.info("Executing Memory Garbage Collection & Distillation Loop...")
        
        try:
            # 1. We must query the underlying SQLite layer for old logs
            # This requires hitting the LongTermMemory instance bypassing the standard KV wrapper.
            # LongTermMemory has a conn object we can query safely.
            cursor = self.memory_system.long_term.conn.cursor()
            
            cutoff_date = (datetime.now() - timedelta(days=self.ttl_days)).strftime("%Y-%m-%d %H:%M:%S")
            
            # Fetch raw chatter from SQLite. We only target THOUGHT and OBSERVATION roles 
            # specifically categorized under "interaction_history"
            cursor.execute('''
                SELECT id, context_key, extracted_facts 
                FROM memory_facts 
                WHERE category = 'interaction_history' AND created_at < ?
                LIMIT 50
            ''', (cutoff_date,))
            
            stale_rows = cursor.fetchall()
            
            if not stale_rows:
                self.logger.info("Nothing to distill. Memory is clean.")
                return "Distillation skipped (No stale logs)."
                
            self.logger.info(f"Found {len(stale_rows)} stale records. Booting LLM compression pipeline...")
            
            # 2. Extract into a blob
            log_blob = ""
            row_ids = []
            for row in stale_rows:
                row_ids.append(row[0])
                log_blob += f"[{row[1]}]: {row[2]}\n"
                
            # 3. Prompt the ModelRouter to distill
            sys_msg = (
                "You are the Cognitive Maintenance Engine.\n"
                "Review the following RAW LOGS of past agent interactions.\n"
                "Extract any critical persistent facts (e.g., user preferences, active long-term project statuses).\n"
                "Discard all noise, tool execution errors, and minor conversational chatter.\n"
                "Output ONLY a succinct, highly dense factual summary."
            )
            
            messages = [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": f"RAW LOGS:\n{log_blob}"}
            ]
            
            # Force fast/cheap tier unconditionally for GC tasks (Ollama)
            summary = self.router.execute_with_failover(messages, force_tier=ModelTier.FAST_CHEAP)
            
            # 4. Save the distilled summary as a permanent fact
            distilled_key = f"distilled_context_{datetime.now().strftime('%Y%m%d_%H%M')}"
            self.memory_system.remember_fact(
                category="system_distilled",
                key=distilled_key,
                facts={"summary": summary}
            )
            
            # 5. Garbage Collection - DELETE the raw rows
            ids_placeholder = ','.join('?' for _ in row_ids)
            cursor.execute(f"DELETE FROM memory_facts WHERE id IN ({ids_placeholder})", row_ids)
            self.memory_system.long_term.conn.commit()
            
            self.logger.info(f"Successfully collapsed {len(stale_rows)} row interactions into 1 distilled node.")
            return f"Processed and deleted {len(row_ids)} stale records."
            
        except Exception as e:
            self.logger.error(f"Distillation pipeline crushed: {e}")
            return f"Error: {str(e)}"

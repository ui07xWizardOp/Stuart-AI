"""
Deep Research Plugin (Phase 12: Cognitive Expansion)

Implements multi-source OSINT data aggregation.
Exposes a `/research` slash command and a native `deep_research` tool.
It searches DuckDuckGo, scrapes the top N results, and uses the local LLM to
synthesize a comprehensive Markdown report.
"""

import os
import json
import time
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

import wikipedia
from observability import get_logging_system
from core.plugin_manager import StuartPlugin
from tools.base import BaseTool, ToolRiskLevel


class DeepResearchTool(BaseTool):
    name = "deep_research"
    description = "Conducts deep OSINT research on a topic, aggregating multiple sources into a markdown report."
    risk_level = ToolRiskLevel.MEDIUM
    
    def __init__(self, router, sandbox_dir: str):
        super().__init__()
        self.router = router
        self.sandbox_dir = sandbox_dir
        self.logger = get_logging_system()
        
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The specific research topic or question"},
                "num_sources": {"type": "integer", "description": "Number of top results to aggregate (max 5)"}
            },
            "required": ["topic"]
        }
        
    def execute(self, params: Dict[str, Any]) -> str:
        topic = params.get("topic")
        num_sources = min(params.get("num_sources", 3), 5)
        
        if not topic:
            return "Error: Topic is required for deep research."
            
        self.logger.info(f"Initiating Deep Research on: '{topic}'")
        
        # 1. Gather Search Results via Wikipedia
        try:
            # Search for related page titles
            search_results = wikipedia.search(topic, results=num_sources)
            if not search_results:
                return f"No Wikipedia results found for '{topic}'."
                
            raw_context_blocks = []
            for page_title in search_results:
                try:
                    page = wikipedia.page(page_title, auto_suggest=False)
                    # Extract a snippet (first 1000 chars of content to avoid token overflow)
                    snippet = page.content[:1000] + "..."
                    raw_context_blocks.append(f"Source: {page.url}\nTitle: {page.title}\nSnippet: {snippet}")
                except wikipedia.exceptions.DisambiguationError as e:
                    # Just take the first disambiguation option
                    try:
                        page = wikipedia.page(e.options[0], auto_suggest=False)
                        snippet = page.content[:1000] + "..."
                        raw_context_blocks.append(f"Source: {page.url}\nTitle: {page.title}\nSnippet: {snippet}")
                    except Exception:
                        pass
                except Exception:
                    pass
            
            if not raw_context_blocks:
                return f"Failed to extract content for '{topic}'."
                
            raw_context = "\n\n".join(raw_context_blocks)
            
        except Exception as e:
            return f"Wikipedia API failed: {e}"
        
        # 3. Synthesize via LLM
        prompt = (
            f"You are an expert OSINT research analyst.\n"
            f"Synthesize the following search results into a comprehensive markdown report about '{topic}'.\n"
            f"Include citations. Do not make up information.\n\n"
            f"---\n{raw_context}"
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        self.logger.info("Synthesizing research data using LLM...")
        try:
            # We use the local client for free synthesis to save cloud quota
            synthesis = self.router.local_client.chat(messages=messages, temperature=0.2)
        except Exception as e:
            self.logger.error(f"LLM synthesis failed: {e}")
            synthesis = f"Synthesis failed due to model error: {e}\n\nRaw Data:\n{raw_context}"
            
        # 4. Save to disk
        safe_topic = "".join(c if c.isalnum() else "_" for c in topic)[:30]
        filename = f"research_{safe_topic}_{int(time.time())}.md"
        filepath = os.path.join(self.sandbox_dir, filename)
        
        os.makedirs(self.sandbox_dir, exist_ok=True)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# Deep Research: {topic}\n\n{synthesis}")
            
            return f"✅ Deep Research Complete. Synthesized from {len(results)} sources. Report saved to `{filepath}`.\n\n{synthesis}"
        except Exception as e:
            return f"Failed to save report: {e}\n\n{synthesis}"


class DeepResearchPlugin(StuartPlugin):
    name = "DeepResearch"
    version = "1.0.0"
    description = "Provides multi-source OSINT deep research capabilities."
    
    def on_load(self, context: Dict[str, Any]):
        self.logger = context.get('logger', get_logging_system())
        
        # Get the LLM router from the slash command context to pass to the tool
        # Wait, plugin context is given via PluginManager. Let's see what we have.
        slash_router = context.get('slash_router')
        llm_router = None
        if slash_router:
            llm_router = slash_router._context.get("router")
            
        if not llm_router:
            self.logger.warning("DeepResearchPlugin could not find LLM router. Synthesis will fail.")
            
        sandbox_dir = os.path.join(os.getcwd(), "data", "sandbox", "research")
        
        self.tool = DeepResearchTool(llm_router, sandbox_dir)
        
        registry = context.get('tool_registry')
        if registry:
            registry.register_tool(self.tool)
            
        if slash_router:
            slash_router.register_command("/research", self._cmd_research, "Run an OSINT deep research report: /research <topic>")
            
        self.logger.info("DeepResearchPlugin loaded successfully.")
            
    def _cmd_research(self, args: str) -> str:
        if not args:
            return "⚠️ Please provide a topic: `/research <topic>`"
            
        # We can just proxy directly to the tool!
        return self.tool.execute({"topic": args, "num_sources": 5})

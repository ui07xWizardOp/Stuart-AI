"""
News Digest Plugin (Phase 13: Tier 3 Differentiators)

Aggregates headlines from configurable RSS feeds and uses the local LLM
to synthesize a daily intelligence briefing. Registers a `/digest` command.
"""

import os
import time
from datetime import datetime
from typing import Dict, Any, List

import feedparser
from core.plugin_manager import StuartPlugin
from observability import get_logging_system

# Default RSS feeds for general technology/science/world news
DEFAULT_FEEDS = [
    ("Hacker News", "https://hnrss.org/frontpage"),
    ("ArXiv CS.AI", "https://rss.arxiv.org/rss/cs.AI"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
]


class NewsDigestPlugin(StuartPlugin):
    name = "NewsDigest"
    version = "1.0.0"
    description = "Generates daily intelligence briefings from curated RSS feeds."

    def on_load(self, context: Dict[str, Any]):
        self.logger = context.get('logger', get_logging_system())
        self.slash_router = context.get('slash_router')
        self.llm_router = None

        if self.slash_router:
            self.llm_router = self.slash_router._context.get("router")
            self.slash_router.register_command(
                "/digest",
                self._cmd_digest,
                "Generate an intelligence briefing: /digest [tech|science|all]"
            )

        self.logger.info("NewsDigestPlugin loaded successfully.")

    def _cmd_digest(self, args: str) -> str:
        """Generate a news digest from RSS feeds."""
        topic_filter = args.strip().lower() if args.strip() else "all"

        self.logger.info(f"Generating news digest (filter: {topic_filter})...")

        # 1. Fetch headlines from RSS feeds
        all_headlines = []
        for feed_name, feed_url in DEFAULT_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                entries = feed.entries[:5]  # Top 5 per source
                for entry in entries:
                    all_headlines.append({
                        "source": feed_name,
                        "title": entry.get("title", "No title"),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", "")[:200],
                    })
            except Exception as e:
                self.logger.warning(f"Failed to fetch RSS feed '{feed_name}': {e}")

        if not all_headlines:
            return "?? Could not fetch any headlines from RSS feeds. Check your network connection."

        # 2. Format raw context
        raw_text = "\n".join([
            f"[{h['source']}] {h['title']}\n  Link: {h['link']}\n  Summary: {h['summary']}"
            for h in all_headlines
        ])

        # 3. Synthesize via LLM
        digest_text = self._synthesize(raw_text, topic_filter)

        # 4. Save to disk
        digest_dir = os.path.join("data", "sandbox", "digests")
        os.makedirs(digest_dir, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        filepath = os.path.join(digest_dir, f"digest_{date_str}.md")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# Intelligence Briefing ? {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                f.write(digest_text)
        except Exception as e:
            self.logger.error(f"Failed to save digest: {e}")

        return (
            f"? **Intelligence Briefing** ({len(all_headlines)} headlines aggregated)\n"
            f"Saved to `{filepath}`\n\n"
            f"{digest_text}"
        )

    def _synthesize(self, raw_text: str, topic_filter: str) -> str:
        """Use local LLM to synthesize the briefing."""
        if not self.llm_router:
            # Fallback: just format the raw headlines
            return f"*Raw Headlines (LLM unavailable):*\n\n{raw_text}"

        prompt = (
            f"You are an expert intelligence analyst. Synthesize the following news headlines "
            f"into a concise, well-organized daily briefing in markdown format.\n"
            f"Group by theme. Highlight the 3 most important stories.\n"
            f"Filter focus: {topic_filter}\n\n"
            f"---\n{raw_text}"
        )

        messages = [{"role": "user", "content": prompt}]

        try:
            return self.llm_router.local_client.chat(messages=messages, temperature=0.3)
        except Exception as e:
            self.logger.error(f"LLM synthesis failed for digest: {e}")
            return f"*Synthesis failed. Raw headlines:*\n\n{raw_text}"

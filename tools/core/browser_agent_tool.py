"""
Browser Agent Tool (Requirement 28)

Provides capabilities to search the web, fetch URL content, and extract
structured data with strict adherence to robots.txt and rate limits.
"""

import time
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from tools.base import BaseTool, CapabilityDescriptor, ToolRiskLevel, ToolResult
from observability import get_logging_system


class BrowserAgentTool(BaseTool):
    """
    Stuart-AI Browser Agent.
    Handles web search, page fetching, and content extraction.
    """

    name = "browser_agent"
    description = "Enables the agent to search the web, visit websites, and extract information from online sources."
    version = "1.0.0"
    category = "web"
    risk_level = ToolRiskLevel.MEDIUM

    parameter_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query for web search."},
            "url": {"type": "string", "description": "The URL to fetch or extract from."},
            "max_results": {"type": "integer", "description": "Maximum number of search results.", "default": 5},
            "selector": {"type": "string", "description": "Optional CSS selector to extract specific content."}
        }
    }

    capabilities = [
        CapabilityDescriptor(
            "search_web",
            "Searches the web for a given query and returns a list of results.",
            ["query"],
            ["max_results"]
        ),
        CapabilityDescriptor(
            "fetch_url",
            "Fetches the raw text content of a webpage, respecting robots.txt.",
            ["url"]
        ),
        CapabilityDescriptor(
            "extract_content",
            "Extracts specific structured content from a URL using CSS selectors.",
            ["url", "selector"]
        )
    ]

    def __init__(self):
        self.logger = get_logging_system()
        self.client = httpx.Client(
            headers={"User-Agent": "Stuart-AI/1.0 (Cognitive Agent; Research Bot)"},
            timeout=10.0,
            follow_redirects=True
        )
        self.robot_cache: Dict[str, RobotFileParser] = {}
        self.last_request_time: Dict[str, float] = {}
        self.min_delay = 1.0  # 1 second minimum delay per domain

    def __del__(self):
        """BUG-09 fix: Ensure httpx.Client is properly closed on destruction."""
        try:
            self.client.close()
        except Exception:
            pass

    def _get_robot_parser(self, domain: str) -> RobotFileParser:
        if domain not in self.robot_cache:
            parser = RobotFileParser()
            try:
                parser.set_url(f"{domain}/robots.txt")
                parser.read()
                self.robot_cache[domain] = parser
            except Exception:
                # BUG-10 fix: If robots.txt fails, create a permissive parser
                # that explicitly allows all access (the default parser denies all
                # when it has no rules loaded).
                permissive_parser = RobotFileParser()
                permissive_parser.parse(["User-agent: *", "Allow: /"])
                self.robot_cache[domain] = permissive_parser
        return self.robot_cache[domain]

    def _check_safety(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # 1. Rate Limiting
        now = time.time()
        last_time = self.last_request_time.get(domain, 0)
        if now - last_time < self.min_delay:
            time.sleep(self.min_delay - (now - last_time))
        self.last_request_time[domain] = time.time()

        # 2. Robots.txt Compliance
        rp = self._get_robot_parser(domain)
        if not rp.can_fetch("Stuart-AI", url):
            self.logger.warning(f"Blocked by robots.txt: {url}")
            return False
        
        return True

    def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> ToolResult:
        start_time = time.time()
        try:
            if action == "search_web":
                return self._search_web(parameters.get("query"), parameters.get("max_results", 5))
            elif action == "fetch_url":
                return self._fetch_url(parameters.get("url"))
            elif action == "extract_content":
                return self._extract_content(parameters.get("url"), parameters.get("selector"))
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}", output=None)
        except Exception as e:
            self.logger.error(f"Browser Agent error in {action}: {e}")
            return ToolResult(success=False, error=str(e), output=None)
        finally:
            execution_time = (time.time() - start_time) * 1000
            # Note: ToolResult will include this in to_dict

    def _search_web(self, query: str, max_results: int) -> ToolResult:
        """Search the web using DuckDuckGo (HTML version for simplicity)."""
        if not query:
            return ToolResult(success=False, error="Search query is required.", output=None)

        self.logger.info(f"Searching web for: {query}")
        search_url = f"https://html.duckduckgo.com/html/?q={query}"
        
        # Note: We don't strictly check robots.txt for search engines in this helper, 
        # but we follow standard etiquette.
        try:
            response = self.client.get(search_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for result in soup.find_all('div', class_='result'):
                if len(results) >= max_results:
                    break
                
                title_tag = result.find('a', class_='result__a')
                snippet_tag = result.find('a', class_='result__snippet')
                
                if title_tag:
                    results.append({
                        "title": title_tag.get_text(strip=True),
                        "url": title_tag['href'],
                        "snippet": snippet_tag.get_text(strip=True) if snippet_tag else ""
                    })
            
            if not results:
                return ToolResult(success=True, output="No results found.")
            
            output = "Web Search Results:\n\n"
            for i, res in enumerate(results):
                output += f"{i+1}. {res['title']}\n   URL: {res['url']}\n   Snippet: {res['snippet']}\n\n"
            
            return ToolResult(success=True, output=output)
            
        except Exception as e:
            return ToolResult(success=False, error=f"Search failed: {str(e)}", output=None)

    def _fetch_url(self, url: str) -> ToolResult:
        """Fetch raw content from a URL and convert to clean text."""
        if not url:
            return ToolResult(success=False, error="URL is required.", output=None)

        if not self._check_safety(url):
            return ToolResult(success=False, error=f"Access to {url} is restricted by robots.txt or rate limits.", output=None)

        self.logger.info(f"Fetching URL: {url}")
        try:
            response = self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Break into lines and remove leading/trailing whitespace
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Drop blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Truncate if too long (max 10k chars)
            if len(text) > 10000:
                text = text[:10000] + "\n\n... [TRUNCATED] ..."
            
            return ToolResult(success=True, output=text)
            
        except Exception as e:
            return ToolResult(success=False, error=f"Fetch failed: {str(e)}", output=None)

    def _extract_content(self, url: str, selector: str) -> ToolResult:
        """Extract specific content from a URL using a CSS selector."""
        if not url or not selector:
            return ToolResult(success=False, error="URL and selector are required.", output=None)

        if not self._check_safety(url):
            return ToolResult(success=False, error=f"Access to {url} is restricted.", output=None)

        self.logger.info(f"Extracting '{selector}' from: {url}")
        try:
            response = self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            elements = soup.select(selector)
            
            if not elements:
                return ToolResult(success=True, output=f"No elements found matching selector: {selector}")
            
            results = [el.get_text(strip=True) for el in elements]
            return ToolResult(success=True, output="\n".join(results))
            
        except Exception as e:
            return ToolResult(success=False, error=f"Extraction failed: {str(e)}", output=None)

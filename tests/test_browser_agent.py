import pytest
from unittest.mock import MagicMock, patch
from tools.core.browser_agent_tool import BrowserAgentTool
from tools.base import ToolResult

@pytest.fixture
def browser_tool():
    return BrowserAgentTool()

def test_browser_tool_metadata(browser_tool):
    assert browser_tool.name == "browser_agent"
    assert "search_web" in [c.capability_name for c in browser_tool.capabilities]

@patch("httpx.Client.get")
def test_search_web_success(mock_get, browser_tool):
    # Mock HTML response from DuckDuckGo
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = """
    <div class="result">
        <a class="result__a" href="https://example.com">Example Title</a>
        <a class="result__snippet">Example Snippet</a>
    </div>
    """
    mock_get.return_value = mock_response

    result = browser_tool.execute("search_web", {"query": "test query"})
    
    assert result.success is True
    assert "Example Title" in result.output
    assert "https://example.com" in result.output

@patch("httpx.Client.get")
def test_fetch_url_robots_txt_respect(mock_get, browser_tool):
    # Mock robots.txt that denies everything
    mock_robots = MagicMock()
    mock_robots.status_code = 200
    mock_robots.text = "User-agent: *\nDisallow: /"
    
    # First call is to get robots.txt (implied by urllib.robotparser via set_url/read)
    # Actually, BrowserAgentTool uses urllib.robotparser.RobotFileParser()
    # We need to patch the RobotFileParser specifically or the URL read.
    
    with patch("urllib.robotparser.RobotFileParser.read") as mock_read:
        with patch("urllib.robotparser.RobotFileParser.can_fetch", return_value=False):
            result = browser_tool.execute("fetch_url", {"url": "https://denied.com/secret"})
            assert result.success is False
            assert "restricted by robots.txt" in result.error

@patch("httpx.Client.get")
def test_extract_content(mock_get, browser_tool):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><h1 class='title'>Main Title</h1></body></html>"
    mock_get.return_value = mock_response

    # Mock robots.txt check to allow
    with patch("tools.core.browser_agent_tool.BrowserAgentTool._check_safety", return_value=True):
        result = browser_tool.execute("extract_content", {"url": "https://example.com", "selector": "h1.title"})
        assert result.success is True
        assert result.output == "Main Title"

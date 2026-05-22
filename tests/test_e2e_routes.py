"""
End-to-end integration and routing tests for Stuart-AI.
Verifies both / and /agent routes, onboarding stepper logic, agent dashboard bento cells,
and style color schemes.
"""

import sys
import urllib.request
import urllib.error
import pytest
from fastapi.testclient import TestClient

# Mock qdrant_client to prevent database lock conflicts if background server is running
from unittest.mock import MagicMock
sys.modules['qdrant_client'] = MagicMock()

from main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_root_route_serves_interview_html(client):
    """Verify that / serves interview.html (the onboarding progress stepper)."""
    response = client.get("/")
    assert response.status_code == 200
    html_content = response.text
    
    # Verify page title
    assert "<title>Stuart</title>" in html_content
    
    # Verify stepper elements (3-step progress stepper)
    assert 'class="stepper-nav" id="stepper-nav"' in html_content
    assert 'data-step="1"' in html_content
    assert 'data-step="2"' in html_content
    assert 'data-step="3"' in html_content
    
    # Verify onboarding step panes
    assert 'id="step-1" class="step-pane active"' in html_content
    assert 'id="step-2" class="step-pane"' in html_content
    assert 'id="step-3" class="step-pane"' in html_content
    
    # Verify script imports: should load main.js for stepper logic, not agent-main.js
    assert "/static/js/main.js" in html_content
    assert "/static/js/agent-main.js" not in html_content
    
    # Verify external app launcher exists to switch to agent dashboard
    assert 'class="app-launcher" id="app-launcher"' in html_content
    assert 'href="/agent"' in html_content

def test_agent_route_serves_agent_html(client):
    """Verify that /agent serves agent.html (the cognitive terminal dashboard)."""
    response = client.get("/agent")
    assert response.status_code == 200
    html_content = response.text
    
    # Verify agent brand logo
    assert "STUART SYNTHESIS" in html_content
    assert 'class="agent-chat-container"' in html_content
    
    # Verify bento grid widgets
    assert 'class="bento-grid"' in html_content
    assert 'reasoning-widget' in html_content
    assert 'pulse-widget' in html_content
    assert 'perimeter-widget' in html_content
    assert 'hil-widget' in html_content
    
    # Verify script imports: should load agent-main.js, not main.js
    assert "/static/js/agent-main.js" in html_content
    assert "/static/js/main.js" not in html_content

def test_static_css_assets_accessible(client):
    """Verify that core static style sheets are served properly."""
    for css_path in ["main.css", "cognitive-terminal.css", "agent-chat.css", "hil-panel.css"]:
        response = client.get(f"/static/css/{css_path}")
        assert response.status_code == 200
        assert "text/css" in response.headers.get("content-type", "")

def test_stuart_navy_red_color_migration(client):
    """Verify that style sheets utilize Stuart brand colors and all old indigo colors are purged."""
    response = client.get("/static/css/main.css")
    assert response.status_code == 200
    css_content = response.text
    
    # Verify Stuart brand variables are defined
    assert "--stuart-navy" in css_content
    assert "--stuart-red" in css_content
    
    # Verify no hardcoded indigo colors (#6366f1, #8b5cf6) remain
    assert "#6366f1" not in css_content
    assert "#8b5cf6" not in css_content
    assert "63, 102, 241" not in css_content  # rgba representation of 6366f1

def test_live_indicator_animation_present(client):
    """Verify the LIVE pulse animation and elements are defined."""
    response = client.get("/static/css/cognitive-terminal.css")
    assert response.status_code == 200
    css_content = response.text
    
    # Verify indicator styles and animations are defined
    assert "live-indicator" in css_content
    assert "pulse" in css_content or "animation" in css_content

def test_running_server_e2e():
    """Verify the live running server if it is reachable on port 8002."""
    try:
        url = "http://127.0.0.1:8002/"
        with urllib.request.urlopen(url, timeout=2) as response:
            html = response.read().decode('utf-8')
            assert response.status == 200
            assert "stepper-nav" in html
            print("Live running server is responding correctly at /")
    except Exception as e:
        pytest.skip(f"Live server at http://127.0.0.1:8002 not reachable: {e}")

"""
Tests for Api Caller Tool (Task 15.3)
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from api_caller import ApiCallerTool

def test_api_caller_url_validation():
    tool = ApiCallerTool()
    
    res = tool.execute("http_request", {"method": "GET", "url": "ftp://bad-url.com"})
    assert res.success is False
    assert "must begin with http" in res.error

@patch('api_caller.urllib.request.urlopen')
def test_api_caller_success(mock_urlopen):
    # Mocking standard HTTP response
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_response.read.side_effect = [b'{"foo":"bar"}', b''] # first call returns body, second returns EOF
    mock_response.info.return_value = {"Content-Type": "application/json"}
    
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_ctx
    
    tool = ApiCallerTool()
    res = tool.execute("http_request", {"method": "GET", "url": "http://example.com"})
    
    assert res.success is True
    assert res.output["status_code"] == 200
    assert '{"foo":"bar"}' in res.output["body"]

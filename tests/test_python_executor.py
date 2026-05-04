"""
Tests for PythonExecutorTool (Task 15.2)
"""

import pytest
from tools.core.python_executor import PythonExecutorTool

def test_python_executor_success():
    tool = PythonExecutorTool()
    
    code = "print('Hello Space!'); x = 5 + 5; print(x)"
    res = tool.execute("execute_python", {"code": code})
    
    assert res.success is True
    assert "Hello Space!" in res.output
    assert "10" in res.output

def test_python_executor_banned_modules():
    tool = PythonExecutorTool()
    
    # Trying to import os should flag the ImportError
    code = "import os; print(os.getcwd())"
    res = tool.execute("execute_python", {"code": code})
    
    assert res.success is False
    assert "Security restriction" in res.error or "ImportError" in res.error
    # assert "forbidden" in res.error

def test_python_executor_banned_builtins():
    tool = PythonExecutorTool()
    
    # Trying to open a file manually is blocked
    code = "f = open('malicious.txt', 'w')"
    res = tool.execute("execute_python", {"code": code})
    
    assert res.success is False
    assert "TypeError: 'NoneType' object is not callable" in res.error

def test_python_executor_syntax_error():
    tool = PythonExecutorTool()
    
    code = "print('hello'   # missing parenthesis"
    res = tool.execute("execute_python", {"code": code})
    
    assert res.success is False
    assert "SyntaxError" in res.error

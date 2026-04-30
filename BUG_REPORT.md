# Stuart-AI Comprehensive Bug Report

This document contains a thorough and granular analysis of all bugs, architectural flaws, security vulnerabilities, and code quality issues found in the `Stuart-AI` codebase.

## 1. Stealth Mode & `window_manager.py` Failures (Priority: Critical)

The "Stealth Mode", advertised as the core capability of the application (preventing screen capture via `WDA_EXCLUDEFROMCAPTURE`), has significant failure points that can cause it to silently fail or not apply properly, leaving users exposed during exams or interviews.

### 1.1 Brittle Window Handle (HWND) Acquisition
**File**: `window_manager.py` (Lines 1257-1300)
**Issue**: The function `apply_capture_protection(window)` attempts to acquire the `pywebview` window handle in highly unstable ways:
- **Method 1**: Uses `getattr(window, '_hwnd', None)`. This accesses a private attribute of `pywebview` which may not be populated depending on the GUI backend (WinForms, CEF, EdgeHTML) or the exact lifecycle phase.
- **Method 2 & 3**: Falls back to `_user32.FindWindowW(None, window.title)` or finding by hardcoded string `"Stuart"`.
**Impact**: Because the window title can change, or there might be multiple windows with the title "Stuart" (e.g., a terminal window running the app), `FindWindowW` might grab the wrong handle. If it grabs the wrong handle, capture protection is applied to the terminal, not the GUI, completely failing its primary purpose.

### 1.2 Threading & Lifecycle Race Conditions
**File**: `main.py`
**Issue**: The application architecture mixes Python threading, `asyncio`, and `pywebview`. `pywebview` must run on the main thread, but `uvicorn` and the application logic run on a background thread (`AsyncioServiceThread`).
- When `window.events.shown` fires, it immediately calls `window_manager.apply_capture_protection(window)`. However, there is no strict guarantee that the underlying OS-level window rendering is fully complete and bound to `_hwnd` when `shown` triggers, leading to race conditions where the handle is null.
- A hardcoded `time.sleep(1.0)` is used in `on_window_shown` to "give window more time to fully initialize" before setting always-on-top. Hardcoded sleep values are anti-patterns and cause non-deterministic behavior depending on CPU load.

### 1.3 Pointer Type Definition Mismatches
**File**: `window_manager.py` (Win32 API setup)
**Issue**: In `_setup_win32_api_definitions`, `GetWindowLongPtrW` and `SetWindowLongPtrW` are defined. However, on 32-bit Windows, these functions do not exist in `user32.dll` (they are macros that resolve to `GetWindowLongW`), but the code tries to load them via `self.user32.GetWindowLongW`. While there is an `is_64bit` check, incorrect type casting for `LPARAM` and pointers can lead to memory access violations (Access Violation / Segfaults) when altering window styles, especially in Python 64-bit environments.

### 1.4 Bare Except Clauses in Critical Operations
**File**: `window_manager.py` (Lines 452, 490, 498, 943)
**Issue**: There are several `try...except:` blocks that use `except:` or `except Exception as e: pass` (e.g., during window enumeration `enum_windows_callback`).
**Impact**: This swallows exceptions silently. If a critical failure occurs while iterating through windows to find screen-share indicators, it fails silently, and screen share detection stops working without logging the true cause.

---

## 2. Architectural & Test Suite Failures (Priority: High)

### 2.1 Broken Module Import System
**Issue**: The entire test suite fails to run (`pytest tests/` returns 32 critical collection errors).
**Cause**: The application lacks proper package structuring. Files inside `tests/` attempt to do things like `from vector_db import VectorDatabase` without correctly resolving the path to `knowledge/vector_db.py`.
**Impact**: The codebase is unmaintainable and untestable in its current state. CI/CD pipelines will fail. To fix this, absolute imports must be used (e.g., `from knowledge.vector_db import VectorDatabase`) and `__init__.py` files must be present, or a proper `PYTHONPATH` resolution strategy (like an `src/` layout or `conftest.py` path hacking) must be implemented.

### 2.2 Unresolved Dependencies
**File**: `tests/test_scheduler.py`
**Issue**: The test suite attempts to `import schedule`, but `schedule` is not in the environment dependencies (or wasn't properly installed).

### 2.3 Hardcoded File Paths in Tests
**File**: `tests/test_tasks_7_4_to_7_9.py`
**Issue**: Triggers `FileNotFoundError: [Errno 2] No such file or directory: '/app/tests/hybrid_planner.py'`. Tests should use dynamic path resolution (e.g., `os.path.join(os.path.dirname(__file__), ...)`) instead of hardcoded paths.

---

## 3. Security Vulnerabilities (Priority: High)

### 3.1 Arbitrary Code Execution via `exec`
**File**: `tools/core/python_executor.py` (Line 76)
**Issue**: `exec(code_str, restricted_globals, {})` is used.
**Vulnerability**: Even with `restricted_globals`, Python's `exec` is notoriously difficult to sandbox properly. An attacker (or a hallucinating LLM) generating malicious code can easily escape restricted globals using built-in reflection (e.g., `().__class__.__bases__[0].__subclasses__()`) to gain full OS command execution capabilities.
**Fix**: Use a proper sandboxing mechanism (e.g., Docker, WebAssembly, or restricted environments like `RestrictedPython`), or avoid `exec` entirely.

### 3.2 Unsafe Subprocess Execution
**File**: `tools/mcp_client.py` (Line 59)
**Issue**: `subprocess.Popen` is used with untrusted input (the `command` parameter).
**Vulnerability**: Depending on how `self.command` is constructed from LLM or user input, this is susceptible to OS Command Injection if `shell=True` is ever accidentally added, or if the executable path is hijacked. (Flagged by Bandit B603).

### 3.3 Server-Side Request Forgery (SSRF) Risk
**File**: `tools/core/api_caller.py` (Line 73)
**Issue**: Uses `urllib.request.urlopen(req)`.
**Vulnerability**: If `req` URL is controlled by the LLM or user, it allows the application to make internal network requests, potentially exposing local services or cloud metadata endpoints. (Flagged by Bandit B310).

---

## 4. Code Quality & Static Analysis Issues (Priority: Medium)

Over 7,000 `pylint` and 6,000 `flake8` warnings were generated. Notable issues include:

### 4.1 Type Checking Failures (Mypy)
**File**: `services/llm_service.py`
**Issue**: Mypy crashes with `Source file found twice under different module names`. This is a direct consequence of the broken import paths (Section 2.1). Fix the package structure to allow static typing validation.

### 4.2 Assertions in Production Code
**Files**: `tests/test_vector_db.py`, `tests/test_vectorizer.py`, `tests/test_tracing_system.py`
**Issue**: While standard in test files, there are numerous `assert` statements flagged by Bandit (B101). Asserts are stripped when Python is run with optimizations (`-O`), which could lead to logic bypasses if asserts are used in application source code for validation. (Ensure no asserts are used for runtime logic outside the `tests` directory).

### 4.3 Redundant and Unused Imports
**File**: `api/agent_api.py` (and many others)
**Issue**: `F401 'typing.Optional' imported but unused`, `F401 'typing.List' imported but unused`. Unused imports bloat memory and cause confusion.
**File**: `automation/cron_manager.py` (Lines 19, 20)
**Issue**: Unused imports (`Optional`, `Callable`).

### 4.4 Style and PEP8 Violations
**Files**: Across the codebase.
**Issue**: Thousands of `E501 line too long`, `C0303 Trailing whitespace`, `C0116 Missing function or method docstring`.
**Fix**: Apply an automated formatter like `black` or `ruff` to standardize the codebase formatting.

### 4.5 Mutable Default Arguments
(Discovered during structural review).
**Issue**: Using mutable defaults (like `[]` or `{}`) in function definitions is a common source of bugs in Python as the default object is shared across all calls.

---

## 5. Potential UI/UX Bugs in Invisible Mode

### 5.1 Click-Through Ghost Mode (Alt+X)
**File**: `window_manager.py`
**Issue**: Ghost mode applies `WS_EX_TRANSPARENT`. When a window has this flag, all mouse clicks pass through it to the window beneath. However, if the user needs to interact with the Stuart UI (e.g., to scroll content not mapped to a hotkey, or click a button), they must toggle the mode off. If they forget, the app appears unresponsive to clicks.

### 5.2 Hotkey Conflicts
**File**: `window_manager.py`
**Issue**: The application registers global hotkeys like `Alt+Z`, `Alt+X`, `Alt+1`. These are very common combinations in other software (e.g., GeForce Experience uses Alt+Z, many IDEs use Alt+Left/Right). Registering these globally will intercept the keystrokes intended for the exam platform or the user's primary IDE, causing unexpected behavior in the target application.

---

## Summary
The codebase requires immediate structural refactoring to establish a valid Python package hierarchy. The Stealth Mode implementation relies on unstable Win32 window acquisition methods that risk the core value proposition of the product failing during critical moments. Security vulnerabilities in the tool executors (`exec` and `subprocess`) pose severe risks to user machines. Testing is currently impossible without resolving path issues.

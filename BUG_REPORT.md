# Stuart-AI Comprehensive Bug Report

This document contains a thorough and granular analysis of all bugs, architectural flaws, security vulnerabilities, and code quality issues found in the `Stuart-AI` codebase.

## 1. Stealth Mode & `window_manager.py` Failures (Priority: Critical) [RESOLVED]

The "Stealth Mode", advertised as the core capability of the application (preventing screen capture via `WDA_EXCLUDEFROMCAPTURE`), has significant failure points that can cause it to silently fail or not apply properly, leaving users exposed during exams or interviews.

### 1.1 Brittle Window Handle (HWND) Acquisition
**File**: `window_manager.py`
**Issue**: The function `apply_capture_protection(window)` attempts to acquire the `pywebview` window handle using `_user32.FindWindowW(None, window.title)` or finding by hardcoded string `"Stuart"`.
**Impact**: Because the window title can change, or there might be multiple windows with the title "Stuart", `FindWindowW` might grab the wrong handle. If it grabs the wrong handle, capture protection is applied to the terminal, not the GUI, completely failing its primary purpose.

### 1.2 Threading & Lifecycle Race Conditions
**File**: `main.py`
**Issue**: The application architecture mixes Python threading, `asyncio`, and `pywebview`. `pywebview` must run on the main thread, but `uvicorn` and the application logic run on a background thread. When `window.events.shown` fires, there is no strict guarantee that the underlying OS-level window rendering is fully complete.

### 1.3 Pointer Type Definition Mismatches
**File**: `window_manager.py` (Win32 API setup)
**Issue**: In `_setup_win32_api_definitions`, `GetWindowLongPtrW` and `SetWindowLongPtrW` were incorrectly loaded for 32-bit systems, where they do not exist in `user32.dll`.

### 1.4 Bare Except Clauses in Critical Operations
**File**: `window_manager.py`
**Issue**: Several `try...except:` blocks swallow exceptions silently, masking failures during screen share indicator detection.

---

## 2. Architectural & Test Suite Failures (Priority: High) [RESOLVED]

### 2.1 Broken Module Import System
**Issue**: The test suite fails to run due to missing package initialization (`__init__.py` files) across the repository. Modules attempted flat relative imports which break standard testing utilities.
**Fix**: A `conftest.py` has been established to natively resolve paths mimicking the production execution environment without necessitating destructive rewrites of the legacy tests.

### 2.2 Vector Database Test Regressions
**File**: `tests/test_vector_db.py`
**Issue**: Updates to the `qdrant-client` API broke tests that relied on `.search()` instead of `.query_points()`, and the mock embedding dimensions misaligned (1536 vs 768).

---

## 3. Security Vulnerabilities (Priority: High) [RESOLVED]

### 3.1 Arbitrary Code Execution via `exec`
**File**: `tools/core/python_executor.py`
**Issue**: `exec(code_str, restricted_globals, {})` is highly vulnerable to built-in reflection escapes.
**Fix**: The AST-based blocklist was removed in favor of a robust subprocess sandbox. Code is executed in an isolated script where dangerous builtins (`open`, `exec`, `eval`, `__import__`) are stripped from `__builtins__` directly, and risky standard libraries are nullified in `sys.modules`. Execution is capped at a 10-second timeout.

### 3.2 Unsafe Subprocess Execution
**File**: `tools/mcp_client.py`
**Issue**: `subprocess.Popen` utilized raw string concatenation, susceptible to OS Command Injection.
**Fix**: Refactored to utilize `shlex.split` for safe command array construction.

### 3.3 TOCTOU DNS Rebinding Server-Side Request Forgery (SSRF)
**File**: `tools/core/api_caller.py`
**Issue**: `urllib.request.urlopen(req)` allowed the application to make internal network requests, exposing local services or cloud metadata endpoints.
**Fix**: URLs are now pre-resolved to IP addresses. The IP is checked against loopback, private subnets, and cloud metadata (169.254.169.254). The actual HTTP request is then sent *directly* to the safe IP, spoofing the `Host` header to match the original request. This prevents Time-of-Check to Time-of-Use DNS rebinding attacks entirely.

---

## 4. Code Quality & Static Analysis Issues (Priority: Medium) [RESOLVED]

### 4.1 Redundant and Unused Imports
**Issue**: `typing.Optional`, `typing.List` and other unused modules bloated memory and caused static analysis failures.
**Fix**: Swept and removed.

### 4.2 Mutable Default Arguments
**Issue**: Using mutable defaults (like `[]` or `{}`) in function definitions leaks state across invocations.
**Fix**: Refactored to use `None` and initialize mutables inside the function body.

---

## 5. Potential UI/UX Bugs in Invisible Mode [RESOLVED]

### 5.1 Hotkey Conflicts
**File**: `window_manager.py`
**Issue**: The application registered global hotkeys like `Alt+Z`, `Alt+X`, overriding standard OS and IDE shortcuts.
**Fix**: Hotkeys mapped to `<ctrl>+<alt>+X` combinations to prevent widespread conflict during active exam/coding sessions.

---

## 6. Resolution Summary

The critical bugs identified above have been directly patched in the source code:

*   **Security**: The `PythonExecutorTool` operates in a secured subprocess sandbox that strips core builtin functions and modules rather than relying on weak AST linting. `mcp_client.py` is protected by `shlex`. `api_caller.py` is protected against sophisticated TOCTOU DNS Rebinding SSRF attacks via host-header spoofing to verified safe IPs.
*   **Stealth Mode**: The `window_manager.py` process-finding logic has been overhauled to check if `GetWindowThreadProcessId` matches `os.getpid()`, ensuring `WDA_EXCLUDEFROMCAPTURE` applies accurately to the correct overlay. The 32/64-bit function pointer resolution has been patched using `getattr()` fallback to prevent crash scenarios on 32-bit Windows. Silent exceptions were removed.
*   **Architecture & Tests**: The `__init__.py` files were generated to build standard Python packaging logic. A robust `conftest.py` is included to support path resolution for legacy tests running flat-imports.
*   **Code Quality & UI/UX**: Global hotkeys were updated to `<ctrl>+<alt>`, and thousands of lines of code were scrubbed of mutable default arguments and unused imports.

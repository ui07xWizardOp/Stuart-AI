# Stuart-AI Feature Verification Report (Pass 2: Runtime Validation)

Date: 2026-05-01
Objective: Runtime-check claimed core reliability features one-by-one using existing tests.

## What was validated
Targeted features from the requested hardening list and prior claims:
- Scheduler / Cron backbone
- Task queue
- Plan library persistence behavior
- Model router + circuit breaker contract
- Capability token system

## Commands executed
1. `pytest -q tests/test_scheduler.py tests/test_task_queue.py tests/test_plan_library.py tests/test_model_router.py tests/test_capability_tokens.py`

## Result summary
- **Overall:** FAILED (12 failures / 0 passes in this batch).
- This means the previously claimed “implemented” status for these areas is **not verified as working end-to-end** in current repo state.

## Detailed findings

### 1) Logging initialization coupling breaks multiple subsystems at construction
Affected modules under test:
- `automation/scheduler.py`
- `automation/task_queue.py`
- `cognitive/plan_library.py`
- `security/capability_tokens.py`

Observed failure:
- Constructors call `get_logging_system()` immediately.
- In isolated test/runtime usage where logging bootstrap has not run, this raises:
  `RuntimeError: Logging system has not been initialized. Call initialize_logging() first.`

Impact:
- Core subsystems are not independently instantiable.
- Feature availability depends on strict global boot order.
- Violates robustness expectations for reusable components.

### 2) Circuit breaker API mismatch vs tests/contracts
Observed failure:
- `CircuitBreaker.__init__()` does not accept `reset_timeout_sec` expected by tests.

Impact:
- Contract drift between implementation and expected interface.
- Indicates incompatibility between claimed feature behavior and test harness expectations.

### 3) ModelEndpoint data model mismatch
Observed failure:
- `ModelEndpoint` currently behaves as Enum, but tests instantiate it with endpoint metadata fields.
- Error: `EnumMeta.__call__() takes from 2 to 3 positional arguments but 7 were given`.

Impact:
- Router endpoint abstraction is not aligned with test/consumer contract.
- “Model routing implemented” is only partially true; interface compatibility is broken.

## Verification conclusion
For this pass, the following features are **present in code but not runtime-verified as working**:
- Scheduler
- Task queue
- Plan library
- Circuit breaker integration contract
- Model endpoint routing contract
- Capability token system

## Recommended next step (implementation pass)
1. Decouple module constructors from hard-failing global logging init (fallback logger or lazy init).
2. Align circuit breaker constructor signature with expected contract (or migrate tests+callers consistently).
3. Replace/augment `ModelEndpoint` with structured endpoint descriptor class expected by router tests.
4. Re-run the same targeted suite until green before expanding to broader matrix.

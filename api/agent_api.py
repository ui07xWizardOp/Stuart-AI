"""
PCA Agent API Bridge (Phase 9B)

FastAPI router that connects the Stuart GUI frontend to the PCA Orchestrator brain.
Provides endpoints for chat, status checking, autonomy level control,
cron management, and budget dashboard.

Phase 9B additions:
  - /api/agent/cron (GET list, POST add, DELETE remove)
  - /api/agent/budget (GET token quota dashboard)
  - Updated /health to include cron manager + file access guard status
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import traceback
import time

router = APIRouter(prefix="/api/agent", tags=["agent"])

# --- Global references (set during boot) ---
_orchestrator = None
_approval_system = None
_cron_manager = None
_token_quota = None
_file_access_guard = None
_boot_time = None

# ── Phase 10: HIL approval queue (in-memory) ─────────────────────────
import uuid
import threading

_hil_lock = threading.Lock()
_hil_pending: dict = {}          # id -> {id, tool, action, risk, timeout_secs, resolved}
_hil_decisions: dict = {}        # id -> True/False
_hil_thresholds: dict = {        # per-tier threshold: 'auto'|'prompt'|'block'
    "LOW":      "auto",
    "MEDIUM":   "auto",
    "HIGH":     "prompt",
    "CRITICAL": "prompt",
}


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    elapsed_ms: float


class AutonomyRequest(BaseModel):
    level: str  # "restricted", "moderate", "full"


class StatusResponse(BaseModel):
    status: str
    autonomy_level: str
    uptime_seconds: float


class CronAddRequest(BaseModel):
    time_str: str
    prompt: str
    job_type: str = "daily"
    interval_minutes: int = 0


def set_orchestrator(orchestrator, approval_system=None, cron_manager=None, 
                     token_quota=None, file_access_guard=None):
    """Called once during main.py boot to inject the live subsystems."""
    global _orchestrator, _approval_system, _cron_manager, _token_quota, _file_access_guard, _boot_time
    _orchestrator = orchestrator
    _approval_system = approval_system
    _cron_manager = cron_manager
    _token_quota = token_quota
    _file_access_guard = file_access_guard
    _boot_time = time.time()


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(req: ChatRequest):
    """
    Primary chat endpoint. Sends user message through the full
    PCA ReAct loop (memory → complexity dispatch → tool execution → response).
    """
    if not _orchestrator:
        raise HTTPException(status_code=503, detail="PCA Orchestrator not initialized.")

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message.")

    start = time.time()
    try:
        # Run the orchestrator synchronously in a thread to not block the event loop
        import asyncio
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(
            None,
            _orchestrator.process_user_message,
            req.message.strip()
        )
        elapsed = (time.time() - start) * 1000
        return ChatResponse(response=response_text, elapsed_ms=round(elapsed, 1))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Orchestrator error: {str(e)[:300]}")


@router.get("/status", response_model=StatusResponse)
async def agent_status():
    """Health check for the PCA brain."""
    if not _orchestrator:
        return StatusResponse(status="offline", autonomy_level="unknown", uptime_seconds=0)

    autonomy = "moderate"
    if _approval_system:
        autonomy = _approval_system.autonomy_level.value

    uptime = time.time() - _boot_time if _boot_time else 0
    return StatusResponse(status="online", autonomy_level=autonomy, uptime_seconds=round(uptime, 1))


@router.post("/autonomy")
async def set_autonomy(req: AutonomyRequest):
    """Allows the frontend to dynamically change the HIL autonomy level."""
    if not _approval_system:
        raise HTTPException(status_code=503, detail="Approval system not initialized.")

    valid_levels = ["restricted", "moderate", "full"]
    if req.level not in valid_levels:
        raise HTTPException(status_code=400, detail=f"Invalid level. Use one of: {valid_levels}")

    from security.approval_system import AutonomyLevel
    level_map = {
        "restricted": AutonomyLevel.RESTRICTED,
        "moderate": AutonomyLevel.MODERATE,
        "full": AutonomyLevel.FULL,
    }
    _approval_system.set_autonomy(level_map[req.level])
    return {"status": "ok", "autonomy_level": req.level}


# ── Phase 9B: Cron Endpoints ──────────────────────────────────────────

@router.get("/cron")
async def list_cron_jobs():
    """List all active cron jobs."""
    if not _cron_manager:
        raise HTTPException(status_code=503, detail="Cron manager not initialized.")
    return {"jobs": _cron_manager.get_jobs_data()}


@router.post("/cron")
async def add_cron_job(req: CronAddRequest):
    """Add a new cron job."""
    if not _cron_manager:
        raise HTTPException(status_code=503, detail="Cron manager not initialized.")

    try:
        job_id = _cron_manager.add(
            time_str=req.time_str,
            prompt=req.prompt,
            job_type=req.job_type,
            interval_minutes=req.interval_minutes,
        )
        return {"status": "ok", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/cron/{job_id}")
async def remove_cron_job(job_id: str):
    """Remove a cron job by ID."""
    if not _cron_manager:
        raise HTTPException(status_code=503, detail="Cron manager not initialized.")

    if _cron_manager.remove(job_id):
        return {"status": "ok", "removed": job_id}
    else:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")


# ── Phase 9B: Budget Endpoint ─────────────────────────────────────────

@router.get("/budget")
async def get_budget():
    """Expose token quota dashboard data."""
    if not _token_quota:
        raise HTTPException(status_code=503, detail="Token quota not initialized.")
    
    try:
        return _token_quota.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Health Endpoint (Phase 9A + 9B) ──────────────────────────────────

@router.get("/health")
async def agent_health():
    """
    Comprehensive health dashboard.
    Phase 9A: circuit breaker, token quota, compactor, checkpoint.
    Phase 9B: cron manager, file access guard.
    """
    if not _orchestrator:
        return {"status": "offline", "subsystems": {}}

    health = {"status": "online", "subsystems": {}}

    # Circuit Breaker + Quota status from ModelRouter
    try:
        health["subsystems"]["router"] = _orchestrator.router.get_status()
    except Exception:
        health["subsystems"]["router"] = {"error": "unavailable"}

    # Context Compactor status
    try:
        if _orchestrator.compactor:
            health["subsystems"]["compactor"] = _orchestrator.compactor.get_status()
    except Exception:
        health["subsystems"]["compactor"] = {"error": "unavailable"}

    # Session Checkpoint status
    try:
        if _orchestrator.checkpoint:
            health["subsystems"]["checkpoint"] = _orchestrator.checkpoint.get_status()
    except Exception:
        health["subsystems"]["checkpoint"] = {"error": "unavailable"}

    # Autonomy level
    if _approval_system:
        health["subsystems"]["autonomy"] = {
            "level": _approval_system.autonomy_level.value,
        }

    # Phase 9B: Cron Manager
    if _cron_manager:
        try:
            health["subsystems"]["cron"] = _cron_manager.get_status()
        except Exception:
            health["subsystems"]["cron"] = {"error": "unavailable"}

    # Phase 9B: File Access Guard
    if _file_access_guard:
        try:
            health["subsystems"]["file_guard"] = _file_access_guard.get_status()
        except Exception:
            health["subsystems"]["file_guard"] = {"error": "unavailable"}

    return health


# ── Phase 10: HIL GUI Endpoints ───────────────────────────────────────

class HILThresholdsRequest(BaseModel):
    LOW: str = "auto"
    MEDIUM: str = "auto"
    HIGH: str = "prompt"
    CRITICAL: str = "prompt"


class HILApproveRequest(BaseModel):
    request_id: str
    approved: bool


@router.get("/hil/queue")
async def hil_get_queue():
    """Returns currently pending HIL approval requests for the GUI."""
    with _hil_lock:
        pending = [
            {"id": v["id"], "tool": v["tool"], "action": v["action"],
             "risk": v["risk"], "timeout_secs": v.get("timeout_secs", 30)}
            for v in _hil_pending.values()
            if not v.get("resolved", False)
        ]
    return {"pending": pending}


@router.post("/hil/thresholds")
async def hil_set_thresholds(req: HILThresholdsRequest):
    """Persist per-tier thresholds from the GUI panel."""
    global _hil_thresholds
    valid = {"auto", "prompt", "block"}
    data = req.dict()
    for k, v in data.items():
        if v not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid threshold value '{v}' for {k}")
    _hil_thresholds = data

    # Propagate to the approval system if it has per-tier support
    if _approval_system and hasattr(_approval_system, 'set_thresholds'):
        _approval_system.set_thresholds(_hil_thresholds)

    return {"status": "ok", "thresholds": _hil_thresholds}


@router.post("/hil/approve")
async def hil_approve(req: HILApproveRequest):
    """Record a human approval/denial decision for a queued tool call."""
    with _hil_lock:
        if req.request_id not in _hil_pending:
            raise HTTPException(status_code=404, detail="Request ID not found.")
        _hil_pending[req.request_id]["resolved"] = True
        _hil_decisions[req.request_id] = req.approved

    decision = "ALLOWED" if req.approved else "DENIED"
    if _approval_system:
        _approval_system.logger.info(
            f"GUI HIL decision for {req.request_id}: {decision}"
        )
    return {"status": "ok", "request_id": req.request_id, "approved": req.approved}


def queue_hil_request(tool: str, action: str, risk: str, timeout_secs: int = 30) -> str:
    """
    Called by the approval system to enqueue a tool execution for GUI approval.
    Returns a request_id that can be polled for the decision.
    """
    request_id = str(uuid.uuid4())[:8]
    with _hil_lock:
        _hil_pending[request_id] = {
            "id": request_id,
            "tool": tool,
            "action": action,
            "risk": risk,
            "timeout_secs": timeout_secs,
            "resolved": False,
        }
    return request_id


def wait_for_hil_decision(request_id: str, timeout_secs: int = 30) -> bool:
    """
    Blocking poll until GUI panel resolves the decision or timeout.
    Returns True if approved, False if denied/timed-out.
    """
    import time
    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        with _hil_lock:
            if request_id in _hil_decisions:
                return _hil_decisions.pop(request_id)
        time.sleep(0.5)
    # Timeout → auto-deny
    with _hil_lock:
        if request_id in _hil_pending:
            _hil_pending[request_id]["resolved"] = True
    return False

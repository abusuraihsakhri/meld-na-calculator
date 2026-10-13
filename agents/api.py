"""Optional FastAPI service for reference calculation and legacy audit tools."""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from meld_na import full_assessment
from .base import AuditLogger, SecurityException
from .models import SystemTaskPayload
from .supervisor import SystemSupervisor

supervisor = SystemSupervisor(model_provider="mock")
app = FastAPI(
    title="MELD Reference Calculator API",
    description="Educational MELD 3.0, MELD-Na and original MELD calculations.",
    version="1.1.0",
)


class CalculateRequest(BaseModel):
    bilirubin: float = Field(gt=0, allow_inf_nan=False)
    inr: float = Field(gt=0, allow_inf_nan=False)
    creatinine: float = Field(gt=0, allow_inf_nan=False)
    sodium: float = Field(gt=0, allow_inf_nan=False)
    albumin: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    female: bool = False
    dialysis: bool = False


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)


@app.get("/health")
def health():
    return {"status": "ok", "service": "meld-na-calculator", "version": "1.1.0"}


@app.get("/metrics")
def metrics():
    return {
        "dossiers_processed_total": len(supervisor.dossier_registry),
        "audit_blocks_total": len(AuditLogger.get_trail()),
        "system_status": "running",
    }


@app.post("/api/calculate")
def api_calculate(req: CalculateRequest):
    try:
        return full_assessment(**req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/audit")
def api_audit(payload: SystemTaskPayload):
    try:
        return supervisor.process_task(payload).to_dict()
    except SecurityException as exc:
        raise HTTPException(status_code=400, detail="Identifier detected in audit payload") from exc


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    try:
        return {"response": supervisor.query_supervisory_chat(req.query)}
    except SecurityException as exc:
        raise HTTPException(status_code=400, detail="Identifier detected in query") from exc


@app.get("/api/audit/logs")
def api_audit_logs():
    return {
        "audit_trail": AuditLogger.get_trail(),
        "verified": AuditLogger.verify_integrity(),
    }


# Mount last so API routes retain precedence; serves the same static app
# used by GitHub Pages when running the optional Python service.
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "web", html=True), name="web")

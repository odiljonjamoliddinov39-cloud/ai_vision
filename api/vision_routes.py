"""Normalized API for blocks, zones, scan history, events, and counts."""
import os
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from database.vision_config_db import VisionConfigDB
from database.vision_db import VisionDB

router = APIRouter(prefix="/api/v1", tags=["vision"])

def history(): return VisionDB(os.getenv("VISION_DB_PATH", "database/vision.db"))
def config(): return VisionConfigDB(os.getenv("VISION_DB_PATH", "database/vision.db"))

class BlockInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

class CameraRuleInput(BaseModel):
    block_id: int | None = None
    confidence: float = Field(.35, ge=0, le=1)
    minimum_track_age: int = Field(4, ge=1, le=1000)
    direction: int = Field(1)
    zones: dict[str, list[list[float]]]

@router.get("/blocks")
def list_blocks(): return {"data": config().list_blocks(), "meta": {}}

@router.post("/blocks", status_code=201)
def create_block(body: BlockInput):
    try: return {"data": config().create_block(body.name, body.description), "meta": {}}
    except Exception as exc: raise HTTPException(409, detail={"error_code": "BLOCK_CONFLICT", "message": str(exc), "service": "config"}) from exc

@router.put("/blocks/{block_id}")
def update_block(block_id: int, body: BlockInput):
    try: value = config().update_block(block_id, name=body.name, description=body.description)
    except Exception as exc: raise HTTPException(409, detail={"error_code": "BLOCK_CONFLICT", "message": str(exc), "service": "config"}) from exc
    if value is None: raise HTTPException(404, detail={"error_code": "BLOCK_NOT_FOUND", "message": "Block not found", "service": "config"})
    return {"data": value, "meta": {}}

@router.delete("/blocks/{block_id}", status_code=204)
def delete_block(block_id: int):
    if not config().delete_block(block_id):
        raise HTTPException(404, detail={"error_code": "BLOCK_NOT_FOUND", "message": "Block not found", "service": "config"})

@router.get("/cameras/{camera_id}/rules")
def get_rules(camera_id: str): return {"data": config().get_camera_rules(camera_id), "meta": {}}

@router.put("/cameras/{camera_id}/rules")
def save_rules(camera_id: str, body: CameraRuleInput):
    try:
        config().save_camera_rules(camera_id, block_id=body.block_id, confidence=body.confidence,
            minimum_track_age=body.minimum_track_age, direction=body.direction, zones=body.zones)
        return {"data": config().get_camera_rules(camera_id), "meta": {}}
    except ValueError as exc: raise HTTPException(422, detail={"error_code": "INVALID_RULES", "message": str(exc), "service": "config", "camera_id": camera_id}) from exc

@router.get("/scan-runs")
def scans(limit: int = Query(100, ge=1, le=500), block_id: str | None = None):
    data = history().list_scans(limit, block_id)
    return {"data": data, "meta": {"count": len(data), "limit": limit}}

@router.get("/scan-runs/{scan_run_id}")
def scan_details(scan_run_id: int):
    data = history().scan_details(scan_run_id)
    if data is None: raise HTTPException(404, detail={"error_code": "SCAN_NOT_FOUND", "message": "Scan not found", "service": "history"})
    return {"data": data, "meta": {}}

@router.get("/events")
def events(limit: int = Query(100, ge=1, le=500), camera_id: str | None = None,
           block_id: str | None = None, class_id: int | None = None,
           date_from: str | None = None, date_to: str | None = None):
    data = history().list_events(limit, camera_id, block_id, class_id, date_from, date_to)
    return {"data": data, "meta": {"count": len(data), "limit": limit}}

@router.get("/counts")
def counts(block_id: str | None = None, camera_id: str | None = None):
    data = history().count_summary(block_id, camera_id)
    return {"data": data, "meta": {"count": len(data)}}

@router.get("/analytics/summary")
def analytics_summary(block_id: str | None = None, camera_id: str | None = None):
    return {"data": history().analytics_summary(block_id, camera_id), "meta": {}}

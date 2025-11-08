from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Union

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from src.routes.system import _INMEM_DB

router = APIRouter(prefix="/api")


class ArtifactType(str, Enum):
    model = "model"
    dataset = "dataset"
    code = "code"


class Artifact(BaseModel):
    id: str
    name: str
    type: ArtifactType
    version: str = "1.0.0"
    description: str | None = None
    created_at: datetime = datetime.utcnow()


@router.put("/ingest")
def ingest(payload: Union[Artifact, List[Artifact]] = Body(...)):
    items = payload if isinstance(payload, list) else [payload]
    existing = {a.get("id") for a in _INMEM_DB.get("artifacts", [])}
    ingested_count = 0
    for a in items:
        # Convert Pydantic model to dict properly (serialize datetime to ISO string)
        if hasattr(a, "model_dump"):
            artifact_dict = a.model_dump(mode="json")
        else:
            artifact_dict = dict(a)
        # Ensure datetime is serialized
        if "created_at" in artifact_dict:
            if isinstance(artifact_dict["created_at"], datetime):
                artifact_dict["created_at"] = artifact_dict["created_at"].isoformat()
        if artifact_dict.get("id") not in existing:
            _INMEM_DB.setdefault("artifacts", []).append(artifact_dict)
            existing.add(artifact_dict.get("id"))
            ingested_count += 1
    return {"ingested": ingested_count}


@router.get("/artifacts")
def list_artifacts():
    # Always return a list, never None
    artifacts = _INMEM_DB.get("artifacts", [])
    return artifacts if artifacts else []


@router.get("/artifacts/by-name/{name}")
def by_name(name: str):
    artifacts = _INMEM_DB.get("artifacts", [])
    out = [a for a in artifacts if a.get("name") == name]
    if not out:
        raise HTTPException(status_code=404, detail="Not found")
    return out


@router.get("/artifacts/{artifact_id}")
def by_id(artifact_id: str):
    artifacts = _INMEM_DB.get("artifacts", [])
    for a in artifacts:
        if a.get("id") == artifact_id:
            return a
    raise HTTPException(status_code=404, detail="Not found")

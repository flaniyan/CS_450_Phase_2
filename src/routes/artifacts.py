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
    existing = {a["id"] for a in _INMEM_DB["artifacts"]}
    for a in items:
        if a.id not in existing:
            _INMEM_DB["artifacts"].append(a.model_dump())
    return {"ingested": len(items)}


@router.get("/artifacts")
def list_artifacts():
    return _INMEM_DB["artifacts"]


@router.get("/artifacts/by-name/{name}")
def by_name(name: str):
    out = [a for a in _INMEM_DB["artifacts"] if a["name"] == name]
    if not out:
        raise HTTPException(404, "Not found")
    return out


@router.get("/artifacts/{artifact_id}")
def by_id(artifact_id: str):
    for a in _INMEM_DB["artifacts"]:
        if a["id"] == artifact_id:
            return a
    raise HTTPException(404, "Not found")


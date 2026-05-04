from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class PipelineNode(BaseModel):
    id: str
    label: str
    type: str
    risk: Optional[str] = "low"
    metadata: Optional[Dict[str, Any]] = None

class PipelineEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None

class Finding(BaseModel):
    title: str
    severity: str
    description: str
    node_id: Optional[str] = None

class PipelineGraph(BaseModel):
    nodes: List[PipelineNode]
    edges: List[PipelineEdge]
    findings: List[Finding]

PipelineNode.model_rebuild()

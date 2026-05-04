import json

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class RepoScan(Base):
    __tablename__ = "repo_scans"

    id = Column(Integer, primary_key=True, index=True)
    repo = Column(String, index=True)
    run_id = Column(String, index=True)
    risk_score = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    graph_json = Column(Text)
    risk_breakdown = Column(Text)

    findings = relationship("StoredFinding", back_populates="scan")


class StoredFinding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("repo_scans.id"))
    title = Column(String)
    severity = Column(String)
    description = Column(Text)
    node_id = Column(String, nullable=True)

    scan = relationship("RepoScan", back_populates="findings")

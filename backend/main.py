import json

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Depends

from sqlalchemy.orm import Session

from database import Base, engine, get_db

from models.db_models import RepoScan, StoredFinding

from services.scan_storage import save_scan
from services.log_analyzer import analyze_logs
from services.pipeline_diff import diff_pipelines
from services.workflow_parser import parse_workflow_yaml
from services.risk_analyzer import analyze_graph
from services.graph_builder import build_graph
from services.github_client import GitHubClient

app = FastAPI(title="Invisible Pipeline Discovery API")

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.get("/runs/{owner}/{repo}")
async def get_runs(owner: str, repo: str):
    github = GitHubClient()

    try:
        data = await github.get_workflow_runs(owner, repo)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs/{owner}/{repo}")
async def get_jobs(owner: str, repo: str):
    github = GitHubClient()

    runs = await github.get_completed_workflow_runs(owner, repo)

    if not runs.get("workflow_runs"):
        raise HTTPException(status_code=404, detail="No runs found")

    latest_run = runs["workflow_runs"][0]

    jobs = await github.get_jobs_for_run(owner, repo, latest_run["id"])

    return {
        "run_id": latest_run["id"],
        "jobs": jobs
    }


@app.get("/graph/{owner}/{repo}")
async def get_pipeline_graph(owner: str, repo: str, db: Session = Depends(get_db)):
    github = GitHubClient()

    runs = await github.get_completed_workflow_runs(owner, repo)

    if not runs.get("workflow_runs"):
        raise HTTPException(
            status_code=404,
            detail="No completed GitHub Actions runs found for this repository",        )

    latest_run = runs["workflow_runs"][0]

    jobs = await github.get_jobs_for_run(owner, repo, latest_run["id"])
    graph = build_graph(jobs)

    # workflows (declared)
    contents = await github.get_repo_contents(owner, repo, ".github/workflows")
    workflows = []

    for item in contents:
        if item["name"].endswith((".yml", ".yaml")):
            yaml_text = await github.get_file_text(item["download_url"])
            parsed = parse_workflow_yaml(item["name"], yaml_text)
            workflows.extend(parsed)

    # logs (actual execution)
    try:
        logs = await github.get_workflow_logs(owner, repo, latest_run["id"])
    except Exception:
        logs = []

    # analysis
    graph = analyze_graph(graph)
    graph = diff_pipelines(graph, workflows)
    graph = analyze_logs(graph, logs)

    save_scan(db, f"{owner}/{repo}", latest_run["id"], graph)

    return graph

@app.get("/workflows/{owner}/{repo}")
async def get_workflows(owner: str, repo: str):
    github = GitHubClient()

    contents = await github.get_repo_contents(owner, repo, ".github/workflows")

    workflows = []

    for item in contents:
        if item["name"].endswith((".yml", ".yaml")):
            yaml_text = await github.get_file_text(item["download_url"])
            parsed = parse_workflow_yaml(item["name"], yaml_text)
            workflows.extend(parsed)

    return {
        "repo": f"{owner}/{repo}",
        "workflows": workflows
    }

@app.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    scans = (
        db.query(RepoScan)
        .order_by(RepoScan.created_at.desc())
        .limit(20)
        .all()
    )

    return [
        {
            "id": scan.id,
            "repo": scan.repo,
            "run_id": scan.run_id,
            "risk_score": scan.risk_score,
            "created_at": scan.created_at,
            "finding_count": len(scan.findings),
            "risk_breakdown": json.loads(scan.risk_breakdown) if scan.risk_breakdown else {},
        }
        for scan in scans
    ]


@app.get("/dashboard/{scan_id}/findings")
def get_scan_findings(scan_id: int, db: Session = Depends(get_db)):
    findings = (
        db.query(StoredFinding)
        .filter(StoredFinding.scan_id == scan_id)
        .all()
    )

    return [
        {
            "title": finding.title,
            "severity": finding.severity,
            "description": finding.description,
            "node_id": finding.node_id,
        }
        for finding in findings
    ]

@app.get("/dashboard/{scan_id}/graph")
def get_saved_scan_graph(scan_id: int, db: Session = Depends(get_db)):
    scan = db.query(RepoScan).filter(RepoScan.id == scan_id).first()

    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    return json.loads(scan.graph_json)

    findings = db.query(StoredFinding).filter(StoredFinding.scan_id == scan_id).all()

    return {
        "repo": scan.repo,
        "run_id": scan.run_id,
        "risk_score": scan.risk_score,
        "findings": [
            {
                "title": finding.title,
                "severity": finding.severity,
                "description": finding.description,
                "node_id": finding.node_id,
            }
            for finding in findings
        ],
    }

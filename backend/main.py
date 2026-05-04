import json

from fastapi import Request
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models.db_models import RepoScan, StoredFinding
from services.pr_commeter import format_pr_comment
from services.github_app_auth import get_installation_token
from services.github_client import GitHubClient
from services.graph_builder import build_graph
from services.risk_analyzer import analyze_graph
from services.workflow_parser import parse_workflow_yaml
from services.pipeline_diff import diff_pipelines
from services.log_analyzer import analyze_logs
from services.scan_storage import save_scan

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
    try:
        github = GitHubClient()
        return await github.get_workflow_runs(owner, repo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{owner}/{repo}")
async def get_jobs(owner: str, repo: str):
    try:
        github = GitHubClient()

        runs = await github.get_completed_workflow_runs(owner, repo)

        if not runs.get("workflow_runs"):
            raise HTTPException(status_code=404, detail="No completed workflow runs found")

        latest_run = runs["workflow_runs"][0]
        jobs = await github.get_jobs_for_run(owner, repo, latest_run["id"])

        return {
            "run_id": latest_run["id"],
            "jobs": jobs,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/{owner}/{repo}")
async def get_pipeline_graph(owner: str, repo: str, db: Session = Depends(get_db)):
    try:
        github = GitHubClient()

        runs = await github.get_completed_workflow_runs(owner, repo)

        if not runs.get("workflow_runs"):
            raise HTTPException(
                status_code=404,
                detail="No completed GitHub Actions runs found for this repository",
            )

        latest_run = runs["workflow_runs"][0]

        jobs = await github.get_jobs_for_run(owner, repo, latest_run["id"])
        graph = build_graph(jobs)

        try:
            contents = await github.get_repo_contents(owner, repo, ".github/workflows")
        except Exception:
            contents = []

        workflows = []

        for item in contents:
            if item["name"].endswith((".yml", ".yaml")):
                yaml_text = await github.get_file_text(item["download_url"])
                parsed = parse_workflow_yaml(item["name"], yaml_text)
                workflows.extend(parsed)

        try:
            logs = await github.get_workflow_logs(owner, repo, latest_run["id"])
        except Exception:
            logs = []

        graph = analyze_graph(graph)
        graph = diff_pipelines(graph, workflows)
        graph = analyze_logs(graph, logs)

        save_scan(db, f"{owner}/{repo}", latest_run["id"], graph)

        return graph

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workflows/{owner}/{repo}")
async def get_workflows(owner: str, repo: str):
    try:
        github = GitHubClient()

        try:
            contents = await github.get_repo_contents(owner, repo, ".github/workflows")
        except Exception:
            contents = []

        workflows = []

        for item in contents:
            if item["name"].endswith((".yml", ".yaml")):
                yaml_text = await github.get_file_text(item["download_url"])
                parsed = parse_workflow_yaml(item["name"], yaml_text)
                workflows.extend(parsed)

        return {
            "repo": f"{owner}/{repo}",
            "workflows": workflows,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
            "risk_breakdown": json.loads(scan.risk_breakdown)
            if scan.risk_breakdown
            else {},
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

    if not scan.graph_json:
        raise HTTPException(status_code=404, detail="Saved graph not found")

    return json.loads(scan.graph_json)

from fastapi import Request

@app.post("/github/webhook")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
        event = request.headers.get("X-GitHub-Event")

        print("WEBHOOK HIT:", event)

        if event == "workflow_run":
            action = payload.get("action")

            if action == "completed":
                repo = payload["repository"]["full_name"]
                run_id = payload["workflow_run"]["id"]

                owner, repo_name = repo.split("/")

                installation_id = payload["installation"]["id"]
                installation_token = await get_installation_token(installation_id)
                github = GitHubClient(token=installation_token)

                jobs = await github.get_jobs_for_run(owner, repo_name, run_id)
                graph = build_graph(jobs)

                try:
                    contents = await github.get_repo_contents(owner, repo_name, ".github/workflows")
                except Exception:
                    contents = []

                workflows = []

                for item in contents:
                    if item["name"].endswith((".yml", ".yaml")):
                        yaml_text = await github.get_file_text(item["download_url"])
                        parsed = parse_workflow_yaml(item["name"], yaml_text)
                        workflows.extend(parsed)

                try:
                    logs = await github.get_workflow_logs(owner, repo_name, run_id)
                except Exception:
                    logs = []

                graph = analyze_graph(graph)
                graph = diff_pipelines(graph, workflows)
                graph = analyze_logs(graph, logs)

                save_scan(db, repo, run_id, graph)

    head_sha = payload["workflow_run"].get("head_sha")
    comment_body = format_pr_comment(repo, graph)

    if comment_body and head_sha:
        try:
            prs = await github.get_pull_requests_for_commit(owner, repo_name, head_sha)

            if prs:
                pr_number = prs[0]["number"]
                await github.create_pr_comment(owner, repo_name, pr_number, comment_body)
                print(f"Commented on PR #{pr_number}")
        except Exception as e:
            print("PR comment error:", e)

                print(f"Auto-scanned {repo}")

                return {"status": "scanned", "repo": repo}

        return {"status": "ignored", "event": event}

    except Exception as e:
        print("WEBHOOK ERROR:", str(e))
        return {"status": "error", "detail": str(e)}

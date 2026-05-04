import json
from models.db_models import RepoScan, StoredFinding

def calculate_risk_breakdown(findings):
    breakdown = {
        "unpinned_actions": 0,
        "third_party_actions": 0,
        "secrets": 0,
        "dangerous_commands": 0,
        "external_calls": 0,
        "dependency_installs": 0,
        "other": 0,
    }

    for f in findings:
        title = f.title.lower()

        if "unpinned" in title:
            breakdown["unpinned_actions"] += 1
        elif "third-party" in title:
            breakdown["third_party_actions"] += 1
        elif "secret" in title or "credential" in title:
            breakdown["secrets"] += 1
        elif "dangerous shell" in title:
            breakdown["dangerous_commands"] += 1
        elif "external" in title or "download" in title:
            breakdown["external_calls"] += 1
        elif "dependency" in title:
            breakdown["dependency_installs"] += 1
        else:
            breakdown["other"] += 1

    return breakdown

def calculate_risk_score(findings):
    score = 0

    for f in findings:
        if f.title == "Unpinned GitHub Action":
            score += 20

        elif f.title == "Third-party GitHub Action trust risk":
            if f.severity == "high":
                score += 25
            else:
                score += 10

        elif "secret" in f.title.lower():
            score += 30

        elif "dangerous shell" in f.title.lower():
            score += 40

        elif "external http" in f.title.lower():
            score += 25

        elif "download" in f.title.lower():
            score += 25

        elif f.severity == "high":
            score += 15

        elif f.severity == "medium":
            score += 7

        elif f.severity == "low":
            score += 3

    # 🔥 cap + normalize
    return min(score, 100)

def save_scan(db, repo, run_id, graph):
    risk_breakdown = calculate_risk_breakdown(graph.findings)
    risk_score = calculate_risk_score(graph.findings)

    scan = RepoScan(
        repo=repo,
        run_id=str(run_id),
        risk_score=risk_score,
        graph_json=json.dumps(graph.model_dump()),
        risk_breakdown=json.dumps(risk_breakdown),
    )

    db.add(scan)
    db.commit()
    db.refresh(scan)

    for finding in graph.findings:
        stored_finding = StoredFinding(
            scan_id=scan.id,
            title=finding.title,
            severity=finding.severity,
            description=finding.description,
            node_id=finding.node_id,
        )

        db.add(stored_finding)

    db.commit()

    return scan

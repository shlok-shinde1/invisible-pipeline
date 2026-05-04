import re
from models.pipeline import Finding


def extract_step_number(file_name):
    match = re.search(r"/(\d+)_", file_name)

    if not match:
        match = re.search(r"^(\d+)_", file_name)

    if not match:
        return None

    return int(match.group(1))


def find_node_by_step_number(graph, step_number):
    for node in graph.nodes:
        if node.type != "step":
            continue

        parts = node.id.split("-")

        if parts[-1].isdigit() and int(parts[-1]) == step_number:
            return node

    return None


def add_finding(graph, node, title, severity, description):
    if node:
        if severity == "high":
            node.risk = "high"
        elif severity == "medium" and node.risk == "low":
            node.risk = "medium"

    graph.findings.append(
        Finding(
            title=title,
            severity=severity,
            description=description,
            node_id=node.id if node else None,
        )
    )


def analyze_logs(graph, logs):
    for log in logs:
        content = log["content"]
        lowered = content.lower()

        step_number = extract_step_number(log["file"])
        node = find_node_by_step_number(graph, step_number) if step_number else None

        if node and node.label.lower() == "complete job":
            continue

        if "npm install" in lowered or "npm ci" in lowered:
            add_finding(
                graph,
                node,
                "Dependency installation detected",
                "low",
                f"Package installation found in {log['file']}",
            )

        if "curl " in lowered:
            add_finding(
                graph,
                node,
                "External HTTP request detected",
                "high",
                f"curl command found in {log['file']}",
            )

        if "wget " in lowered:
            add_finding(
                graph,
                node,
                "External download detected",
                "high",
                f"wget command found in {log['file']}",
            )

        if "chmod 777" in lowered or "sudo " in lowered or "rm -rf" in lowered:
            add_finding(
                graph,
                node,
                "Dangerous shell command detected",
                "high",
                f"Risky shell command found in {log['file']}",
            )

        if "github_token" in lowered or "secrets." in lowered or "password" in lowered:
            add_finding(
                graph,
                node,
                "Possible secret reference detected",
                "high",
                f"Possible credential usage found in {log['file']}",
            )

    return graph

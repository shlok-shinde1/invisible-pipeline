import re
from models.pipeline import Finding


KNOWN_ACTION_ORGS = ["actions", "github", "docker"]


def add_finding(graph, node, title, severity, description):
    if severity == "high":
        node.risk = "high"
    elif severity == "medium" and node.risk == "low":
        node.risk = "medium"

    graph.findings.append(
        Finding(
            title=title,
            severity=severity,
            description=description,
            node_id=node.id,
        )
    )


def extract_action_name(content):
    match = re.search(r"([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)@([^\s]+)", content)

    if not match:
        return None, None

    return match.group(1), match.group(2)


def is_unpinned_action(version):
    if not version:
        return False

    return not re.fullmatch(r"[a-f0-9]{40}", version)


def classify_action_trust(action_name):
    if not action_name:
        return None, None

    org = action_name.split("/")[0]

    if org == "actions":
        return "low", "Official GitHub action"

    if org in KNOWN_ACTION_ORGS:
        return "medium", "Well-known organization action"

    return "high", "Unverified third-party action"


def analyze_graph(graph):
    for node in graph.nodes:
        if node.type != "step":
            continue

        if node.label.lower().startswith("post run"):
            continue

        content = node.label.lower()

        if node.metadata:
            if node.metadata.get("run"):
                content += " " + node.metadata["run"].lower()
            if node.metadata.get("uses"):
                content += " " + node.metadata["uses"].lower()

        action_name, version = extract_action_name(content)

        if action_name:
            add_finding(
                graph,
                node,
                "GitHub Action execution detected",
                "medium",
                f"{action_name}@{version} executed in '{node.label}'",
            )

            if is_unpinned_action(version):
                add_finding(
                    graph,
                    node,
                    "Unpinned GitHub Action",
                    "high",
                    f"{action_name}@{version} uses a tag instead of a full commit SHA",
                )

            trust_severity, trust_description = classify_action_trust(action_name)

            if trust_severity and trust_severity != "low":
                add_finding(
                    graph,
                    node,
                    "Third-party GitHub Action trust risk",
                    trust_severity,
                    f"{action_name} is classified as: {trust_description}",
                )

        if any(k in content for k in ["token", "secret", "password"]):
            add_finding(
                graph,
                node,
                "Possible secret or credential usage",
                "high",
                f"Credential-related keyword detected in '{node.label}'",
            )

        if any(k in content for k in ["deploy", "release", "publish"]):
            add_finding(
                graph,
                node,
                "Deployment or publishing step",
                "medium",
                f"Deployment-related step detected in '{node.label}'",
            )

    return graph

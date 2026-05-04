from models.pipeline import Finding

def normalize(text):
    if not text:
        return ""
    return text.lower().strip()


def diff_pipelines(graph, workflows):
    declared_steps = set()

    # collect declared step names + commands
    for wf in workflows:
        for step in wf.get("steps", []):
            declared_steps.add(normalize(step.get("name")))
            declared_steps.add(normalize(step.get("run")))
            declared_steps.add(normalize(step.get("uses")))

    for node in graph.nodes:
        if node.type != "step":
            continue

        label = normalize(node.label)

        run = ""
        uses = ""

        if node.metadata:
            run = normalize(node.metadata.get("run"))
            uses = normalize(node.metadata.get("uses"))

        # check if anything matches declared pipeline
        if not any([
            label in declared_steps,
            run in declared_steps,
            uses in declared_steps
        ]):
            graph.findings.append(
                Finding(
                    title="Undeclared step execution",
                    severity="high",
                    description=f"Step '{node.label}' executed but not found in workflow YAML",
                    node_id=node.id,
                )
            )

        # detect skipped declared steps
        if node.metadata and node.metadata.get("conclusion") == "skipped":
            graph.findings.append(
                Finding(
                    title="Conditional or hidden execution path",
                    severity="medium",
                    description=f"Step '{node.label}' was skipped (possible hidden logic)",
                    node_id=node.id,
                )
            )

    return graph

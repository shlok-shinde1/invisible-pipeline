from models.pipeline import PipelineNode, PipelineEdge, PipelineGraph

def build_graph(jobs_data):
    nodes = []
    edges = []
    findings = []

    jobs = jobs_data.get("jobs", [])

    for job in jobs:
        job_id = f"job-{job['id']}"

        nodes.append(PipelineNode(
            id=job_id,
            label=job["name"],
            type="job",
            risk="low",
            metadata={
                "status": job.get("status"),
                "conclusion": job.get("conclusion"),
            }
        ))

        prev_step_id = None

        for step in job.get("steps", []):
            step_id = f"step-{job['id']}-{step['number']}"

            nodes.append(PipelineNode(
                id=step_id,
                label=step["name"],
                type="step",
                risk="low",
                metadata={
                    "status": step.get("status"),
                    "conclusion": step.get("conclusion"),
                    "started_at": step.get("started_at"),
                    "completed_at": step.get("completed_at"),
                    "run": step.get("run"),
                    "uses": step.get("uses"),
                }
            ))

            if prev_step_id is None:
                edges.append(PipelineEdge(
                    source=job_id,
                    target=step_id,
                    label="starts"
                ))
            else:
                edges.append(PipelineEdge(
                    source=prev_step_id,
                    target=step_id,
                    label="next"
                ))

            prev_step_id = step_id

    return PipelineGraph(nodes=nodes, edges=edges, findings=findings)

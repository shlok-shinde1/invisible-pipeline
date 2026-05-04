import yaml

def parse_workflow_yaml(file_name, yaml_text):
    parsed = yaml.safe_load(yaml_text)

    workflows = []

    if not parsed:
        return workflows

    jobs = parsed.get("jobs", {})

    for job_name, job_data in jobs.items():
        workflow_job = {
            "workflow_file": file_name,
            "job_name": job_name,
            "runs_on": job_data.get("runs-on"),
            "steps": []
        }

        for index, step in enumerate(job_data.get("steps", []), start=1):
            workflow_job["steps"].append({
                "number": index,
                "name": step.get("name", f"step-{index}"),
                "run": step.get("run"),
                "uses": step.get("uses"),
                "if": step.get("if"),
                "env": step.get("env"),
            })

        workflows.append(workflow_job)

    return workflows

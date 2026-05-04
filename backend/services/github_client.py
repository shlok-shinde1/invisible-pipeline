import httpx
import zipfile
import io
from config import GITHUB_TOKEN

class GitHubClient:
    def __init__(self, token=None):
        self.headers = {
            "Authorization": f"Bearer {token or GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        }

    async def get_workflow_runs(self, owner: str, repo: str):
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=self.headers)
            res.raise_for_status()
            return res.json()

    async def get_completed_workflow_runs(self, owner: str, repo: str):
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?status=completed"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=self.headers)
            res.raise_for_status()
            return res.json()

    async def get_jobs_for_run(self, owner: str, repo: str, run_id: int):
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=self.headers)
            res.raise_for_status()
            return res.json()

    async def get_repo_contents(self, owner: str, repo: str, path: str):
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=self.headers)
            res.raise_for_status()
            return res.json()

    async def get_file_text(self, download_url: str):
        async with httpx.AsyncClient() as client:
            res = await client.get(download_url)
            res.raise_for_status()
            return res.text

    async def get_workflow_logs(self, owner: str, repo: str, run_id: int):
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/logs"

        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=self.headers, follow_redirects=True)
            res.raise_for_status()

            zip_bytes = io.BytesIO(res.content)

            logs = []

            with zipfile.ZipFile(zip_bytes) as z:
                for file_name in z.namelist():
                    with z.open(file_name) as f:
                        logs.append({
                            "file": file_name,
                            "content": f.read().decode("utf-8", errors="ignore")
                        })

            return logs

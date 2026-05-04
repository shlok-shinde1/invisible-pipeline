import time
import jwt
import httpx

from config import GITHUB_APP_ID, GITHUB_PRIVATE_KEY


def create_app_jwt():
    now = int(time.time())

    payload = {
        "iat": now - 60,
        "exp": now + 10 * 60,
        "iss": GITHUB_APP_ID,
    }

    private_key = GITHUB_PRIVATE_KEY.replace("\\n", "\n")

    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(installation_id: int):
    app_jwt = create_app_jwt()

    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(url, headers=headers)
        res.raise_for_status()
        return res.json()["token"]

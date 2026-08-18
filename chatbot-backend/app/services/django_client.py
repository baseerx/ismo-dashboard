import logging
from typing import Any, Dict, Optional

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)


async def django_get(
    path: str,
    auth_header: Optional[str],
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    headers = {"Authorization": auth_header} if auth_header else {}

    async with httpx.AsyncClient(base_url=settings.DJANGO_API_BASE_URL, timeout=10.0) as client:
        response = await client.get(path, headers=headers, params=params or {})
        if response.status_code >= 400:
            logger.warning(
                "django_get: %s returned %d - %s (auth_header present: %s)",
                path, response.status_code, response.text[:300], bool(auth_header),
            )
        response.raise_for_status()
        return response.json()


async def django_post(
    path: str,
    auth_header: Optional[str],
    json: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    headers = {"Authorization": auth_header} if auth_header else {}

    async with httpx.AsyncClient(base_url=settings.DJANGO_API_BASE_URL, timeout=10.0) as client:
        response = await client.post(path, headers=headers, json=json or {})
        if response.status_code >= 400:
            logger.warning(
                "django_post: %s returned %d - %s (auth_header present: %s)",
                path, response.status_code, response.text[:300], bool(auth_header),
            )
        response.raise_for_status()
        return response.json()
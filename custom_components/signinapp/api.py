"""API Client for Sign In App."""
import logging
import aiohttp
from typing import Optional, Dict, Any

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)

HEADERS = {
    "accept": "application/json",
    "accept-language": "en-GB-oxendict,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://companion.signin.app",
    "referer": "https://companion.signin.app/",
    "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36",
    "x-app-version": "Web companion app/3.18.2+302148",
}

class SignInAppApi:
    """SignInApp API Client."""

    def __init__(self, session: aiohttp.ClientSession, timezone: str = "Europe/London"):
        """Initialize the API client."""
        self._session = session
        self._timezone = timezone
        self._token: Optional[str] = None

    def set_token(self, token: str):
        """Set the authentication token."""
        self._token = token

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for requests."""
        headers = HEADERS.copy()
        headers["x-timezone"] = self._timezone
        if self._token:
            headers["authorization"] = f"Bearer {self._token}"
        return headers

    async def connect(self, code: str) -> str:
        """Exchange companion code for a token."""
        url = f"{API_BASE_URL}/connect"
        headers = self._get_headers()
        # Ensure no token is sent for connect? PS script uses CommonHeaders not AuthHeaders.
        # So I should remove authorization if it exists, although it shouldn't be set yet.
        if "authorization" in headers:
            del headers["authorization"]

        payload = {"code": code}

        async with self._session.post(url, headers=headers, json=payload) as response:
            data = await response.json()
            if not data.get("success") or not data.get("token"):
                _LOGGER.error("Failed to connect: %s", data)
                raise Exception(f"Connection failed: {data}")
            return data["token"]

    async def sign_in(self, site_id: int, lat: float, lng: float, accuracy: float) -> Dict[str, Any]:
        """Sign in to a site."""
        url = f"{API_BASE_URL}/sign-in"
        headers = self._get_headers()

        payload = {
            "method": "sign-in",
            "automated": False,
            "location": {
                "accuracy": accuracy,
                "lat": lat,
                "lng": lng
            },
            "siteId": site_id,
            "additional": [],
            "personalFields": {},
            "notifyId": None,
            "messages": []
        }

        async with self._session.post(url, headers=headers, json=payload) as response:
            response.raise_for_status()
            return await response.json()

    async def sign_out(self, site_id: int, lat: float, lng: float, accuracy: float) -> Dict[str, Any]:
        """Sign out from a site."""
        url = f"{API_BASE_URL}/sign-out"
        headers = self._get_headers()

        payload = {
            "automated": False,
            "location": {
                "accuracy": accuracy,
                "lat": lat,
                "lng": lng
            },
            "siteId": site_id,
            "additional": [],
            "personalFields": {},
            "notifyId": None,
            "messages": []
        }

        async with self._session.post(url, headers=headers, json=payload) as response:
            response.raise_for_status()
            return await response.json()

    async def get_config(self) -> Dict[str, Any]:
        """Get configuration and status."""
        url = f"{API_BASE_URL}/config-v2"
        headers = self._get_headers()

        async with self._session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.json()

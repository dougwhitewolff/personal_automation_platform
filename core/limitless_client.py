"""
Limitless API client wrapper.

Handles all interactions with the Limitless API including:
- Polling for new lifelogs
- Searching lifelogs
- Fetching full day transcripts
"""

import requests
from datetime import date, datetime
from typing import List, Dict, Optional
import time


class LimitlessClient:
    """Wrapper for the official Limitless Developer API (v1, 2025)."""

    def __init__(self, api_key: str, base_url: str = "https://api.limitless.ai/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

    # -------------------------------------------------------------------------
    # 1. Poll recent lifelogs
    # -------------------------------------------------------------------------
    def poll_recent_entries(
        self,
        start_time: Optional[str] = None,
        limit: int = 10,
        timezone: str = "America/Los_Angeles"
    ) -> List[Dict]:
        """
        Poll for recent lifelog entries.
        Ensures timestamps follow the API's required format (no offsets, lowercase booleans).
        Automatically retries with 'date' mode if needed.
        """
        now = datetime.utcnow()

        def _request(params):
            response = requests.get(
                f"{self.base_url}/lifelogs",
                params=params,
                headers=self.headers,
                timeout=15
            )
            return response

        # --- Clean timestamp formatting ---
        params = {
            "limit": str(min(limit, 10)),          # ensure string type
            "direction": "desc",
            "includeMarkdown": "true"              # must be lowercase string
        }

        if start_time:
            clean_start = start_time.replace("T", " ").split("Z")[0].split(".")[0]
            # remove timezone suffix if any (e.g., "-08:00")
            clean_start = clean_start.split("+")[0].split("-08:00")[0].strip()

            clean_end = now.strftime("%Y-%m-%d %H:%M:%S")

            params.update({
                "start": clean_start,
                "end": clean_end
            })
        else:
            params.update({
                "date": now.strftime("%Y-%m-%d"),
                "timezone": timezone
            })

        print("\n=== LIMITLESS DEBUG REQUEST (PRIMARY) ===")
        print(f"URL: {self.base_url}/lifelogs")
        print(f"Headers: {{'X-API-Key': '***redacted***', 'Content-Type': 'application/json'}}")
        print(f"Params: {params}")
        print("=========================================")

        try:
            response = _request(params)
            print(f"Status: {response.status_code}")
            print(f"Body: {response.text}\n")

            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("lifelogs", data.get("lifelogs", []))

            if response.status_code == 429:
                print("⚠️  Rate limited by Limitless API — backing off for 60s")
                time.sleep(60)
                return []

            if response.status_code == 400:
                print("⚠️  Falling back to 'date' parameter (start/end rejected by API)...")
                fallback_params = {
                    "date": now.strftime("%Y-%m-%d"),
                    "includeMarkdown": "true",
                    "limit": str(min(limit, 10)),
                    "direction": "desc",
                    "timezone": timezone
                }

                response = _request(fallback_params)
                print(f"Fallback Status: {response.status_code}")
                print(f"Fallback Body: {response.text}\n")

                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", {}).get("lifelogs", data.get("lifelogs", []))

            print(f"❌ Limitless API error {response.status_code}: {response.text}")
            return []

        except requests.exceptions.RequestException as e:
            print(f"❌ Limitless API request failed: {e}")
            return []

    # -------------------------------------------------------------------------
    # 2. Fetch today’s transcript
    # -------------------------------------------------------------------------
    def get_todays_transcript(self, timezone: str = "America/Los_Angeles") -> str:
        """Fetch all markdown entries for today's date."""
        today = date.today().isoformat()
        params = {
            "date": today,
            "timezone": timezone,
            "includeMarkdown": "true",   # <-- must be lowercase string
            "direction": "asc"
        }

        all_entries = []
        cursor = None

        while True:
            if cursor:
                params["cursor"] = cursor

            try:
                response = requests.get(
                    f"{self.base_url}/lifelogs",
                    params=params,
                    headers=self.headers,
                    timeout=15
                )

                if response.status_code != 200:
                    print(f"❌ Transcript fetch failed: {response.status_code} {response.text}")
                    break

                data = response.json()
                all_entries.extend(data.get("data", {}).get("lifelogs", []))
                cursor = data.get("meta", {}).get("lifelogs", {}).get("nextCursor")

                if not cursor:
                    break

            except requests.exceptions.RequestException as e:
                print(f"❌ Error fetching transcript: {e}")
                break

        transcript = "\n\n---\n\n".join(
            f"[{entry.get('startTime')} - {entry.get('endTime')}]\n{entry.get('markdown','')}"
            for entry in all_entries
        )
        return transcript

    # -------------------------------------------------------------------------
    # 3. Search lifelogs
    # -------------------------------------------------------------------------
    def search_lifelogs(
        self,
        query: str,
        date_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Search lifelogs using hybrid (semantic + keyword) search."""
        params = {
            "search": query,
            "limit": min(limit, 10),
            "includeMarkdown": "true"
        }

        if date_filter:
            params["date"] = date_filter

        try:
            response = requests.get(
                f"{self.base_url}/lifelogs",
                params=params,
                headers=self.headers,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("lifelogs", [])

            print(f"❌ Search failed {response.status_code}: {response.text}")
            return []

        except requests.exceptions.RequestException as e:
            print(f"❌ Search request failed: {e}")
            return []

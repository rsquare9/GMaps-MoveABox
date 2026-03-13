"""
Google Business Profile API Wrapper
MoveABox GBP Agent v2.0

Handles all interactions with the Google Business Profile API:
- Fetching GBP Insights (views, searches, actions)
- Publishing posts
- Fetching and responding to reviews
- Profile updates
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

# GBP API scopes required
SCOPES = [
    "https://www.googleapis.com/auth/business.manage",
]

GBP_BASE_URL = "https://mybusiness.googleapis.com/v4"
GBP_V1_URL = "https://businessprofileperformance.googleapis.com/v1"

LOCATION_ACCOUNT_MAP = {
    "moveabox-bannerghatta": os.getenv("GBP_ACCOUNT_BANNERGHATTA", ""),
    "moveabox-banashankari": os.getenv("GBP_ACCOUNT_BANASHANKARI", ""),
    "moveabox-koramangala": os.getenv("GBP_ACCOUNT_KORAMANGALA", ""),
}


class GBPClient:
    """Client for Google Business Profile API interactions."""

    def __init__(self):
        self.credentials = self._load_credentials()
        self.session = requests.Session()

    def _load_credentials(self) -> Credentials:
        """Load or refresh OAuth2 credentials."""
        token_path = "config/token.json"
        creds = None

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "config/credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())

        return creds

    def _get_headers(self) -> dict:
        """Return authenticated request headers."""
        if self.credentials.expired:
            self.credentials.refresh(Request())
        return {
            "Authorization": f"Bearer {self.credentials.token}",
            "Content-Type": "application/json",
        }

    # -------------------------------------------------------------------------
    # Insights
    # -------------------------------------------------------------------------

    def fetch_insights(self, location_slug: str, days: int = 7) -> dict:
        """
        Fetch GBP performance insights for a location.

        Returns views, searches, and customer actions for the given period.
        """
        account_id = LOCATION_ACCOUNT_MAP.get(location_slug)
        if not account_id:
            raise ValueError(f"Unknown location slug: {location_slug}")

        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)

        url = f"{GBP_V1_URL}/locations/{account_id}:fetchMultiDailyMetricsTimeSeries"
        params = {
            "dailyMetrics": [
                "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
                "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
                "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
                "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
                "CALL_CLICKS",
                "DIRECTION_REQUESTS",
                "WEBSITE_CLICKS",
            ],
            "dailyRange.start_date.year": start_date.year,
            "dailyRange.start_date.month": start_date.month,
            "dailyRange.start_date.day": start_date.day,
            "dailyRange.end_date.year": end_date.year,
            "dailyRange.end_date.month": end_date.month,
            "dailyRange.end_date.day": end_date.day,
        }

        response = self.session.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        data = response.json()

        return self._parse_insights(data, location_slug)

    def _parse_insights(self, raw: dict, location_slug: str) -> dict:
        """Parse raw API response into a clean insights dict."""
        insights = {
            "location_slug": location_slug,
            "fetched_at": datetime.utcnow().isoformat(),
            "total_views": 0,
            "search_views": 0,
            "maps_views": 0,
            "calls": 0,
            "direction_requests": 0,
            "website_clicks": 0,
            "daily_breakdown": [],
        }

        for series in raw.get("multiDailyMetricTimeSeries", []):
            metric = series.get("dailyMetric", "")
            for point in series.get("timeSeries", {}).get("datedValues", []):
                value = int(point.get("value", 0))
                if "SEARCH" in metric:
                    insights["search_views"] += value
                if "MAPS" in metric:
                    insights["maps_views"] += value
                if metric == "CALL_CLICKS":
                    insights["calls"] += value
                if metric == "DIRECTION_REQUESTS":
                    insights["direction_requests"] += value
                if metric == "WEBSITE_CLICKS":
                    insights["website_clicks"] += value

        insights["total_views"] = insights["search_views"] + insights["maps_views"]
        return insights

    def fetch_all_insights(self, days: int = 7) -> list[dict]:
        """Fetch insights for all 3 MoveABox locations."""
        results = []
        for slug in LOCATION_ACCOUNT_MAP:
            try:
                result = self.fetch_insights(slug, days)
                results.append(result)
                logger.info(f"Fetched insights for {slug}")
            except Exception as e:
                logger.error(f"Failed to fetch insights for {slug}: {e}")
        return results

    # -------------------------------------------------------------------------
    # Reviews
    # -------------------------------------------------------------------------

    def fetch_reviews(self, location_slug: str) -> list[dict]:
        """Fetch all reviews for a location."""
        account_id = LOCATION_ACCOUNT_MAP.get(location_slug)
        url = f"{GBP_BASE_URL}/accounts/{account_id}/locations/{account_id}/reviews"

        reviews = []
        page_token = None

        while True:
            params = {"pageSize": 50}
            if page_token:
                params["pageToken"] = page_token

            response = self.session.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()

            reviews.extend(data.get("reviews", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return reviews

    def respond_to_review(
        self, location_slug: str, review_id: str, response_text: str
    ) -> dict:
        """Post a response to a specific review."""
        account_id = LOCATION_ACCOUNT_MAP.get(location_slug)
        url = (
            f"{GBP_BASE_URL}/accounts/{account_id}/locations/{account_id}"
            f"/reviews/{review_id}/reply"
        )

        payload = {"comment": response_text}
        response = self.session.put(
            url, headers=self._get_headers(), json=payload
        )
        response.raise_for_status()
        logger.info(f"Responded to review {review_id} for {location_slug}")
        return response.json()

    # -------------------------------------------------------------------------
    # Posts
    # -------------------------------------------------------------------------

    def publish_post(self, location_slug: str, post: dict) -> dict:
        """
        Publish a post to Google Business Profile.

        post dict must contain: post_body, cta_text, cta_url, and optionally
        call_to_action_type (BOOK, ORDER, SHOP, SIGN_UP, GET_OFFER, LEARN_MORE, CALL)
        """
        account_id = LOCATION_ACCOUNT_MAP.get(location_slug)
        url = f"{GBP_BASE_URL}/accounts/{account_id}/locations/{account_id}/localPosts"

        cta_type_map = {
            "Book now": "BOOK",
            "Call now": "CALL",
            "Get offer": "GET_OFFER",
            "Learn more": "LEARN_MORE",
            "Order online": "ORDER",
            "Sign up": "SIGN_UP",
            "Get quote": "GET_OFFER",
        }

        payload = {
            "languageCode": "en-IN",
            "summary": post["post_body"],
            "callToAction": {
                "actionType": cta_type_map.get(post.get("cta_text", ""), "LEARN_MORE"),
                "url": post.get("cta_url", "https://moveabox.in"),
            },
            "topicType": "STANDARD",
        }

        response = self.session.post(
            url, headers=self._get_headers(), json=payload
        )
        response.raise_for_status()
        result = response.json()
        logger.info(f"Published post for {location_slug}: {result.get('name')}")
        return result

    # -------------------------------------------------------------------------
    # Profile
    # -------------------------------------------------------------------------

    def get_profile(self, location_slug: str) -> dict:
        """Fetch the current GBP profile for a location."""
        account_id = LOCATION_ACCOUNT_MAP.get(location_slug)
        url = f"{GBP_BASE_URL}/accounts/{account_id}/locations/{account_id}"

        response = self.session.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_all_profiles(self) -> list[dict]:
        """Fetch profiles for all 3 locations."""
        results = []
        for slug in LOCATION_ACCOUNT_MAP:
            try:
                profile = self.get_profile(slug)
                profile["location_slug"] = slug
                results.append(profile)
            except Exception as e:
                logger.error(f"Failed to fetch profile for {slug}: {e}")
        return results


def load_benchmarks() -> dict:
    """Load existing benchmark data from file."""
    path = "data/benchmarks.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_benchmarks(data: dict) -> None:
    """Save benchmark data to file."""
    path = "data/benchmarks.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def append_daily_snapshot(insights_list: list[dict]) -> None:
    """Append today's insights snapshot to benchmarks.json."""
    benchmarks = load_benchmarks()
    today = datetime.utcnow().date().isoformat()

    if "daily_snapshots" not in benchmarks:
        benchmarks["daily_snapshots"] = {}

    benchmarks["daily_snapshots"][today] = {
        "fetched_at": datetime.utcnow().isoformat(),
        "locations": {i["location_slug"]: i for i in insights_list},
    }

    save_benchmarks(benchmarks)
    logger.info(f"Saved daily snapshot for {today}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = GBPClient()
    insights = client.fetch_all_insights(days=7)
    append_daily_snapshot(insights)
    print(json.dumps(insights, indent=2))

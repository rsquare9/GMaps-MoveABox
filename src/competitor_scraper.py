"""
Competitor Data Collection Engine
MoveABox GBP Agent v2.0

Collects and tracks competitor GBP data using Outscraper / SerpAPI.
Feeds the benchmark engine and content differentiation system.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

OUTSCRAPER_API_KEY = os.getenv("OUTSCRAPER_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

LOCATION_COORDINATES = {
    "moveabox-bannerghatta": {"lat": 12.8745, "lng": 77.5970},
    "moveabox-banashankari": {"lat": 12.9256, "lng": 77.5564},
    "moveabox-koramangala": {"lat": 12.9352, "lng": 77.6245},
}

TIER1_KEYWORDS = [
    "packers and movers",
    "house shifting services",
    "office relocation",
    "courier service",
    "storage facility",
]


class CompetitorScraper:
    """Collects competitor GBP data for benchmarking and content differentiation."""

    def __init__(self):
        self.competitors_file = "data/competitors.json"
        self.competitors = self._load_competitors()

    def _load_competitors(self) -> dict:
        """Load existing competitor data."""
        if os.path.exists(self.competitors_file):
            with open(self.competitors_file) as f:
                return json.load(f)
        return {"locations": {}, "last_discovery": None}

    def _save_competitors(self) -> None:
        """Persist competitor data to file."""
        with open(self.competitors_file, "w") as f:
            json.dump(self.competitors, f, indent=2)

    # -------------------------------------------------------------------------
    # Competitor Discovery
    # -------------------------------------------------------------------------

    def discover_competitors(self, location_slug: str) -> list[dict]:
        """
        Search Google Maps for packers/movers near the location.
        Returns top competitors sorted by composite threat score.
        """
        coords = LOCATION_COORDINATES.get(location_slug)
        if not coords:
            raise ValueError(f"Unknown location: {location_slug}")

        all_results = []

        for keyword in TIER1_KEYWORDS:
            results = self._search_google_maps(
                keyword=f"{keyword} Bangalore",
                lat=coords["lat"],
                lng=coords["lng"],
            )
            all_results.extend(results)

        # Deduplicate by place_id
        seen = set()
        unique = []
        for r in all_results:
            pid = r.get("place_id", "")
            if pid and pid not in seen:
                seen.add(pid)
                unique.append(r)

        # Score and rank
        scored = [self._score_competitor(c, location_slug) for c in unique]
        scored.sort(key=lambda x: x["threat_score"], reverse=True)

        # Return top 5
        top5 = scored[:5]
        logger.info(
            f"Discovered {len(top5)} top competitors for {location_slug}"
        )
        return top5

    def _search_google_maps(
        self, keyword: str, lat: float, lng: float
    ) -> list[dict]:
        """Search Google Maps via SerpAPI for a keyword near coordinates."""
        if not SERPAPI_KEY:
            logger.warning("SERPAPI_KEY not set — using mock data")
            return self._mock_search_results(keyword)

        url = "https://serpapi.com/search"
        params = {
            "engine": "google_maps",
            "q": keyword,
            "ll": f"@{lat},{lng},14z",
            "type": "search",
            "api_key": SERPAPI_KEY,
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        return data.get("local_results", [])

    def _mock_search_results(self, keyword: str) -> list[dict]:
        """Return mock results for testing without API keys."""
        return [
            {
                "place_id": f"mock_{i}",
                "title": f"Mock Competitor {i}",
                "rating": 4.0 + (i * 0.1),
                "reviews": 50 + (i * 30),
                "type": "Moving company",
                "address": "Bangalore, Karnataka",
            }
            for i in range(1, 8)
        ]

    def _score_competitor(
        self, competitor: dict, location_slug: str
    ) -> dict:
        """Compute a composite threat score for a competitor."""
        review_count = competitor.get("reviews", 0)
        rating = competitor.get("rating", 0)

        # Weighted threat score
        threat_score = (
            (min(review_count, 500) / 500) * 40
            + (rating / 5.0) * 30
            + 30  # base score; reduced by other factors later
        )

        return {
            **competitor,
            "location_zone": location_slug,
            "threat_score": round(threat_score, 2),
            "threat_level": (
                "HIGH" if threat_score >= 70
                else "MEDIUM" if threat_score >= 45
                else "LOW"
            ),
        }

    # -------------------------------------------------------------------------
    # Weekly Data Collection
    # -------------------------------------------------------------------------

    def collect_competitor_data(self, competitor_id: str) -> dict:
        """
        Collect full GBP data for a single competitor via Outscraper.
        Returns updated competitor profile.
        """
        location_data = None
        for loc_data in self.competitors.get("locations", {}).values():
            for comp in loc_data:
                if comp.get("competitor_id") == competitor_id:
                    location_data = comp
                    break

        if not location_data:
            raise ValueError(f"Competitor {competitor_id} not found")

        gbp_url = location_data.get("gbp_url", "")
        if not gbp_url:
            logger.warning(f"No GBP URL for competitor {competitor_id}")
            return location_data

        if OUTSCRAPER_API_KEY:
            updated = self._scrape_via_outscraper(gbp_url)
        else:
            logger.warning("OUTSCRAPER_API_KEY not set — using mock data")
            updated = self._mock_competitor_data(location_data)

        updated["last_updated"] = datetime.utcnow().date().isoformat()
        return updated

    def _scrape_via_outscraper(self, gbp_url: str) -> dict:
        """Scrape GBP data via Outscraper API."""
        url = "https://api.outscraper.com/maps/reviews-v3"
        headers = {"X-API-KEY": OUTSCRAPER_API_KEY}
        params = {
            "query": gbp_url,
            "reviewsLimit": 0,  # We only want profile data, not reviews
            "fields": "name,rating,reviews,photos_count,posts_count",
        }

        response = requests.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        result = data.get("data", [{}])[0] if data.get("data") else {}
        return {
            "review_count": result.get("reviews", 0),
            "average_rating": result.get("rating", 0),
            "total_photos": result.get("photos_count", 0),
            "post_count_last_30d": result.get("posts_count", 0),
        }

    def _mock_competitor_data(self, existing: dict) -> dict:
        """Return mock update data for testing."""
        return {
            **existing,
            "review_count": existing.get("review_count", 0) + 2,
            "average_rating": existing.get("average_rating", 4.0),
            "total_photos": existing.get("total_photos", 0),
            "post_count_last_30d": existing.get("post_count_last_30d", 0),
            "review_velocity_30d": 5,
            "response_rate_pct": 65,
            "avg_response_time_hours": 24,
        }

    def collect_all_competitor_data(self) -> None:
        """Run weekly collection for all 15 competitors."""
        for location_slug, competitors in self.competitors.get(
            "locations", {}
        ).items():
            for comp in competitors:
                try:
                    updated = self.collect_competitor_data(
                        comp["competitor_id"]
                    )
                    comp.update(updated)
                    logger.info(
                        f"Updated {comp['business_name']} for {location_slug}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to update {comp.get('competitor_id')}: {e}"
                    )

        self._save_competitors()

    # -------------------------------------------------------------------------
    # Content Intelligence
    # -------------------------------------------------------------------------

    def get_recent_competitor_posts(
        self, location_slug: str, days: int = 14
    ) -> list[dict]:
        """
        Return all competitor posts from the last N days for a location.
        Used by post_generator.py for content differentiation.
        """
        competitors = self.competitors.get("locations", {}).get(
            location_slug, []
        )
        all_posts = []

        for comp in competitors:
            posts = comp.get("recent_posts", [])
            all_posts.extend(
                [p for p in posts if self._is_within_days(p.get("date", ""), days)]
            )

        return all_posts

    def _is_within_days(self, date_str: str, days: int) -> bool:
        """Check if a date string is within the last N days."""
        if not date_str:
            return False
        try:
            post_date = datetime.fromisoformat(date_str).date()
            cutoff = (datetime.utcnow() - __import__("datetime").timedelta(days=days)).date()
            return post_date >= cutoff
        except ValueError:
            return False

    def get_forbidden_topics(self, location_slug: str) -> list[str]:
        """
        Return list of topics covered by competitors in the last 14 days.
        Used to avoid content overlap.
        """
        recent_posts = self.get_recent_competitor_posts(location_slug, days=14)
        topics = []
        for post in recent_posts:
            topic = post.get("topic", "")
            keywords = post.get("keywords", [])
            if topic:
                topics.append(topic)
            topics.extend(keywords)

        return list(set(topics))

    # -------------------------------------------------------------------------
    # Competitor Discovery Run
    # -------------------------------------------------------------------------

    def run_full_discovery(self) -> None:
        """Run full competitor discovery for all 3 locations. Monthly operation."""
        for location_slug in LOCATION_COORDINATES:
            logger.info(f"Running competitor discovery for {location_slug}")
            top5 = self.discover_competitors(location_slug)

            # Format with full schema
            formatted = []
            for i, comp in enumerate(top5, start=1):
                location_key = location_slug.split("-")[-1]
                formatted.append({
                    "competitor_id": f"comp_{location_key}_{i:03d}",
                    "business_name": comp.get("title", "Unknown"),
                    "gbp_url": comp.get("place_id", ""),
                    "location_zone": location_slug,
                    "distance_km": comp.get("distance", 0),
                    "primary_category": comp.get("type", "Moving Company"),
                    "secondary_categories": [],
                    "review_count": comp.get("reviews", 0),
                    "average_rating": comp.get("rating", 0),
                    "review_velocity_30d": 0,
                    "response_rate_pct": 0,
                    "avg_response_time_hours": 0,
                    "total_photos": 0,
                    "photos_last_30d": 0,
                    "post_count_last_30d": 0,
                    "post_types": [],
                    "qa_count": 0,
                    "services_listed": 0,
                    "has_booking_link": False,
                    "has_messaging": False,
                    "website_url": comp.get("website", ""),
                    "citation_count_estimate": 0,
                    "local_pack_appearances": {},
                    "strengths": [],
                    "weaknesses": [],
                    "threat_level": comp.get("threat_level", "MEDIUM"),
                    "recent_posts": [],
                    "last_updated": datetime.utcnow().date().isoformat(),
                })

            self.competitors.setdefault("locations", {})[location_slug] = formatted

        self.competitors["last_discovery"] = datetime.utcnow().isoformat()
        self._save_competitors()
        logger.info("Competitor discovery complete for all locations")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = CompetitorScraper()
    scraper.run_full_discovery()
    scraper.collect_all_competitor_data()

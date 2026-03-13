"""
Competitor Benchmarking Engine
MoveABox GBP Agent v2.0

Computes the MoveABox Benchmark Score (MBS) for all tracked profiles,
runs gap analysis, and generates prioritized opportunity lists.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# MBS scoring thresholds
SCORING_MATRIX = {
    "review_volume": {
        "weight": 0.15,
        "thresholds": [(50, 3), (200, 6), (float("inf"), 10)],
    },
    "review_quality": {
        "weight": 0.15,
        "thresholds": [(3.5, 3), (4.3, 6), (float("inf"), 10)],
    },
    "review_velocity": {
        "weight": 0.12,
        "thresholds": [(3, 3), (10, 6), (float("inf"), 10)],
    },
    "response_rate": {
        "weight": 0.10,
        "thresholds": [(30, 3), (70, 6), (float("inf"), 10)],
    },
    "content_freshness": {
        "weight": 0.10,
        "thresholds": [(2, 3), (12, 6), (float("inf"), 10)],
    },
    "visual_richness": {
        "weight": 0.08,
        "thresholds": [(15, 3), (50, 6), (float("inf"), 10)],
    },
    "profile_depth": {
        "weight": 0.08,
        "thresholds": [(40, 3), (75, 6), (float("inf"), 10)],
    },
    "qa_coverage": {
        "weight": 0.07,
        "thresholds": [(3, 3), (10, 6), (float("inf"), 10)],
    },
    "citation_strength": {
        "weight": 0.08,
        "thresholds": [(10, 3), (30, 6), (float("inf"), 10)],
    },
    "local_pack_rank": {
        "weight": 0.07,
        "thresholds": [(10, 3), (4, 6), (1, 10)],  # Lower rank = better
        "inverse": True,
    },
}

EFFORT_MULTIPLIERS = {
    "quick_win": 3.0,   # < 1 hour
    "medium": 2.0,       # 1 day
    "high_effort": 1.0,  # 1 week+
}


class BenchmarkEngine:
    """Computes MBS scores and gap analysis for MoveABox and competitors."""

    def __init__(self):
        self.benchmarks_path = "data/benchmarks.json"
        self.competitors_path = "data/competitors.json"
        self.benchmarks = self._load_benchmarks()
        self.competitors = self._load_competitors()

    def _load_benchmarks(self) -> dict:
        if os.path.exists(self.benchmarks_path):
            with open(self.benchmarks_path) as f:
                return json.load(f)
        return {"snapshots": {}, "daily_snapshots": {}}

    def _load_competitors(self) -> dict:
        if os.path.exists(self.competitors_path):
            with open(self.competitors_path) as f:
                return json.load(f)
        return {"locations": {}}

    def _save_benchmarks(self) -> None:
        with open(self.benchmarks_path, "w") as f:
            json.dump(self.benchmarks, f, indent=2)

    # -------------------------------------------------------------------------
    # MBS Score Calculation
    # -------------------------------------------------------------------------

    def score_profile(self, profile: dict) -> dict:
        """
        Compute MBS for a single profile.
        Returns dict with dimension scores and total MBS.
        """
        scores = {}
        total_weighted = 0.0

        for dimension, config in SCORING_MATRIX.items():
            value = profile.get(dimension, 0)
            raw_score = self._threshold_score(
                value, config["thresholds"], config.get("inverse", False)
            )
            weighted = raw_score * config["weight"]
            scores[dimension] = {"raw": raw_score, "weighted": round(weighted, 3)}
            total_weighted += weighted

        mbs = round(total_weighted * 10, 1)  # Scale to 0–100

        return {
            "business_name": profile.get("business_name", "Unknown"),
            "location_slug": profile.get("location_slug", ""),
            "mbs": mbs,
            "dimension_scores": scores,
            "computed_at": datetime.utcnow().isoformat(),
        }

    def _threshold_score(
        self, value: float, thresholds: list, inverse: bool = False
    ) -> int:
        """Convert a raw value to a score 0–10 using threshold bands."""
        if inverse:
            # For rank: lower value is better
            if value <= thresholds[2][0]:
                return thresholds[2][1]
            elif value <= thresholds[1][0]:
                return thresholds[1][1]
            else:
                return thresholds[0][1]
        else:
            for threshold, score in thresholds:
                if value < threshold:
                    return score - 4 if score > 3 else 0
            return thresholds[-1][1]

    # -------------------------------------------------------------------------
    # Weekly Benchmark Snapshot
    # -------------------------------------------------------------------------

    def compute_weekly_snapshot(
        self, moveabox_profiles: list[dict]
    ) -> dict:
        """
        Compute MBS scores for MoveABox and all competitors.
        Stores snapshot in benchmarks.json.
        """
        week_key = datetime.utcnow().strftime("%Y-W%W")
        snapshot = {
            "week": week_key,
            "computed_at": datetime.utcnow().isoformat(),
            "locations": {},
        }

        for profile in moveabox_profiles:
            location_slug = profile.get("location_slug", "")
            location_snapshot = {
                "moveabox": self.score_profile(profile),
                "competitors": [],
            }

            competitors = self.competitors.get("locations", {}).get(
                location_slug, []
            )
            for comp in competitors:
                comp_profile = self._competitor_to_profile(comp)
                score = self.score_profile(comp_profile)
                location_snapshot["competitors"].append(score)

            # Sort competitors by MBS descending
            location_snapshot["competitors"].sort(
                key=lambda x: x["mbs"], reverse=True
            )

            snapshot["locations"][location_slug] = location_snapshot

        self.benchmarks.setdefault("snapshots", {})[week_key] = snapshot
        self._save_benchmarks()
        logger.info(f"Saved weekly benchmark snapshot for {week_key}")
        return snapshot

    def _competitor_to_profile(self, comp: dict) -> dict:
        """Convert competitor data dict to a scorable profile dict."""
        return {
            "business_name": comp.get("business_name", ""),
            "location_slug": comp.get("location_zone", ""),
            "review_volume": comp.get("review_count", 0),
            "review_quality": comp.get("average_rating", 0),
            "review_velocity": comp.get("review_velocity_30d", 0),
            "response_rate": comp.get("response_rate_pct", 0),
            "content_freshness": comp.get("post_count_last_30d", 0),
            "visual_richness": comp.get("total_photos", 0),
            "profile_depth": comp.get("profile_completeness", 50),
            "qa_coverage": comp.get("qa_count", 0),
            "citation_strength": comp.get("citation_count_estimate", 0),
            "local_pack_rank": 5,  # Default if unknown
        }

    # -------------------------------------------------------------------------
    # Gap Analysis
    # -------------------------------------------------------------------------

    def run_gap_analysis(
        self, location_slug: str, moveabox_profile: dict
    ) -> list[dict]:
        """
        Run gap analysis comparing MoveABox against all competitors.
        Returns prioritized list of opportunities.
        """
        competitors = self.competitors.get("locations", {}).get(location_slug, [])
        if not competitors:
            logger.warning(f"No competitors found for {location_slug}")
            return []

        gaps = []
        gap_counter = 1

        for comp in competitors:
            comp_profile = self._competitor_to_profile(comp)

            for dimension, config in SCORING_MATRIX.items():
                moveabox_val = moveabox_profile.get(dimension, 0)
                comp_val = comp_profile.get(dimension, 0)

                if config.get("inverse"):
                    delta = comp_val - moveabox_val  # Lower rank is better for us
                else:
                    delta = moveabox_val - comp_val

                if delta < 0:  # MoveABox is behind
                    effort, effort_mult = self._classify_effort(dimension, abs(delta))
                    action = self._suggest_action(dimension, location_slug, abs(delta))

                    opportunity_score = (
                        config["weight"] * abs(delta) * effort_mult
                    )

                    location_key = location_slug.split("-")[-1].upper()[:3]
                    gaps.append({
                        "gap_id": f"GAP-{location_key}-{gap_counter:03d}",
                        "location": location_slug,
                        "metric": dimension,
                        "moveabox_value": moveabox_val,
                        "competitor_name": comp.get("business_name", ""),
                        "competitor_value": comp_val,
                        "delta": delta,
                        "opportunity_score": round(opportunity_score, 2),
                        "action": action,
                        "effort": effort,
                        "priority": 0,  # Set after sorting
                    })
                    gap_counter += 1

        # Sort by opportunity score and assign priorities
        gaps.sort(key=lambda x: x["opportunity_score"], reverse=True)
        for i, gap in enumerate(gaps):
            gap["priority"] = i + 1

        return gaps

    def _classify_effort(self, dimension: str, delta: float) -> tuple[str, float]:
        """Classify the effort required to close a gap."""
        quick_win_dimensions = {"content_freshness", "qa_coverage", "response_rate"}
        medium_dimensions = {"visual_richness", "profile_depth", "citation_strength"}

        if dimension in quick_win_dimensions:
            return "quick_win", EFFORT_MULTIPLIERS["quick_win"]
        elif dimension in medium_dimensions:
            return "medium", EFFORT_MULTIPLIERS["medium"]
        else:
            return "high_effort", EFFORT_MULTIPLIERS["high_effort"]

    def _suggest_action(
        self, dimension: str, location_slug: str, delta: float
    ) -> str:
        """Generate a specific action recommendation for a gap."""
        location_name = location_slug.split("-")[-1].title()

        action_map = {
            "review_volume": f"Launch review velocity campaign targeting {int(delta/12 + 5)} reviews/month",
            "review_quality": "Audit recent negative reviews; implement post-move follow-up survey",
            "review_velocity": f"Send review requests to last {int(delta * 3)} customers; target {int(delta)} reviews this month",
            "response_rate": "Enable GBP notifications; respond to all unresponded reviews within 24 hours",
            "content_freshness": f"Increase posting to daily — currently behind competitor by {int(delta)} posts/month",
            "visual_richness": f"Upload {int(delta) + 10} new geo-tagged photos: exterior, team, at-work, completed jobs",
            "profile_depth": "Complete all missing profile sections: services menu, attributes, products, description",
            "qa_coverage": "Seed 10 location-specific FAQs covering pricing, timelines, and services",
            "citation_strength": f"Build {int(delta)} new citations on Justdial, Sulekha, IndiaMART, TradeIndia",
            "local_pack_rank": f"Target Tier 1 keywords in next 5 posts; build 3 new citations for {location_name}",
        }
        return action_map.get(dimension, f"Close {dimension} gap of {delta:.1f} units")

    # -------------------------------------------------------------------------
    # Scorecard Generation
    # -------------------------------------------------------------------------

    def generate_scorecard(self, location_slug: str) -> str:
        """Generate a markdown scorecard table for a location."""
        week_key = datetime.utcnow().strftime("%Y-W%W")
        snapshot = self.benchmarks.get("snapshots", {}).get(week_key, {})
        location_data = snapshot.get("locations", {}).get(location_slug, {})

        if not location_data:
            return f"No benchmark data for {location_slug} in week {week_key}"

        moveabox = location_data.get("moveabox", {})
        competitors = location_data.get("competitors", [])

        lines = [
            f"## Benchmark Scorecard — {location_slug.split('-')[-1].title()}",
            f"Week: {week_key}\n",
            "| Business | MBS | Reviews | Rating | Posts/mo | Photos | Trend |",
            "|----------|-----|---------|--------|----------|--------|-------|",
        ]

        lines.append(
            f"| ⭐ MoveABox | {moveabox.get('mbs', 0)}/100 | — | — | — | — | — |"
        )

        for comp in competitors:
            lines.append(
                f"| {comp.get('business_name', 'Competitor')} | "
                f"{comp.get('mbs', 0)}/100 | — | — | — | — | — |"
            )

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Trend Analysis
    # -------------------------------------------------------------------------

    def get_mbs_trend(self, location_slug: str, weeks: int = 4) -> list[dict]:
        """Return MBS scores for MoveABox over the last N weeks."""
        trend = []
        snapshots = self.benchmarks.get("snapshots", {})

        for week_key in sorted(snapshots.keys(), reverse=True)[:weeks]:
            snapshot = snapshots[week_key]
            location_data = snapshot.get("locations", {}).get(location_slug, {})
            moveabox_score = location_data.get("moveabox", {}).get("mbs", 0)
            trend.append({"week": week_key, "mbs": moveabox_score})

        return list(reversed(trend))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    engine = BenchmarkEngine()

    # Example: score a mock MoveABox profile
    mock_profile = {
        "business_name": "MoveABox",
        "location_slug": "moveabox-bannerghatta",
        "review_volume": 89,
        "review_quality": 4.5,
        "review_velocity": 8,
        "response_rate": 75,
        "content_freshness": 28,
        "visual_richness": 45,
        "profile_depth": 72,
        "qa_coverage": 10,
        "citation_strength": 22,
        "local_pack_rank": 3,
    }

    score = engine.score_profile(mock_profile)
    print(f"MoveABox MBS: {score['mbs']}/100")

    gaps = engine.run_gap_analysis("moveabox-bannerghatta", mock_profile)
    print(f"\nTop 5 Opportunities:")
    for gap in gaps[:5]:
        print(f"  {gap['priority']}. [{gap['metric']}] {gap['action']}")
        print(f"     Score: {gap['opportunity_score']} | Effort: {gap['effort']}")

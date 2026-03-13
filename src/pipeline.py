"""
MoveABox GBP Agent — Daily Pipeline Runner
Version 2.0

Entry point for the automated daily pipeline. Orchestrates all modules
in sequence as defined in CLAUDE.md and the /daily-run slash command.

Usage:
    python src/pipeline.py --mode daily
    python src/pipeline.py --mode competitor-audit
    python src/pipeline.py --mode review-respond
    python src/pipeline.py --mode weekly-report
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Load .env if present
env_path = Path("config/.env")
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

from gbp_api import GBPClient, append_daily_snapshot
from competitor_scraper import CompetitorScraper
from post_generator import PostGenerator
from review_manager import ReviewManager
from benchmark_engine import BenchmarkEngine
from seo_auditor import SEOAuditor
from notifier import Notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("pipeline")

LOCATIONS = [
    "moveabox-bannerghatta",
    "moveabox-banashankari",
    "moveabox-koramangala",
]


class DailyPipeline:
    """Executes the full daily pipeline for all 3 MoveABox locations."""

    def __init__(self):
        self.gbp = GBPClient()
        self.scraper = CompetitorScraper()
        self.post_gen = PostGenerator()
        self.review_mgr = ReviewManager()
        self.benchmark = BenchmarkEngine()
        self.notifier = Notifier()

        self.date = datetime.utcnow().date().isoformat()
        self.results = {
            "date": self.date,
            "started_at": datetime.utcnow().isoformat(),
            "insights": [],
            "posts": [],
            "reviews": {},
            "competitor_alerts": [],
            "anomalies": [],
            "errors": [],
        }

    def run(self) -> dict:
        """Execute the complete daily pipeline."""
        logger.info(f"=== MoveABox Daily Pipeline — {self.date} ===")

        self._step1_fetch_insights()
        self._step2_review_check()
        self._step3_competitor_pulse()
        self._step4_to_9_generate_posts()
        self._step10_send_digest()
        self._step11_log_everything()

        self.results["completed_at"] = datetime.utcnow().isoformat()
        logger.info("=== Daily Pipeline Complete ===")
        return self.results

    def _step1_fetch_insights(self) -> None:
        """Step 1: Fetch GBP Insights for all 3 locations."""
        logger.info("Step 1: Fetching GBP Insights...")
        try:
            insights = self.gbp.fetch_all_insights(days=7)
            append_daily_snapshot(insights)
            self.results["insights"] = insights
            logger.info(f"Fetched insights for {len(insights)} locations")
        except Exception as e:
            logger.error(f"Step 1 failed: {e}")
            self.results["errors"].append(f"Insights fetch failed: {e}")

    def _step2_review_check(self) -> None:
        """Step 2: Fetch new reviews and generate responses."""
        logger.info("Step 2: Checking for new reviews...")
        try:
            reviews_by_location = {}
            for location_slug in LOCATIONS:
                raw = self.gbp.fetch_reviews(location_slug)
                reviews_by_location[location_slug] = raw

            summary = self.review_mgr.process_all_reviews(reviews_by_location)
            self.results["reviews"] = summary

            # Check for anomalies
            for location_slug, metrics in self.review_mgr.review_history.get(
                "metrics", {}
            ).items():
                if metrics.get("average_rating", 5) < 4.3:
                    self.results["anomalies"].append(
                        f"⚠️ {location_slug}: Rating dropped below 4.3 "
                        f"({metrics['average_rating']})"
                    )

            logger.info(
                f"Processed {summary.get('total_new', 0)} new reviews; "
                f"{summary.get('flagged_urgent', 0)} urgent"
            )
        except Exception as e:
            logger.error(f"Step 2 failed: {e}")
            self.results["errors"].append(f"Review check failed: {e}")

    def _step3_competitor_pulse(self) -> None:
        """Step 3: Quick competitor pulse check."""
        logger.info("Step 3: Running competitor pulse check...")
        try:
            # Load last snapshot to compare
            with open("data/competitors.json") as f:
                comp_data = json.load(f)

            for location_slug, competitors in comp_data.get("locations", {}).items():
                for comp in competitors:
                    # Check for review spikes (delta > 10 in a week)
                    # In production, this compares against last week's count
                    current = comp.get("review_count", 0)
                    prev = comp.get("review_count_prev_week", current)
                    delta = current - prev

                    if delta >= 10:
                        alert = (
                            f"{comp['business_name']} gained {delta} reviews "
                            f"this week in {location_slug}"
                        )
                        self.results["competitor_alerts"].append(alert)
                        self.notifier.send_competitor_alert(
                            alert_type="review_spike",
                            location_slug=location_slug,
                            competitor_name=comp["business_name"],
                            details=f"+{delta} reviews this week",
                        )

            logger.info(
                f"Competitor pulse complete. "
                f"{len(self.results['competitor_alerts'])} alerts triggered."
            )
        except Exception as e:
            logger.error(f"Step 3 failed: {e}")
            self.results["errors"].append(f"Competitor pulse failed: {e}")

    def _step4_to_9_generate_posts(self) -> None:
        """Steps 4–9: Determine post type, check competitors, generate posts."""
        logger.info("Steps 4–9: Generating daily posts...")
        try:
            # Build competitor context per location
            competitor_context = {}
            for location_slug in LOCATIONS:
                forbidden = self.scraper.get_forbidden_topics(location_slug)
                competitor_context[f"{location_slug}_forbidden"] = forbidden

            posts = self.post_gen.generate_daily_posts(competitor_context)
            self.results["posts"] = posts

            auto_count = sum(1 for p in posts if p.get("auto_publish"))
            review_count = sum(1 for p in posts if p.get("requires_human_review"))
            logger.info(
                f"Generated {len(posts)} posts: "
                f"{auto_count} auto-publish, {review_count} needs review"
            )
        except Exception as e:
            logger.error(f"Steps 4–9 failed: {e}")
            self.results["errors"].append(f"Post generation failed: {e}")

    def _step10_send_digest(self) -> None:
        """Step 10: Compile and send daily digest."""
        logger.info("Step 10: Sending daily digest...")
        try:
            self.notifier.send_daily_digest(
                posts=self.results.get("posts", []),
                review_summary=self.results.get("reviews", {}),
                competitor_alerts=self.results.get("competitor_alerts", []),
                anomalies=self.results.get("anomalies", []),
            )
        except Exception as e:
            logger.error(f"Step 10 failed: {e}")
            self.results["errors"].append(f"Digest send failed: {e}")

    def _step11_log_everything(self) -> None:
        """Step 11: Save results to daily report."""
        logger.info("Step 11: Logging pipeline results...")
        try:
            report_dir = "reports/daily"
            os.makedirs(report_dir, exist_ok=True)
            report_path = f"{report_dir}/{self.date}.json"

            with open(report_path, "w") as f:
                json.dump(self.results, f, indent=2)

            # Also write a human-readable markdown summary
            md_path = f"{report_dir}/{self.date}.md"
            self._write_daily_md(md_path)

            logger.info(f"Pipeline results saved to {report_path}")
        except Exception as e:
            logger.error(f"Step 11 failed: {e}")

    def _write_daily_md(self, path: str) -> None:
        """Write a human-readable daily report in markdown."""
        posts = self.results.get("posts", [])
        reviews = self.results.get("reviews", {})
        alerts = self.results.get("competitor_alerts", [])
        anomalies = self.results.get("anomalies", [])
        errors = self.results.get("errors", [])

        lines = [
            f"# MoveABox GBP Daily Report — {self.date}",
            f"Generated: {self.results.get('completed_at', 'N/A')}",
            "",
            "## Posts Generated",
        ]

        for post in posts:
            slug = post.get("location_slug", "").split("-")[-1].title()
            score = post.get("quality_score", 0)
            status = "✅ Auto-publish" if post.get("auto_publish") else "⚠️ Needs review"
            lines.append(f"- **{slug}**: {post.get('post_title', 'Untitled')} [{score}/50] {status}")

        lines.extend(["", "## Reviews"])
        lines.append(f"- Total new: {reviews.get('total_new', 0)}")
        lines.append(f"- Urgent escalations: {reviews.get('flagged_urgent', 0)}")
        lines.append(f"- Suspicious flags: {reviews.get('flagged_suspicious', 0)}")

        if alerts:
            lines.extend(["", "## Competitor Alerts"])
            for alert in alerts:
                lines.append(f"- {alert}")

        if anomalies:
            lines.extend(["", "## Anomalies"])
            for anomaly in anomalies:
                lines.append(f"- {anomaly}")

        if errors:
            lines.extend(["", "## Errors"])
            for error in errors:
                lines.append(f"- ❌ {error}")

        with open(path, "w") as f:
            f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="MoveABox GBP Agent Pipeline")
    parser.add_argument(
        "--mode",
        choices=["daily", "competitor-audit", "review-respond", "weekly-report"],
        default="daily",
        help="Pipeline mode to run",
    )
    args = parser.parse_args()

    if args.mode == "daily":
        pipeline = DailyPipeline()
        results = pipeline.run()
        errors = results.get("errors", [])
        if errors:
            logger.warning(f"Pipeline completed with {len(errors)} errors")
            sys.exit(1)
        sys.exit(0)

    elif args.mode == "review-respond":
        review_mgr = ReviewManager()
        gbp = GBPClient()
        notifier = Notifier()

        reviews_by_location = {}
        for slug in LOCATIONS:
            reviews_by_location[slug] = gbp.fetch_reviews(slug)

        summary = review_mgr.process_all_reviews(reviews_by_location)
        logger.info(f"Review respond complete: {summary}")

    elif args.mode == "competitor-audit":
        scraper = CompetitorScraper()
        engine = BenchmarkEngine()

        scraper.collect_all_competitor_data()
        logger.info("Competitor audit complete")

    elif args.mode == "weekly-report":
        engine = BenchmarkEngine()
        notifier = Notifier()

        # In production: gather full weekly data and generate report
        logger.info("Weekly report generation — see /weekly-report slash command")


if __name__ == "__main__":
    main()

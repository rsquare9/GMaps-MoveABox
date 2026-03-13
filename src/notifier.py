"""
Notification Engine
MoveABox GBP Agent v2.0

Sends alerts and digests via Slack and WhatsApp.
Used for: daily digests, competitor alerts, review escalations, weekly reports.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")  # e.g., Twilio or WATI
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")
WHATSAPP_GROUP_ID = os.getenv("WHATSAPP_GROUP_ID", "")

SLACK_CHANNELS = {
    "daily": os.getenv("SLACK_CHANNEL_DAILY", "#gbp-daily"),
    "weekly": os.getenv("SLACK_CHANNEL_WEEKLY", "#gbp-weekly"),
    "alerts": os.getenv("SLACK_CHANNEL_ALERTS", "#gbp-alerts"),
    "escalations": os.getenv("SLACK_CHANNEL_ESCALATIONS", "#escalations"),
    "competitor": os.getenv("SLACK_CHANNEL_COMPETITOR", "#competitor-intel"),
}


class Notifier:
    """Sends notifications via Slack and WhatsApp."""

    # -------------------------------------------------------------------------
    # Slack
    # -------------------------------------------------------------------------

    def send_slack(
        self,
        message: str,
        channel_key: str = "daily",
        blocks: Optional[list] = None,
    ) -> bool:
        """Send a message to a Slack channel via webhook."""
        if not SLACK_WEBHOOK_URL:
            logger.warning("SLACK_WEBHOOK_URL not set — skipping Slack notification")
            self._log_notification("slack", channel_key, message)
            return False

        channel = SLACK_CHANNELS.get(channel_key, "#gbp-daily")
        payload = {
            "channel": channel,
            "text": message,
        }
        if blocks:
            payload["blocks"] = blocks

        try:
            response = requests.post(
                SLACK_WEBHOOK_URL,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            logger.info(f"Slack notification sent to {channel}")
            return True
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # WhatsApp
    # -------------------------------------------------------------------------

    def send_whatsapp(self, message: str) -> bool:
        """Send a WhatsApp message to the manager group."""
        if not WHATSAPP_API_URL or not WHATSAPP_API_TOKEN:
            logger.warning("WhatsApp API not configured — skipping notification")
            self._log_notification("whatsapp", "manager_group", message)
            return False

        try:
            headers = {
                "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
                "Content-Type": "application/json",
            }
            payload = {
                "groupId": WHATSAPP_GROUP_ID,
                "message": message,
            }
            response = requests.post(
                WHATSAPP_API_URL,
                headers=headers,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            logger.info("WhatsApp notification sent")
            return True
        except Exception as e:
            logger.error(f"WhatsApp notification failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # Daily Digest
    # -------------------------------------------------------------------------

    def send_daily_digest(
        self,
        posts: list[dict],
        review_summary: dict,
        competitor_alerts: list[str],
        anomalies: list[str],
    ) -> None:
        """Compile and send the daily digest to Slack and WhatsApp."""
        date = datetime.utcnow().strftime("%d %b %Y")

        lines = [
            f"*MoveABox GBP Daily Digest — {date}*",
            "",
            "*📝 Posts Generated Today:*",
        ]

        for post in posts:
            slug = post.get("location_slug", "").split("-")[-1].title()
            score = post.get("quality_score", 0)
            status = "✅ Auto-publish" if post.get("auto_publish") else "⚠️ Needs review"
            lines.append(
                f"  • {slug}: {post.get('post_title', 'Untitled')} "
                f"[Score: {score}/50] {status}"
            )

        lines.append("")
        lines.append("*⭐ Reviews:*")
        total_new = review_summary.get("total_new", 0)
        flagged_urgent = review_summary.get("flagged_urgent", 0)
        lines.append(f"  • {total_new} new reviews processed")
        if flagged_urgent:
            lines.append(f"  • ⚠️ {flagged_urgent} urgent escalations pending human review")

        if competitor_alerts:
            lines.append("")
            lines.append("*🔍 Competitor Alerts:*")
            for alert in competitor_alerts:
                lines.append(f"  • {alert}")

        if anomalies:
            lines.append("")
            lines.append("*🚨 Anomalies:*")
            for anomaly in anomalies:
                lines.append(f"  • {anomaly}")

        message = "\n".join(lines)

        self.send_slack(message, channel_key="daily")
        self.send_whatsapp(message)

    # -------------------------------------------------------------------------
    # Competitor Alerts
    # -------------------------------------------------------------------------

    def send_competitor_alert(
        self,
        alert_type: str,
        location_slug: str,
        competitor_name: str,
        details: str,
    ) -> None:
        """Send an immediate competitor alert."""
        location = location_slug.split("-")[-1].title()

        alert_emojis = {
            "review_spike": "📈",
            "rating_overtake": "⭐",
            "new_3pack": "🎯",
            "new_service": "🆕",
            "posting_surge": "📝",
            "ranking_loss": "📉",
        }

        emoji = alert_emojis.get(alert_type, "⚠️")

        message = (
            f"{emoji} *COMPETITOR ALERT — {location}*\n"
            f"Type: {alert_type.replace('_', ' ').title()}\n"
            f"Competitor: {competitor_name}\n"
            f"Details: {details}\n"
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )

        self.send_slack(message, channel_key="alerts")
        self.send_whatsapp(message)
        logger.warning(f"Competitor alert sent: {alert_type} for {location_slug}")

    # -------------------------------------------------------------------------
    # Review Escalation
    # -------------------------------------------------------------------------

    def send_review_escalation(
        self,
        location_slug: str,
        reviewer_name: str,
        star_rating: int,
        review_text: str,
        response_draft: str,
    ) -> None:
        """Send an urgent review escalation to the manager."""
        location = location_slug.split("-")[-1].title()
        stars = "⭐" * star_rating

        message = (
            f"🚨 *URGENT REVIEW ESCALATION — {location}*\n"
            f"Rating: {stars} ({star_rating}/5)\n"
            f"Reviewer: {reviewer_name}\n\n"
            f"*Review:*\n{review_text}\n\n"
            f"*Draft Response (requires human approval):*\n{response_draft}\n\n"
            f"Please review and publish/edit within 2 hours."
        )

        self.send_slack(message, channel_key="escalations")
        self.send_whatsapp(message)

    # -------------------------------------------------------------------------
    # Weekly Report Summary
    # -------------------------------------------------------------------------

    def send_weekly_summary(
        self,
        week: str,
        location_scores: dict[str, float],
        top_opportunities: list[str],
        report_path: str,
    ) -> None:
        """Send weekly report summary to Slack."""
        lines = [
            f"*MoveABox GBP Weekly Report — {week}*",
            "",
            "*📊 Benchmark Scores:*",
        ]

        for location, score in location_scores.items():
            name = location.split("-")[-1].title()
            trend = "↑" if score > 60 else "→"
            lines.append(f"  • {name}: {score}/100 {trend}")

        lines.append("")
        lines.append("*🎯 Top Opportunities This Week:*")
        for i, opp in enumerate(top_opportunities[:5], 1):
            lines.append(f"  {i}. {opp}")

        lines.append("")
        lines.append(f"📄 Full report saved: `{report_path}`")

        message = "\n".join(lines)
        self.send_slack(message, channel_key="weekly")
        self.send_whatsapp(message)

    # -------------------------------------------------------------------------
    # Anomaly Alert
    # -------------------------------------------------------------------------

    def send_anomaly_alert(
        self,
        anomaly_type: str,
        location_slug: str,
        current_value: float,
        threshold: float,
        details: str,
    ) -> None:
        """Send alert when a metric breaches a threshold."""
        location = location_slug.split("-")[-1].title()

        message = (
            f"🔴 *ANOMALY ALERT — {location}*\n"
            f"Issue: {anomaly_type.replace('_', ' ').title()}\n"
            f"Current: {current_value} | Threshold: {threshold}\n"
            f"Details: {details}"
        )

        self.send_slack(message, channel_key="alerts")
        self.send_whatsapp(message)

    # -------------------------------------------------------------------------
    # Logging Fallback
    # -------------------------------------------------------------------------

    def _log_notification(self, channel: str, destination: str, message: str) -> None:
        """Log notifications to file when API not configured."""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        path = f"{log_dir}/notifications.log"

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "channel": channel,
            "destination": destination,
            "message": message,
        }

        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    notifier = Notifier()

    # Test daily digest
    notifier.send_daily_digest(
        posts=[
            {
                "location_slug": "moveabox-koramangala",
                "post_title": "Weekend Moving Special",
                "quality_score": 43,
                "auto_publish": True,
            }
        ],
        review_summary={"total_new": 3, "flagged_urgent": 0},
        competitor_alerts=[],
        anomalies=[],
    )
    print("Test notification sent (logged to logs/notifications.log if APIs not configured)")

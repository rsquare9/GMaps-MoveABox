"""
Review Monitoring & Response Engine
MoveABox GBP Agent v2.0

Monitors all 3 GBP locations for new reviews, generates brand-voice responses,
flags suspicious reviews, and manages review velocity campaigns.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-6"

LOCATION_DETAILS = {
    "moveabox-bannerghatta": {
        "name": "Bannerghatta Road",
        "manager_name": os.getenv("MANAGER_BANNERGHATTA", "Rajesh Kumar"),
        "phone": os.getenv("PHONE_BANNERGHATTA", "+91-XXXXXXXXXX"),
        "review_link": "https://g.page/r/BANNERGHATTA_REVIEW_ID/review",
    },
    "moveabox-banashankari": {
        "name": "Banashankari",
        "manager_name": os.getenv("MANAGER_BANASHANKARI", "Suresh Nair"),
        "phone": os.getenv("PHONE_BANASHANKARI", "+91-XXXXXXXXXX"),
        "review_link": "https://g.page/r/BANASHANKARI_REVIEW_ID/review",
    },
    "moveabox-koramangala": {
        "name": "Koramangala",
        "manager_name": os.getenv("MANAGER_KORAMANGALA", "Anita Sharma"),
        "phone": os.getenv("PHONE_KORAMANGALA", "+91-XXXXXXXXXX"),
        "review_link": "https://g.page/r/KORAMANGALA_REVIEW_ID/review",
    },
}

TIER1_KEYWORDS = [
    "packers and movers",
    "house shifting",
    "office relocation",
    "courier service",
    "storage solutions",
]

ESCALATION_KEYWORDS = [
    "lost items", "damage", "fraud", "cheating", "police",
    "complaint", "legal", "court", "scam", "stolen",
]

REVIEW_REQUEST_TEMPLATES = [
    """Hi {name}! 😊 Thank you for choosing MoveABox for your move.
We'd love to hear about your experience! It takes just 30 seconds.
Share your feedback here: {review_link}
Your review helps other families find trusted movers. 🙏""",

    """Hello {name}! Hope your move went smoothly with MoveABox. 🏠
Could you spare a moment to leave us a Google review?
👉 {review_link}
Your feedback means the world to our team in {location}!""",
]


class ReviewManager:
    """Manages review monitoring, responses, and velocity campaigns."""

    def __init__(self):
        self.client = anthropic.Anthropic()
        self.review_history_path = "data/review_history.json"
        self.review_history = self._load_review_history()

    def _load_review_history(self) -> dict:
        if os.path.exists(self.review_history_path):
            with open(self.review_history_path) as f:
                return json.load(f)
        return {
            "reviews": {},
            "metrics": {},
            "last_template_index": 0,
        }

    def _save_review_history(self) -> None:
        with open(self.review_history_path, "w") as f:
            json.dump(self.review_history, f, indent=2)

    # -------------------------------------------------------------------------
    # New Review Detection
    # -------------------------------------------------------------------------

    def get_new_reviews(
        self, location_slug: str, raw_reviews: list[dict]
    ) -> list[dict]:
        """
        Filter raw_reviews to only those not yet in review_history.
        Returns list of new reviews sorted by priority (low-star first).
        """
        known_ids = set(
            r["review_id"]
            for r in self.review_history.get("reviews", {}).get(location_slug, [])
        )

        new = [r for r in raw_reviews if r.get("reviewId", "") not in known_ids]

        # Sort: 1–2 star first, then 3–4, then 5
        def priority(review):
            rating = review.get("starRating", "FIVE")
            order = {"ONE": 0, "TWO": 1, "THREE": 2, "FOUR": 3, "FIVE": 4}
            return order.get(rating, 4)

        new.sort(key=priority)
        return new

    # -------------------------------------------------------------------------
    # Suspicious Review Detection
    # -------------------------------------------------------------------------

    def is_suspicious(self, review: dict) -> bool:
        """Detect potentially fake or spam reviews."""
        comment = review.get("comment", "").lower()
        reviewer = review.get("reviewer", {})

        # No profile photo
        has_photo = bool(reviewer.get("profilePhotoUrl", ""))

        # Very short generic text
        word_count = len(comment.split())

        # Check for escalation keywords
        has_escalation = any(kw in comment for kw in ESCALATION_KEYWORDS)

        if not has_photo and word_count < 5:
            return True
        if word_count < 3:
            return True

        return False

    def has_escalation_keywords(self, review: dict) -> bool:
        """Check if review contains escalation trigger words."""
        comment = review.get("comment", "").lower()
        return any(kw in comment for kw in ESCALATION_KEYWORDS)

    # -------------------------------------------------------------------------
    # Response Generation
    # -------------------------------------------------------------------------

    def generate_response(
        self, review: dict, location_slug: str
    ) -> dict:
        """Generate an appropriate response to a review."""
        star_rating = review.get("starRating", "FIVE")
        rating_map = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
        stars = rating_map.get(star_rating, 5)

        reviewer_name = review.get("reviewer", {}).get("displayName", "")
        comment = review.get("comment", "")
        location = LOCATION_DETAILS[location_slug]

        if stars >= 5:
            response_text = self._generate_5star_response(
                reviewer_name, comment, location, location_slug
            )
            requires_review = False
            priority = "normal"
        elif stars >= 3:
            response_text = self._generate_3to4star_response(
                reviewer_name, comment, location, location_slug
            )
            requires_review = True
            priority = "medium"
        else:
            response_text = self._generate_1to2star_response(
                reviewer_name, comment, location, location_slug
            )
            requires_review = True
            priority = "urgent"

        return {
            "review_id": review.get("reviewId", ""),
            "location_slug": location_slug,
            "star_rating": stars,
            "reviewer_name": reviewer_name,
            "review_text": comment,
            "response_text": response_text,
            "requires_human_review": requires_review,
            "priority": priority,
            "is_suspicious": self.is_suspicious(review),
            "has_escalation": self.has_escalation_keywords(review),
            "generated_at": datetime.utcnow().isoformat(),
            "status": "queued",
        }

    def _generate_5star_response(
        self,
        name: str,
        comment: str,
        location: dict,
        location_slug: str,
    ) -> str:
        """Generate a warm, keyword-rich response to a 5-star review."""
        keyword = TIER1_KEYWORDS[
            hash(name) % len(TIER1_KEYWORDS)
        ]  # Rotate keywords

        prompt = f"""Generate a Google Business Profile response to this 5-star review.

REVIEWER NAME: {name}
REVIEW TEXT: {comment}
LOCATION: {location['name']}, Bangalore
PHONE: {location['phone']}

REQUIREMENTS:
- Thank reviewer by name
- Reference specific service mentioned (if any)
- Naturally embed this keyword: "{keyword} in {location['name']}"
- Cross-sell one other MoveABox service (courier, storage, or office relocation)
- 40–80 words
- Tone: warm, grateful, specific
- Professional but friendly
- End with an invitation to use us again

Respond with ONLY the response text, no JSON, no quotes."""

        message = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    def _generate_3to4star_response(
        self,
        name: str,
        comment: str,
        location: dict,
        location_slug: str,
    ) -> str:
        """Generate a constructive response to a 3–4 star review."""
        prompt = f"""Generate a Google Business Profile response to this 3-4 star review.

REVIEWER NAME: {name}
REVIEW TEXT: {comment}
LOCATION: {location['name']}, Bangalore
MANAGER NAME: {location['manager_name']}
PHONE: {location['phone']}

REQUIREMENTS:
- Thank warmly, acknowledge specific feedback
- Mention a concrete improvement or resolution
- Provide direct contact: phone + manager name
- 60–120 words
- Tone: constructive, accountable, solution-focused
- Never defensive or dismissive

Respond with ONLY the response text, no JSON, no quotes."""

        message = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    def _generate_1to2star_response(
        self,
        name: str,
        comment: str,
        location: dict,
        location_slug: str,
    ) -> str:
        """Generate an empathetic, resolution-focused response to a 1–2 star review."""
        prompt = f"""Generate a Google Business Profile response to this 1-2 star review.

REVIEWER NAME: {name}
REVIEW TEXT: {comment}
LOCATION: {location['name']}, Bangalore
MANAGER NAME: {location['manager_name']}
PHONE: {location['phone']}

REQUIREMENTS:
- Express genuine concern and apologize sincerely
- NEVER argue, deflect, or make excuses
- Offer offline resolution with manager name and phone
- 80–150 words
- Tone: empathetic, professional, ownership-taking
- Show accountability without admitting specific fault publicly

Respond with ONLY the response text, no JSON, no quotes."""

        message = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    # -------------------------------------------------------------------------
    # Batch Processing
    # -------------------------------------------------------------------------

    def process_all_reviews(
        self, reviews_by_location: dict[str, list[dict]]
    ) -> dict:
        """
        Process all new reviews across all locations.
        Returns summary dict of actions taken.
        """
        summary = {
            "total_new": 0,
            "responded": 0,
            "flagged_urgent": 0,
            "flagged_suspicious": 0,
            "by_location": {},
        }

        for location_slug, raw_reviews in reviews_by_location.items():
            new_reviews = self.get_new_reviews(location_slug, raw_reviews)
            location_summary = {
                "new": len(new_reviews),
                "responses": [],
                "alerts": [],
            }

            for review in new_reviews:
                response = self.generate_response(review, location_slug)

                if response["is_suspicious"]:
                    response["status"] = "dispute_flagged"
                    location_summary["alerts"].append(
                        f"Suspicious review flagged: {response['reviewer_name']}"
                    )
                    summary["flagged_suspicious"] += 1

                if response["has_escalation"]:
                    response["priority"] = "urgent"
                    location_summary["alerts"].append(
                        f"ESCALATION: Review contains sensitive keywords"
                    )
                    summary["flagged_urgent"] += 1

                location_summary["responses"].append(response)
                self._save_response_to_output(response)
                summary["responded"] += 1
                summary["total_new"] += 1

                # Update review history
                self.review_history.setdefault(
                    "reviews", {}
                ).setdefault(location_slug, []).append({
                    "review_id": review.get("reviewId", ""),
                    "star_rating": response["star_rating"],
                    "reviewer_name": response["reviewer_name"],
                    "review_text": response["review_text"],
                    "response_text": response["response_text"],
                    "status": response["status"],
                    "created_at": datetime.utcnow().isoformat(),
                })

            summary["by_location"][location_slug] = location_summary

        self._save_review_history()
        self.update_metrics()
        return summary

    def _save_response_to_output(self, response: dict) -> None:
        """Save a review response to the output directory."""
        date = datetime.utcnow().date().isoformat()
        slug = response["location_slug"].split("-")[-1]
        priority = response.get("priority", "normal")
        filename = f"output/review_responses/{date}-{slug}-{priority}.json"

        existing = []
        if os.path.exists(filename):
            with open(filename) as f:
                existing = json.load(f)

        existing.append(response)
        with open(filename, "w") as f:
            json.dump(existing, f, indent=2)

    # -------------------------------------------------------------------------
    # Review Velocity Campaign
    # -------------------------------------------------------------------------

    def generate_review_request(self, location_slug: str) -> str:
        """Generate a WhatsApp-friendly review request message (rotates templates)."""
        location = LOCATION_DETAILS[location_slug]
        template_idx = self.review_history.get("last_template_index", 0) % len(
            REVIEW_REQUEST_TEMPLATES
        )
        template = REVIEW_REQUEST_TEMPLATES[template_idx]

        message = template.format(
            name="[Customer Name]",
            location=location["name"],
            review_link=location["review_link"],
        )

        self.review_history["last_template_index"] = (template_idx + 1) % len(
            REVIEW_REQUEST_TEMPLATES
        )
        self._save_review_history()

        filename = (
            f"output/review_responses/review-request-"
            f"{datetime.utcnow().date().isoformat()}-"
            f"{location_slug.split('-')[-1]}.txt"
        )
        with open(filename, "w") as f:
            f.write(message)

        return message

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    def update_metrics(self) -> None:
        """Calculate and update review metrics for all locations."""
        metrics = {}
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()

        for location_slug, reviews in self.review_history.get("reviews", {}).items():
            total = len(reviews)
            ratings = [r["star_rating"] for r in reviews if r.get("star_rating")]
            responded = sum(1 for r in reviews if r.get("response_text"))

            recent = [r for r in reviews if r.get("created_at", "") >= thirty_days_ago]

            metrics[location_slug] = {
                "total_reviews": total,
                "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
                "response_rate": round(responded / total * 100, 1) if total else 0,
                "velocity_30d": len(recent),
                "updated_at": datetime.utcnow().isoformat(),
            }

        self.review_history["metrics"] = metrics
        self._save_review_history()

    def get_review_target(self, location_slug: str, top_competitor_count: int) -> int:
        """Calculate monthly review target to close gap with top competitor."""
        current = self.review_history.get("metrics", {}).get(
            location_slug, {}
        ).get("total_reviews", 0)
        target = max(5, (top_competitor_count - current) // 12 + 5)
        return target


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = ReviewManager()

    # Example: process mock reviews
    mock_reviews = {
        "moveabox-koramangala": [
            {
                "reviewId": "test_001",
                "starRating": "FIVE",
                "reviewer": {"displayName": "Priya Sharma", "profilePhotoUrl": "http://example.com"},
                "comment": "Excellent service! Team was very professional and on time.",
            }
        ]
    }

    summary = manager.process_all_reviews(mock_reviews)
    print(json.dumps(summary, indent=2))

"""
Post Generation Engine
MoveABox GBP Agent v2.0

Generates keyword-targeted, location-specific, competitor-differentiated
Google Business Profile posts for all 3 MoveABox locations.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-6"

POST_ROTATION = {
    0: {"type": "service_spotlight", "focus": "Deep-dive one service", "cta": "Book your move today"},
    1: {"type": "local_area_guide", "focus": "Neighborhood-specific moving tips", "cta": "Moving to [area]? Call us"},
    2: {"type": "customer_testimonial", "focus": "Reframe a real review as story", "cta": "Read more reviews"},
    3: {"type": "offer_promotion", "focus": "Seasonal or location-specific deal", "cta": "Claim this offer"},
    4: {"type": "how_to_checklist", "focus": "Packing, moving, storage tips", "cta": "Get a free quote"},
    5: {"type": "behind_the_scenes", "focus": "Team, process, warehouse tour", "cta": "Meet our team"},
    6: {"type": "faq_myth_buster", "focus": "Common moving questions answered", "cta": "Ask us anything"},
}

LOCATION_DETAILS = {
    "moveabox-bannerghatta": {
        "name": "Bannerghatta Road",
        "neighborhoods": ["JP Nagar", "Arekere", "Gottigere", "Hulimavu", "Begur", "Bommanahalli"],
        "landmarks": ["Bannerghatta National Park", "Gottigere Metro Station", "IIM Bangalore", "Meenakshi Temple"],
        "maps_link": "https://maps.app.goo.gl/b6FU5TNh5kecUg9c8",
        "phone": os.getenv("PHONE_BANNERGHATTA", "+91-XXXXXXXXXX"),
        "website_utm": "https://moveabox.in/book?loc=bannerghatta&utm_source=gbp",
    },
    "moveabox-banashankari": {
        "name": "Banashankari",
        "neighborhoods": ["Padmanabhanagar", "Kumaraswamy Layout", "Uttarahalli", "RR Nagar", "Girinagar"],
        "landmarks": ["Banashankari Temple", "Turahalli Forest", "Nayandahalli Metro", "BMS College"],
        "maps_link": "https://maps.app.goo.gl/N9JCzMd98UTrTPBE7",
        "phone": os.getenv("PHONE_BANASHANKARI", "+91-XXXXXXXXXX"),
        "website_utm": "https://moveabox.in/book?loc=banashankari&utm_source=gbp",
    },
    "moveabox-koramangala": {
        "name": "Koramangala",
        "neighborhoods": ["HSR Layout", "BTM Layout", "Madiwala", "Ejipura", "Domlur"],
        "landmarks": ["Forum Mall", "National Games Village", "St. John's Hospital", "Sony World"],
        "maps_link": "https://maps.app.goo.gl/Ry7wJSGhYWG5GLF67",
        "phone": os.getenv("PHONE_KORAMANGALA", "+91-XXXXXXXXXX"),
        "website_utm": "https://moveabox.in/book?loc=koramangala&utm_source=gbp",
    },
}

TIER1_KEYWORDS = [
    "packers and movers",
    "house shifting services",
    "office relocation",
    "courier service",
    "storage facility",
    "affordable movers",
    "home shifting",
    "best packers and movers",
]


class PostGenerator:
    """Generates GBP posts with keyword targeting and competitor differentiation."""

    def __init__(self):
        self.client = anthropic.Anthropic()
        self.post_history = self._load_post_history()
        self.keywords = self._load_keywords()

    def _load_post_history(self) -> list[dict]:
        path = "data/post_history.json"
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
                return data.get("posts", [])
        return []

    def _load_keywords(self) -> dict:
        path = "data/keywords.json"
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return {"tier1": TIER1_KEYWORDS, "tier2": [], "tier3": [], "tier4": []}

    def _save_post_history(self, post: dict) -> None:
        path = "data/post_history.json"
        history = {"posts": self.post_history}
        if os.path.exists(path):
            with open(path) as f:
                history = json.load(f)
        history.setdefault("posts", []).append(post)
        with open(path, "w") as f:
            json.dump(history, f, indent=2)

    # -------------------------------------------------------------------------
    # Post Type Determination
    # -------------------------------------------------------------------------

    def get_todays_post_type(self) -> dict:
        """Return today's post type from the weekly rotation."""
        day_of_week = datetime.utcnow().weekday()  # 0=Monday, 6=Sunday
        return POST_ROTATION[day_of_week]

    def get_seasonal_override(self) -> Optional[str]:
        """Check if a seasonal content window applies today."""
        today = datetime.utcnow()
        month = today.month

        if month in (6, 7, 8, 9):
            return "monsoon"
        elif month in (3, 4):
            return "festival_ugadi"
        elif month in (10, 11):
            return "festival_diwali"
        elif month == 1:
            return "new_year"
        elif month in (5, 6):
            return "summer_student"
        return None

    # -------------------------------------------------------------------------
    # Post Generation
    # -------------------------------------------------------------------------

    def generate_post(
        self,
        location_slug: str,
        forbidden_topics: list[str],
        competitor_angles: list[str],
        post_count: int = 0,
    ) -> dict:
        """
        Generate a single GBP post for a location.
        Returns the post dict. Raises on quality gate failure after 3 attempts.
        """
        post_type = self.get_todays_post_type()
        seasonal = self.get_seasonal_override()
        location = LOCATION_DETAILS[location_slug]

        for attempt in range(3):
            post = self._call_claude(
                location_slug=location_slug,
                location=location,
                post_type=post_type,
                seasonal=seasonal,
                forbidden_topics=forbidden_topics,
                competitor_angles=competitor_angles,
                post_count=post_count,
            )

            score = self._score_post(post, location_slug)
            post["quality_score"] = score
            post["quality_gate_attempt"] = attempt + 1

            if score >= 40:
                post["auto_publish"] = True
                post["requires_human_review"] = False
                break
            elif score >= 35:
                post["auto_publish"] = False
                post["requires_human_review"] = True
                break
            else:
                logger.warning(
                    f"Post scored {score}/50 for {location_slug} "
                    f"(attempt {attempt+1}). Regenerating."
                )

        return post

    def _call_claude(
        self,
        location_slug: str,
        location: dict,
        post_type: dict,
        seasonal: Optional[str],
        forbidden_topics: list[str],
        competitor_angles: list[str],
        post_count: int,
    ) -> dict:
        """Call Claude API to generate post content."""
        include_maps = (post_count + 1) % 3 == 0
        neighborhood = location["neighborhoods"][post_count % len(location["neighborhoods"])]
        landmark = location["landmarks"][post_count % len(location["landmarks"])]

        seasonal_context = ""
        if seasonal:
            seasonal_context = f"\nSEASONAL CONTEXT: We are in the {seasonal} content window. Incorporate this theme naturally."

        forbidden_str = "\n".join(f"- {t}" for t in forbidden_topics[:10]) if forbidden_topics else "None"
        competitor_str = "\n".join(f"- {a}" for a in competitor_angles[:5]) if competitor_angles else "None"

        prompt = f"""Generate a Google Business Profile post for MoveABox in {location['name']}, Bangalore.

POST TYPE: {post_type['type'].replace('_', ' ').title()}
FOCUS: {post_type['focus']}
CTA: {post_type['cta']}
{seasonal_context}

LOCATION DETAILS:
- Area: {location['name']}, Bangalore
- Feature neighborhood: {neighborhood}
- Feature landmark: {landmark}
- Phone: {location['phone']}
- Booking URL: {location['website_utm']}
{"- Include Maps link: " + location['maps_link'] if include_maps else ""}

COMPETITOR TOPICS TO AVOID (posted in last 14 days):
{forbidden_str}

COMPETITOR ANGLES USED RECENTLY (do NOT repeat):
{competitor_str}

REQUIREMENTS:
1. 150–300 words (800–1200 characters)
2. Naturally embed at least ONE of these Tier 1 keywords: {', '.join(TIER1_KEYWORDS[:5])}
3. Reference {location['name']} AND mention {neighborhood} or {landmark}
4. Max 3 emojis. No hashtags.
5. End with clear CTA: "{post_type['cta']}" with the phone or booking URL
6. Brand voice: professional yet warm, like a trusted local expert
7. 8th-grade reading level. Bangalore-local flavor encouraged.
8. NEVER duplicate competitor angles listed above

Respond with a JSON object:
{{
  "post_title": "...",
  "post_body": "...",
  "cta_text": "...",
  "cta_url": "...",
  "target_keywords": ["...", "..."],
  "neighborhoods_mentioned": ["...", "..."],
  "competitor_angle_avoided": "...",
  "image_prompt": "Detailed Midjourney/DALL-E prompt for a photo..."
}}"""

        message = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        content = message.content[0].text
        # Extract JSON from response
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            raise ValueError("Claude did not return valid JSON")

        post_data = json.loads(json_match.group())

        return {
            "location_slug": location_slug,
            "post_date": datetime.utcnow().date().isoformat(),
            "day_of_week": datetime.utcnow().strftime("%A"),
            "post_type": post_type["type"],
            "post_title": post_data.get("post_title", ""),
            "post_body": post_data.get("post_body", ""),
            "cta_text": post_data.get("cta_text", post_type["cta"]),
            "cta_url": post_data.get("cta_url", location["website_utm"]),
            "target_keywords": post_data.get("target_keywords", []),
            "neighborhoods_mentioned": post_data.get("neighborhoods_mentioned", []),
            "competitor_angle_avoided": post_data.get("competitor_angle_avoided", ""),
            "image_prompt": post_data.get("image_prompt", ""),
            "seasonal_theme": seasonal,
            "scheduled_time": "10:30 AM IST",
            "generated_at": datetime.utcnow().isoformat(),
        }

    # -------------------------------------------------------------------------
    # Quality Gate
    # -------------------------------------------------------------------------

    def _score_post(self, post: dict, location_slug: str) -> int:
        """
        Score a post on 5 dimensions (0–10 each). Max 50.
        """
        body = post.get("post_body", "").lower()
        location = LOCATION_DETAILS[location_slug]

        # 1. Keyword Relevance (0–10)
        keyword_hits = sum(1 for kw in TIER1_KEYWORDS if kw.lower() in body)
        keyword_score = min(keyword_hits * 3, 10)

        # 2. Location Specificity (0–10)
        location_score = 0
        if location["name"].lower() in body:
            location_score += 5
        if any(n.lower() in body for n in location["neighborhoods"]):
            location_score += 3
        if any(l.lower() in body for l in location["landmarks"]):
            location_score += 2

        # 3. Uniqueness (0–10)
        recent_posts = [
            p["post_body"].lower()
            for p in self.post_history[-30:]
            if p.get("location_slug") == location_slug
        ]
        max_overlap = 0
        for old_body in recent_posts:
            overlap = self._estimate_overlap(body, old_body)
            max_overlap = max(max_overlap, overlap)
        uniqueness_score = 10 if max_overlap < 0.1 else 7 if max_overlap < 0.2 else 3

        # 4. CTA Clarity (0–10)
        cta_score = 0
        if post.get("cta_text"):
            cta_score += 5
        if post.get("cta_url"):
            cta_score += 3
        if any(w in body for w in ["call", "book", "contact", "whatsapp", "quote"]):
            cta_score += 2

        # 5. Tone & Voice (0–10) — basic checks
        word_count = len(body.split())
        emoji_count = sum(1 for c in post.get("post_body", "") if ord(c) > 127000)
        has_hashtag = "#" in body

        tone_score = 8  # Start high, deduct for violations
        if word_count < 100:
            tone_score -= 3
        if word_count > 400:
            tone_score -= 2
        if emoji_count > 3:
            tone_score -= 2
        if has_hashtag:
            tone_score -= 3
        tone_score = max(0, tone_score)

        total = keyword_score + location_score + uniqueness_score + cta_score + tone_score
        logger.info(
            f"Post score for {location_slug}: {total}/50 "
            f"(kw={keyword_score}, loc={location_score}, "
            f"uniq={uniqueness_score}, cta={cta_score}, tone={tone_score})"
        )
        return total

    def _estimate_overlap(self, text1: str, text2: str) -> float:
        """Estimate word-level overlap between two texts."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        return len(intersection) / len(words1)

    # -------------------------------------------------------------------------
    # Batch Generation
    # -------------------------------------------------------------------------

    def generate_daily_posts(
        self, competitor_data: Optional[dict] = None
    ) -> list[dict]:
        """
        Generate one post per location (3 total) for today.
        Returns list of post dicts.
        """
        posts = []
        post_count = len(self.post_history)

        for location_slug in LOCATION_DETAILS:
            forbidden_topics = []
            competitor_angles = []

            if competitor_data:
                forbidden_topics = competitor_data.get(
                    f"{location_slug}_forbidden", []
                )
                competitor_angles = competitor_data.get(
                    f"{location_slug}_angles", []
                )

            try:
                post = self.generate_post(
                    location_slug=location_slug,
                    forbidden_topics=forbidden_topics,
                    competitor_angles=competitor_angles,
                    post_count=post_count,
                )
                posts.append(post)
                self._save_post_to_output(post)
                self._save_post_history(post)
                self.post_history.append(post)
                post_count += 1
                logger.info(
                    f"Generated post for {location_slug} "
                    f"(score: {post.get('quality_score')}/50)"
                )
            except Exception as e:
                logger.error(f"Failed to generate post for {location_slug}: {e}")

        return posts

    def _save_post_to_output(self, post: dict) -> None:
        """Save a post to the output/posts/ directory."""
        date = post["post_date"]
        slug = post["location_slug"].split("-")[-1]
        filename = f"output/posts/{date}-{slug}.json"
        with open(filename, "w") as f:
            json.dump(post, f, indent=2)
        logger.info(f"Saved post to {filename}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generator = PostGenerator()
    posts = generator.generate_daily_posts()
    for p in posts:
        print(f"\n{'='*60}")
        print(f"Location: {p['location_slug']}")
        print(f"Title: {p['post_title']}")
        print(f"Score: {p['quality_score']}/50")
        print(f"Auto-publish: {p.get('auto_publish', False)}")
        print(f"\n{p['post_body']}")

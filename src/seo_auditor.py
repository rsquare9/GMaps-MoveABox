"""
SEO & Profile Completeness Auditor
MoveABox GBP Agent v2.0

Audits NAP consistency, GBP profile completeness, and citation coverage.
Generates structured audit reports and action items.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

CITATION_SOURCES = {
    "tier1": [
        "google_business_profile",
        "justdial",
        "sulekha",
        "indiamart",
        "facebook",
        "bing_places",
    ],
    "tier2": [
        "tradeindia",
        "grotal",
        "yellow_pages_india",
        "exporters_india",
    ],
    "tier3": [
        "india_business_directory",
        "bangalore_local",
        "startup_india",
    ],
    "tier4": [
        "apartment_community_boards",
        "locality_facebook_groups",
    ],
}

PROFILE_COMPLETENESS_WEIGHTS = {
    "business_name": 10,
    "primary_secondary_categories": 15,
    "business_description": 10,
    "services_with_descriptions": 10,
    "operating_hours": 5,
    "photos": 15,
    "qa_section": 10,
    "products_services_menu": 10,
    "business_attributes": 5,
    "website_booking_links": 10,
}

LOCATION_NAP = {
    "moveabox-bannerghatta": {
        "name": "MoveABox - Bannerghatta Road",
        "address": os.getenv(
            "ADDRESS_BANNERGHATTA",
            "Bannerghatta Road, JP Nagar, Bangalore - 560076",
        ),
        "phone": os.getenv("PHONE_BANNERGHATTA", "+91-XXXXXXXXXX"),
        "website": "https://moveabox.in",
    },
    "moveabox-banashankari": {
        "name": "MoveABox - Banashankari",
        "address": os.getenv(
            "ADDRESS_BANASHANKARI",
            "Banashankari Stage 2, Bangalore - 560070",
        ),
        "phone": os.getenv("PHONE_BANASHANKARI", "+91-XXXXXXXXXX"),
        "website": "https://moveabox.in",
    },
    "moveabox-koramangala": {
        "name": "MoveABox - Koramangala",
        "address": os.getenv(
            "ADDRESS_KORAMANGALA",
            "Koramangala 4th Block, Bangalore - 560034",
        ),
        "phone": os.getenv("PHONE_KORAMANGALA", "+91-XXXXXXXXXX"),
        "website": "https://moveabox.in",
    },
}


class SEOAuditor:
    """Audits NAP consistency and GBP profile completeness."""

    def __init__(self):
        self.audit_results = {}

    # -------------------------------------------------------------------------
    # Profile Completeness
    # -------------------------------------------------------------------------

    def score_profile_completeness(self, profile: dict) -> dict:
        """
        Score a GBP profile on 10 elements (100 points total).
        Returns detailed scoring with gaps identified.
        """
        location_slug = profile.get("location_slug", "")
        scores = {}
        total = 0

        # 1. Business Name (10 pts)
        has_name = bool(profile.get("name", ""))
        scores["business_name"] = {
            "score": 10 if has_name else 0,
            "max": 10,
            "status": "pass" if has_name else "fail",
            "action": None if has_name else "Add business name with city identifier",
        }
        total += scores["business_name"]["score"]

        # 2. Primary + Secondary Categories (15 pts)
        primary_cat = profile.get("primaryCategory", {})
        secondary_cats = profile.get("additionalCategories", [])
        has_primary = bool(primary_cat)
        cat_score = 5 if has_primary else 0
        cat_score += min(len(secondary_cats) * 5, 10)
        scores["primary_secondary_categories"] = {
            "score": cat_score,
            "max": 15,
            "status": "pass" if cat_score >= 12 else "partial" if cat_score > 0 else "fail",
            "action": None if cat_score >= 12 else f"Add {3 - len(secondary_cats)} more relevant secondary categories",
        }
        total += cat_score

        # 3. Business Description (10 pts)
        description = profile.get("profile", {}).get("description", "")
        desc_len = len(description)
        desc_score = 10 if desc_len >= 600 else 7 if desc_len >= 300 else 3 if desc_len > 0 else 0
        scores["business_description"] = {
            "score": desc_score,
            "max": 10,
            "status": "pass" if desc_score >= 8 else "partial" if desc_score > 0 else "fail",
            "action": None if desc_score >= 8 else f"Expand description to 750 chars (currently {desc_len})",
        }
        total += desc_score

        # 4. Services with Descriptions (10 pts)
        services = profile.get("serviceItems", [])
        service_count = len(services)
        svc_score = 10 if service_count >= 8 else 6 if service_count >= 4 else 3 if service_count > 0 else 0
        scores["services_with_descriptions"] = {
            "score": svc_score,
            "max": 10,
            "status": "pass" if svc_score >= 8 else "partial" if svc_score > 0 else "fail",
            "action": None if svc_score >= 8 else f"Add {8 - service_count} more services with descriptions and pricing",
        }
        total += svc_score

        # 5. Operating Hours (5 pts)
        hours = profile.get("regularHours", {})
        has_hours = bool(hours.get("periods", []))
        hours_score = 5 if has_hours else 0
        scores["operating_hours"] = {
            "score": hours_score,
            "max": 5,
            "status": "pass" if has_hours else "fail",
            "action": None if has_hours else "Add operating hours including holiday hours",
        }
        total += hours_score

        # 6. Photos (15 pts)
        photo_count = profile.get("photo_count", 0)
        photo_score = 15 if photo_count >= 25 else 10 if photo_count >= 15 else 5 if photo_count >= 5 else 0
        scores["photos"] = {
            "score": photo_score,
            "max": 15,
            "status": "pass" if photo_score >= 12 else "partial" if photo_score > 0 else "fail",
            "action": None if photo_score >= 12 else f"Upload {25 - photo_count} more geo-tagged photos",
        }
        total += photo_score

        # 7. Q&A Section (10 pts)
        qa_count = profile.get("qa_count", 0)
        qa_score = 10 if qa_count >= 10 else 6 if qa_count >= 5 else 3 if qa_count > 0 else 0
        scores["qa_section"] = {
            "score": qa_score,
            "max": 10,
            "status": "pass" if qa_score >= 8 else "partial" if qa_score > 0 else "fail",
            "action": None if qa_score >= 8 else f"Seed {10 - qa_count} more location-specific Q&As",
        }
        total += qa_score

        # 8. Products/Services Menu (10 pts)
        products = profile.get("products", [])
        product_score = 10 if len(products) >= 5 else 6 if len(products) >= 2 else 0
        scores["products_services_menu"] = {
            "score": product_score,
            "max": 10,
            "status": "pass" if product_score >= 8 else "partial" if product_score > 0 else "fail",
            "action": None if product_score >= 8 else "Add service packages with pricing to Products section",
        }
        total += product_score

        # 9. Business Attributes (5 pts)
        attributes = profile.get("attributes", [])
        attr_score = 5 if len(attributes) >= 5 else 3 if len(attributes) >= 2 else 0
        scores["business_attributes"] = {
            "score": attr_score,
            "max": 5,
            "status": "pass" if attr_score >= 4 else "partial" if attr_score > 0 else "fail",
            "action": None if attr_score >= 4 else "Enable all relevant attributes: online booking, payment methods, etc.",
        }
        total += attr_score

        # 10. Website + Booking Links (10 pts)
        website = profile.get("websiteUri", "")
        booking = profile.get("moreHours", [])
        link_score = 7 if website else 0
        link_score += 3 if "utm_source=gbp" in website else 0
        scores["website_booking_links"] = {
            "score": link_score,
            "max": 10,
            "status": "pass" if link_score >= 8 else "partial" if link_score > 0 else "fail",
            "action": None if link_score >= 8 else "Add UTM-tagged booking URL and verify website link",
        }
        total += link_score

        return {
            "location_slug": location_slug,
            "total_score": total,
            "max_score": 100,
            "grade": self._grade(total),
            "dimension_scores": scores,
            "gaps": [
                {"element": k, "action": v["action"]}
                for k, v in scores.items()
                if v["action"]
            ],
            "audited_at": datetime.utcnow().isoformat(),
        }

    def _grade(self, score: int) -> str:
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        return "F"

    # -------------------------------------------------------------------------
    # NAP Consistency
    # -------------------------------------------------------------------------

    def audit_nap_consistency(self, location_slug: str) -> dict:
        """
        Check NAP consistency for a location across known sources.
        Returns a report of matches, mismatches, and missing listings.
        """
        canonical = LOCATION_NAP.get(location_slug, {})
        if not canonical:
            raise ValueError(f"Unknown location: {location_slug}")

        audit = {
            "location_slug": location_slug,
            "canonical_nap": canonical,
            "sources_checked": [],
            "mismatches": [],
            "missing_listings": [],
            "consistency_score": 0,
            "audited_at": datetime.utcnow().isoformat(),
        }

        # In production, this would scrape each directory
        # For now, we log what needs to be checked
        for tier, sources in CITATION_SOURCES.items():
            for source in sources:
                audit["sources_checked"].append({
                    "source": source,
                    "tier": tier,
                    "status": "pending_verification",
                    "nap_match": None,
                })

        return audit

    # -------------------------------------------------------------------------
    # Citation Audit
    # -------------------------------------------------------------------------

    def get_citation_opportunities(
        self, location_slug: str, competitor_citations: list[str]
    ) -> list[dict]:
        """
        Return citation directories the competitor is on that MoveABox is not.
        """
        all_sources = []
        for sources in CITATION_SOURCES.values():
            all_sources.extend(sources)

        # In production, compare against actual MoveABox citation list
        moveabox_citations = []  # Load from DB/file

        opportunities = []
        for citation in competitor_citations:
            if citation not in moveabox_citations and citation not in all_sources:
                opportunities.append({
                    "source": citation,
                    "type": "competitor_sourced",
                    "priority": "high",
                    "action": f"Create listing on {citation}",
                })

        return opportunities

    # -------------------------------------------------------------------------
    # Keyword Extraction from Competitor Profiles
    # -------------------------------------------------------------------------

    def extract_competitor_keywords(self, competitor_text: str) -> list[str]:
        """
        Extract relevant keywords from competitor GBP description or posts.
        Used to expand data/keywords.json with Tier 4 competitor-sourced keywords.
        """
        # Basic keyword extraction — in production use NLP/Claude
        service_terms = [
            "packers", "movers", "shifting", "relocation", "courier",
            "storage", "warehousing", "transportation", "delivery",
            "packing", "unpacking", "loading", "unloading",
        ]

        found = []
        text_lower = competitor_text.lower()
        for term in service_terms:
            if term in text_lower:
                # Extract surrounding context as keyword phrase
                pattern = rf"\b\w+ {re.escape(term)}\b|\b{re.escape(term)} \w+\b"
                matches = re.findall(pattern, text_lower)
                found.extend(matches)

        return list(set(found))

    # -------------------------------------------------------------------------
    # Full Audit Run
    # -------------------------------------------------------------------------

    def run_full_audit(self, profiles: list[dict]) -> list[dict]:
        """Run complete profile audit for all locations."""
        results = []
        for profile in profiles:
            audit = self.score_profile_completeness(profile)
            nap = self.audit_nap_consistency(profile["location_slug"])
            audit["nap_audit"] = nap
            results.append(audit)
            logger.info(
                f"Audit: {profile['location_slug']} scored {audit['total_score']}/100 ({audit['grade']})"
            )
        return results

    def generate_audit_report(self, audit_results: list[dict]) -> str:
        """Generate a markdown audit report."""
        lines = [
            "# MoveABox Profile Completeness Audit",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n",
        ]

        for audit in audit_results:
            slug = audit["location_slug"].split("-")[-1].title()
            lines.append(f"## {slug}")
            lines.append(
                f"**Score: {audit['total_score']}/100 (Grade: {audit['grade']})**\n"
            )

            if audit["gaps"]:
                lines.append("### Action Items:")
                for gap in audit["gaps"]:
                    lines.append(f"- {gap['action']}")
            else:
                lines.append("✅ Profile fully optimized!")
            lines.append("")

        return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    auditor = SEOAuditor()

    # Mock profile for testing
    mock_profile = {
        "location_slug": "moveabox-koramangala",
        "name": "MoveABox - Koramangala",
        "primaryCategory": {"displayName": "Moving Company"},
        "additionalCategories": [
            {"displayName": "Courier Service"},
            {"displayName": "Storage Facility"},
        ],
        "profile": {"description": "Professional packers and movers in Koramangala." * 5},
        "serviceItems": [{"name": "Local Shifting"}, {"name": "Office Relocation"}],
        "regularHours": {"periods": [{"openDay": "MONDAY"}]},
        "photo_count": 20,
        "qa_count": 8,
        "products": [{"name": "1BHK Package"}],
        "attributes": ["online_appointments", "wheelchair_accessible"],
        "websiteUri": "https://moveabox.in/koramangala?utm_source=gbp",
    }

    result = auditor.score_profile_completeness(mock_profile)
    print(f"Profile Score: {result['total_score']}/100 (Grade: {result['grade']})")
    print("\nGaps:")
    for gap in result["gaps"]:
        print(f"  - {gap['action']}")

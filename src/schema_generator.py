"""
JSON-LD Structured Data Generator
MoveABox GBP Agent v2.0

Generates Schema.org structured data markup for all 3 MoveABox locations.
Supports: MovingCompany, CourierService, SelfStorage, LocalBusiness.
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

LOCATION_SCHEMA_DATA = {
    "moveabox-bannerghatta": {
        "name": "MoveABox Packers and Movers - Bannerghatta Road",
        "url": "https://moveabox.in/bannerghatta",
        "telephone": os.getenv("PHONE_BANNERGHATTA", "+91-XXXXXXXXXX"),
        "address": {
            "streetAddress": os.getenv("STREET_BANNERGHATTA", "JP Nagar 5th Phase"),
            "addressLocality": "Bannerghatta Road",
            "addressRegion": "Karnataka",
            "postalCode": os.getenv("POSTAL_BANNERGHATTA", "560076"),
            "addressCountry": "IN",
        },
        "geo": {
            "latitude": 12.8745,
            "longitude": 77.5970,
        },
        "service_area": [
            "JP Nagar", "Bannerghatta Road", "Arekere", "Gottigere",
            "Hulimavu", "Begur", "Bommanahalli", "Sarakki", "Jayanagar",
        ],
        "maps_url": "https://maps.app.goo.gl/b6FU5TNh5kecUg9c8",
        "price_range": "₹₹",
        "aggregate_rating": {
            "rating_value": 4.5,
            "review_count": 89,
        },
    },
    "moveabox-banashankari": {
        "name": "MoveABox Packers and Movers - Banashankari",
        "url": "https://moveabox.in/banashankari",
        "telephone": os.getenv("PHONE_BANASHANKARI", "+91-XXXXXXXXXX"),
        "address": {
            "streetAddress": os.getenv("STREET_BANASHANKARI", "Banashankari Stage 2"),
            "addressLocality": "Banashankari",
            "addressRegion": "Karnataka",
            "postalCode": os.getenv("POSTAL_BANASHANKARI", "560070"),
            "addressCountry": "IN",
        },
        "geo": {
            "latitude": 12.9256,
            "longitude": 77.5564,
        },
        "service_area": [
            "Banashankari", "Padmanabhanagar", "Kumaraswamy Layout",
            "Uttarahalli", "Kanakapura Road", "RR Nagar", "Girinagar",
            "Kathriguppe", "Basavanagudi",
        ],
        "maps_url": "https://maps.app.goo.gl/N9JCzMd98UTrTPBE7",
        "price_range": "₹₹",
        "aggregate_rating": {
            "rating_value": 4.4,
            "review_count": 0,  # Updated from GBP
        },
    },
    "moveabox-koramangala": {
        "name": "MoveABox Packers and Movers - Koramangala",
        "url": "https://moveabox.in/koramangala",
        "telephone": os.getenv("PHONE_KORAMANGALA", "+91-XXXXXXXXXX"),
        "address": {
            "streetAddress": os.getenv("STREET_KORAMANGALA", "Koramangala 4th Block"),
            "addressLocality": "Koramangala",
            "addressRegion": "Karnataka",
            "postalCode": os.getenv("POSTAL_KORAMANGALA", "560034"),
            "addressCountry": "IN",
        },
        "geo": {
            "latitude": 12.9352,
            "longitude": 77.6245,
        },
        "service_area": [
            "Koramangala", "HSR Layout", "BTM Layout", "Madiwala",
            "Ejipura", "Indiranagar", "Adugodi", "Domlur",
        ],
        "maps_url": "https://maps.app.goo.gl/Ry7wJSGhYWG5GLF67",
        "price_range": "₹₹",
        "aggregate_rating": {
            "rating_value": 4.6,
            "review_count": 0,  # Updated from GBP
        },
    },
}

OPENING_HOURS = [
    {
        "@type": "OpeningHoursSpecification",
        "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "opens": "08:00",
        "closes": "20:00",
    },
    {
        "@type": "OpeningHoursSpecification",
        "dayOfWeek": ["Saturday"],
        "opens": "08:00",
        "closes": "18:00",
    },
    {
        "@type": "OpeningHoursSpecification",
        "dayOfWeek": ["Sunday"],
        "opens": "09:00",
        "closes": "16:00",
    },
]

SERVICE_CATALOG = [
    {
        "@type": "Offer",
        "itemOffered": {
            "@type": "Service",
            "name": "Local Home Shifting",
            "description": "1BHK, 2BHK, 3BHK home shifting within Bangalore",
        },
        "priceSpecification": {
            "@type": "PriceSpecification",
            "priceCurrency": "INR",
            "minPrice": 3000,
            "maxPrice": 15000,
        },
    },
    {
        "@type": "Offer",
        "itemOffered": {
            "@type": "Service",
            "name": "Intercity Relocation",
            "description": "Bangalore to all major Indian cities",
        },
        "priceSpecification": {
            "@type": "PriceSpecification",
            "priceCurrency": "INR",
            "minPrice": 8000,
            "maxPrice": 50000,
        },
    },
    {
        "@type": "Offer",
        "itemOffered": {
            "@type": "Service",
            "name": "Office Relocation",
            "description": "Commercial and IT office relocation services",
        },
    },
    {
        "@type": "Offer",
        "itemOffered": {
            "@type": "Service",
            "name": "Courier Service",
            "description": "Same-day and express courier delivery across Bangalore and India",
        },
    },
    {
        "@type": "Offer",
        "itemOffered": {
            "@type": "Service",
            "name": "Storage Solutions",
            "description": "Short-term and long-term climate-controlled storage",
        },
        "priceSpecification": {
            "@type": "PriceSpecification",
            "priceCurrency": "INR",
            "unitCode": "MON",
            "minPrice": 1500,
        },
    },
]


class SchemaGenerator:
    """Generates JSON-LD structured data for MoveABox locations."""

    def generate_moving_company_schema(self, location_slug: str) -> dict:
        """Generate @type MovingCompany schema for a location."""
        data = LOCATION_SCHEMA_DATA.get(location_slug)
        if not data:
            raise ValueError(f"Unknown location: {location_slug}")

        schema = {
            "@context": "https://schema.org",
            "@type": ["MovingCompany", "LocalBusiness"],
            "name": data["name"],
            "url": data["url"],
            "telephone": data["telephone"],
            "priceRange": data["price_range"],
            "image": f"https://moveabox.in/images/{location_slug}-exterior.jpg",
            "logo": "https://moveabox.in/logo.png",
            "address": {
                "@type": "PostalAddress",
                **data["address"],
            },
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": data["geo"]["latitude"],
                "longitude": data["geo"]["longitude"],
            },
            "hasMap": data["maps_url"],
            "openingHoursSpecification": OPENING_HOURS,
            "areaServed": [
                {
                    "@type": "AdministrativeArea",
                    "name": area,
                }
                for area in data["service_area"]
            ],
            "hasOfferCatalog": {
                "@type": "OfferCatalog",
                "name": "MoveABox Services",
                "itemListElement": SERVICE_CATALOG,
            },
            "sameAs": [
                "https://www.facebook.com/moveabox",
                "https://www.instagram.com/moveabox",
                data["maps_url"],
            ],
        }

        if data["aggregate_rating"]["review_count"] > 0:
            schema["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": data["aggregate_rating"]["rating_value"],
                "reviewCount": data["aggregate_rating"]["review_count"],
                "bestRating": "5",
                "worstRating": "1",
            }

        return schema

    def generate_courier_schema(self, location_slug: str) -> dict:
        """Generate @type CourierService schema for a location."""
        data = LOCATION_SCHEMA_DATA.get(location_slug)
        if not data:
            raise ValueError(f"Unknown location: {location_slug}")

        return {
            "@context": "https://schema.org",
            "@type": "CourierService",
            "name": f"MoveABox Courier Service - {data['address']['addressLocality']}",
            "url": data["url"],
            "telephone": data["telephone"],
            "address": {
                "@type": "PostalAddress",
                **data["address"],
            },
            "areaServed": {
                "@type": "City",
                "name": "Bangalore",
            },
            "availableDeliveryMethod": [
                "http://purl.org/goodrelations/v1#DeliveryModeDirectDownload",
                "http://purl.org/goodrelations/v1#DeliveryModeFreight",
            ],
            "openingHoursSpecification": OPENING_HOURS,
        }

    def generate_storage_schema(self, location_slug: str) -> dict:
        """Generate @type SelfStorage schema for a location."""
        data = LOCATION_SCHEMA_DATA.get(location_slug)
        if not data:
            raise ValueError(f"Unknown location: {location_slug}")

        return {
            "@context": "https://schema.org",
            "@type": "SelfStorage",
            "name": f"MoveABox Storage Solutions - {data['address']['addressLocality']}",
            "url": data["url"],
            "telephone": data["telephone"],
            "address": {
                "@type": "PostalAddress",
                **data["address"],
            },
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": data["geo"]["latitude"],
                "longitude": data["geo"]["longitude"],
            },
            "openingHoursSpecification": OPENING_HOURS,
            "amenityFeature": [
                {"@type": "LocationFeatureSpecification", "name": "Climate Control", "value": True},
                {"@type": "LocationFeatureSpecification", "name": "24/7 Security", "value": True},
                {"@type": "LocationFeatureSpecification", "name": "Pickup & Delivery", "value": True},
            ],
        }

    def generate_faq_schema(self, faqs: list[dict]) -> dict:
        """Generate FAQ schema from a list of Q&A pairs."""
        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq["question"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": faq["answer"],
                    },
                }
                for faq in faqs
            ],
        }

    def generate_all_schemas(self, location_slug: str) -> dict:
        """Generate all schema types for a location."""
        return {
            "moving_company": self.generate_moving_company_schema(location_slug),
            "courier": self.generate_courier_schema(location_slug),
            "storage": self.generate_storage_schema(location_slug),
        }

    def save_schemas(self, location_slug: str) -> None:
        """Generate and save all schemas for a location to output directory."""
        schemas = self.generate_all_schemas(location_slug)
        slug_short = location_slug.split("-")[-1]

        output_dir = "output/schema"
        os.makedirs(output_dir, exist_ok=True)

        for schema_type, schema in schemas.items():
            filename = f"{output_dir}/{slug_short}-{schema_type}-schema.json"
            with open(filename, "w") as f:
                json.dump(schema, f, indent=2)
            logger.info(f"Saved schema: {filename}")

    def generate_html_script_tags(self, location_slug: str) -> str:
        """Generate HTML <script> tags for embedding schemas in website."""
        schemas = self.generate_all_schemas(location_slug)
        tags = []

        for schema in schemas.values():
            json_str = json.dumps(schema, indent=2, ensure_ascii=False)
            tags.append(
                f'<script type="application/ld+json">\n{json_str}\n</script>'
            )

        return "\n\n".join(tags)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generator = SchemaGenerator()

    for slug in LOCATION_SCHEMA_DATA:
        generator.save_schemas(slug)
        print(f"Generated schemas for {slug}")

    # Print HTML tags for Koramangala
    print("\n--- HTML Script Tags for Koramangala ---")
    print(generator.generate_html_script_tags("moveabox-koramangala")[:500] + "...")

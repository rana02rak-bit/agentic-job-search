from sqlalchemy import select

from app.db import SessionLocal, create_tables
from app.models import Company, CompanySource, Priority

SEED_COMPANIES = [
    ("Ola Electric", "https://www.olaelectric.com", "EV / Consumer", "Bangalore", "HIGH"),
    ("Zepto", "https://www.zeptonow.com", "Consumer Internet", "Bangalore", "HIGH"),
    ("Meesho", "https://www.meesho.io", "Consumer Internet", "Bangalore", "HIGH"),
    ("Perplexity", "https://www.perplexity.ai", "AI", "Remote", "HIGH"),
    ("Rippling", "https://www.rippling.com", "SaaS", "Bangalore", "MEDIUM"),
    ("Namma Yatri", "https://nammayatri.in", "Mobility", "Bangalore", "MEDIUM"),
    ("Groww", "https://groww.in", "Fintech", "Bangalore", "HIGH"),
    ("Razorpay", "https://razorpay.com", "Fintech", "Bangalore", "HIGH"),
    ("CRED", "https://cred.club", "Fintech / Consumer", "Bangalore", "MEDIUM"),
    ("PhonePe", "https://www.phonepe.com", "Fintech / Consumer", "Bangalore", "HIGH"),
]


def seed() -> None:
    create_tables()
    with SessionLocal() as db:
        existing = set(db.scalars(select(Company.name)).all())
        for name, website, industry, location, priority in SEED_COMPANIES:
            if name in existing:
                continue
            db.add(
                Company(
                    name=name,
                    website=website,
                    industry=industry,
                    location=location,
                    source=CompanySource.USER.value,
                    priority=Priority(priority).value,
                    is_watchlisted=True,
                )
            )
        db.commit()


if __name__ == "__main__":
    seed()


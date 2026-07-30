from pydantic import BaseModel, Field

from app.core.config import Settings
from app.models import CandidateProfile, Company, Job, Recruiter
from app.services.structured_ai import (
    StructuredAIUnavailable,
    generate_structured,
)


class MessageGenerationUnavailable(RuntimeError):
    pass


class GeneratedOutreach(BaseModel):
    subject: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=20, max_length=2000)
    rationale: str = Field(min_length=10, max_length=1000)


def generate_outreach_message(
    settings: Settings,
    profile: CandidateProfile,
    company: Company,
    job: Job | None,
    recruiter: Recruiter,
    extra_context: str | None,
) -> GeneratedOutreach:
    target_role = (
        job.title
        if job
        else "Product, AI, Strategy, Growth, Platform or Founder's Office opportunities"
    )
    target_location = (
        job.location if job else company.location or "Bangalore, Gurgaon, Mumbai or Remote"
    )
    prompt = (
        f"Candidate: {profile.name}\n"
        f"Resume:\n{profile.resume_text}\n"
        f"Positioning:\n{profile.positioning or 'Not supplied'}\n"
        f"Company: {company.name}\n"
        f"Target role or function: {target_role}\n"
        f"Location: {target_location}\n"
        f"Specific live job supplied: {'Yes' if job else 'No'}\n"
        f"Recipient: {recruiter.name}, "
        f"{recruiter.designation or 'designation unknown'}\n"
        f"Recipient activity: {recruiter.activity or 'Not supplied'}\n"
        f"Additional context: {extra_context or 'None'}"
    )
    try:
        return generate_structured(
            settings,
            GeneratedOutreach,
            (
                "Write one original LinkedIn outreach message and a short optional InMail "
                "subject. Do not use a reusable template, brackets, placeholders, exaggerated "
                "claims, or generic praise. Keep the message between 70 and 120 words. Reference "
                "the specific role when one is supplied and the candidate's most relevant "
                "evidence. When no live job is supplied, write a company-specific message about "
                "the target functions without claiming that a role is open. Ask for a brief "
                "conversation or direction to the right person. The user will review and "
                "explicitly approve before sending."
            ),
            prompt,
        )
    except StructuredAIUnavailable as exc:
        raise MessageGenerationUnavailable(str(exc)) from exc

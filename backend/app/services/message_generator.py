from openai import OpenAI
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.models import CandidateProfile, Job, Recruiter


class MessageGenerationUnavailable(RuntimeError):
    pass


class GeneratedOutreach(BaseModel):
    body: str = Field(min_length=20, max_length=2000)
    rationale: str = Field(min_length=10, max_length=1000)


def generate_outreach_message(
    settings: Settings,
    profile: CandidateProfile,
    job: Job,
    recruiter: Recruiter,
    extra_context: str | None,
) -> GeneratedOutreach:
    if not settings.openai_api_key:
        raise MessageGenerationUnavailable(
            "OPENAI_API_KEY is not configured. Add it to .env to generate personalized messages."
        )

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.parse(
        model=settings.openai_model,
        reasoning={"effort": "low"},
        input=[
            {
                "role": "developer",
                "content": (
                    "Write one original LinkedIn outreach message. Do not use a reusable template, "
                    "brackets, placeholders, exaggerated claims, or generic praise. Keep it "
                    "between 70 and 120 words. Reference the specific role, the candidate's most "
                    "relevant evidence, and why this recipient is relevant. Ask for a brief "
                    "conversation or direction to the right person. The user will review before "
                    "sending."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Candidate: {profile.name}\n"
                    f"Resume:\n{profile.resume_text}\n"
                    f"Positioning:\n{profile.positioning or 'Not supplied'}\n"
                    f"Company: {job.company.name}\n"
                    f"Role: {job.title}\n"
                    f"Location: {job.location}\n"
                    f"Recipient: {recruiter.name}, "
                    f"{recruiter.designation or 'designation unknown'}\n"
                    f"Recipient activity: {recruiter.activity or 'Not supplied'}\n"
                    f"Additional context: {extra_context or 'None'}"
                ),
            },
        ],
        text_format=GeneratedOutreach,
    )
    if response.output_parsed is None:
        raise MessageGenerationUnavailable("The model did not return a message.")
    return response.output_parsed

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreComponents:
    funding: int
    hiring: int
    ai: int
    location: int
    role_match: int

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if not 0 <= value <= 10:
                raise ValueError(f"{name} score must be between 0 and 10")

    @property
    def total(self) -> int:
        return self.funding + self.hiring + self.ai + self.location + self.role_match


def clamp_score(value: int) -> int:
    return max(0, min(10, value))


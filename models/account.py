from dataclasses import dataclass

@dataclass(frozen=True)
class Account:
    name: str
    currency: str
    provider: str

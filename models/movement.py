from dataclasses import dataclass

@dataclass(frozen=True)
class Movement:
    occurred_at: str
    description: str
    amount: float
    currency: str
    fee: float
    kind: str

from pydantic import BaseModel


class StartVerificationRequest(BaseModel):
    travel_direction: str
    latitude: float | None = None
    longitude: float | None = None


class DecisionRequest(BaseModel):
    decision: str  # approved / rejected / escalated


class WatchlistCreateResponse(BaseModel):
    id: str
    reference_label: str


class FamilyMemberRequest(BaseModel):
    relationship: str  # spouse / child / parent / sibling / other_relative
    relationship_proof_presented: bool = False

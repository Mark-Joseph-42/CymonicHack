from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class ClientTier(str, Enum):
    ENTERPRISE_VIP = "ENTERPRISE_VIP"
    STANDARD = "STANDARD"

class DelayCause(str, Enum):
    CARRIER_FAULT = "CARRIER_FAULT"
    WEATHER_FORCE_MAJEURE = "WEATHER_FORCE_MAJEURE"
    CUSTOMS_HOLD = "CUSTOMS_HOLD"

class ClaimStatus(str, Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    FLAG_FOR_AUDIT = "FLAG_FOR_AUDIT"
    REJECT = "REJECT"

class ClientBase(BaseModel):
    client_id: str = Field(..., description="Unique client identifier, e.g. CL-1001")
    company_name: str
    tier: ClientTier
    refund_count_30d: int = Field(default=0, ge=0)
    account_status: str = Field(default="ACTIVE")
    contact_email: str

class ClientCreate(ClientBase):
    pass

class ClientResponse(ClientBase):
    created_at: str
    updated_at: str

class ClaimSubmission(BaseModel):
    order_id: str = Field(..., description="Unique shipment order ID, e.g. ORD-2026-9001")
    tracking_number: str = Field(..., description="Shipment tracking number")
    client_id: str = Field(..., description="Submitting client ID")
    declared_value: float = Field(..., ge=0, description="Total declared cargo value in USD")
    claim_amount: float = Field(..., ge=0, description="Requested refund amount in USD")
    delay_cause: DelayCause = Field(..., description="Primary cause of delay or loss")
    notes: Optional[str] = Field(None, description="Additional context or client notes")

class DecisionResult(BaseModel):
    decision: ClaimStatus
    reasoning: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    rules_triggered: list[str]

class OrderResponse(BaseModel):
    order_id: str
    tracking_number: str
    client_id: str
    declared_value: float
    claim_amount: float
    delay_cause: DelayCause
    claim_status: ClaimStatus
    ai_justification: Optional[str]
    claim_submitted_at: str
    evaluated_at: Optional[str]
    created_at: str
    updated_at: str

class ManualReviewPayload(BaseModel):
    decision: ClaimStatus = Field(..., description="Updated decision: AUTO_APPROVE, FLAG_FOR_AUDIT, or REJECT")
    reviewer_notes: str = Field(..., description="Audit/review notes by human agent")

class MetricsResponse(BaseModel):
    total_claims: int
    auto_approve_count: int
    flagged_for_audit_count: int
    reject_count: int
    total_claimed_value: float
    auto_approved_value: float
    average_claim_amount: float
    sla_compliance_rate: float

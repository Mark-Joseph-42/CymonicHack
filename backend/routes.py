from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from .models import (
    ClaimSubmission,
    OrderResponse,
    ClientResponse,
    ClientCreate,
    ManualReviewPayload,
    MetricsResponse,
    ClaimStatus,
)
from .database import DatabaseManager
from .engine import LLMReasoningAgent

router = APIRouter()
ai_agent = LLMReasoningAgent()

# -----------------------------------------------------------------------------
# Claims Ingestion & Evaluation Endpoints
# -----------------------------------------------------------------------------
@router.post(
    "/claims/submit",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a freight claim payload and execute automated decisioning",
)
async def submit_claim(claim: ClaimSubmission):
    """
    Ingest a new claim payload, evaluate business trade-offs via AI reasoning model,
    persist decision state into SQLite, and optionally update client refund velocity.
    """
    # 1. Verify if order already exists
    existing_order = DatabaseManager.get_order(claim.order_id)
    if existing_order:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order {claim.order_id} has already been registered and evaluated.",
        )

    # 2. Retrieve client profile
    client = DatabaseManager.get_client(claim.client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{claim.client_id}' does not exist. Please register client profile first.",
        )

    # 3. Evaluate claim through AI reasoning agent
    decision_result = await ai_agent.evaluate_claim(claim, client)

    # 4. Format justification string
    formatted_justification = (
        f"{decision_result.reasoning} "
        f"[Confidence: {decision_result.confidence_score * 100:.1f}%. "
        f"Triggers: {', '.join(decision_result.rules_triggered)}]"
    )

    # 5. Persist order & claim evaluation to database
    new_order = DatabaseManager.insert_order_evaluation(
        order_id=claim.order_id,
        tracking_number=claim.tracking_number,
        client_id=claim.client_id,
        declared_value=claim.declared_value,
        claim_amount=claim.claim_amount,
        delay_cause=claim.delay_cause.value,
        claim_status=decision_result.decision.value,
        ai_justification=formatted_justification,
    )

    # 6. If approved, increment 30-day refund frequency for client
    if decision_result.decision == ClaimStatus.AUTO_APPROVE:
        DatabaseManager.increment_refund_count(claim.client_id)

    return new_order


@router.get(
    "/claims",
    response_model=List[OrderResponse],
    summary="List and filter all orders and claim evaluations",
)
def list_claims(
    status: Optional[ClaimStatus] = Query(None, description="Filter by status (AUTO_APPROVE, FLAG_FOR_AUDIT, REJECT)"),
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    limit: int = Query(100, ge=1, le=500),
):
    status_str = status.value if status else None
    return DatabaseManager.list_orders(status=status_str, client_id=client_id, limit=limit)


@router.get(
    "/claims/{order_id}",
    response_model=OrderResponse,
    summary="Get single order evaluation details by order_id",
)
def get_claim(order_id: str):
    order = DatabaseManager.get_order(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order {order_id} not found.")
    return order


@router.patch(
    "/claims/{order_id}/review",
    response_model=OrderResponse,
    summary="Human auditor manual override for flagged claims",
)
def audit_claim_review(order_id: str, payload: ManualReviewPayload):
    """
    Human-in-the-loop audit endpoint allowing claims agents to override
    or finalize decisions for flagged claims.
    """
    order = DatabaseManager.get_order(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order {order_id} not found.")

    updated_order = DatabaseManager.update_order_status(
        order_id=order_id,
        new_status=payload.decision.value,
        audit_notes=payload.reviewer_notes,
    )

    # If transitioning to AUTO_APPROVE from audit, track client refund count
    if payload.decision == ClaimStatus.AUTO_APPROVE and order["claim_status"] != "AUTO_APPROVE":
        DatabaseManager.increment_refund_count(order["client_id"])

    return updated_order


# -----------------------------------------------------------------------------
# Clients Endpoints
# -----------------------------------------------------------------------------
@router.get("/clients", response_model=List[ClientResponse], summary="List all registered client accounts")
def list_clients():
    return DatabaseManager.list_clients()


@router.get("/clients/{client_id}", response_model=ClientResponse, summary="Retrieve a client profile")
def get_client(client_id: str):
    client = DatabaseManager.get_client(client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Client {client_id} not found.")
    return client


@router.post("/clients", response_model=ClientResponse, summary="Create or update client profile")
def upsert_client(payload: ClientCreate):
    return DatabaseManager.create_or_update_client(payload.model_dump())


# -----------------------------------------------------------------------------
# Operations & Metrics Dashboard Data
# -----------------------------------------------------------------------------
@router.get("/metrics", response_model=MetricsResponse, summary="Aggregated operations & SLA metrics")
def get_metrics():
    return DatabaseManager.get_metrics()

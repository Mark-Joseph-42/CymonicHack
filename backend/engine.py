import os
import json
import logging
from typing import Dict, Any, List
import httpx
from .models import ClaimSubmission, ClaimStatus, DelayCause, ClientTier, DecisionResult

logger = logging.getLogger("decision_engine")

INSTANT_APPROVAL_THRESHOLD = 2500.0
HIGH_REFUND_FREQUENCY_THRESHOLD = 5  # > 5 refunds in 30 days triggers audit/scrutiny

class RuleEngine:
    """
    Deterministic rule-based baseline engine for freight claims.
    Evaluates:
      1. Delay Cause (Carrier Fault vs Force Majeure vs Customs Hold)
      2. Claim Amount vs Instant Approval Threshold ($2,500)
      3. Client Tier (ENTERPRISE_VIP vs STANDARD)
      4. Historical Client Refund Frequency (refund_count_30d)
    """

    @staticmethod
    def evaluate(claim: ClaimSubmission, client: Dict[str, Any]) -> DecisionResult:
        rules_triggered: List[str] = []
        tier = client.get("tier", ClientTier.STANDARD.value)
        refund_count = client.get("refund_count_30d", 0)
        account_status = client.get("account_status", "ACTIVE")
        amount = claim.claim_amount
        cause = claim.delay_cause

        # Rule 1: Account Status check
        if account_status in ["SUSPENDED", "UNDER_REVIEW"]:
            rules_triggered.append(f"Client account is {account_status}")
            return DecisionResult(
                decision=ClaimStatus.FLAG_FOR_AUDIT,
                reasoning=(
                    f"Client {client.get('company_name', claim.client_id)} is currently {account_status}. "
                    f"Automated resolution halted; requires operational compliance audit."
                ),
                confidence_score=0.98,
                rules_triggered=rules_triggered,
            )

        # Rule 2: Force Majeure / Weather delays
        if cause == DelayCause.WEATHER_FORCE_MAJEURE:
            rules_triggered.append("WEATHER_FORCE_MAJEURE exempt under Terms of Carriage")
            if tier == ClientTier.ENTERPRISE_VIP.value and amount <= 1000.0 and refund_count <= 2:
                rules_triggered.append("Enterprise VIP goodwill concession review")
                return DecisionResult(
                    decision=ClaimStatus.FLAG_FOR_AUDIT,
                    reasoning=(
                        f"Weather/Force Majeure event is normally exempt from compensation under carriage terms. "
                        f"However, client holds ENTERPRISE_VIP tier with low claim velocity ({refund_count} in 30d). "
                        f"Flagged for account manager review for commercial goodwill exception."
                    ),
                    confidence_score=0.88,
                    rules_triggered=rules_triggered,
                )
            else:
                return DecisionResult(
                    decision=ClaimStatus.REJECT,
                    reasoning=(
                        f"Delay cause classified as WEATHER_FORCE_MAJEURE. "
                        f"Standard Terms of Carriage section 4.2 disclaims carrier liability for certified acts of nature. "
                        f"Claim denied."
                    ),
                    confidence_score=0.99,
                    rules_triggered=rules_triggered,
                )

        # Rule 3: Customs Hold
        if cause == DelayCause.CUSTOMS_HOLD:
            rules_triggered.append("CUSTOMS_HOLD regulatory delay")
            return DecisionResult(
                decision=ClaimStatus.FLAG_FOR_AUDIT,
                reasoning=(
                    f"Delay attributed to CUSTOMS_HOLD. Documentation and cross-border regulatory inspection "
                    f"require verification to establish tariff and customs broker liability before disbursements."
                ),
                confidence_score=0.92,
                rules_triggered=rules_triggered,
            )

        # Rule 4: High refund velocity anomaly detection
        if refund_count >= HIGH_REFUND_FREQUENCY_THRESHOLD:
            rules_triggered.append(f"Elevated 30-day refund frequency anomaly ({refund_count} refunds)")
            return DecisionResult(
                decision=ClaimStatus.FLAG_FOR_AUDIT,
                reasoning=(
                    f"Client exhibits high 30-day refund velocity ({refund_count} historical claims). "
                    f"Automated approval suspended to prevent fraud and assess pattern trends."
                ),
                confidence_score=0.94,
                rules_triggered=rules_triggered,
            )

        # Rule 5: Carrier Fault claim amount checks
        if cause == DelayCause.CARRIER_FAULT:
            rules_triggered.append("Verified CARRIER_FAULT")
            if amount <= INSTANT_APPROVAL_THRESHOLD:
                rules_triggered.append(f"Claim amount (${amount:,.2f}) <= threshold (${INSTANT_APPROVAL_THRESHOLD:,.2f})")
                return DecisionResult(
                    decision=ClaimStatus.AUTO_APPROVE,
                    reasoning=(
                        f"Direct CARRIER_FAULT confirmed. Claim amount of ${amount:,.2f} is within the "
                        f"${INSTANT_APPROVAL_THRESHOLD:,.2f} instant auto-approval ceiling. "
                        f"Client tier is {tier} with satisfactory 30-day claim velocity ({refund_count} claims). "
                        f"Approved automatically under service level agreement guarantee."
                    ),
                    confidence_score=0.96,
                    rules_triggered=rules_triggered,
                )
            else:
                rules_triggered.append(f"Claim amount (${amount:,.2f}) exceeds threshold (${INSTANT_APPROVAL_THRESHOLD:,.2f})")
                return DecisionResult(
                    decision=ClaimStatus.FLAG_FOR_AUDIT,
                    reasoning=(
                        f"Carrier fault acknowledged; however, claim amount of ${amount:,.2f} exceeds "
                        f"the ${INSTANT_APPROVAL_THRESHOLD:,.2f} instant threshold. "
                        f"Routing to high-value claim audit team for proof-of-loss verification."
                    ),
                    confidence_score=0.95,
                    rules_triggered=rules_triggered,
                )

        # Fallback / Default
        rules_triggered.append("Default fallback review")
        return DecisionResult(
            decision=ClaimStatus.FLAG_FOR_AUDIT,
            reasoning="Parameters do not match deterministic approval criteria; queued for standard agent evaluation.",
            confidence_score=0.75,
            rules_triggered=rules_triggered,
        )


class LLMReasoningAgent:
    """
    Agentic reasoning model.
    Utilizes an LLM provider (OpenAI / Gemini / Anthropic / local Ollama / LM Studio)
    if API key or local endpoint is configured, with seamless automated fallback to
    the cognitive RuleEngine when external providers are unconfigured.
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    async def evaluate_claim(self, claim: ClaimSubmission, client: Dict[str, Any]) -> DecisionResult:
        # Check rule engine baseline first
        baseline = RuleEngine.evaluate(claim, client)

        # If LLM key is not provided, return the deterministic baseline decision
        if not self.api_key:
            logger.info("Using built-in cognitive rule engine for claim evaluation.")
            return baseline

        # If LLM key is configured, enrich via API reasoning
        try:
            prompt = f"""
You are the Chief Claims Auditor for Apex Logistics. Evaluate this B2B freight refund claim:

Shipment Details:
- Order ID: {claim.order_id}
- Tracking Number: {claim.tracking_number}
- Declared Cargo Value: ${claim.declared_value:,.2f}
- Claim Amount Requested: ${claim.claim_amount:,.2f}
- Reported Delay Cause: {claim.delay_cause.value}
- Additional Notes: {claim.notes or 'None'}

Client Profile:
- Company: {client.get('company_name', 'Unknown')}
- Tier: {client.get('tier', 'STANDARD')}
- 30-Day Refund Frequency: {client.get('refund_count_30d', 0)} claims
- Account Status: {client.get('account_status', 'ACTIVE')}

Business Policies:
1. Instant approval threshold is $2,500.00 for verified CARRIER_FAULT with normal refund velocity (<5).
2. WEATHER_FORCE_MAJEURE is exempt from carrier liability (REJECT), unless high-value VIP relationship justifies goodwill review.
3. CUSTOMS_HOLD requires audit verification (FLAG_FOR_AUDIT).
4. Claims over $2,500 must be audited (FLAG_FOR_AUDIT).
5. Refund count >= 5 triggers fraud/audit hold (FLAG_FOR_AUDIT).

Respond ONLY with valid JSON:
{{
  "decision": "AUTO_APPROVE" | "FLAG_FOR_AUDIT" | "REJECT",
  "reasoning": "Professional explanation of decision",
  "confidence_score": 0.0 to 1.0,
  "rules_triggered": ["rule1", "rule2"]
}}
"""
            async with httpx.AsyncClient(timeout=15.0) as client_http:
                response = await client_http.post(
                    f"{self.openai_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
                        "messages": [
                            {"role": "system", "content": "You are a precise B2B logistics decision engine returning strict JSON."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return DecisionResult(
                        decision=ClaimStatus(parsed["decision"]),
                        reasoning=parsed["reasoning"],
                        confidence_score=float(parsed.get("confidence_score", 0.95)),
                        rules_triggered=list(parsed.get("rules_triggered", [])),
                    )
        except Exception as e:
            logger.warning(f"LLM API call failed or timed out: {e}. Falling back to RuleEngine.")

        return baseline

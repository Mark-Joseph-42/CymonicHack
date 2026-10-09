"""
Apex Logistics - B2B Freight Claim & Refund Decision Engine
Core Evaluation Logic & AI Reasoning Module
"""

import math
from typing import Dict, Any, Tuple

# Configuration Constants
INSTANT_APPROVAL_THRESHOLD = 2500.00  # Claims <= $2,500 can be auto-approved
MAX_30D_REFUNDS_STANDARD = 3           # Max velocity before audit for Standard
MAX_30D_REFUNDS_VIP = 5                # Max velocity before audit for Enterprise VIP


class ClaimDecisionEngine:
    """
    Automated Decision Engine for evaluating B2B cargo freight refund claims.
    Weighs Client Tier, Claim Amount, Delay Cause, and Historical Refund Frequency.
    """

    @staticmethod
    def evaluate(client: Dict[str, Any], claim_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates a freight claim payload against client profile and business rules.

        Returns:
            Dict containing:
            - status: 'AUTO_APPROVE' | 'FLAG_FOR_AUDIT' | 'REJECT'
            - risk_score: int (0 to 100)
            - risk_factors: List[str]
            - ai_justification: str (human-readable explanation chain)
        """
        tier = client.get("tier", "STANDARD")
        refund_count_30d = client.get("refund_count_30d", 0)
        account_status = client.get("account_status", "ACTIVE")
        company_name = client.get("company_name", "Unknown Client")

        claim_amount = float(claim_payload.get("claim_amount", 0.0))
        declared_value = float(claim_payload.get("declared_value", 0.0))
        delay_cause = claim_payload.get("delay_cause", "CARRIER_FAULT")
        tracking_number = claim_payload.get("tracking_number", "N/A")

        risk_factors = []
        risk_score = 10

        # ---------------------------------------------------------
        # Rule 1: Account Status Hard Checks
        # ---------------------------------------------------------
        if account_status == "SUSPENDED":
            risk_score = 95
            risk_factors.append("Client account is currently SUSPENDED.")
            justification = (
                f"REJECTED: Client account ({company_name}) is currently SUSPENDED due to past billing "
                f"or compliance violations. All automated refund claims are blocked pending account reinstatement."
            )
            return {
                "status": "REJECT",
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "ai_justification": justification
            }

        # ---------------------------------------------------------
        # Rule 2: Force Majeure / Weather Exemption
        # ---------------------------------------------------------
        if delay_cause == "WEATHER_FORCE_MAJEURE":
            risk_score = 85
            risk_factors.append("Delay caused by Weather / Force Majeure event.")
            justification = (
                f"REJECTED: The recorded delay cause is WEATHER_FORCE_MAJEURE for shipment {tracking_number}. "
                f"Under Apex Logistics Standard Conditions of Carriage (Section 4.2), weather disruptions and acts "
                f"of nature are non-reimbursable force majeure events without an explicit weather-guarantee policy addendum."
            )
            return {
                "status": "REJECT",
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "ai_justification": justification
            }

        # ---------------------------------------------------------
        # Rule 3: Zero or Excessive Claim Amount Checks
        # ---------------------------------------------------------
        if claim_amount <= 0:
            risk_score = 100
            risk_factors.append("Claim amount is zero or negative.")
            justification = "REJECTED: Invalid claim amount ($0.00). Claim value must be positive."
            return {
                "status": "REJECT",
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "ai_justification": justification
            }

        if declared_value > 0 and claim_amount > declared_value:
            risk_score = 90
            risk_factors.append("Claim amount exceeds shipment declared value.")
            justification = (
                f"FLAG_FOR_AUDIT: Claim amount (${claim_amount:,.2f}) exceeds total shipment declared value "
                f"(${declared_value:,.2f}). Requires audit to verify liability limits."
            )
            return {
                "status": "FLAG_FOR_AUDIT",
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "ai_justification": justification
            }

        # ---------------------------------------------------------
        # Risk Score Accumulation
        # ---------------------------------------------------------
        # Velocity Risk
        velocity_limit = MAX_30D_REFUNDS_VIP if tier == "ENTERPRISE_VIP" else MAX_30D_REFUNDS_STANDARD
        is_high_velocity = refund_count_30d > velocity_limit

        if is_high_velocity:
            risk_score += 35
            risk_factors.append(f"High 30-day claim velocity ({refund_count_30d} claims, limit: {velocity_limit}).")

        # Threshold Risk
        is_high_value = claim_amount > INSTANT_APPROVAL_THRESHOLD
        if is_high_value:
            risk_score += 40
            risk_factors.append(f"Claim amount (${claim_amount:,.2f}) exceeds instant approval threshold (${INSTANT_APPROVAL_THRESHOLD:,.2f}).")

        # Customs Hold Risk
        if delay_cause == "CUSTOMS_HOLD":
            risk_score += 30
            risk_factors.append("Delay cause is CUSTOMS_HOLD (requires regulatory documentation verification).")

        # Account Under Review
        if account_status == "UNDER_REVIEW":
            risk_score += 25
            risk_factors.append("Client account status is currently UNDER_REVIEW.")

        # VIP Benefit: Lower base risk score
        if tier == "ENTERPRISE_VIP":
            risk_score = max(0, risk_score - 15)

        # ---------------------------------------------------------
        # Decision Routing Logic
        # ---------------------------------------------------------
        
        # 1. Audit Flags (High Value, High Velocity, Customs Hold, or Under Review)
        if is_high_value or is_high_velocity or delay_cause == "CUSTOMS_HOLD" or account_status == "UNDER_REVIEW":
            reasons = []
            if is_high_value:
                reasons.append(f"claim amount (${claim_amount:,.2f}) exceeds the ${INSTANT_APPROVAL_THRESHOLD:,.2f} instant threshold")
            if is_high_velocity:
                reasons.append(f"30-day refund count ({refund_count_30d}) exceeds the {tier} safety cap ({velocity_limit})")
            if delay_cause == "CUSTOMS_HOLD":
                reasons.append("delay cause is CUSTOMS_HOLD requiring tariff/document audit")
            if account_status == "UNDER_REVIEW":
                reasons.append("client account is currently UNDER_REVIEW")

            reasons_str = "; ".join(reasons)
            tier_label = "Enterprise VIP" if tier == "ENTERPRISE_VIP" else "Standard"

            justification = (
                f"FLAG_FOR_AUDIT: Claim of ${claim_amount:,.2f} for {company_name} ({tier_label}) flagged for human review because "
                f"{reasons_str}. Escalated to operations queue to prevent SLA violation while ensuring compliance."
            )
            return {
                "status": "FLAG_FOR_AUDIT",
                "risk_score": min(100, risk_score),
                "risk_factors": risk_factors,
                "ai_justification": justification
            }

        # 2. Auto Approve (Low Risk, Carrier Fault, <= $2,500, Clean Velocity)
        if delay_cause == "CARRIER_FAULT" and claim_amount <= INSTANT_APPROVAL_THRESHOLD:
            tier_label = "ENTERPRISE_VIP" if tier == "ENTERPRISE_VIP" else "STANDARD"
            justification = (
                f"AUTO_APPROVE: Claim amount (${claim_amount:,.2f}) is within the instant approval threshold (${INSTANT_APPROVAL_THRESHOLD:,.2f}). "
                f"Client ({company_name}) holds {tier_label} status with clean 30-day claim velocity ({refund_count_30d} prior claims). "
                f"Delay verified as CARRIER_FAULT. Auto-approved per automated SLA contract guidelines."
            )
            return {
                "status": "AUTO_APPROVE",
                "risk_score": min(100, risk_score),
                "risk_factors": risk_factors,
                "ai_justification": justification
            }

        # Fallback default
        justification = f"FLAG_FOR_AUDIT: Standard review required for claim amount ${claim_amount:,.2f}."
        return {
            "status": "FLAG_FOR_AUDIT",
            "risk_score": min(100, risk_score),
            "risk_factors": risk_factors,
            "ai_justification": justification
        }

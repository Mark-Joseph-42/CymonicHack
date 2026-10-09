"""
Apex Logistics - Database Interface Module (SQLite)
Handles transactional database persistence for clients, claims, and decision state.
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from engine import ClaimDecisionEngine

DB_PATH = Path(__file__).parent / "apex_claims.db"


def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection configured with Row factory and Foreign Key enforcement."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Converts a SQLite Row into a standard dictionary."""
    return {key: row[key] for key in row.keys()} if row else {}


# -----------------------------------------------------------------------------
# CLIENT SERVICES
# -----------------------------------------------------------------------------
def get_all_clients() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT * FROM clients ORDER BY company_name ASC")
        return [row_to_dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def get_client_by_id(client_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT * FROM clients WHERE client_id = ?", (client_id,))
        row = cursor.fetchone()
        return row_to_dict(row) if row else None
    finally:
        conn.close()


def create_client(client_data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        client_id = client_data.get("client_id")
        company_name = client_data["company_name"]
        tier = client_data.get("tier", "STANDARD")
        contact_email = client_data.get("contact_email", f"info@{company_name.lower().replace(' ', '')}.com")
        account_status = client_data.get("account_status", "ACTIVE")

        conn.execute(
            """
            INSERT INTO clients (client_id, company_name, tier, refund_count_30d, account_status, contact_email)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (client_id, company_name, tier, account_status, contact_email)
        )
        conn.commit()
        return get_client_by_id(client_id)
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# ORDER / CLAIM SERVICES
# -----------------------------------------------------------------------------
def get_all_orders(
    status: Optional[str] = None,
    client_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        query = """
            SELECT 
                o.*, 
                c.company_name, 
                c.tier as client_tier, 
                c.refund_count_30d, 
                c.account_status
            FROM orders o
            JOIN clients c ON o.client_id = c.client_id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND o.claim_status = ?"
            params.append(status)

        if client_id:
            query += " AND o.client_id = ?"
            params.append(client_id)

        if search:
            query += " AND (o.tracking_number LIKE ? OR o.order_id LIKE ? OR c.company_name LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])

        query += " ORDER BY o.claim_submitted_at DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        return [row_to_dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        query = """
            SELECT 
                o.*, 
                c.company_name, 
                c.tier as client_tier, 
                c.refund_count_30d, 
                c.account_status,
                c.contact_email
            FROM orders o
            JOIN clients c ON o.client_id = c.client_id
            WHERE o.order_id = ?
        """
        cursor = conn.execute(query, (order_id,))
        row = cursor.fetchone()
        return row_to_dict(row) if row else None
    finally:
        conn.close()


def submit_claim(claim_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ingests claim payload, fetches client context, executes Decision Engine evaluation,
    persists order into database, updates client refund counters if auto-approved,
    and returns full saved claim record.
    """
    conn = get_db_connection()
    try:
        client_id = claim_payload.get("client_id")
        client = get_client_by_id(client_id)
        if not client:
            raise ValueError(f"Client with ID '{client_id}' not found.")

        order_id = claim_payload.get("order_id") or f"ORD-2026-{int(datetime.datetime.now().timestamp() * 1000) % 100000}"
        tracking_number = claim_payload.get("tracking_number") or f"APX-TRK-{int(datetime.datetime.now().timestamp() * 100) % 10000000}"
        declared_value = float(claim_payload.get("declared_value", 0.0))
        claim_amount = float(claim_payload.get("claim_amount", 0.0))
        delay_cause = claim_payload.get("delay_cause", "CARRIER_FAULT")

        # Execute decision engine evaluation
        eval_result = ClaimDecisionEngine.evaluate(client, {
            "declared_value": declared_value,
            "claim_amount": claim_amount,
            "delay_cause": delay_cause,
            "tracking_number": tracking_number
        })

        claim_status = eval_result["status"]
        ai_justification = eval_result["ai_justification"]
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            """
            INSERT INTO orders (
                order_id, tracking_number, client_id, declared_value, claim_amount,
                delay_cause, claim_status, ai_justification, claim_submitted_at, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id, tracking_number, client_id, declared_value, claim_amount,
                delay_cause, claim_status, ai_justification, now_str, now_str
            )
        )

        # Increment client rolling refund velocity if AUTO_APPROVE
        if claim_status == "AUTO_APPROVE":
            conn.execute(
                """
                UPDATE clients 
                SET refund_count_30d = refund_count_30d + 1, updated_at = ?
                WHERE client_id = ?
                """,
                (now_str, client_id)
            )

        conn.commit()
        return get_order_by_id(order_id)
    finally:
        conn.close()


def override_claim_decision(order_id: str, new_status: str, agent_note: str) -> Dict[str, Any]:
    """
    Allows human agent to override decision (e.g. approve a flagged claim).
    """
    if new_status not in ("AUTO_APPROVE", "FLAG_FOR_AUDIT", "REJECT"):
        raise ValueError("Invalid target claim_status.")

    conn = get_db_connection()
    try:
        order = get_order_by_id(order_id)
        if not order:
            raise ValueError(f"Order '{order_id}' not found.")

        old_status = order["claim_status"]
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updated_justification = (
            f"{order['ai_justification']} | [HUMAN AGENT OVERRIDE on {now_str}]: "
            f"Changed from '{old_status}' to '{new_status}'. Reason: {agent_note}"
        )

        conn.execute(
            """
            UPDATE orders
            SET claim_status = ?, ai_justification = ?, evaluated_at = ?, updated_at = ?
            WHERE order_id = ?
            """,
            (new_status, updated_justification, now_str, now_str, order_id)
        )

        # Manage client refund counter adjustment
        if old_status != "AUTO_APPROVE" and new_status == "AUTO_APPROVE":
            conn.execute(
                "UPDATE clients SET refund_count_30d = refund_count_30d + 1, updated_at = ? WHERE client_id = ?",
                (now_str, order["client_id"])
            )
        elif old_status == "AUTO_APPROVE" and new_status != "AUTO_APPROVE":
            conn.execute(
                "UPDATE clients SET refund_count_30d = MAX(0, refund_count_30d - 1), updated_at = ? WHERE client_id = ?",
                (now_str, order["client_id"])
            )

        conn.commit()
        return get_order_by_id(order_id)
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# DASHBOARD ANALYTICS & METRICS
# -----------------------------------------------------------------------------
def get_dashboard_analytics() -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        total_claims = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        auto_approved = conn.execute("SELECT COUNT(*) FROM orders WHERE claim_status = 'AUTO_APPROVE'").fetchone()[0]
        flagged_audit = conn.execute("SELECT COUNT(*) FROM orders WHERE claim_status = 'FLAG_FOR_AUDIT'").fetchone()[0]
        rejected = conn.execute("SELECT COUNT(*) FROM orders WHERE claim_status = 'REJECT'").fetchone()[0]

        total_refunded = conn.execute("SELECT SUM(claim_amount) FROM orders WHERE claim_status = 'AUTO_APPROVE'").fetchone()[0] or 0.0
        pending_audit_value = conn.execute("SELECT SUM(claim_amount) FROM orders WHERE claim_status = 'FLAG_FOR_AUDIT'").fetchone()[0] or 0.0

        carrier_fault_cnt = conn.execute("SELECT COUNT(*) FROM orders WHERE delay_cause = 'CARRIER_FAULT'").fetchone()[0]
        weather_cnt = conn.execute("SELECT COUNT(*) FROM orders WHERE delay_cause = 'WEATHER_FORCE_MAJEURE'").fetchone()[0]
        customs_cnt = conn.execute("SELECT COUNT(*) FROM orders WHERE delay_cause = 'CUSTOMS_HOLD'").fetchone()[0]

        auto_rate = round((auto_approved / total_claims * 100), 1) if total_claims > 0 else 0.0
        audit_rate = round((flagged_audit / total_claims * 100), 1) if total_claims > 0 else 0.0
        reject_rate = round((rejected / total_claims * 100), 1) if total_claims > 0 else 0.0

        # Estimate SLA processing time saved (assuming manual review takes 45 mins per claim)
        hours_saved = round((auto_approved * 45) / 60, 1)

        return {
            "total_claims": total_claims,
            "auto_approved_count": auto_approved,
            "flagged_audit_count": flagged_audit,
            "rejected_count": rejected,
            "auto_approval_rate_pct": auto_rate,
            "audit_rate_pct": audit_rate,
            "rejection_rate_pct": reject_rate,
            "total_refund_payout_usd": round(total_refunded, 2),
            "pending_audit_value_usd": round(pending_audit_value, 2),
            "sla_hours_saved": hours_saved,
            "delay_cause_breakdown": {
                "CARRIER_FAULT": carrier_fault_cnt,
                "WEATHER_FORCE_MAJEURE": weather_cnt,
                "CUSTOMS_HOLD": customs_cnt
            }
        }
    finally:
        conn.close()

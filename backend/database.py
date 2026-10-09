import sqlite3
from pathlib import Path
from typing import Optional, Any, List, Dict
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "apex_claims.db"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def ensure_database():
    """Ensure database exists and schema is loaded if empty."""
    if not DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            conn.commit()

class DatabaseManager:
    @staticmethod
    def get_client(client_id: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clients WHERE client_id = ?", (client_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_clients() -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clients ORDER BY client_id ASC")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def create_or_update_client(client_data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO clients (client_id, company_name, tier, refund_count_30d, account_status, contact_email)
                VALUES (:client_id, :company_name, :tier, :refund_count_30d, :account_status, :contact_email)
                ON CONFLICT(client_id) DO UPDATE SET
                    company_name = excluded.company_name,
                    tier = excluded.tier,
                    refund_count_30d = excluded.refund_count_30d,
                    account_status = excluded.account_status,
                    contact_email = excluded.contact_email,
                    updated_at = CURRENT_TIMESTAMP
                """,
                client_data,
            )
            cursor.execute("SELECT * FROM clients WHERE client_id = ?", (client_data["client_id"],))
            return dict(cursor.fetchone())

    @staticmethod
    def increment_refund_count(client_id: str):
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE clients SET refund_count_30d = refund_count_30d + 1, updated_at = CURRENT_TIMESTAMP WHERE client_id = ?",
                (client_id,),
            )

    @staticmethod
    def get_order(order_id: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_order_by_tracking(tracking_number: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE tracking_number = ?", (tracking_number,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_orders(status: Optional[str] = None, client_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        query = "SELECT * FROM orders"
        params: List[Any] = []
        conditions = []

        if status:
            conditions.append("claim_status = ?")
            params.append(status)
        if client_id:
            conditions.append("client_id = ?")
            params.append(client_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY claim_submitted_at DESC LIMIT ?"
        params.append(limit)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def insert_order_evaluation(
        order_id: str,
        tracking_number: str,
        client_id: str,
        declared_value: float,
        claim_amount: float,
        delay_cause: str,
        claim_status: str,
        ai_justification: str,
    ) -> Dict[str, Any]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO orders (
                    order_id, tracking_number, client_id, declared_value,
                    claim_amount, delay_cause, claim_status, ai_justification,
                    claim_submitted_at, evaluated_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    order_id,
                    tracking_number,
                    client_id,
                    declared_value,
                    claim_amount,
                    delay_cause,
                    claim_status,
                    ai_justification,
                ),
            )
            cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            return dict(cursor.fetchone())

    @staticmethod
    def update_order_status(order_id: str, new_status: str, audit_notes: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE orders
                SET claim_status = ?,
                    ai_justification = COALESCE(ai_justification, '') || char(10) || '[AUDIT UPDATE]: ' || ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE order_id = ?
                """,
                (new_status, audit_notes, order_id),
            )
            cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_metrics() -> Dict[str, Any]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_claims,
                    SUM(CASE WHEN claim_status = 'AUTO_APPROVE' THEN 1 ELSE 0 END) as auto_approve_count,
                    SUM(CASE WHEN claim_status = 'FLAG_FOR_AUDIT' THEN 1 ELSE 0 END) as flagged_for_audit_count,
                    SUM(CASE WHEN claim_status = 'REJECT' THEN 1 ELSE 0 END) as reject_count,
                    COALESCE(SUM(claim_amount), 0.0) as total_claimed_value,
                    COALESCE(SUM(CASE WHEN claim_status = 'AUTO_APPROVE' THEN claim_amount ELSE 0 END), 0.0) as auto_approved_value,
                    COALESCE(AVG(claim_amount), 0.0) as average_claim_amount
                FROM orders
                """
            )
            stats = dict(cursor.fetchone())
            total = stats["total_claims"]
            auto_app = stats["auto_approve_count"] or 0
            stats["sla_compliance_rate"] = round((auto_app / total * 100), 2) if total > 0 else 100.0
            return stats

"""
Apex Logistics - Decision Engine Unit & Integration Tests
"""

import unittest
import os
import sqlite3
from pathlib import Path
import database
from engine import ClaimDecisionEngine


class TestApexDecisionEngine(unittest.TestCase):

    def setUp(self):
        """Re-initialize DB before running tests."""
        from init_db import init_database
        init_database()

    def test_auto_approve_enterprise_vip(self):
        """VIP Client + Carrier Fault + $1,450 <= $2,500 threshold -> AUTO_APPROVE"""
        client = database.get_client_by_id("CL-1001")
        payload = {
            "claim_amount": 1450.00,
            "declared_value": 12500.00,
            "delay_cause": "CARRIER_FAULT",
            "tracking_number": "TEST-TRK-001"
        }
        res = ClaimDecisionEngine.evaluate(client, payload)
        self.assertEqual(res["status"], "AUTO_APPROVE")
        self.assertIn("AUTO_APPROVE", res["ai_justification"])

    def test_auto_approve_standard_client(self):
        """Standard Client + Carrier Fault + $620 <= $2,500 threshold -> AUTO_APPROVE"""
        client = database.get_client_by_id("CL-1004")
        payload = {
            "claim_amount": 620.00,
            "declared_value": 4200.00,
            "delay_cause": "CARRIER_FAULT",
            "tracking_number": "TEST-TRK-002"
        }
        res = ClaimDecisionEngine.evaluate(client, payload)
        self.assertEqual(res["status"], "AUTO_APPROVE")

    def test_flag_for_audit_high_value(self):
        """VIP Client + Carrier Fault + $6,800 > $2,500 threshold -> FLAG_FOR_AUDIT"""
        client = database.get_client_by_id("CL-1002")
        payload = {
            "claim_amount": 6800.00,
            "declared_value": 48000.00,
            "delay_cause": "CARRIER_FAULT",
            "tracking_number": "TEST-TRK-003"
        }
        res = ClaimDecisionEngine.evaluate(client, payload)
        self.assertEqual(res["status"], "FLAG_FOR_AUDIT")
        self.assertIn("exceeds", res["ai_justification"].lower())

    def test_flag_for_audit_velocity(self):
        """VIP Client with 7 refunds (high velocity) + Customs Hold -> FLAG_FOR_AUDIT"""
        client = database.get_client_by_id("CL-1003")
        payload = {
            "claim_amount": 2100.00,
            "declared_value": 9500.00,
            "delay_cause": "CUSTOMS_HOLD",
            "tracking_number": "TEST-TRK-004"
        }
        res = ClaimDecisionEngine.evaluate(client, payload)
        self.assertEqual(res["status"], "FLAG_FOR_AUDIT")

    def test_reject_weather_force_majeure(self):
        """Standard Client + Weather / Force Majeure -> REJECT"""
        client = database.get_client_by_id("CL-1005")
        payload = {
            "claim_amount": 3400.00,
            "declared_value": 18000.00,
            "delay_cause": "WEATHER_FORCE_MAJEURE",
            "tracking_number": "TEST-TRK-005"
        }
        res = ClaimDecisionEngine.evaluate(client, payload)
        self.assertEqual(res["status"], "REJECT")
        self.assertIn("WEATHER_FORCE_MAJEURE", res["ai_justification"])

    def test_submit_claim_integration(self):
        """Integration test for database submission endpoint."""
        claim_data = {
            "client_id": "CL-1001",
            "declared_value": 10000.00,
            "claim_amount": 1200.00,
            "delay_cause": "CARRIER_FAULT",
            "tracking_number": "TEST-TRK-INT-001"
        }
        saved_order = database.submit_claim(claim_data)
        self.assertIsNotNone(saved_order)
        self.assertEqual(saved_order["claim_status"], "AUTO_APPROVE")
        self.assertEqual(saved_order["client_id"], "CL-1001")

    def test_override_decision_integration(self):
        """Integration test for human agent override."""
        order_id = "ORD-2026-8003"  # Initially FLAG_FOR_AUDIT
        updated = database.override_claim_decision(order_id, "AUTO_APPROVE", "Manager verified damaged items manifest.")
        self.assertEqual(updated["claim_status"], "AUTO_APPROVE")
        self.assertIn("HUMAN AGENT OVERRIDE", updated["ai_justification"])


if __name__ == "__main__":
    unittest.main()

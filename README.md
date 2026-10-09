# Apex Logistics - B2B Freight Claim & Refund Decision Engine

An automated decision engine for processing B2B cargo shipment refund claims, resolving backlog bottlenecks, and upholding strict enterprise client SLAs.

---

## 📌 Problem & Business Context
Apex Logistics handles 15,000+ daily cargo shipments. Weather disruptions, customs clearance holds, and transit damages trigger thousands of refund claims weekly. Manual review resulted in a 4-day processing backlog and SLA penalties.

This decision engine automates evaluations into:
- **`AUTO_APPROVE`**: Low-risk claims within threshold and carrier liability.
- **`FLAG_FOR_AUDIT`**: High-value claims or anomaly signals (e.g., high 30-day velocity, complex customs holds) requiring human sign-off.
- **`REJECT`**: Non-qualifying events (e.g., Force Majeure / weather exemptions under carriage terms).

---

## 🗄️ Database Architecture (`schema.sql`)

### Tables
1. **`clients`**:
   - `client_id` (TEXT PRIMARY KEY)
   - `company_name` (TEXT NOT NULL)
   - `tier` (`ENTERPRISE_VIP` | `STANDARD`)
   - `refund_count_30d` (INTEGER) - Rolling 30-day claim velocity
   - `account_status`, `contact_email`, `created_at`, `updated_at`

2. **`orders`**:
   - `order_id` (TEXT PRIMARY KEY)
   - `tracking_number` (TEXT UNIQUE)
   - `client_id` (FOREIGN KEY -> `clients.client_id`)
   - `declared_value`, `claim_amount` (REAL)
   - `delay_cause` (`CARRIER_FAULT` | `WEATHER_FORCE_MAJEURE` | `CUSTOMS_HOLD`)
   - `claim_status` (`AUTO_APPROVE` | `FLAG_FOR_AUDIT` | `REJECT`)
   - `ai_justification` (TEXT) - Machine reasoning chain explaining the verdict
   - Timestamps: `claim_submitted_at`, `evaluated_at`, `created_at`, `updated_at`

---

## 🚀 Quickstart

### 1. Initialize Database
Initialize the database using Python:
```bash
python3 init_db.py
```
Or via SQLite CLI (if installed):
```bash
sqlite3 apex_claims.db < schema.sql
```

### 2. Verify Schema & Seed Records
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('apex_claims.db')
print('Clients:', conn.execute('SELECT COUNT(*) FROM clients').fetchone()[0])
print('Orders/Claims:', conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0])
"
```

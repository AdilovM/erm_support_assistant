# PCI DSS v4.0 — Payment System Checklist

## Scope

This checklist applies to all system components that store, process, or transmit
cardholder data (CHD) or sensitive authentication data (SAD), plus all connected
system components.

In this system, the **Cardholder Data Environment (CDE)** includes:
- Payment API endpoints (`/api/v1/payments`)
- Payment service (`payment_service.py`)
- Gateway adapters (`stripe_gateway.py`, `authorize_net_gateway.py`)
- Transaction database table (`transactions`)
- UI payment forms (client-side tokenization)

---

## Data Classification

| Data Element | Storage Allowed | Must Protect | Our Approach |
|-------------|----------------|-------------|--------------|
| PAN (full card number) | NO | N/A — never store | Client-side tokenization only |
| Cardholder Name | Yes | Yes | Stored as `payer_name` |
| Expiration Date | Yes | Yes | NOT stored (gateway handles) |
| Service Code | No | N/A | Never received |
| CVV/CVC | NO (never after auth) | N/A | Never stored, never logged |
| PIN / PIN Block | NO | N/A | Never received |
| Card last 4 | Yes | No (not considered PAN) | Stored in `card_last_four` |

---

## Key Requirements for This System

### Tokenization Strategy (Requirement 3)

The system uses **client-side tokenization** to stay out of PCI scope for card
data handling:

1. Frontend collects card details via gateway-hosted iframe (Stripe Elements /
   Authorize.Net Accept.js)
2. Card data goes directly to the payment processor — never touches our servers
3. We receive only a `payment_method_token` — an opaque, non-reversible token
4. Token is used once to create a charge, then the `gateway_transaction_id` is
   stored for refunds/voids

**Grep patterns to detect violations:**
```
card_number, card_num, pan, full_card, cc_number
cvv, cvc, cvv2, card_verification, security_code
track_data, track1, track2, magnetic_stripe
pin_block, pin_number, card_pin
```

### Logging Safety (Requirement 3.3, 10.5)

Ensure these are NEVER logged:
- Full PAN
- CVV/CVC
- Full ACH account numbers
- Tokens (which could be reused)

Check all `logger.*` calls and print statements for sensitive data exposure.

### Network Security (Requirement 4)

- All API communication must use TLS 1.2+
- No HTTP endpoints (redirect HTTP to HTTPS in production)
- Gateway API calls must use HTTPS
- ERM integration calls must use HTTPS
- Webhook endpoints must validate signatures

### Access Control (Requirement 7, 8)

- Every API endpoint must require authentication (API key or JWT)
- API keys must be associated with specific entities
- Actions must be scoped to the authenticated entity
- Failed authentication attempts must be logged

### Audit Logging (Requirement 10)

Every audit log entry must contain:
- `id` — unique entry ID
- `transaction_id` — associated transaction (if applicable)
- `entity_id` — government entity
- `action` — what happened
- `actor` — who did it (user/API key ID)
- `ip_address` — origin
- `details` — action-specific data (JSON)
- `previous_state` — state before change
- `new_state` — state after change
- `created_at` — timestamp (UTC)

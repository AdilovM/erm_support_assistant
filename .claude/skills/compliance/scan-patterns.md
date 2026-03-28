# Compliance Scan Patterns

## Grep Patterns for Automated Detection

Use these patterns when scanning the codebase for compliance violations.

### PCI DSS — Cardholder Data Exposure

```
# Full card number storage/handling (should NEVER match)
card_number|card_num|cc_number|credit_card_number|pan_number

# CVV/security code (should NEVER be stored)
cvv|cvc|cvv2|cvc2|card_verification|security_code

# Raw card data (should NEVER exist server-side)
track_data|track1|track2|magnetic_stripe|swipe_data

# PIN data (should NEVER exist)
pin_block|card_pin|pin_number
```

**Expected matches**: Only in documentation, enums, or comments.
**Violation**: Any match in service code, models, or API handlers.

### Hardcoded Secrets

```
# API keys and secrets hardcoded
(api_key|secret_key|password|token)\s*=\s*["'][^"']{8,}["']

# Stripe keys hardcoded
sk_live_[a-zA-Z0-9]{20,}
pk_live_[a-zA-Z0-9]{20,}

# Generic secrets
(SECRET|PASSWORD|KEY|TOKEN)\s*=\s*["'][^"']+["']
```

**Expected matches**: Only in `.env.example` with placeholder values.
**Violation**: Any real key/secret in source code.

### SQL Injection

```
# Raw SQL string concatenation
f["'].*SELECT.*{
f["'].*INSERT.*{
f["'].*UPDATE.*{
f["'].*DELETE.*{
\.execute\(f["']
\.execute\(.*\+.*\)
\.execute\(.*%.*%.*\)
```

**Expected matches**: None — all queries should use SQLAlchemy ORM or parameterized queries.

### Sensitive Data in Logs

```
# Logging patterns that might expose PII/card data
logger\.\w+\(.*card
logger\.\w+\(.*payer
logger\.\w+\(.*account
logger\.\w+\(.*routing
print\(.*card
print\(.*token
print\(.*secret
```

### Missing Authentication

```
# API routes without auth dependency
@router\.(get|post|put|delete|patch)\(
# Should be followed by: api_key.*=.*Depends(verify_api_key)
```

### CORS Misconfiguration

```
# Wildcard CORS in production
allow_origins.*\*
AllowOrigin.*\*
Access-Control-Allow-Origin.*\*
```

### Insecure HTTP

```
# HTTP URLs (should be HTTPS in production)
http://(?!localhost|127\.0\.0|0\.0\.0)
```

---

## File-Level Checks

### Models (database.py)
- [ ] No column stores full PAN
- [ ] `card_last_four` is max 4 chars (`String(4)`)
- [ ] `ach_routing_number` stores partial only
- [ ] `ach_account_last_four` is max 4 chars
- [ ] Audit log table has no DELETE/UPDATE operations defined

### API Schemas (schemas.py)
- [ ] `card_last_four` has `max_length=4` validator
- [ ] `ach_account_last_four` has `max_length=4` validator
- [ ] `subtotal` has `gt=0` validator (prevents negative payments)
- [ ] `refund.amount` has `gt=0` validator
- [ ] Reason fields have `min_length=1` (required)

### Payment Service (payment_service.py)
- [ ] Uses tokenized payments only (`payment_method_token`)
- [ ] Refund amount validated against available balance
- [ ] Void window is enforced (configurable time limit)
- [ ] Refund window is enforced (configurable day limit)
- [ ] All state changes create audit log entries
- [ ] Actor is always recorded in audit logs

### Gateway Adapters
- [ ] Uses HTTPS for all API calls
- [ ] Does not log raw gateway responses containing card data
- [ ] Error handling does not expose internal gateway details to client
- [ ] Refunds reference original transaction ID (no new card details)

### UI Templates
- [ ] No card input fields (tokenization via gateway iframe)
- [ ] Fee amount shown separately before payment confirmation
- [ ] Status indicated by text + color (not color alone)
- [ ] All form fields have labels
- [ ] Keyboard navigation works for modals

### Configuration
- [ ] Secrets loaded from environment variables, not hardcoded
- [ ] Debug mode defaults to `False`
- [ ] JWT secret has a default that is clearly marked as needing change
- [ ] CORS is not wildcard in production

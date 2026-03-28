# Government Payment Regulations Reference

## Federal Regulations

### 31 CFR Part 206 — Management of Federal Agency Receipts
- Federal agencies must deposit receipts by the next business day
- Electronic payments must be processed and recorded same-day
- Daily settlement batches are required
- **System check**: Verify `SettlementBatch` model exists and daily batch processing is implemented

### 31 CFR Part 210 — Federal Government Participation in ACH
- Governs federal agency participation in ACH network
- Requires proper NACHA formatting for ACH transactions
- Return/reversal handling must follow ACH rules (R01-R85 return codes)
- **System check**: Verify ACH payment method is properly handled with routing/account masking

### OMB Circular A-123 — Management's Responsibility for Internal Controls
- Requires internal controls over financial reporting
- Transaction reconciliation must compare:
  - Internal transaction records vs. gateway settlement records
  - Identifies discrepancies automatically
- **System check**: Verify `reconciliation_report` exists in reporting service

### OMB Circular A-130 — Management of Federal Information Resources
- Requires protection of government information systems
- Security categorization of payment data as MODERATE or HIGH impact
- Requires access controls, audit logging, incident response procedures

### FISMA (Federal Information Security Modernization Act)
- Applies to federal agency systems
- Requires NIST 800-53 security controls
- Key controls for payment systems:
  - AC (Access Control)
  - AU (Audit and Accountability)
  - IA (Identification and Authentication)
  - SC (System and Communications Protection)

---

## State & County Regulations

### Uniform Commercial Code (UCC) Article 4A — Funds Transfers
- Governs electronic fund transfers (ACH/wire)
- Requires documented authorization from payer
- Sender must verify authenticity of payment orders
- **System check**: ACH payments should capture authorization evidence

### State Convenience Fee Rules

Government entities collecting convenience fees must comply with state law.
Common patterns:

| Rule | States (Examples) | Requirement |
|------|-------------------|-------------|
| Fee disclosure | All states | Fee must be disclosed before payment |
| Fee caps | Varies | Some states cap at $2, $3, or 2-3% |
| Fee type | Most states | Must be "convenience fee" not "surcharge" |
| Fee refund | Varies | Some require fee refund on full refund |
| Separate line item | Most states | Fee must be shown separately from payment |

**System checks**:
- `fee_amount` is a separate field from `subtotal` — GOOD
- `FeeSchedule` supports `max_fee` cap — GOOD
- API response includes `fee_amount` separately — verify
- UI shows fee as separate line item before confirmation — verify

### State Data Breach Notification Laws
- All 50 states have breach notification laws
- Government entities are NOT exempt
- Typical requirements:
  - Notify affected individuals within 30-60 days
  - Notify state attorney general
  - Provide credit monitoring for financial data breaches
- **System check**: Ensure PII is minimized and protected

### State Records Retention
- Government financial records typically must be retained:
  - 3 years minimum (most states)
  - 5 years (common for financial transactions)
  - 7 years (IRS recommendation for tax-related)
  - Permanent (some recording office documents)
- **System check**: No auto-deletion of transaction records

---

## County Recording Office Specific

### Recording Fee Regulations
- Recording fees are set by state statute, not the county
- Fees typically include:
  - Base recording fee (first page)
  - Per-page fee (additional pages)
  - Document type-specific fees (deed, mortgage, lien, etc.)
  - Special surcharges (housing trust fund, etc.)
- **System check**: `FeeSchedule` model supports `flat_amount` and can be configured per entity

### Recording Workflow
When integrated with Tyler Tech Recorder:
1. Clerk receives document for recording
2. System calculates recording fees + convenience fee
3. Payment is collected
4. Payment confirmation is sent to Tyler Tech
5. Tyler Tech proceeds with recording
6. Recording number is assigned

**Critical compliance point**: If payment is voided/refunded AFTER recording,
the recording may need to be reversed. The system must notify Tyler Tech of
voids/refunds so they can handle the recording side.

---

## Card Brand Rules for Government

### Visa Government Program
- Government agencies may charge convenience fees on credit card payments
- Fee must be a flat fee or fixed percentage
- Fee must be disclosed before the transaction
- Fee appears as a separate transaction or line item

### Mastercard Government Program
- Similar to Visa — convenience fees allowed for government
- Must be clearly disclosed as a "convenience fee"
- Cannot exceed the actual cost of accepting cards (in some programs)

### Refund Rules (All Brands)
- Refunds must go back to the original card used
- Refund cannot exceed original transaction amount
- Timeframe: typically within 120 days of original transaction
- **System check**: Refunds use `gateway_transaction_id` referencing original charge

---

## Compliance Documentation Requirements

Government payment systems should maintain:

1. **System Security Plan (SSP)** — documents security controls
2. **Privacy Impact Assessment (PIA)** — documents PII handling
3. **Authority to Operate (ATO)** — for federal systems
4. **Merchant agreements** — with payment processors
5. **Fee disclosure documentation** — published fee schedules
6. **Data retention policy** — how long records are kept
7. **Incident response plan** — for breaches and outages
8. **Change management log** — all system changes documented

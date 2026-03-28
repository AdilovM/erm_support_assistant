# Government Payment System

Payment processing system for federal, state, and county government entities. Designed for integration with ERM systems like Tyler Tech Recorder, Eagle, and Odyssey.

## Features

### Payment Processing
- **Multiple payment methods**: Credit/debit card, ACH/eCheck, cash, check, money order
- **Multi-gateway support**: Stripe, Authorize.Net (extensible to others)
- **Automatic fee calculation**: Configurable per entity and payment method (flat, percentage, or combined)
- **Tokenized payments**: PCI-compliant via client-side tokenization

### Void & Refund
- **Void**: Cancel authorized/captured transactions within a configurable window (default 24 hours)
- **Full refund**: Refund the entire transaction amount
- **Partial refund**: Issue multiple partial refunds up to the original amount
- **Fee refund**: Option to refund convenience fees proportionally
- **Refund window**: Configurable maximum days for refund eligibility (default 180 days)

### Reporting
- **Daily settlement**: Transaction totals, fees, refunds, and net settlement by entity
- **Transaction history**: Filtered search with date range, payment method, status
- **Reconciliation**: Compare captured payments vs refunds vs voids
- **Revenue by entity**: Cross-entity revenue breakdown
- **Audit trail**: Immutable log of all payment operations

### ERM Integration
- **Tyler Tech Recorder**: County recording offices (deeds, mortgages, liens)
- **Tyler Tech Eagle**: Assessor/recorder (property assessments, tax records)
- **Extensible adapter pattern**: Add new ERM systems by implementing the `ERMIntegration` interface

### Multi-Entity Support
- Federal agencies, state departments, counties, municipalities
- Per-entity gateway configuration
- Per-entity fee schedules
- Per-entity ERM system configuration

## Architecture

```
gov_pay/
├── api/                    # FastAPI REST API layer
│   ├── routes/             # Endpoint handlers
│   │   ├── payments.py     # Payment, void, refund endpoints
│   │   ├── entities.py     # Entity & fee schedule management
│   │   ├── reports.py      # Reporting endpoints
│   │   └── erm.py          # ERM integration endpoints
│   ├── schemas.py          # Pydantic request/response models
│   └── middleware/         # Auth, logging
├── domain/
│   ├── models/database.py  # SQLAlchemy models
│   └── enums/              # System enumerations
├── services/
│   ├── payment_service.py  # Core payment processing
│   ├── fee_service.py      # Fee calculation
│   └── reporting_service.py # Report generation
├── integrations/
│   ├── gateways/           # Payment gateway adapters
│   │   ├── base.py         # Abstract gateway interface
│   │   ├── stripe_gateway.py
│   │   ├── authorize_net_gateway.py
│   │   └── gateway_factory.py
│   └── erm/                # ERM system adapters
│       ├── base.py         # Abstract ERM interface
│       └── tyler_tech.py   # Tyler Tech Recorder & Eagle
├── config/
│   ├── settings.py         # Pydantic settings
│   └── database.py         # Async DB session
└── main.py                 # FastAPI application
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database and gateway credentials

# Run the application
uvicorn gov_pay.main:app --reload

# API docs available at
# http://localhost:8000/api/v1/docs
```

## API Endpoints

### Payments
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/payments` | Process a payment |
| POST | `/api/v1/payments/{id}/void` | Void a transaction |
| POST | `/api/v1/payments/{id}/refund` | Refund a transaction |
| GET | `/api/v1/payments/{id}` | Get transaction details |
| POST | `/api/v1/payments/search` | Search transactions |

### Entities
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/entities` | Register an entity |
| GET | `/api/v1/entities/{id}` | Get entity details |
| GET | `/api/v1/entities` | List entities |
| POST | `/api/v1/entities/fee-schedules` | Create fee schedule |
| GET | `/api/v1/entities/{id}/fee-schedules` | Get fee schedules |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/reports/daily-settlement` | Daily settlement report |
| POST | `/api/v1/reports/transaction-history` | Transaction history |
| POST | `/api/v1/reports/reconciliation` | Reconciliation report |
| POST | `/api/v1/reports/revenue-by-entity` | Revenue by entity |
| POST | `/api/v1/reports/audit-trail` | Audit trail |

### ERM
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/erm/documents/{entity_id}/{ref_id}` | Get ERM document |
| GET | `/api/v1/erm/health/{entity_id}` | Check ERM connectivity |

## Testing

```bash
pytest tests/ -v
```

## Docker

```bash
docker build -t gov-pay .
docker run -p 8000:8000 gov-pay
```

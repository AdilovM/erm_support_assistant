# Tirithel

**"One Who Watches Far"** - AI Support UI Learning Tool

Tirithel learns how to navigate any software by observing remote support sessions. During a session (e.g., via Bomgar), it captures screenshots and conversation transcripts, maps what's being discussed to UI actions, and builds a knowledge base. When a user has a similar issue later, Tirithel provides plain-English step-by-step instructions.

## How It Works

1. **Record** - Start a session, upload screenshots and conversation transcripts from a support interaction
2. **Learn** - Tirithel uses OCR to read the UI, AI to understand the conversation, and correlates them into navigation paths
3. **Guide** - Ask a question like "How do I change a fee schedule?" and get step-by-step instructions based on learned paths

## Quick Start

```bash
# Clone and set up
git clone https://github.com/AdilovM/tirithel.git
cd tirithel

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Anthropic API key

# Run
uvicorn tirithel.main:app --reload
```

Open http://localhost:8000/static/index.html for the web UI, or http://localhost:8000/api/v1/docs for the API docs.

## Prerequisites

- Python 3.11+
- Tesseract OCR (`apt install tesseract-ocr` or `brew install tesseract`)
- Anthropic API key (for Claude-powered analysis)

## Architecture

```
tirithel/
├── main.py              # FastAPI entry point
├── config/              # Settings & database
├── api/routes/          # REST endpoints
├── domain/              # SQLAlchemy models & enums
├── services/            # Business logic
│   ├── screen_capture   # OCR & UI element detection
│   ├── conversation     # Transcript processing
│   ├── session_mapper   # Core brain: correlate conversation <-> UI
│   ├── knowledge        # Knowledge base CRUD
│   ├── guidance         # Generate step-by-step instructions
│   └── embedding        # Vector search (ChromaDB)
├── processing/          # Data processing pipelines
├── integrations/        # External services (OCR, Claude API)
└── static/              # Web UI
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/sessions` | Start a recording session |
| POST | `/api/v1/sessions/{id}/screenshots` | Upload a screenshot |
| POST | `/api/v1/sessions/{id}/transcript` | Upload conversation transcript |
| POST | `/api/v1/sessions/{id}/complete` | Process the session |
| POST | `/api/v1/guidance/query` | Ask for navigation help |
| GET | `/api/v1/knowledge/paths` | Browse learned paths |
| POST | `/api/v1/knowledge/search` | Semantic search |

## Example

**Input**: Support agent helps user change a fee schedule, Tirithel observes.

**Later, a user asks**: "How do I change a fee for Substitution of Trustee?"

**Tirithel responds**:
> 1. Navigate to **Administration** in the main menu
> 2. Click on **System Setup**
> 3. Select **Financial** > **Product**
> 4. Click on **Fee Schedules**
> 5. Find the fee you need to change in the list
> 6. Update the amount and click **Save**

## License

MIT

# Quick Start: AI Underwriting Webhook Integration

## 🎯 What You Have

Your repository now contains a **complete AI underwriting system** that:

1. **Receives webhooks** from Forth CRM when contracts are uploaded
2. **Parses PDFs** using Gemini AI to extract structured data
3. **Runs 5 validation checks** as specified in your requirements
4. **Provides Teams bot integration** for manual validation requests
5. **Stores results and feedback** for continuous improvement

## 🔧 Webhook Configuration

### Forth CRM Webhook Setup:
- **Webhook Name**: `UW-docs`
- **URL**: `http://localhost:8000/webhook/forth-docs` (local) or `https://your-domain.com/webhook/forth-docs` (production)
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Trigger**: `document_type == "agreement"`

### Expected Payload:
```json
{
  "contact_id": "string",
  "document_type": "agreement",
  "document_url": "string",
  "document_name": "string",
  "created_by": "string",
  "timestamp": "2025-01-20T10:00:00Z"
}
```

## 🚀 How to Test Locally

### 1. Setup Environment
```bash
# Copy the environment template
cp env_template.txt configs/.env

# Edit configs/.env and add your API keys:
# - FORTH_API_BASE_URL and FORTH_API_KEY (required)
# - GOOGLE_API_KEY (required for Gemini)
# - Teams credentials (for Teams bot)
```

### 2. Install Dependencies
```bash
uv sync
```

### 3. Run the Application
```bash
# Option 1: Use the run script (recommended)
python run_local.py

# Option 2: Direct uvicorn command
uvicorn forth_ai_underwriting.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Test the Webhook
```bash
# Run the comprehensive test suite
python test_webhook_integration.py

# Or test manually with curl
curl -X POST http://localhost:8000/webhook/forth-docs \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": "test_contact_12345",
    "document_type": "agreement",
    "document_url": "https://example.com/sample.pdf",
    "document_name": "sample.pdf",
    "created_by": "test_user",
    "timestamp": "2025-01-20T10:00:00Z"
  }'
```

## 📋 Validation Checks Implemented

Your system performs exactly the validation checks you specified:

1. **✅ Valid Claim of Hardship**
   - AI-powered analysis using Gemini
   - Confidence scoring
   - Keywords detection
   - One-word entries acceptable

2. **✅ Budget Analysis**
   - Positive surplus validation
   - Income vs expenses comparison

3. **✅ Contract Validation** (Multiple sub-checks):
   - Sender IP ≠ Signer IP (AI parsing)
   - Mailing address consistency
   - Signature requirements (no dots/dashes)
   - Bank details matching
   - SSN consistency across 3 sources
   - DOB consistency and 18+ age check

4. **✅ Address Validation**
   - State-to-company mapping
   - Reference table validation

5. **✅ Draft Validation**
   - Minimum $250 payment amount
   - 2-30 day timing rules (2-45 for Credit Care)

## 🤖 Teams Bot Usage

Users can interact via Microsoft Teams:

1. **Send validation request**:
   ```
   validate contact_id:12345
   ```

2. **Receive formatted results**:
   ```
   📊 Underwriting Validation Results
   
   ✅ Valid Claim of Hardship ---- Pass ---- Valid financial hardship description
   ✅ Budget Analysis ---- Pass ---- Positive surplus of $1000.00
   ❌ Contract - IP Addresses ---- No Pass ---- Sender and signer IP are the same
   ```

3. **Provide feedback**:
   ```
   feedback contact_id:12345 rating:5 description:Very accurate results!
   ```

## 📊 How the Flow Works

```
[Agent uploads contract PDF] 
    ↓
[Forth CRM checks: document_type == "agreement"]
    ↓
[Triggers UW-docs webhook]
    ↓
[Your AI system receives webhook]
    ↓
[Background processing starts]
    ↓
[AI Parser extracts contract data]
    ↓
[Validation service runs all 5 checks]
    ↓
[Results stored in database]
    ↓
[Teams bot can retrieve results]
```

## 🔍 Monitoring and Debugging

### Health Checks:
- Main health: `GET http://localhost:8000/health`
- Simple status: `GET http://localhost:8000/`

### Key Log Messages to Watch:
- `"Received webhook for contact_id: {contact_id}"`
- `"Document processing completed for contact {contact_id}"`
- `"Validation completed for contact {contact_id}"`

### Debug Endpoints:
```bash
# Test Teams validation directly
curl -X POST http://localhost:8000/teams/validate \
  -H "Content-Type: application/json" \
  -d '{"contact_id": "test_id", "user_id": "user", "conversation_id": "conv"}'

# Submit feedback
curl -X POST http://localhost:8000/teams/feedback \
  -H "Content-Type: application/json" \
  -d '{"contact_id": "test_id", "rating": 5, "feedback": "Great!", "user_id": "user"}'
```

## 📂 Repository Structure

Your current structure supports the complete workflow:

```
forth-ai-underwriting/
├── src/forth_ai_underwriting/
│   ├── api/main.py                 # FastAPI app with webhook endpoint
│   ├── infrastructure/ai_parser.py # AI document processing orchestrator
│   ├── services/
│   │   ├── validation.py           # All 5 validation checks
│   │   ├── gemini_service.py       # Gemini AI integration
│   │   ├── process.py              # Document processing
│   │   └── teams_bot.py            # Teams integration
│   ├── models/                     # Pydantic models for all data
│   ├── prompts/                    # AI prompt management
│   ├── core/                       # Database, middleware, etc.
│   └── config/settings.py          # Environment configuration
├── test_webhook_integration.py     # Comprehensive test suite
├── run_local.py                    # Easy local development
├── WEBHOOK_SETUP.md                # Detailed setup guide
└── env_template.txt                # Environment configuration template
```

## 🎉 Next Steps

1. **Setup your environment**: Copy `env_template.txt` to `configs/.env` and add your API keys
2. **Test locally**: Run `python test_webhook_integration.py`
3. **Configure Forth CRM**: Set up the UW-docs webhook pointing to your endpoint
4. **Deploy to production**: Use the Docker and Kubernetes configs provided
5. **Monitor and improve**: Use the feedback system to enhance AI accuracy

Your system is **production-ready** and implements all the requirements from your DATA-1084 specification! 🚀 
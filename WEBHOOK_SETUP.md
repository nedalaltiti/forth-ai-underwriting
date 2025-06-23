# Webhook Setup Guide for Forth AI Underwriting

## Overview

This guide explains how to configure the webhook integration between Forth CRM and the AI Underwriting system.

## Webhook Configuration

### 1. Forth CRM Webhook Setup

Configure the following webhook in your Forth CRM system:

**Webhook Details:**
- **Name**: `UW-docs`
- **URL**: 
  - **Production**: `https://your-domain.com/webhook/forth-docs`
  - **Local Development**: `http://localhost:8000/webhook/forth-docs`
- **HTTP Method**: `POST`
- **Content-Type**: `application/json`
- **Trigger Condition**: `document_type == "agreement"`

### 2. Payload Structure

The webhook should send the following JSON payload:

```json
{
  "contact_id": "string",
  "document_type": "agreement",
  "document_url": "string",
  "document_name": "string", 
  "created_by": "string",
  "timestamp": "ISO datetime string",
  "additional_data": {
    "file_size": "number",
    "upload_source": "string"
  }
}
```

### 3. Environment Configuration

Ensure your `.env` file contains:

```env
# Webhook Configuration
WEBHOOK_ENDPOINT=/webhook/forth-docs
WEBHOOK_TIMEOUT=30
FORTH_WEBHOOK_SECRET=your_webhook_secret_here

# Forth API Configuration  
FORTH_API_BASE_URL=https://your-forth-api.com
FORTH_API_KEY=your_api_key_here
FORTH_API_TIMEOUT=30

# Gemini AI Configuration
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL_NAME=gemini-2.0-flash-001
GEMINI_TEMPERATURE=0.0

# Database Configuration (PostgreSQL required)
DATABASE_URL=postgresql://forth_user:forth_password@localhost:5432/forth_underwriting_dev

# Teams Configuration
MICROSOFT_APP_ID=your_teams_app_id
MICROSOFT_APP_PASSWORD=your_teams_app_password
TENANT_ID=your_tenant_id
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
```

## How It Works

### 1. Document Upload Flow

```mermaid
graph LR
    A[Agent uploads PDF] --> B[Forth CRM]
    B --> C{document_type == 'agreement'?}
    C -->|Yes| D[Trigger UW-docs webhook]
    C -->|No| E[No action]
    D --> F[AI Underwriting System]
    F --> G[Process contract]
    G --> H[Run validations]
    H --> I[Store results]
```

### 2. Validation Checks

The system performs these validation checks:

1. **Valid Claim of Hardship** - AI analysis with confidence score
2. **Budget Analysis** - Positive surplus check
3. **Contract Validation** - Multiple sub-checks:
   - IP address validation (sender ≠ signer)
   - Mailing address consistency 
   - Signature requirements
   - Bank details matching
   - SSN consistency across sources
   - DOB consistency and age verification
4. **Address Validation** - State-to-company mapping
5. **Draft Validation** - Payment amount and timing rules

### 3. Teams Bot Integration

Users can interact via Microsoft Teams:
- Send contact ID to get validation results
- Receive formatted validation summary
- Provide feedback (1-5 stars + description)

## Testing

### Local Testing

1. **Start the application:**
   ```bash
   python test_webhook_integration.py
   ```

2. **Manual webhook simulation:**
   ```bash
   python test_webhook_integration.py --simulate
   ```

3. **Manual curl test:**
   ```bash
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

### Production Testing

1. Upload a contract PDF in Forth CRM with document type "agreement"
2. Check logs for webhook trigger
3. Verify processing in the system
4. Test Teams bot functionality

## Monitoring

### Health Checks

- **Main Health**: `GET /health`
- **Simple Status**: `GET /`

### Logs

Monitor these key log messages:
- `"Received webhook for contact_id: {contact_id}"`
- `"Document processing completed for contact {contact_id}"`
- `"Validation completed for contact {contact_id}"`

### Metrics

The system tracks:
- Webhook processing time
- Validation success rates
- API response times
- Error rates by component

## Troubleshooting

### Common Issues

1. **Webhook not triggering:**
   - Check Forth CRM webhook configuration
   - Verify URL accessibility
   - Check document_type filter

2. **Document processing fails:**
   - Verify document URL accessibility
   - Check AI service API keys
   - Monitor processing logs

3. **Validation errors:**
   - Check Forth API connectivity
   - Verify reference data is loaded
   - Review validation logic

### Debug Commands

```bash
# Check service health
curl http://localhost:8000/health

# Test Teams validation directly
curl -X POST http://localhost:8000/teams/validate \
  -H "Content-Type: application/json" \
  -d '{"contact_id": "test_id", "user_id": "test_user", "conversation_id": "test_conv"}'

# Check logs
tail -f logs/app.log
```

## Security Considerations

1. **Webhook Authentication**: Use `FORTH_WEBHOOK_SECRET` for signature verification
2. **API Rate Limiting**: Configured per endpoint
3. **Data Encryption**: All sensitive data encrypted in transit
4. **Access Control**: Teams bot requires proper authentication

## Next Steps

1. Configure production webhook in Forth CRM
2. Set up monitoring and alerting
3. Train teams on bot usage
4. Monitor validation accuracy and adjust AI prompts as needed 
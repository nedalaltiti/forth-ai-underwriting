# Forth AI Underwriting - Microservices Architecture

## 🏗️ **True Microservices Implementation**

This directory contains the refactored microservices architecture following industry best practices from [microservices organization structure](https://github.com/aydabd/microservice-app-structure) and [component separation guidelines](https://github.com/goldbergyoni/nodebestpractices/blob/master/sections/projectstructre/breakintcomponents.md).

## 📁 **Architecture Structure**

```
services/
├── webhook-service/          # Webhook ingestion microservice
│   ├── src/
│   │   ├── main.py          # FastAPI webhook endpoints
│   │   ├── webhook_processor.py  # Business logic
│   │   └── models.py        # Service-specific models
│   ├── config/
│   │   └── settings.py      # Service-specific configuration
│   ├── Dockerfile
│   └── requirements.txt     # Minimal dependencies
│
├── document-service/         # Document processing microservice
│   ├── src/
│   │   ├── main.py          # Service main entry point
│   │   ├── document_processor.py  # Document business logic
│   │   └── models.py        # Service-specific models
│   ├── config/
│   │   └── settings.py      # Service-specific configuration
│   ├── Dockerfile
│   └── requirements.txt     # Document processing dependencies
│
├── validation-service/       # AI validation microservice
│   ├── src/
│   │   ├── main.py          # FastAPI validation endpoints
│   │   ├── validation_processor.py  # AI validation logic
│   │   └── models.py        # Service-specific models
│   ├── config/
│   │   └── settings.py      # Service-specific configuration
│   ├── data/                # Validation reference data
│   ├── Dockerfile
│   └── requirements.txt     # AI/ML dependencies
│
├── shared-libs/              # Minimal common utilities
│   ├── models/
│   │   └── common.py        # Shared data models
│   ├── utils/
│   │   └── logging.py       # Shared logging utilities
│   └── infrastructure/
│       └── queue.py         # Queue abstraction
│
└── docker-compose.yml       # Service orchestration
```

## 🎯 **Domain Boundaries**

### **Webhook Service** (Port 8000)
**Domain**: Webhook ingestion and message queuing
- **Responsibility**: Receive webhooks, validate payloads, queue messages
- **Dependencies**: SQS, minimal FastAPI
- **Data**: Webhook payloads, queue messages

### **Document Service** (Background)
**Domain**: Document lifecycle management
- **Responsibility**: Download, process, and store documents
- **Dependencies**: SQS, S3, Forth API
- **Data**: Document metadata, file storage

### **Validation Service** (Port 8001)
**Domain**: AI-powered underwriting validation
- **Responsibility**: Validate hardship, contracts, business rules
- **Dependencies**: Gemini AI, validation rules
- **Data**: Validation results, AI assessments

## 🚀 **Deployment**

### **Individual Service Deployment**
```bash
# Deploy specific service
cd services/webhook-service
docker build -t webhook-service .
docker run -p 8000:8000 --env-file .env webhook-service

# Deploy document service
cd services/document-service
docker build -t document-service .
docker run --env-file .env document-service

# Deploy validation service
cd services/validation-service
docker build -t validation-service .
docker run -p 8001:8001 --env-file .env validation-service
```

### **Complete Stack Deployment**
```bash
cd services/
docker-compose up -d
```

## 🔧 **Configuration**

Each service manages its own configuration:

```bash
# Webhook Service Environment
WEBHOOK_QUEUE_NAME=uw-contracts-parser-dev-sqs
WEBHOOK_AWS_REGION=us-west-1
WEBHOOK_LOG_LEVEL=INFO

# Document Service Environment
DOCUMENT_QUEUE_NAME=uw-contracts-parser-dev-sqs
DOCUMENT_S3_BUCKET=contact-contracts-dev-s3-us-west-1
DOCUMENT_MAX_CONCURRENT_DOWNLOADS=3

# Validation Service Environment
VALIDATION_GEMINI_API_KEY=your_gemini_key
VALIDATION_FORTH_API_BASE_URL=https://api.forthcrm.com/v1
VALIDATION_LOG_LEVEL=INFO
```

## ✅ **Microservices Best Practices Implemented**

### **1. Domain-Driven Design**
- ✅ Clear business boundaries (webhook, document, validation)
- ✅ Single responsibility per service
- ✅ Domain-specific models and logic

### **2. Service Independence**
- ✅ Separate configuration per service
- ✅ Minimal shared dependencies
- ✅ Independent deployment and scaling
- ✅ Database-per-service pattern (each owns its data)

### **3. Communication Patterns**
- ✅ Asynchronous messaging via SQS
- ✅ API-based communication for validation service
- ✅ Event-driven architecture ready

### **4. Operational Excellence**
- ✅ Service-specific health checks
- ✅ Individual metrics and monitoring
- ✅ Container-based deployment
- ✅ Non-root user security

## 📊 **Service Communication Flow**

```
External → Webhook Service → SQS → Document Service → S3
                ↓
         Validation Service ← API Call ← Document Service
```

## 🔍 **Health Monitoring**

```bash
# Check individual service health
curl http://localhost:8000/health  # Webhook Service
curl http://localhost:8001/health  # Validation Service

# Document service health (background service)
docker logs document-service
```

## 🎯 **Benefits Achieved**

1. **True Microservices**: Each service has distinct business responsibility
2. **Independent Scaling**: Scale validation service differently from webhook service
3. **Technology Diversity**: Different services can use different tech stacks
4. **Fault Isolation**: One service failure doesn't impact others
5. **Team Autonomy**: Different teams can own different services
6. **Deployment Independence**: Deploy services separately

This architecture transforms your previous "distributed monolith" into true microservices following 2025 best practices!

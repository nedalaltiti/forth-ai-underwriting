# Forth AI Underwriting System - Architecture Documentation

## Overview

The Forth AI Underwriting System is a modular, scalable, and production-ready application that provides AI-powered underwriting validation for debt settlement programs. The system follows modern software engineering best practices with clean architecture, proper separation of concerns, and comprehensive error handling.

## System Architecture

### Core Principles

1. **Modularity**: Each component has a single responsibility and clear interfaces
2. **Scalability**: Services can be scaled independently and run in distributed environments
3. **Maintainability**: Clean code, proper documentation, and comprehensive testing
4. **Reliability**: Robust error handling, fallback mechanisms, and monitoring
5. **Security**: Proper authentication, authorization, and data protection

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                     │
├─────────────────────────────────────────────────────────────┤
│                 Service Layer (Business Logic)             │
├─────────────────────────────────────────────────────────────┤
│              Infrastructure Layer (AI/External APIs)       │
├─────────────────────────────────────────────────────────────┤
│                   Data Layer (Database/Cache)              │
└─────────────────────────────────────────────────────────────┘
```

## Component Overview

### 1. API Layer (`src/forth_ai_underwriting/api/`)

**Purpose**: Handles HTTP requests and responses, provides REST API endpoints

**Key Components**:
- `main.py`: FastAPI application with endpoint definitions
- Middleware for security, logging, and error handling
- Request/response models with Pydantic validation

**Endpoints**:
- `POST /webhook/forth-docs`: Receives document upload notifications
- `POST /teams/validate`: Teams bot validation requests
- `POST /teams/feedback`: User feedback collection
- `GET /health`: System health checks

### 2. Service Layer (`src/forth_ai_underwriting/services/`)

**Purpose**: Contains business logic and orchestrates operations

**Key Services**:

#### ValidationService (`validation.py`)
- Orchestrates all validation checks
- Modular validation components (IP, addresses, signatures, etc.)
- Uses AI services for hardship assessment
- Fallback mechanisms when AI services fail

#### GeminiService (`gemini_service.py`)
- Specialized Gemini AI integration
- Uses centralized prompt management
- Handles contract parsing, hardship assessment, budget analysis
- Clean interface abstracting AI complexities

#### LLMService (`llm_service.py`)
- Unified interface for multiple AI providers
- Provider fallback logic (Gemini → OpenAI)
- Standardized request/response formats
- Circuit breaker pattern for resilience

#### DocumentProcessor (`process.py`)
- Multi-method PDF extraction (PyMuPDF, PyPDF2, LangChain)
- Quality assessment and best extraction selection
- Document validation and metadata extraction
- Async processing support

### 3. Infrastructure Layer (`src/forth_ai_underwriting/infrastructure/`)

**Purpose**: Handles external integrations and low-level operations

#### AIParserService (`ai_parser.py`)
- Orchestrates the complete document processing pipeline
- Delegates to specialized services
- Provides fallback data structures
- Clean integration point for document analysis

### 4. Prompt Management (`src/forth_ai_underwriting/prompts/`)

**Purpose**: Centralized prompt template management with versioning

**Key Components**:
- `prompt_manager.py`: Core prompt management system
- `contract_prompts.py`: Contract parsing prompts
- `hardship_prompts.py`: Hardship assessment prompts
- `validation_prompts.py`: Budget and debt validation prompts

**Features**:
- Template versioning for A/B testing
- Variable validation and rendering
- Output schema validation
- Prompt categorization and organization

### 5. Data Models (`src/forth_ai_underwriting/models/`)

**Purpose**: Pydantic data models with comprehensive validation

**Key Models**:
- `base_models.py`: Core validation patterns and base classes
- `contract_models.py`: Contract data with business rule validation
- `hardship_models.py`: Hardship assessment with confidence scoring
- `validation_models.py`: Budget analysis and debt validation
- `client_models.py`: Client profiles and contact information

### 6. Core Infrastructure (`src/forth_ai_underwriting/core/`)

**Purpose**: Core system components and utilities

#### Service Registry (`service_registry.py`)
- Manages all service lifecycles
- Dependency injection and resolution
- Health monitoring across all services
- Graceful startup and shutdown

#### Database Layer (`database.py`, `models.py`)
- SQLAlchemy ORM with relationship management
- Connection pooling and optimization
- Database health monitoring

#### Exception Handling (`exceptions.py`)
- Custom exception hierarchy
- Proper HTTP status code mapping
- Structured error responses

#### Middleware (`middleware.py`)
- Request logging with unique IDs
- Security headers
- Rate limiting with Redis
- Exception handling and response formatting

### 7. Configuration Management (`src/forth_ai_underwriting/config/`)

**Purpose**: Environment-aware configuration with validation

#### Settings (`settings.py`)
- Pydantic-based configuration with validation
- Environment-specific settings (dev, staging, prod)
- Feature flags for easy toggling
- Comprehensive validation of all configuration values

### 8. Utilities (`src/forth_ai_underwriting/utils/`)

**Purpose**: Common utilities and helper functions

#### Retry Logic (`retry.py`)
- Exponential backoff retry mechanisms
- Circuit breaker pattern implementation
- API-specific retry configurations
- Async operation support

### 9. CLI Interface (`src/forth_ai_underwriting/cli/`)

**Purpose**: Command-line interface for administration

**Commands**:
- `server start`: Start the FastAPI server
- `services list/init/health`: Service management
- `db init/status`: Database operations
- `validate contact`: Manual validation
- `config show/validate`: Configuration management
- `monitoring health`: System health checks

## Data Flow

### 1. Document Processing Flow

```
Document Upload → Webhook → Background Task → AI Parser → Document Processor
                                                    ↓
Contract Data ← Gemini Service ← Prompt Manager ← LLM Service
       ↓
Validation Service → Multiple Validators → Results Storage
```

### 2. Teams Bot Flow

```
Teams Request → API Endpoint → Validation Service → AI Services
                     ↓
Teams Response ← Result Formatter ← Validation Results
```

### 3. Validation Pipeline

```
Contact Data → Hardship AI → Budget Analysis → Contract Validation
                                                      ↓
Address Validation → Draft Validation → Results Aggregation
```

## AI Integration

### Prompt Management System

The system uses a centralized prompt management approach:

1. **Template Storage**: All prompts stored as versioned templates
2. **Variable Validation**: Ensures all required variables are provided
3. **Rendering Engine**: Safely renders templates with provided data
4. **Output Validation**: Validates AI responses against expected schemas

### AI Service Architecture

```
Application Code → LLM Service → Provider (Gemini/OpenAI) → AI API
                      ↓
                 Fallback Logic → Alternative Provider
                      ↓
                Circuit Breaker → Error Handling
```

## Database Design

### Core Tables

1. **contacts**: Client information and metadata
2. **validation_runs**: Validation execution records
3. **validation_results**: Individual validation check results
4. **documents**: Document metadata and parsing status
5. **user_feedback**: Teams bot feedback collection
6. **audit_logs**: System action audit trail
7. **validation_cache**: Performance optimization cache
8. **system_metrics**: Monitoring and performance data

### Relationships

- Contacts have many ValidationRuns
- ValidationRuns have many ValidationResults
- Contacts have many Documents
- ValidationRuns can have UserFeedback

## Security Considerations

### Authentication & Authorization
- API key-based authentication for Forth integration
- Teams bot authentication via Microsoft Graph API
- Environment-specific security configurations

### Data Protection
- Sensitive data masking in logs
- Secure credential management
- CORS configuration for API access
- Rate limiting to prevent abuse

### Input Validation
- Comprehensive Pydantic validation on all inputs
- SQL injection prevention via ORM
- File type and size validation for uploads

## Monitoring & Observability

### Health Checks
- Application-level health endpoints
- Service-specific health monitoring
- Database connectivity checks
- External API availability monitoring

### Logging
- Structured logging with unique request IDs
- Different log levels for different environments
- Audit logging for compliance

### Metrics
- Performance metrics collection
- Usage statistics
- Error rate monitoring
- System resource utilization

## Deployment

### Environment Support
- Development: Local with hot reload
- Staging: Container-based with test data
- Production: Kubernetes with full monitoring

### Configuration Management
- Environment variables for all settings
- Secrets management for sensitive data
- Feature flags for gradual rollouts

### Scalability
- Horizontal scaling via container orchestration
- Database connection pooling
- Async processing for background tasks
- Caching for frequently accessed data

## Development Workflow

### Code Quality
- Automated linting (ruff) and formatting (black)
- Type checking with mypy
- Pre-commit hooks for consistency
- Comprehensive test coverage

### Testing Strategy
- Unit tests for individual components
- Integration tests for service interactions
- End-to-end tests for complete workflows
- Performance tests for scalability validation

### Documentation
- Code-level documentation with docstrings
- API documentation via FastAPI/OpenAPI
- Architecture documentation (this file)
- Deployment guides and runbooks

## Future Enhancements

### Planned Features
1. Real-time validation updates via WebSockets
2. Machine learning model training pipelines
3. Advanced analytics and reporting
4. Multi-tenant support
5. Enhanced caching strategies

### Technical Improvements
1. GraphQL API for flexible data queries
2. Event-driven architecture with message queues
3. Advanced monitoring with distributed tracing
4. Automated scaling based on load
5. Enhanced security with OAuth2/OIDC

## Troubleshooting

### Common Issues
1. **Service Initialization Failures**: Check configuration and dependencies
2. **AI API Errors**: Verify API keys and rate limits
3. **Database Connection Issues**: Check connection string and network
4. **Document Processing Failures**: Verify file format and accessibility

### Debugging Tools
1. CLI health checks: `forth-underwriting monitoring health`
2. Service status: `forth-underwriting services health`
3. Configuration validation: `forth-underwriting config validate`
4. Database status: `forth-underwriting db status`

## Conclusion

The Forth AI Underwriting System provides a robust, scalable foundation for AI-powered underwriting validation. Its modular architecture, comprehensive error handling, and extensive monitoring capabilities make it suitable for production deployment while maintaining the flexibility needed for future enhancements.

The system's clean separation of concerns, centralized service management, and comprehensive testing ensure maintainability and reliability in production environments. 
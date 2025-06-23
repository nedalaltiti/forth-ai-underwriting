
## Project Structure

This project follows a well-defined, modern repository structure designed for AI/ML and software engineering best practices in 2025. The layout aims to promote modularity, scalability, and maintainability.

```
forth-ai-underwriting/
├── configs/                # Environment and app configs
├── docker/                 # Dockerfiles and Compose for local/dev/prod
├── docs/                   # Documentation and architecture decisions
├── k8s/                    # Kubernetes manifests (base/overlays)
├── model_registry/         # Model versioning and registry
├── notebooks/              # Jupyter notebooks (exploration, prototyping)
├── scripts/                # Automation scripts (seed, migrate, update)
├── src/
│   └── forth_ai_underwriting/
│       ├── api/            # FastAPI app and routers (main.py)
│       ├── cli/            # CLI entrypoints (e.g., for running validations manually)
│       ├── config/         # Pydantic settings and environment loader (settings.py)
│       ├── core/           # Core logic, schemas, errors (ValidationResult, base models)
│       ├── data/           # Data samples, fixtures (reference_tables.json)
│       ├── infrastructure/ # LLM providers, storage, messaging, tracking (ai_parser.py)
│       ├── models/         # ML, GenAI, agent models
│       ├── pipelines/      # Data/ML pipelines (ingest, preprocess, train, eval)
│       ├── prompts/        # Prompt templates and evaluators (for AI parsing)
│       ├── services/       # Service layer (ValidationService, TeamsBot)
│       ├── utils/          # Utilities (logging, retry, etc.)
│       └── version.py      # Version info
├── tests/                  # E2E and fixture tests
├── Makefile                # Common dev commands
├── pyproject.toml          # Python dependencies and metadata
├── bitbucket-pipelines.yml # CI/CD pipeline config
└── README.md               # This file
```

## Getting Started

### Prerequisites

- Python 3.11+
- `uv` (install with `pip install uv`)
- Docker (for containerized deployment)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd forth-ai-underwriting
    ```

2.  **Set up environment variables:**
    Copy the example environment file and fill in your details:
    ```bash
    cp configs/.env.example configs/.env
    # Open configs/.env and add your API keys and other configurations
    ```

3.  **Install dependencies:**
    ```bash
    uv sync
    ```

### Running the Application

To run the FastAPI application locally:

```bash
uv run python -m uvicorn forth_ai_underwriting.api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be accessible at `http://localhost:8000`.

### Running Tests

To run the unit and integration tests:

```bash
uv run pytest
```

## Core Components

### Webhook Endpoint

The FastAPI application exposes a webhook endpoint (configured via `WEBHOOK_ENDPOINT` in `.env`) that Forth Debt Resolution will call when a new contract PDF is uploaded. This endpoint initiates the document processing in a background task.

### AI-Powered Contract Parsing

The `infrastructure/ai_parser.py` module handles the extraction of structured data from contract documents. It is designed to leverage both Azure Form Recognizer for precise, structured data extraction and OpenAI for more general information extraction and to fill any gaps.

### Underwriting Validation Service

The `services/validation.py` module contains the core business logic for all underwriting validation checks. It implements the five key validation points:

1.  **Valid Claim of Hardship**: Analyzes the hardship description for validity and relevance.
2.  **Budget Analysis**: Verifies a positive surplus in the client's budget.
3.  **Contract Validation**: Checks various aspects of the contract, including IP addresses, mailing address consistency, signature adherence to Forth's requirements, bank details matching, and SSN/DOB consistency across multiple sources.
4.  **Address Validation**: Ensures the client's state address adheres to the assigned company based on a reference table.
5.  **Draft Validation**: Validates minimum payment amounts and ensures the first draft date is within acceptable ranges, considering affiliate-specific exceptions.

### Microsoft Teams Chatbot

The `services/teams_bot.py` module integrates with Microsoft Teams to provide a conversational interface for the underwriting system. It allows users to:

-   Manually trigger validation checks for a given `contact_id`.
-   Receive formatted validation results directly in Teams.
-   Provide feedback on the AI's performance (e.g., rating and description).

## Deployment

Refer to `docs/DEPLOYMENT.md` for detailed deployment instructions.

## Contributing

Contributions are welcome! Please refer to `CONTRIBUTING.md` (to be added) for guidelines.

## License

This project is licensed under the MIT License. See the `LICENSE` file (to be added) for details.



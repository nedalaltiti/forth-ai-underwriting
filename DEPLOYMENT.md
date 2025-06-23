# Deployment Guide for Forth AI Underwriting System

This document provides comprehensive instructions for deploying the Forth AI Underwriting System to various environments.

## Table of Contents

1.  [Prerequisites](#1-prerequisites)
2.  [Local Development Setup](#2-local-development-setup)
3.  [Containerized Deployment (Docker)](#3-containerized-deployment-docker)
    *   [Building the Docker Image](#building-the-docker-image)
    *   [Running the Docker Container](#running-the-docker-container)
4.  [Kubernetes Deployment](#4-kubernetes-deployment)
    *   [Prerequisites](#prerequisites-1)
    *   [Configuration](#configuration)
    *   [Deployment Steps](#deployment-steps)
5.  [CI/CD Pipeline (Bitbucket Pipelines)](#5-cicd-pipeline-bitbucket-pipelines)
6.  [Environment Variables Management](#6-environment-variables-management)
7.  [Monitoring and Logging](#7-monitoring-and-logging)
8.  [Troubleshooting](#8-troubleshooting)

## 1. Prerequisites

Before you begin, ensure you have the following installed and configured:

*   **Git**: For cloning the repository.
*   **Python 3.11+**: For local development and testing.
*   **uv**: For dependency management (`pip install uv`).
*   **Docker**: For building and running containerized applications.
*   **kubectl**: For interacting with Kubernetes clusters.
*   **Helm (Optional)**: For managing Kubernetes applications.
*   **Azure Account**: If using Azure Form Recognizer.
*   **OpenAI Account**: If using OpenAI services.
*   **Microsoft Azure Bot Service**: For Teams bot integration.

## 2. Local Development Setup

Refer to the `README.md` file for detailed instructions on setting up the project for local development.

## 3. Containerized Deployment (Docker)

Docker provides a consistent environment for running the application across different stages.

### Building the Docker Image

Navigate to the root of the project directory and build the Docker image:

```bash
docker build -t forth-ai-underwriting:latest -f docker/Dockerfile .
```

This command builds an image named `forth-ai-underwriting` with the tag `latest` using the `Dockerfile` located in the `docker/` directory.

### Running the Docker Container

Once the image is built, you can run a container:

```bash
docker run -d -p 8000:8000 --name forth-ai-underwriting \
  --env-file configs/.env \
  forth-ai-underwriting:latest
```

*   `-d`: Runs the container in detached mode.
*   `-p 8000:8000`: Maps port 8000 on your host to port 8000 in the container.
*   `--name forth-ai-underwriting`: Assigns a name to your container for easy reference.
*   `--env-file configs/.env`: Loads environment variables from your `.env` file. **For production, consider using Docker secrets or Kubernetes secrets for sensitive information.**

Verify the container is running:

```bash
docker ps
```

You should see `forth-ai-underwriting` listed.

## 4. Kubernetes Deployment

For production deployments, Kubernetes is recommended for orchestration, scaling, and high availability.

### Prerequisites

*   A running Kubernetes cluster (e.g., AKS, EKS, GKE, or a self-managed cluster).
*   `kubectl` configured to connect to your cluster.
*   `kustomize` (often included with `kubectl`) or `Helm` for managing manifests.

### Configuration

Kubernetes manifests are located in the `k8s/` directory. This directory is structured to support different environments (e.g., `base`, `overlays/dev`, `overlays/prod`).

*   **`k8s/base/deployment.yaml`**: Defines the core deployment for the application.
*   **`k8s/base/service.yaml`**: Defines the Kubernetes Service to expose the application.
*   **`k8s/base/secrets.yaml` (or similar)**: Placeholder for Kubernetes Secrets. **Do not commit actual secrets to your repository.** Use a secure method for managing secrets (e.g., Sealed Secrets, HashiCorp Vault, cloud-specific secret managers).

**Example `k8s/base/deployment.yaml` (simplified):**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: forth-ai-underwriting
  labels:
    app: forth-ai-underwriting
spec:
  replicas: 2
  selector:
    matchLabels:
      app: forth-ai-underwriting
  template:
    metadata:
      labels:
        app: forth-ai-underwriting
    spec:
      containers:
      - name: forth-ai-underwriting
        image: your-docker-registry/forth-ai-underwriting:latest # Replace with your image
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: forth-ai-underwriting-secrets # Reference your Kubernetes Secret
        # Add resource limits and probes
```

**Example `k8s/base/service.yaml`:**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: forth-ai-underwriting
spec:
  selector:
    app: forth-ai-underwriting
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP # Use LoadBalancer for external access in cloud environments
```

### Deployment Steps (using Kustomize)

1.  **Create Kubernetes Secrets**: Securely create secrets for your environment variables. For example:
    ```bash
    kubectl create secret generic forth-ai-underwriting-secrets \
      --from-env-file=configs/.env
    ```
    **Note**: This is for demonstration. In production, use more secure methods like `kubectl apply -f <sealed-secret-manifest.yaml>`.

2.  **Apply Base Manifests**: Navigate to the `k8s/base` directory and apply the manifests:
    ```bash
    kubectl apply -k .
    ```

3.  **Apply Environment Overlays**: For specific environments (e.g., `dev`, `prod`), navigate to the respective overlay directory and apply:
    ```bash
    # For development
    kubectl apply -k k8s/overlays/dev

    # For production
    kubectl apply -k k8s/overlays/prod
    ```

Verify the deployment:

```bash
kubectl get pods -l app=forth-ai-underwriting
kubectl get services forth-ai-underwriting
```

## 5. CI/CD Pipeline (Bitbucket Pipelines)

The `bitbucket-pipelines.yml` file defines the CI/CD workflow for the project. A typical pipeline for this project would include:

*   **Build**: Linting, running tests, building the Docker image.
*   **Test**: Running unit and integration tests.
*   **Scan**: Security scanning of code and Docker images.
*   **Push**: Pushing the Docker image to a container registry.
*   **Deploy**: Deploying the application to Kubernetes (e.g., using `kubectl` or `Helm`).

**Example `bitbucket-pipelines.yml` (simplified):**

```yaml
# This is a sample Bitbucket Pipelines configuration.
# It uses uv for dependency management and Docker for building the application.

image: python:3.11-slim-buster

pipelines:
  default:
    - step:
        name: Install uv and dependencies
        script:
          - pip install uv
          - uv sync
        caches:
          - pip
    - step:
        name: Run tests
        script:
          - uv run pytest
    - step:
        name: Build and push Docker image
        services:
          - docker
        script:
          - docker build -t your-docker-registry/forth-ai-underwriting:$BITBUCKET_COMMIT -f docker/Dockerfile .
          - docker login -u $DOCKER_HUB_USERNAME -p $DOCKER_HUB_PASSWORD
          - docker push your-docker-registry/forth-ai-underwriting:$BITBUCKET_COMMIT
    - step:
        name: Deploy to Kubernetes (Dev)
        trigger: manual # Manual trigger for dev deployments
        script:
          - apt-get update && apt-get install -y kubectl
          - kubectl config use-context your-dev-cluster-context
          - kubectl apply -k k8s/overlays/dev
  branches:
    main:
      - step:
          name: Deploy to Kubernetes (Prod)
          script:
            - apt-get update && apt-get install -y kubectl
            - kubectl config use-context your-prod-cluster-context
            - kubectl apply -k k8s/overlays/prod
```

**Note**: Replace `your-docker-registry` and Kubernetes context names with your actual values. Store sensitive credentials (like `DOCKER_HUB_USERNAME`, `DOCKER_HUB_PASSWORD`) as secure variables in Bitbucket Pipelines.

## 6. Environment Variables Management

Environment variables are crucial for configuring the application in different environments. We use `pydantic-settings` to load configurations from `.env` files.

*   **`configs/.env.example`**: Provides a template for all required environment variables.
*   **`configs/.env`**: (Local only) Your local environment variables. **This file should not be committed to version control.**

For production, environment variables should be managed securely:

*   **Docker**: Use `--env-file` for local Docker runs, but for production, consider Docker secrets or Kubernetes secrets.
*   **Kubernetes**: Use Kubernetes Secrets to store sensitive information. These secrets are then mounted as environment variables or files into your pods.

## 7. Monitoring and Logging

*   **Logging**: The application uses `loguru` for structured logging. Logs should be collected by a centralized logging system (e.g., ELK Stack, Datadog, Splunk) for analysis and monitoring.
*   **Monitoring**: Implement application performance monitoring (APM) tools (e.g., Prometheus, Grafana, Datadog) to track key metrics like request latency, error rates, and resource utilization.
*   **Health Checks**: The FastAPI application includes `/health` and `/` endpoints for readiness and liveness probes in Kubernetes.

## 8. Troubleshooting

*   **Check Logs**: Always start by checking the application logs for errors or warnings.
*   **Container Status**: Use `docker ps` or `kubectl get pods` to ensure your containers/pods are running.
*   **Network Issues**: Verify network connectivity between services and external APIs.
*   **Environment Variables**: Double-check that all required environment variables are correctly set and loaded.
*   **Dependency Issues**: Ensure all dependencies are correctly installed and compatible.



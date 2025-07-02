#!/bin/bash
set -e

# Deploy Webhook Service Only
echo "🚀 Deploying Webhook Service..."

# Build webhook service image
echo "📦 Building webhook service image..."
docker build -f docker/Dockerfile.webhook -t forth-webhook-service:latest .

# Stop and remove existing container
echo "🛑 Stopping existing webhook service..."
docker stop forth-webhook-service 2>/dev/null || true
docker rm forth-webhook-service 2>/dev/null || true

# Run webhook service
echo "▶️ Starting webhook service..."
docker run -d \
  --name forth-webhook-service \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  forth-webhook-service:latest

# Wait for health check
echo "🏥 Waiting for service to be healthy..."
sleep 10

# Check health
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
  echo "✅ Webhook service deployed successfully!"
  echo "🌐 Webhook endpoint: http://localhost:8000/webhook/forth"
else
  echo "❌ Webhook service health check failed!"
  echo "📋 Checking logs..."
  docker logs forth-webhook-service --tail 20
  exit 1
fi

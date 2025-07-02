#!/bin/bash
set -e

# Deploy Document Download Service Only
echo "🚀 Deploying Document Download Service..."

# Build download service image
echo "📦 Building download service image..."
docker build -f docker/Dockerfile.download -t forth-download-service:latest .

# Stop and remove existing container
echo "🛑 Stopping existing download service..."
docker stop forth-download-service 2>/dev/null || true
docker rm forth-download-service 2>/dev/null || true

# Run download service
echo "▶️ Starting download service..."
docker run -d \
  --name forth-download-service \
  --restart unless-stopped \
  --env-file .env \
  forth-download-service:latest

# Wait for service to start
echo "⏳ Waiting for service to start..."
sleep 15

# Check if container is running
if docker ps | grep -q forth-download-service; then
  echo "✅ Download service deployed successfully!"
  echo "📋 Checking recent logs..."
  docker logs forth-download-service --tail 10
else
  echo "❌ Download service failed to start!"
  echo "📋 Checking logs..."
  docker logs forth-download-service --tail 20
  exit 1
fi

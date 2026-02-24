#!/bin/bash
# DataForge Quick Setup Script
# Initializes the full platform locally

set -e

clear
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║      DataForge - Financial Data Lakehouse Platform           ║"
echo "║                   Quick Setup Script                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Check prerequisites
echo -e "${YELLOW}[1/6]${NC} Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Install Docker Desktop.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker found${NC}"

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker Compose found${NC}"

# Step 2: Check Docker resources
echo -e "${YELLOW}[2/6]${NC} Verifying Docker resources (need 4+ CPUs, 8+ GB RAM)..."
DOCKER_INFO=$(docker info)
if echo "$DOCKER_INFO" | grep -q "WARNING"; then
    echo -e "${YELLOW}⚠️  Docker resource warning. Ensure 8GB+ RAM allocated.${NC}"
fi
echo -e "${GREEN}✅ Docker resources OK${NC}"

# Step 3: Build images
echo -e "${YELLOW}[3/6]${NC} Building Docker images (this may take 5-10 minutes)..."
docker-compose -f docker/docker-compose.yml build --quiet
echo -e "${GREEN}✅ Images built${NC}"

# Step 4: Start services
echo -e "${YELLOW}[4/6]${NC} Starting services..."
docker-compose -f docker/docker-compose.yml up -d
echo -e "${GREEN}✅ Services started${NC}"

# Step 5: Wait for health checks
echo -e "${YELLOW}[5/6]${NC} Waiting for services to be ready (max 60 seconds)..."
MAX_ATTEMPTS=60
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if docker exec dataforge-postgres pg_isready -U dataforge > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL ready${NC}"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."
    sleep 1
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo -e "${RED}❌ PostgreSQL failed to start${NC}"
        exit 1
    fi
done

echo ""

# Step 6: Print access information
echo -e "${YELLOW}[6/6]${NC} Setup complete!"
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              DataForge Platform is Ready! 🎉                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "📊 Access Services:"
echo "   Airflow UI:          http://localhost:8888        (admin/admin)"
echo "   API Documentation:   http://localhost:8000/docs"
echo "   Spark Master UI:     http://localhost:8080"
echo "   MinIO Console:       http://localhost:9001        (minioadmin/minioadmin)"
echo "   PostgreSQL:          localhost:5432"
echo "   Jupyter Notebook:    http://localhost:8888(Airflow tab)"
echo ""
echo "🚀 Quick Start Commands:"
echo "   make help            - See all available commands"
echo "   make logs            - Stream all logs"
echo "   make dag-bronze      - Run Bronze ingestion DAG"
echo "   make dag-full        - Run full Bronze→Silver→Gold pipeline"
echo "   make health          - Check service health"
echo ""
echo "📖 Documentation:       README.md"
echo "🧪 Run tests:          make test"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:8888 (Airflow)"
echo "  2. Enable 'dag_bronze_ingestion' DAG"
echo "  3. Trigger manually to test"
echo ""

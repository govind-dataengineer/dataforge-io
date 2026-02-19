#!/bin/bash
# Database initialization script for DataForge

set -e

POSTGRES_HOST=${POSTGRES_HOST:-postgres}
POSTGRES_USER=${POSTGRES_USER:-postgres}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}

echo "Initializing DataForge PostgreSQL databases..."

# Wait for PostgreSQL to be ready
until PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER -c '\q' 2>/dev/null; do
  echo "Waiting for PostgreSQL..."
  sleep 1
done

# Create databases
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -U $POSTGRES_USER <<EOF
CREATE DATABASE IF NOT EXISTS dataforge_metadata;
CREATE DATABASE IF NOT EXISTS dataforge_audit;
CREATE DATABASE IF NOT EXISTS dataforge_staging;
EOF

echo "Databases created successfully"

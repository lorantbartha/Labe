#!/bin/bash

# Exit immediately if any command fails
set -e
set -x

echo "Initializing LocalStack resources..."

# ── Helper ────────────────────────────────────────────────────────────────────

table_exists() {
    local table_name=$1
    awslocal dynamodb describe-table --table-name "$table_name" --region us-east-1 >/dev/null 2>&1
}

# ── Goals table ───────────────────────────────────────────────────────────────
if table_exists "Labe-Local-Goals"; then
    echo "Goals table already exists, skipping."
else
    awslocal dynamodb create-table \
        --table-name Labe-Local-Goals \
        --attribute-definitions \
            AttributeName=user_id,AttributeType=S \
            AttributeName=id,AttributeType=S \
        --key-schema \
            AttributeName=user_id,KeyType=HASH \
            AttributeName=id,KeyType=RANGE \
        --provisioned-throughput ReadCapacityUnits=10,WriteCapacityUnits=10 \
        --region us-east-1
    echo "Goals table created."
fi

# ── Verify ────────────────────────────────────────────────────────────────────
echo "Current DynamoDB tables:"
awslocal dynamodb list-tables --region us-east-1

echo "LocalStack initialization complete."

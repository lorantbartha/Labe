#!/bin/bash

echo "Running post_create.sh"

apt-get update && apt-get install -y --no-install-recommends nodejs npm

pip install awscli

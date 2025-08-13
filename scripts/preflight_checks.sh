#!/bin/bash
# Preflight checks before deployment

echo "🔍 Running preflight checks..."

# Check Python version
python3 --version || { echo "❌ Python 3 not found"; exit 1; }

# Check required environment variables
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ BOT_TOKEN not set"
    exit 1
fi

if [ -z "$ALLOWED_USERS" ]; then
    echo "❌ ALLOWED_USERS not set"
    exit 1
fi

# Check if port is available (if needed)
if command -v netstat >/dev/null 2>&1; then
    if netstat -tuln | grep :8080 >/dev/null 2>&1; then
        echo "⚠️  Port 8080 is already in use"
    fi
fi

# Check disk space
available_space=$(df / | tail -1 | awk '{print $4}')
if [ "$available_space" -lt 1048576 ]; then  # Less than 1GB
    echo "⚠️  Low disk space: $(df -h / | tail -1 | awk '{print $4}') available"
fi

# Check systemd
if ! systemctl --version >/dev/null 2>&1; then
    echo "⚠️  Systemd not available"
fi

echo "✅ Preflight checks completed"

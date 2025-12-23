FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies + Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install MCP server globally
RUN npm install -g @modelcontextprotocol/server-sequential-thinking

# Copy requirements first for layer caching
COPY src/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ .

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "uvicorn", "entrypoints.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

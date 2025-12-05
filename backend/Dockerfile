FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy source code
COPY src/ ./src/

# Expose port
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uvicorn", "src.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

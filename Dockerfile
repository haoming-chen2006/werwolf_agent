FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files first for better caching
COPY pyproject.toml .
COPY README.md .

# Copy source code
COPY src/ ./src/
COPY main.py .
COPY config.yml .

# Install dependencies using uv
RUN uv sync --no-dev

# Expose the default agent port
EXPOSE 9000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command - can be overridden
CMD ["uv", "run", "python", "main.py", "white"]

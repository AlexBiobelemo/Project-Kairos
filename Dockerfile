# Production Dockerfile for Project Kairos
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    KAIROS_ENV=production \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN groupadd -r kairos && useradd -r -g kairos kairos

# Create directories with proper permissions
RUN mkdir -p /app/data /app/logs /app/backups && \
    chown -R kairos:kairos /app

# Copy application code
COPY --chown=kairos:kairos . .

# Switch to non-root user
USER kairos

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Create entrypoint script
COPY --chown=kairos:kairos docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Run the application
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["streamlit", "run", "app_production.py", "--server.port=8501", "--server.address=0.0.0.0"]

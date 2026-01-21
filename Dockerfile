# Multi-stage build for optimized image size
FROM python:3.12-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.12-slim

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application files
COPY unifi_api_firewall_flask.py .
COPY config.yaml .

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=2)"

# Expose port
EXPOSE 8080

# Use gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "unifi_api_firewall_flask:app"]

# Multi-stage build for optimized image size
FROM python:3.12-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.12-slim

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Copy Python dependencies from builder and set ownership
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application files
COPY --chown=appuser:appuser unifi_api_firewall_flask.py .
COPY --chown=appuser:appuser config.yaml.example config.yaml

# Make sure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=2)"

# Expose port
EXPOSE 8080

# Use gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "unifi_api_firewall_flask:app"]

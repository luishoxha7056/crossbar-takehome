# Use a small official Python image
FROM python:3.11-slim

# Default RPC (can be overridden in docker-compose)
ENV RPC_URL="https://ethereum.publicnode.com"

WORKDIR /app

# Install dependencies
# (if you prefer, you can use requirements.txt instead)
RUN pip install --no-cache-dir fastapi uvicorn requests

# Copy app code
COPY app.py .

# Expose port for documentation only (not required for function)
EXPOSE 8000

# Start FastAPI with Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

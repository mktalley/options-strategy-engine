# Dockerfile for Options Strategy Engine
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \

# Download TextBlob corpora for sentiment analysis
RUN python -m textblob.download_corpora --quiet

       tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Default command: run bot (scheduler inside main.py handles market hours)
CMD ["python", "main.py"]

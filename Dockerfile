FROM python:3.11-slim

# Install system dependencies (needed by Playwright)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser
RUN playwright install chromium

COPY . .

# Create data directories
RUN mkdir -p /data/memory/priority/critical /data/memory/priority/normal \
    /data/memory/journals /data/plugins /data/browser/profiles /data/logs

ENV DOCKER_CONTAINER=1
ENV BROWSER_HEADLESS=true

CMD ["python", "main.py"]

FROM python:3.11-slim

# Set to 1 to install Playwright (the pip package, chromium and its system
# libraries — ~316MB). Default 0 keeps the image slim.
ARG INSTALL_BROWSER=0

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright (package + system libraries + chromium)
RUN if [ "$INSTALL_BROWSER" = "1" ]; then \
      pip install --no-cache-dir playwright \
      && apt-get update && apt-get install -y \
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
        && rm -rf /var/lib/apt/lists/* \
        && playwright install chromium; \
    fi

COPY . .

# Create data directories
RUN mkdir -p /data/memory/priority/critical /data/memory/priority/normal \
    /data/memory/journals /data/plugins /data/browser/profiles /data/logs

ENV DOCKER_CONTAINER=1
ENV BROWSER_HEADLESS=true

CMD ["python", "main.py"]

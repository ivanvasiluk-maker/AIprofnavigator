FROM python:3.12-slim

# Install dependencies for Playwright and PDF rendering
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcb1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libx11-6 \
    libxext6 \
    fonts-dejavu \
    fonts-noto \
    curl \
    ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN python -m playwright install chromium

# Copy application
COPY . .

# Create reports directory
RUN mkdir -p reports

# Start bot
CMD ["python", "bot.py"]

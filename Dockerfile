FROM python:3.12-slim

# System deps for Playwright Chromium
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2-dev \
    libcairo2-dev \
    pkg-config \
    build-essential \
    meson \
    ninja-build \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-xetex \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium binary
RUN playwright install chromium

# Copy application source
COPY . .

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "home.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0", \
            "--server.headless=true"]

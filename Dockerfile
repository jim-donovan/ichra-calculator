FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for PostgreSQL and Playwright Chromium
RUN apt-get update && apt-get install -y \
    libpq-dev \
    # Playwright Chromium dependencies
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
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
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Inject Ruttl feedback widget into Streamlit's index.html (no iframe, runs in main document)
RUN STREAMLIT_INDEX=$(python -c "import streamlit; print(streamlit.__file__.replace('__init__.py', 'static/index.html'))") && \
    sed -i '/<\/head>/i <ruttl-poetry id="atwA7I0ONbXhe3w45XMl"><\/ruttl-poetry><script src="https:\/\/web.ruttl.com\/poetry.js"><\/script>' "$STREAMLIT_INDEX"

# Install Playwright Chromium browser
RUN playwright install chromium

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
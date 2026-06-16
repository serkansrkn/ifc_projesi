# ─────────────────────────────────────────────────────────────────────────────
# IFC Pipeline — Docker Image
# ifcopenshell C++ bağımlılıkları dahil, Streamlit ile web arayüzü
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim AS base

# Sistem bağımlılıkları (ifcopenshell derlemesi + healthcheck için)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Çalışma dizini
WORKDIR /app

# Bağımlılıkları önce kur (Docker cache için)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Streamlit portu
EXPOSE 8501

# Sağlık kontrolü
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Streamlit ayarları (headless mod, CORS kapalı, sunucu adresi)
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_THEME_BASE=dark

# Uygulama başlat
ENTRYPOINT ["streamlit", "run", "app.py"]

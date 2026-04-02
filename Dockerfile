FROM python:3.11-slim

# Playwright用のシステム依存パッケージ
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存パッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Playwrightのブラウザをインストール
RUN playwright install chromium

# アプリケーションコードをコピー
COPY . .

# 必要なディレクトリを作成
RUN mkdir -p input/done output browser_data templates static docs samples prompts

# 環境変数
ENV HEADLESS=true
ENV PORT=8080

EXPOSE 8080

# gunicornで起動
CMD gunicorn webapp:app --bind 0.0.0.0:$PORT --timeout 300 --workers 1

# Railway 배포용 Dockerfile
# Playwright + Chromium이 포함된 Python 환경

FROM python:3.11-slim-bookworm

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Playwright 브라우저 경로
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# 시스템 의존성 설치 (Playwright Chromium 실행에 필요)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 기본 도구
    wget \
    curl \
    gnupg \
    # Chromium 의존성
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    # 폰트 (한글 지원) - fonts-nanum만 사용 (다른 패키지 포함됨)
    fonts-nanum \
    # 정리
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Chromium 설치
RUN playwright install chromium \
    && playwright install-deps chromium

# 애플리케이션 코드 복사
COPY ./app ./app

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 서버 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

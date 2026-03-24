"""
애플리케이션 설정 관리
환경 변수 기반의 중앙 집중 설정
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Gemini API
    gemini_api_key: Optional[str] = None

    # 서버 설정
    port: int = 8000
    debug: bool = False

    # Playwright 설정
    browser_headless: bool = True
    browser_timeout: int = 30000       # 30초
    page_load_timeout: int = 60000     # 60초

    # 작가웹 설정
    artist_web_base_url: str = "https://artist.idus.com"
    artist_web_login_timeout: int = 15000
    artist_web_navigation_delay: int = 1000   # 페이지 이동 간 대기 (ms)
    artist_web_input_delay: int = 100          # 입력 간 대기 (ms)

    # 번역 설정
    translation_rate_limit_delay: float = 6.5  # Gemini API 요청 간격 (초)
    translation_max_retries: int = 3
    title_max_length_global: int = 80          # 글로벌 작품명 최대 길이

    # 일괄 처리 설정
    batch_max_size: int = 10
    batch_item_delay: float = 3.0              # 작품 간 대기 (초)

    # CORS
    cors_origins: list[str] = ["*"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

# GB 작품 연계 등록 자동화 - 구현 상세 명세서

> **문서 버전**: v1.0
> **작성일**: 2026-03-23
> **기반 설계**: GB_INTEGRATION_DESIGN.md
> **상태**: 구현 준비 단계

---

## 1. 구현 범위 및 Phase 정의

### Phase 1: 백엔드 리팩토링 + 작가웹 연동 기반

목표: 기존 모놀리식 구조를 모듈화하고, 작가웹 세션/인증 기반을 구축한다.

### Phase 2: 국내 데이터 읽기 + 번역 파이프라인

목표: 작가웹 국내 탭에서 데이터를 추출하고 GB 등록에 최적화된 번역을 수행한다.

### Phase 3: 글로벌 탭 자동 입력 + 일괄 처리

목표: 번역 결과를 작가웹 글로벌 탭에 자동 입력하고, 일괄 처리를 지원한다.

---

## 2. Phase 1 구현 상세

### 2.1 디렉토리 마이그레이션

기존 파일을 새 구조로 이동한다. 기존 v1 API는 유지하면서 v2 API를 병렬로 추가한다.

```bash
# 실행 순서

# 1. 새 디렉토리 생성
mkdir -p backend/app/models
mkdir -p backend/app/services
mkdir -p backend/app/scraper
mkdir -p backend/app/translator
mkdir -p backend/app/routers

# 2. 기존 파일 이동 (복사 후 원본 유지)
cp backend/app/scraper.py backend/app/scraper/consumer_page.py
cp backend/app/translator.py backend/app/translator/gemini_client.py
cp backend/app/models.py backend/app/models/common.py

# 3. 새 파일 생성
touch backend/app/models/__init__.py
touch backend/app/models/domestic.py
touch backend/app/models/global_product.py
touch backend/app/services/__init__.py
touch backend/app/services/artist_web.py
touch backend/app/services/product_reader.py
touch backend/app/services/product_writer.py
touch backend/app/services/batch_processor.py
touch backend/app/scraper/__init__.py
touch backend/app/scraper/base.py
touch backend/app/scraper/artist_page.py
touch backend/app/translator/__init__.py
touch backend/app/translator/product_translator.py
touch backend/app/routers/__init__.py
touch backend/app/routers/health.py
touch backend/app/routers/products.py
touch backend/app/routers/translation.py
touch backend/app/routers/registration.py
touch backend/app/routers/session.py
touch backend/app/config.py
```

### 2.2 config.py — 설정 관리

```python
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

### 2.3 models/domestic.py — 국내 작품 모델

```python
"""
작가웹 국내 탭 기반 작품 데이터 모델
artist.idus.com에서 추출한 데이터 구조
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class GlobalStatus(str, Enum):
    """글로벌 등록 상태"""
    NOT_REGISTERED = "not_registered"   # 미등록
    REGISTERED = "registered"           # 등록 (판매중)
    PAUSED = "paused"                   # 일시중지
    DRAFT = "draft"                     # 임시저장


class ProductStatus(str, Enum):
    """국내 작품 상태"""
    SELLING = "selling"                 # 판매중
    PAUSED = "paused"                   # 일시중지
    DRAFT = "draft"                     # 임시저장


class ProductImage(BaseModel):
    """작품 이미지"""
    url: str
    order: int = 0                              # 순서 (0 = 대표 이미지)
    is_representative: bool = False


class OptionValue(BaseModel):
    """옵션 값"""
    value: str
    additional_price: int = 0                   # 추가 금액 (원)
    stock: Optional[int] = None                 # 재고


class DomesticOption(BaseModel):
    """국내 작품 옵션"""
    name: str                                   # 옵션명 (예: 색상)
    values: list[OptionValue]
    option_type: str = "basic"                  # "basic" | "request"


class ProductSummary(BaseModel):
    """작품 목록에 표시할 요약 정보"""
    product_id: str                             # UUID
    title: str
    price: int
    thumbnail_url: Optional[str] = None
    status: ProductStatus
    global_status: GlobalStatus = GlobalStatus.NOT_REGISTERED
    global_languages: list[str] = []            # 등록된 언어 ["en", "ja"]


class DomesticProduct(BaseModel):
    """작가웹 국내 탭 전체 데이터"""
    product_id: str
    product_url: str

    # 기본 정보
    title: str = Field(max_length=30)
    price: int
    quantity: int = 0
    is_made_to_order: bool = False

    # 카테고리
    category_path: str = ""                     # "디지털/폰 케이스 > 스마트톡 > 기타"
    category_restricted: bool = False           # 글로벌 판매 제한 카테고리 여부

    # 이미지
    product_images: list[ProductImage] = []

    # 상세 설명 영역
    intro: Optional[str] = None                 # 작품 인트로 (100자)
    features: list[str] = []                    # 특장점 (최대 5개)
    process_steps: list[str] = []               # 제작과정 (최대 6개)
    description_html: str = ""                  # 작품 설명 (HTML)
    gift_wrapping: bool = False                 # 선물 포장 제공

    # 옵션
    options: list[DomesticOption] = []

    # 키워드
    keywords: list[str] = []

    # 상태
    status: ProductStatus = ProductStatus.SELLING
    global_status: GlobalStatus = GlobalStatus.NOT_REGISTERED
```

### 2.4 models/global_product.py — 글로벌 등록 모델

```python
"""
작가웹 글로벌 탭 등록 데이터 모델
"""
from pydantic import BaseModel, Field
from typing import Optional


class LanguageData(BaseModel):
    """언어별 글로벌 등록 데이터"""
    title: str = Field(max_length=80)           # 글로벌 작품명
    description_html: str = ""                  # 작품 설명 (HTML)
    keywords: list[str] = []                    # 작품 키워드
    use_domestic_images: bool = True            # 국내 이미지 불러오기 사용
    custom_image_urls: list[str] = []           # 별도 이미지 URL


class GlobalOption(BaseModel):
    """글로벌 옵션 (일본어/영어 공용)"""
    original_name: str                          # 원본 한국어 옵션명
    name_en: str = ""
    name_ja: str = ""
    original_values: list[str] = []             # 원본 한국어 옵션값
    values_en: list[str] = []
    values_ja: list[str] = []
    option_type: str = "basic"                  # "basic" | "request"


class GlobalProductData(BaseModel):
    """글로벌 탭 입력 데이터 (번역 결과물)"""
    source_product_id: str                      # 원본 국내 작품 UUID
    en: Optional[LanguageData] = None
    ja: Optional[LanguageData] = None
    global_options: list[GlobalOption] = []


class RegistrationResult(BaseModel):
    """GB 등록 실행 결과"""
    product_id: str
    success: bool
    languages_registered: list[str] = []        # 성공한 언어 ["en", "ja"]
    languages_failed: list[str] = []            # 실패한 언어
    error_message: Optional[str] = None
    saved_as_draft: bool = False                # 임시저장 여부
```

### 2.5 services/artist_web.py — 작가웹 세션 관리

```python
"""
작가웹(artist.idus.com) 브라우저 세션 관리
Playwright 기반의 인증 및 네비게이션
"""
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from ..config import settings
from ..models.domestic import ProductSummary, ProductStatus, GlobalStatus


class ArtistWebSession:
    """작가웹 브라우저 세션"""

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._authenticated = False

    async def initialize(self):
        """Playwright 브라우저 초기화"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=settings.browser_headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ]
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            locale='ko-KR',
        )
        self.page = await self.context.new_page()

    async def login(self, email: str, password: str) -> bool:
        """
        작가웹 로그인

        절차:
        1. artist.idus.com 접속 → 로그인 페이지로 리다이렉트
        2. 이메일 입력 (input[type=email])
        3. 비밀번호 입력 (input[type=password])
        4. 로그인 버튼 클릭
        5. 대시보드 로딩 확인 (URL 변경 또는 특정 요소 존재)
        """
        if not self.page:
            await self.initialize()

        await self.page.goto(
            f"{settings.artist_web_base_url}/login",
            timeout=settings.page_load_timeout
        )

        # 이메일 입력
        email_input = self.page.locator('input[type="email"]')
        await email_input.fill(email)

        # 비밀번호 입력
        password_input = self.page.locator('input[type="password"]')
        await password_input.fill(password)

        # 로그인 버튼 클릭
        login_button = self.page.locator('button:has-text("로그인")')
        await login_button.click()

        # 로그인 성공 확인 (대시보드로 이동되는지)
        try:
            await self.page.wait_for_url(
                f"{settings.artist_web_base_url}/",
                timeout=settings.artist_web_login_timeout
            )
            self._authenticated = True
            return True
        except Exception:
            self._authenticated = False
            return False

    async def is_authenticated(self) -> bool:
        """인증 상태 확인"""
        if not self._authenticated or not self.page:
            return False
        # 현재 URL이 로그인 페이지가 아닌지 확인
        current_url = self.page.url
        return "/login" not in current_url

    async def get_product_list(
        self,
        status: str = "selling"
    ) -> list[ProductSummary]:
        """
        작품 목록 조회

        절차:
        1. /product/list 또는 /product/list/pause로 이동
        2. 작품 카드 요소들에서 데이터 추출
        3. 각 작품의 글로벌 상태도 확인
        """
        if not await self.is_authenticated():
            raise Exception("로그인이 필요합니다")

        # 상태에 따른 URL
        url_map = {
            "selling": "/product/list",
            "paused": "/product/list/pause",
            "draft": "/product/list/draft",
        }
        target_url = f"{settings.artist_web_base_url}{url_map.get(status, '/product/list')}"
        await self.page.goto(target_url, timeout=settings.page_load_timeout)
        await self.page.wait_for_load_state("networkidle")

        # 작품 목록 추출 (JavaScript 실행)
        products = await self.page.evaluate("""
            () => {
                // 작품 카드 요소에서 정보 추출
                // 실제 DOM 구조에 맞춰 셀렉터 조정 필요
                const cards = document.querySelectorAll('[class*="product"]');
                return Array.from(cards).map(card => {
                    const link = card.querySelector('a');
                    const href = link ? link.getAttribute('href') : '';
                    const id = href ? href.split('/').pop() : '';
                    const title = card.querySelector('[class*="title"]')?.textContent?.trim() || '';
                    const price = card.querySelector('[class*="price"]')?.textContent?.trim() || '';
                    return { product_id: id, title, price_text: price };
                });
            }
        """)

        # ProductSummary로 변환
        result = []
        for p in products:
            if p.get("product_id"):
                result.append(ProductSummary(
                    product_id=p["product_id"],
                    title=p.get("title", ""),
                    price=self._parse_price(p.get("price_text", "0")),
                    status=ProductStatus(status),
                ))
        return result

    async def navigate_to_product(self, product_id: str) -> bool:
        """작품 수정 페이지로 이동"""
        url = f"{settings.artist_web_base_url}/product/{product_id}"
        await self.page.goto(url, timeout=settings.page_load_timeout)
        await self.page.wait_for_load_state("networkidle")
        return "product" in self.page.url

    async def close(self):
        """세션 정리"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self._authenticated = False

    @staticmethod
    def _parse_price(price_text: str) -> int:
        """가격 텍스트를 정수로 변환 ('10,000원' → 10000)"""
        import re
        digits = re.sub(r'[^\d]', '', price_text)
        return int(digits) if digits else 0
```

### 2.6 services/product_reader.py — 국내 데이터 읽기

```python
"""
작가웹 국내 탭 데이터 추출 서비스
"""
import re
from typing import Optional
from playwright.async_api import Page
from ..models.domestic import (
    DomesticProduct, ProductImage, DomesticOption, OptionValue,
    ProductStatus, GlobalStatus
)
from ..config import settings

# 글로벌 판매 제한 카테고리
RESTRICTED_CATEGORIES = [
    "식품", "가구", "식물", "디퓨저",
    "14k", "18k", "24k"
]


class ProductReader:
    """작가웹 국내 탭 데이터 추출기"""

    def __init__(self, page: Page):
        self.page = page

    async def read_domestic_data(self, product_id: str) -> DomesticProduct:
        """
        국내 탭 전체 데이터 추출

        전제: 이미 /product/{product_id} 페이지에 위치
        국내 탭이 기본 선택 상태여야 함
        """
        # 국내 탭 활성화 확인
        await self._ensure_domestic_tab()

        # 각 필드 추출
        title = await self._read_title()
        price = await self._read_price()
        quantity = await self._read_quantity()
        is_made_to_order = await self._read_made_to_order()
        category_path = await self._read_category()
        images = await self._read_images()
        intro = await self._read_intro()
        features = await self._read_features()
        process_steps = await self._read_process_steps()
        description_html = await self._read_description()
        options = await self._read_options()
        keywords = await self._read_keywords()
        gift_wrapping = await self._read_gift_wrapping()

        # 글로벌 판매 제한 카테고리 확인
        category_restricted = any(
            keyword in category_path for keyword in RESTRICTED_CATEGORIES
        )

        # 글로벌 상태 확인
        global_status = await self._read_global_status()

        return DomesticProduct(
            product_id=product_id,
            product_url=self.page.url,
            title=title,
            price=price,
            quantity=quantity,
            is_made_to_order=is_made_to_order,
            category_path=category_path,
            category_restricted=category_restricted,
            product_images=images,
            intro=intro,
            features=features,
            process_steps=process_steps,
            description_html=description_html,
            options=options,
            keywords=keywords,
            gift_wrapping=gift_wrapping,
            global_status=global_status,
        )

    async def _ensure_domestic_tab(self):
        """국내 탭이 활성화되어 있는지 확인하고, 아니면 클릭"""
        # 탭 영역에서 "국내" 텍스트가 있는 탭 요소 확인
        domestic_tab = self.page.locator('text=국내').first
        if domestic_tab:
            await domestic_tab.click()
            await self.page.wait_for_timeout(settings.artist_web_navigation_delay)

    async def _read_title(self) -> str:
        """작품명 추출 — 작품명 input 필드 value"""
        # 작가웹에서 작품명 필드: "작품명*" 라벨 하단의 textarea 또는 input
        title_input = self.page.locator(
            'textarea[placeholder*="작품명"], input[placeholder*="작품명"]'
        ).first
        if title_input:
            return await title_input.input_value()

        # 대안: 텍스트 직접 추출
        title_el = self.page.locator('[class*="title"] input').first
        return await title_el.input_value() if title_el else ""

    async def _read_price(self) -> int:
        """가격 추출"""
        price_input = self.page.locator('input[type="number"]').first
        if price_input:
            val = await price_input.input_value()
            return int(re.sub(r'[^\d]', '', val)) if val else 0
        return 0

    async def _read_quantity(self) -> int:
        """수량 추출"""
        # "수량" 라벨 인접 input
        # 구조: 수량 * → input → "11 개"
        quantity_section = self.page.locator('text=수량').locator('..')
        qty_input = quantity_section.locator('input').first
        if qty_input:
            val = await qty_input.input_value()
            return int(re.sub(r'[^\d]', '', val)) if val else 0
        return 0

    async def _read_made_to_order(self) -> bool:
        """주문 시 제작 여부"""
        checkbox = self.page.locator('text=주문 시 제작').locator('..').locator('input[type="checkbox"]')
        if await checkbox.count() > 0:
            return await checkbox.is_checked()
        return False

    async def _read_category(self) -> str:
        """카테고리 경로 추출"""
        # "카테고리 & 속성" 섹션 하단의 텍스트
        category_el = self.page.locator('text=카테고리 & 속성').locator('..')
        # 카테고리 경로 텍스트 추출 (예: "디지털/폰 케이스 > 스마트톡 > 기타 스마트톡")
        path_el = category_el.locator('p, span, div').filter(has_text=re.compile(r'>'))
        if await path_el.count() > 0:
            return await path_el.first.inner_text()
        return ""

    async def _read_images(self) -> list[ProductImage]:
        """작품 이미지 URL 및 순서 추출"""
        images = []
        # 이미지 영역에서 img 태그들 추출
        img_elements = self.page.locator(
            'section:has-text("작품 이미지") img[src*="image.idus.com"]'
        )
        count = await img_elements.count()
        for i in range(count):
            src = await img_elements.nth(i).get_attribute('src')
            if src:
                images.append(ProductImage(
                    url=src,
                    order=i,
                    is_representative=(i == 0)
                ))
        return images

    async def _read_intro(self) -> Optional[str]:
        """작품 인트로 추출"""
        intro_input = self.page.locator(
            'textarea[placeholder*="작품을 한 줄로 간결하게"]'
        ).first
        if intro_input and await intro_input.count() > 0:
            val = await intro_input.input_value()
            return val if val else None
        return None

    async def _read_features(self) -> list[str]:
        """특장점 추출"""
        features = []
        feature_items = self.page.locator('section:has-text("특장점") [class*="item"]')
        count = await feature_items.count()
        for i in range(count):
            text = await feature_items.nth(i).inner_text()
            if text.strip():
                features.append(text.strip())
        return features

    async def _read_process_steps(self) -> list[str]:
        """제작과정 추출"""
        steps = []
        step_items = self.page.locator('section:has-text("제작과정") [class*="item"]')
        count = await step_items.count()
        for i in range(count):
            text = await step_items.nth(i).inner_text()
            if text.strip():
                steps.append(text.strip())
        return steps

    async def _read_description(self) -> str:
        """작품 설명 HTML 추출"""
        # "작품 설명" 섹션의 에디터 콘텐츠
        desc_section = self.page.locator('section:has-text("작품 설명")')
        editor_content = desc_section.locator('[class*="editor"], [class*="content"], [contenteditable]')
        if await editor_content.count() > 0:
            return await editor_content.first.inner_html()

        # 대안: "작성된 내용이 없습니다" 확인
        empty_text = desc_section.locator('text=작성된 내용이 없습니다')
        if await empty_text.count() > 0:
            return ""

        return ""

    async def _read_options(self) -> list[DomesticOption]:
        """옵션 데이터 추출"""
        options = []
        option_section = self.page.locator('section:has-text("옵션")')

        # 옵션이 있는 경우 각 옵션 그룹 추출
        option_groups = option_section.locator('[class*="option-group"], [class*="optionItem"]')
        count = await option_groups.count()

        for i in range(count):
            group = option_groups.nth(i)
            name_el = group.locator('[class*="name"], label').first
            name = await name_el.inner_text() if await name_el.count() > 0 else f"옵션{i+1}"

            # 옵션값 추출
            value_elements = group.locator('[class*="value"], [class*="chip"]')
            values = []
            val_count = await value_elements.count()
            for j in range(val_count):
                val_text = await value_elements.nth(j).inner_text()
                if val_text.strip():
                    values.append(OptionValue(value=val_text.strip()))

            if values:
                options.append(DomesticOption(
                    name=name.strip(),
                    values=values,
                    option_type="basic"
                ))

        return options

    async def _read_keywords(self) -> list[str]:
        """작품 키워드 추출"""
        keywords = []
        keyword_section = self.page.locator('section:has-text("작품 키워드")')
        keyword_chips = keyword_section.locator('[class*="chip"], [class*="tag"]')
        count = await keyword_chips.count()
        for i in range(count):
            text = await keyword_chips.nth(i).inner_text()
            if text.strip():
                keywords.append(text.strip())
        return keywords

    async def _read_gift_wrapping(self) -> bool:
        """선물 포장 제공 여부"""
        checkbox = self.page.locator('text=선물 포장 제공').locator('..').locator('input[type="checkbox"]')
        if await checkbox.count() > 0:
            return await checkbox.is_checked()
        return False

    async def _read_global_status(self) -> GlobalStatus:
        """글로벌 등록 상태 확인"""
        # 글로벌 탭의 텍스트로 판단
        global_tab = self.page.locator('text=글로벌').first
        if global_tab and await global_tab.count() > 0:
            tab_text = await global_tab.inner_text()
            if "미등록" in tab_text:
                return GlobalStatus.NOT_REGISTERED
            elif "등록" in tab_text:
                return GlobalStatus.REGISTERED
        return GlobalStatus.NOT_REGISTERED
```

### 2.7 services/product_writer.py — 글로벌 탭 자동 입력

```python
"""
작가웹 글로벌 탭 자동 입력 서비스
번역 결과를 실제 폼에 입력하는 핵심 모듈
"""
import asyncio
from playwright.async_api import Page
from ..models.global_product import GlobalProductData, LanguageData, GlobalOption
from ..config import settings


class ProductWriter:
    """작가웹 글로벌 탭 데이터 입력기"""

    def __init__(self, page: Page):
        self.page = page

    async def navigate_to_global_tab(self) -> bool:
        """
        글로벌 탭으로 이동

        주의: 현재 /product/{id} 페이지에 위치해야 함
        """
        global_tab = self.page.locator('text=글로벌').first
        if await global_tab.count() == 0:
            return False

        await global_tab.click()
        await self.page.wait_for_timeout(settings.artist_web_navigation_delay)

        # URL에 /global이 포함되는지 확인
        return "/global" in self.page.url

    async def select_language_tab(self, language: str) -> bool:
        """
        언어 서브탭 선택

        Args:
            language: "en" (영어) 또는 "ja" (일본어)
        """
        lang_text = "영어" if language == "en" else "일본어"
        lang_tab = self.page.locator(f'text={lang_text}').first
        if await lang_tab.count() == 0:
            return False

        await lang_tab.click()
        await self.page.wait_for_timeout(settings.artist_web_navigation_delay)
        return True

    async def import_domestic_images(self) -> bool:
        """
        '국내 작품 이미지 불러오기' 실행

        작가웹 글로벌 탭의 이미지 영역에서
        드롭다운 또는 버튼을 통해 국내 이미지를 가져옴
        """
        # "등록 전 확인해 주세요" 드롭다운 클릭
        dropdown = self.page.locator('text=등록 전 확인해 주세요').first
        if await dropdown.count() > 0:
            await dropdown.click()
            await self.page.wait_for_timeout(500)

        # 국내 이미지 불러오기 옵션 확인
        # 실제 구현 시 DOM 구조에 맞춰 셀렉터 조정 필요
        import_btn = self.page.locator(
            'button:has-text("국내 작품 이미지 불러오기"), '
            'text=국내 작품 이미지 불러오기'
        ).first
        if await import_btn.count() > 0:
            await import_btn.click()
            await self.page.wait_for_timeout(2000)  # 이미지 로딩 대기
            return True

        return False

    async def fill_title(self, title: str) -> bool:
        """
        작품명 입력

        글로벌 작품명 필드 (80자 제한)
        """
        # 현재 언어 탭의 작품명 입력 필드
        title_input = self.page.locator(
            'textarea[placeholder*="입력해 주세요"]'
        ).first

        if await title_input.count() == 0:
            return False

        # 기존 내용 지우고 새 내용 입력
        await title_input.click()
        await title_input.fill("")
        await title_input.type(
            title[:settings.title_max_length_global],
            delay=settings.artist_web_input_delay
        )
        return True

    async def fill_description(self, description_html: str) -> bool:
        """
        작품 설명 입력

        '작품 설명 작성하기' 버튼을 클릭하여 에디터를 열고,
        에디터에 HTML 콘텐츠를 삽입

        주의: 리치 텍스트 에디터의 DOM 구조에 따라 구현 방식이 달라짐
        """
        # "작품 설명 작성하기" 버튼 클릭
        edit_btn = self.page.locator('button:has-text("작품 설명 작성하기")').first
        if await edit_btn.count() > 0:
            await edit_btn.click()
            await self.page.wait_for_timeout(1000)

        # 에디터 영역에 HTML 삽입
        # 방법 1: contenteditable 요소에 직접 innerHTML 설정
        editor = self.page.locator('[contenteditable="true"]').first
        if await editor.count() > 0:
            await editor.evaluate(
                '(el, html) => { el.innerHTML = html; }',
                description_html
            )
            # 변경 이벤트 트리거
            await editor.evaluate(
                '(el) => { el.dispatchEvent(new Event("input", { bubbles: true })); }'
            )
            return True

        # 방법 2: textarea가 있는 경우
        textarea = self.page.locator('textarea[class*="description"]').first
        if await textarea.count() > 0:
            await textarea.fill(description_html)
            return True

        return False

    async def fill_keywords(self, keywords: list[str]) -> bool:
        """
        작품 키워드 입력

        키워드 섹션의 입력 필드에 하나씩 추가
        """
        keyword_section = self.page.locator('text=작품 키워드').locator('..')
        keyword_input = keyword_section.locator('input').first

        if await keyword_input.count() == 0:
            return False

        for keyword in keywords:
            await keyword_input.fill(keyword)
            await keyword_input.press('Enter')
            await self.page.wait_for_timeout(300)

        return True

    async def fill_global_options(self, options: list[GlobalOption]) -> bool:
        """
        글로벌 옵션 입력 (일본어/영어 공용)

        '옵션 편집' 버튼 클릭 → 다이얼로그에서 옵션 추가
        """
        # 옵션 편집 버튼 클릭
        edit_btn = self.page.locator('text=옵션 편집').first
        if await edit_btn.count() == 0:
            return False

        await edit_btn.click()
        await self.page.wait_for_timeout(1000)

        # 글로벌 옵션 다이얼로그가 열린 상태
        for option in options:
            # "추가" 버튼 클릭
            add_btn = self.page.locator('button:has-text("추가")').first
            await add_btn.click()
            await self.page.wait_for_timeout(500)

            # 옵션명 입력 (현재 언어 탭에 따라 en 또는 ja 값 사용)
            # 실제 구현 시 다이얼로그 내부 DOM 구조에 맞춤
            option_input = self.page.locator(
                'input[placeholder*="옵션명"]'
            ).last
            if await option_input.count() > 0:
                await option_input.fill(option.name_en)  # 또는 name_ja

        # "적용" 버튼 클릭
        apply_btn = self.page.locator('text=적용').first
        if await apply_btn.count() > 0:
            await apply_btn.click()
            await self.page.wait_for_timeout(1000)

        return True

    async def save_draft(self) -> bool:
        """임시저장"""
        # "임시저장" 버튼 (영어: "영어 임시저장", 일본어: "일본어 임시저장")
        draft_btn = self.page.locator('button:has-text("임시저장")').first
        if await draft_btn.count() == 0:
            return False

        await draft_btn.click()
        await self.page.wait_for_timeout(2000)

        # 저장 성공 확인 (토스트 메시지 또는 URL 변경)
        return True

    async def publish(self) -> bool:
        """판매 등록 — '작품 판매하기' 버튼 클릭"""
        publish_btn = self.page.locator('button:has-text("작품 판매하기")').first
        if await publish_btn.count() == 0:
            return False

        await publish_btn.click()
        await self.page.wait_for_timeout(3000)
        return True

    async def fill_language_data(
        self,
        language: str,
        data: LanguageData,
        use_domestic_images: bool = True
    ) -> bool:
        """
        특정 언어 탭의 전체 데이터 입력 (통합 메서드)

        Args:
            language: "en" 또는 "ja"
            data: 해당 언어의 등록 데이터
            use_domestic_images: 국내 이미지 불러오기 사용 여부
        """
        # 1. 언어 탭 선택
        if not await self.select_language_tab(language):
            return False

        # 2. 이미지 처리
        if use_domestic_images:
            await self.import_domestic_images()

        # 3. 작품명 입력
        await self.fill_title(data.title)

        # 4. 작품 설명 입력
        await self.fill_description(data.description_html)

        # 5. 키워드 입력
        if data.keywords:
            await self.fill_keywords(data.keywords)

        return True
```

### 2.8 translator/product_translator.py — GB 전용 번역기

```python
"""
GB 등록용 번역 서비스
기존 translator.py의 Gemini 클라이언트를 활용하면서
GB 등록에 특화된 번역 로직을 추가
"""
from typing import Optional
from ..models.domestic import DomesticProduct, DomesticOption
from ..models.global_product import GlobalProductData, LanguageData, GlobalOption
from ..translator.gemini_client import ProductTranslator  # 기존 번역 클래스 재활용
from ..config import settings


# GB 등록용 추가 프롬프트
GB_DESCRIPTION_PROMPT_EN = """You are translating a Korean handmade product description
for registration on the global idus marketplace.

CRITICAL RULES:
1. Preserve ALL HTML tags exactly as they are (<p>, <img>, <br>, <div>, etc.)
2. Only translate the TEXT content inside HTML tags
3. Do NOT translate image URLs or HTML attributes
4. Remove Korea-specific content (Korean won prices, Korean shipping info, Korean holidays)
5. Add at the end: "For production time and details, please contact us via the idus app messaging."
6. Keep the tone warm and inviting, suitable for international buyers
7. Maximum title length: 80 characters

Korean HTML:
{text}

English HTML (preserve all tags):"""


GB_DESCRIPTION_PROMPT_JA = """韓国のハンドメイド商品説明をグローバルidusマーケットプレイスの登録用に翻訳してください。

重要ルール：
1. すべてのHTMLタグをそのまま保持（<p>, <img>, <br>, <div>など）
2. HTMLタグ内のテキストのみ翻訳
3. 画像URLやHTML属性は翻訳しない
4. 韓国固有のコンテンツを削除（韓国ウォン価格、韓国の配送情報、韓国の祝日）
5. 末尾に追加：「もし作品の制作時間や詳細について知りたい場合は、アイディアス(idus)アプリのメッセージ機能を通じてご連絡ください。」
6. ミンネやクリーマのような日本のハンドメイドマーケットに適した温かいトーンで
7. タイトル最大文字数：80文字

韓国語HTML：
{text}

日本語HTML（すべてのタグを保持）："""


GB_KEYWORD_PROMPT_EN = """Translate these Korean product keywords to English.
Make them SEO-friendly for international buyers searching on a handmade marketplace.
Output one keyword per line, no numbering.

Korean keywords:
{text}

English keywords:"""


GB_KEYWORD_PROMPT_JA = """韓国語の商品キーワードを日本語に翻訳してください。
ミンネやクリーマで検索する日本のバイヤーに最適化してください。
1行に1キーワード、番号なし。

韓国語キーワード：
{text}

日本語キーワード："""


class GBProductTranslator:
    """GB 등록 전용 번역기"""

    def __init__(self, base_translator: ProductTranslator):
        self.translator = base_translator

    async def translate_for_gb(
        self,
        domestic: DomesticProduct,
        target_languages: list[str]
    ) -> GlobalProductData:
        """
        국내 작품 데이터를 글로벌 등록용으로 번역

        Args:
            domestic: 국내 작품 데이터
            target_languages: ["en", "ja"] 등
        """
        en_data = None
        ja_data = None
        global_options = []

        # 영어 번역
        if "en" in target_languages:
            en_data = await self._translate_language(domestic, "en")

        # 일본어 번역
        if "ja" in target_languages:
            ja_data = await self._translate_language(domestic, "ja")

        # 옵션 번역 (일본어/영어 공용이므로 한 번에 처리)
        if domestic.options:
            global_options = await self._translate_options(
                domestic.options, target_languages
            )

        return GlobalProductData(
            source_product_id=domestic.product_id,
            en=en_data,
            ja=ja_data,
            global_options=global_options,
        )

    async def _translate_language(
        self,
        domestic: DomesticProduct,
        language: str
    ) -> LanguageData:
        """특정 언어로 번역"""

        # 1. 작품명 번역 (80자 제한)
        title = await self._translate_title(domestic.title, language)
        if len(title) > settings.title_max_length_global:
            title = title[:settings.title_max_length_global]

        # 2. 작품 설명 번역 (HTML 구조 유지)
        description_html = await self._translate_description(
            domestic.description_html, language
        )

        # 3. 키워드 번역
        keywords = await self._translate_keywords(domestic.keywords, language)

        return LanguageData(
            title=title,
            description_html=description_html,
            keywords=keywords,
            use_domestic_images=True,
        )

    async def _translate_title(self, title: str, language: str) -> str:
        """작품명 번역 — 기존 프롬프트 재활용"""
        from ..models.common import TargetLanguage
        target = TargetLanguage.ENGLISH if language == "en" else TargetLanguage.JAPANESE
        return await self.translator._translate_text_with_retry(
            title, target, "title"
        )

    async def _translate_description(self, html: str, language: str) -> str:
        """작품 설명 HTML 번역"""
        if not html or html.strip() == "":
            return ""

        prompt_template = (
            GB_DESCRIPTION_PROMPT_EN if language == "en"
            else GB_DESCRIPTION_PROMPT_JA
        )
        prompt = prompt_template.format(text=html)

        response = await self.translator._call_gemini(prompt)
        return response if response else html

    async def _translate_keywords(
        self,
        keywords: list[str],
        language: str
    ) -> list[str]:
        """키워드 목록 번역"""
        if not keywords:
            return []

        prompt_template = (
            GB_KEYWORD_PROMPT_EN if language == "en"
            else GB_KEYWORD_PROMPT_JA
        )
        text = "\n".join(keywords)
        prompt = prompt_template.format(text=text)

        response = await self.translator._call_gemini(prompt)
        if response:
            return [kw.strip() for kw in response.strip().split("\n") if kw.strip()]
        return keywords

    async def _translate_options(
        self,
        options: list[DomesticOption],
        languages: list[str]
    ) -> list[GlobalOption]:
        """옵션 번역 (영어/일본어 동시)"""
        result = []

        for option in options:
            global_opt = GlobalOption(
                original_name=option.name,
                original_values=[v.value for v in option.values],
                option_type=option.option_type,
            )

            # 옵션명 번역
            if "en" in languages:
                global_opt.name_en = await self._translate_title(
                    option.name, "en"
                )
            if "ja" in languages:
                global_opt.name_ja = await self._translate_title(
                    option.name, "ja"
                )

            # 옵션값 번역
            values_text = "\n".join(v.value for v in option.values)
            if "en" in languages:
                en_result = await self._translate_keywords(
                    [v.value for v in option.values], "en"
                )
                global_opt.values_en = en_result

            if "ja" in languages:
                ja_result = await self._translate_keywords(
                    [v.value for v in option.values], "ja"
                )
                global_opt.values_ja = ja_result

            result.append(global_opt)

        return result
```

### 2.9 routers/session.py — 세션 관리 API

```python
"""
작가웹 세션 관리 API 라우터
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..services.artist_web import ArtistWebSession

router = APIRouter(prefix="/api/v2/session", tags=["Session"])

# 전역 세션 (단일 사용자 기준, 추후 세션 풀로 확장)
_session: Optional[ArtistWebSession] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionStatus(BaseModel):
    authenticated: bool
    email: Optional[str] = None


@router.post("/login")
async def login(request: LoginRequest):
    """작가웹 로그인"""
    global _session

    if _session:
        await _session.close()

    _session = ArtistWebSession()
    await _session.initialize()

    success = await _session.login(request.email, request.password)

    if not success:
        await _session.close()
        _session = None
        raise HTTPException(status_code=401, detail="로그인 실패")

    return {"success": True, "message": "로그인 성공"}


@router.get("/status", response_model=SessionStatus)
async def get_session_status():
    """세션 상태 확인"""
    if not _session:
        return SessionStatus(authenticated=False)

    authenticated = await _session.is_authenticated()
    return SessionStatus(authenticated=authenticated)


@router.post("/logout")
async def logout():
    """세션 종료"""
    global _session
    if _session:
        await _session.close()
        _session = None
    return {"success": True, "message": "로그아웃 완료"}


def get_session() -> ArtistWebSession:
    """현재 세션 반환 (의존성 주입용)"""
    if not _session:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    return _session
```

### 2.10 routers/registration.py — GB 등록 API

```python
"""
GB 등록 실행 API 라우터
번역 + 작가웹 입력 + 저장을 통합 실행
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from ..services.artist_web import ArtistWebSession
from ..services.product_reader import ProductReader
from ..services.product_writer import ProductWriter
from ..translator.product_translator import GBProductTranslator
from ..models.domestic import DomesticProduct
from ..models.global_product import GlobalProductData, RegistrationResult
from .session import get_session

router = APIRouter(prefix="/api/v2", tags=["Registration"])


class RegisterRequest(BaseModel):
    product_id: str
    target_languages: list[str] = ["en", "ja"]
    save_as_draft: bool = True              # True=임시저장, False=바로 판매


class TranslatePreviewRequest(BaseModel):
    product_id: str
    target_languages: list[str] = ["en", "ja"]


class TranslatePreviewResponse(BaseModel):
    success: bool
    domestic: Optional[DomesticProduct] = None
    global_data: Optional[GlobalProductData] = None
    warnings: list[str] = []


@router.get("/products")
async def list_products(
    status: str = "selling",
    session: ArtistWebSession = Depends(get_session)
):
    """국내 작품 목록 조회"""
    products = await session.get_product_list(status)
    return {"success": True, "products": products}


@router.get("/products/{product_id}")
async def get_product_detail(
    product_id: str,
    session: ArtistWebSession = Depends(get_session)
):
    """국내 작품 상세 데이터 조회"""
    await session.navigate_to_product(product_id)
    reader = ProductReader(session.page)
    domestic = await reader.read_domestic_data(product_id)
    return {"success": True, "data": domestic}


@router.post("/translate", response_model=TranslatePreviewResponse)
async def translate_preview(
    request: TranslatePreviewRequest,
    session: ArtistWebSession = Depends(get_session)
):
    """
    번역 미리보기 (등록하지 않고 결과만 반환)

    1. 국내 데이터 읽기
    2. 번역 수행
    3. 결과 반환 (사용자가 편집 가능)
    """
    # 1. 국내 데이터 추출
    await session.navigate_to_product(request.product_id)
    reader = ProductReader(session.page)
    domestic = await reader.read_domestic_data(request.product_id)

    # 경고 메시지 수집
    warnings = []
    if domestic.category_restricted:
        warnings.append(
            f"카테고리 '{domestic.category_path}'는 글로벌 판매가 제한될 수 있습니다."
        )
    if not domestic.description_html:
        warnings.append("작품 설명이 비어 있습니다. 설명을 먼저 작성해주세요.")
    if not domestic.product_images:
        warnings.append("작품 이미지가 없습니다.")

    # 2. 번역 수행
    # 주의: GBProductTranslator 인스턴스는 main.py에서 관리
    from ..main import get_gb_translator
    translator = get_gb_translator()
    global_data = await translator.translate_for_gb(
        domestic, request.target_languages
    )

    return TranslatePreviewResponse(
        success=True,
        domestic=domestic,
        global_data=global_data,
        warnings=warnings,
    )


@router.post("/register")
async def register_global(
    request: RegisterRequest,
    session: ArtistWebSession = Depends(get_session)
):
    """
    GB 등록 실행

    전체 파이프라인:
    1. 국내 데이터 읽기
    2. 번역
    3. 글로벌 탭 이동
    4. 각 언어 탭 데이터 입력
    5. 옵션 입력
    6. 임시저장 또는 판매
    """
    # 1. 국내 데이터 추출
    await session.navigate_to_product(request.product_id)
    reader = ProductReader(session.page)
    domestic = await reader.read_domestic_data(request.product_id)

    # 2. 번역
    from ..main import get_gb_translator
    translator = get_gb_translator()
    global_data = await translator.translate_for_gb(
        domestic, request.target_languages
    )

    # 3. 글로벌 탭 이동
    writer = ProductWriter(session.page)
    if not await writer.navigate_to_global_tab():
        return RegistrationResult(
            product_id=request.product_id,
            success=False,
            error_message="글로벌 탭으로 이동할 수 없습니다."
        )

    languages_registered = []
    languages_failed = []

    # 4. 각 언어별 입력
    for lang in request.target_languages:
        lang_data = global_data.en if lang == "en" else global_data.ja
        if not lang_data:
            languages_failed.append(lang)
            continue

        try:
            success = await writer.fill_language_data(
                language=lang,
                data=lang_data,
                use_domestic_images=True
            )

            if success:
                # 5. 임시저장 또는 판매
                if request.save_as_draft:
                    await writer.save_draft()
                else:
                    await writer.publish()
                languages_registered.append(lang)
            else:
                languages_failed.append(lang)

        except Exception as e:
            languages_failed.append(lang)

    # 6. 옵션 입력 (언어 공용)
    if global_data.global_options:
        await writer.fill_global_options(global_data.global_options)

    return RegistrationResult(
        product_id=request.product_id,
        success=len(languages_registered) > 0,
        languages_registered=languages_registered,
        languages_failed=languages_failed,
        saved_as_draft=request.save_as_draft,
    )
```

### 2.11 main.py 확장 — v2 라우터 등록

```python
# main.py에 추가할 내용 (기존 코드 유지하면서 v2 추가)

# 기존 v1 API는 그대로 유지
# ...

# v2 라우터 등록
from .routers import session, products, registration

app.include_router(session.router)
app.include_router(registration.router)

# GB 번역기 인스턴스 (전역)
_gb_translator = None

def get_gb_translator():
    global _gb_translator, translator
    if _gb_translator is None and translator:
        from .translator.product_translator import GBProductTranslator
        _gb_translator = GBProductTranslator(translator)
    return _gb_translator
```

---

## 3. 프론트엔드 구현 상세

### 3.1 새로운 페이지 구조

```
frontend/
├── app/
│   ├── page.tsx                         # 기존 유지 (v1 단건 번역)
│   ├── v2/
│   │   ├── layout.tsx                   # v2 레이아웃 (사이드바 포함)
│   │   ├── page.tsx                     # v2 대시보드 (로그인/작품목록)
│   │   ├── product/
│   │   │   └── [id]/
│   │   │       └── page.tsx             # 작품 상세 + 번역 미리보기
│   │   └── register/
│   │       └── page.tsx                 # 등록 진행 상태
│   ├── batch/
│   │   └── page.tsx                     # 기존 유지 (v1 배치)
│   └── glossary/
│       └── page.tsx                     # 기존 유지
```

### 3.2 주요 API 클라이언트 추가 (lib/api-v2.ts)

```typescript
/**
 * v2 API 클라이언트 — 작가웹 연동 GB 등록용
 */

const API_V2_BASE = `${getApiBaseUrl()}/api/v2`;

// ============ Types ============

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ProductSummary {
  product_id: string;
  title: string;
  price: number;
  thumbnail_url: string | null;
  status: string;
  global_status: string;
  global_languages: string[];
}

export interface DomesticProduct {
  product_id: string;
  product_url: string;
  title: string;
  price: number;
  quantity: number;
  is_made_to_order: boolean;
  category_path: string;
  category_restricted: boolean;
  product_images: Array<{
    url: string;
    order: number;
    is_representative: boolean;
  }>;
  intro: string | null;
  features: string[];
  process_steps: string[];
  description_html: string;
  options: Array<{
    name: string;
    values: Array<{ value: string; additional_price: number }>;
    option_type: string;
  }>;
  keywords: string[];
  global_status: string;
}

export interface LanguageData {
  title: string;
  description_html: string;
  keywords: string[];
  use_domestic_images: boolean;
}

export interface GlobalProductData {
  source_product_id: string;
  en: LanguageData | null;
  ja: LanguageData | null;
  global_options: Array<{
    original_name: string;
    name_en: string;
    name_ja: string;
    values_en: string[];
    values_ja: string[];
  }>;
}

export interface TranslatePreviewResponse {
  success: boolean;
  domestic: DomesticProduct | null;
  global_data: GlobalProductData | null;
  warnings: string[];
}

export interface RegistrationResult {
  product_id: string;
  success: boolean;
  languages_registered: string[];
  languages_failed: string[];
  error_message: string | null;
  saved_as_draft: boolean;
}

// ============ API Functions ============

export async function loginArtistWeb(
  email: string,
  password: string
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_V2_BASE}/session/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  return response.json();
}

export async function getSessionStatus(): Promise<{
  authenticated: boolean;
  email?: string;
}> {
  const response = await fetch(`${API_V2_BASE}/session/status`);
  return response.json();
}

export async function logoutArtistWeb(): Promise<void> {
  await fetch(`${API_V2_BASE}/session/logout`, { method: 'POST' });
}

export async function getProductList(
  status: string = 'selling'
): Promise<{ success: boolean; products: ProductSummary[] }> {
  const response = await fetch(
    `${API_V2_BASE}/products?status=${status}`
  );
  return response.json();
}

export async function getProductDetail(
  productId: string
): Promise<{ success: boolean; data: DomesticProduct }> {
  const response = await fetch(`${API_V2_BASE}/products/${productId}`);
  return response.json();
}

export async function translatePreview(
  productId: string,
  targetLanguages: string[] = ['en', 'ja']
): Promise<TranslatePreviewResponse> {
  const response = await fetch(`${API_V2_BASE}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      product_id: productId,
      target_languages: targetLanguages,
    }),
  });
  return response.json();
}

export async function registerGlobal(
  productId: string,
  targetLanguages: string[] = ['en', 'ja'],
  saveAsDraft: boolean = true
): Promise<RegistrationResult> {
  const response = await fetch(`${API_V2_BASE}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      product_id: productId,
      target_languages: targetLanguages,
      save_as_draft: saveAsDraft,
    }),
  });
  return response.json();
}
```

### 3.3 v2 대시보드 페이지 (app/v2/page.tsx) 핵심 구조

```typescript
// 주요 상태 관리 흐름
// 1. 로그인 상태 확인 → 미인증 시 로그인 폼 표시
// 2. 인증 후 → 작품 목록 로드 (판매중/일시중지 탭)
// 3. 작품 선택 → /v2/product/[id]로 이동
// 4. 일괄 선택 → 일괄 번역+등록 실행

// 컴포넌트 구조:
// <V2Layout>
//   <LoginForm />           ← 미인증 시
//   <ProductListPanel>      ← 인증 후
//     <StatusTabs />         (판매중 | 일시중지)
//     <ProductCard />        (작품 카드, 체크박스 포함)
//     <GlobalStatusBadge />  (미등록/등록 상태)
//   </ProductListPanel>
//   <BatchActionBar />       ← 작품 선택 시 하단에 표시
// </V2Layout>
```

### 3.4 작품 상세 + 번역 미리보기 (app/v2/product/[id]/page.tsx) 핵심 구조

```typescript
// 주요 흐름:
// 1. 작품 ID로 국내 데이터 로드
// 2. "번역 미리보기" 버튼 클릭 → translatePreview API 호출
// 3. 좌측: 국내 원본 / 우측: 번역 결과 (탭: 영어 | 일본어)
// 4. 번역 결과 편집 가능 (인라인 에디터)
// 5. "GB 등록" 버튼 클릭 → registerGlobal API 호출

// 컴포넌트 구조:
// <ProductDetailLayout>
//   <DomesticDataPanel>       ← 좌측: 국내 원본
//     <ProductImageCarousel />
//     <ProductInfoSection />   (작품명, 가격, 카테고리)
//     <DescriptionPreview />   (HTML 렌더링)
//     <OptionsTable />
//   </DomesticDataPanel>
//   <TranslationPanel>         ← 우측: 번역 결과
//     <LanguageTabs />          (영어 | 일본어)
//     <EditableTitle />
//     <EditableDescription />   (HTML 에디터)
//     <EditableKeywords />
//     <EditableOptions />
//     <WarningList />           (품질 경고)
//     <ActionButtons />         (임시저장 | 판매등록)
//   </TranslationPanel>
// </ProductDetailLayout>
```

---

## 4. 구현 시 주의사항

### 4.1 셀렉터 안정성

작가웹의 DOM 구조는 변경될 수 있으므로, 셀렉터 전략:

| 우선순위 | 셀렉터 유형 | 예시 |
|----------|-------------|------|
| 1 | data 속성 | `[data-testid="title-input"]` |
| 2 | aria 속성 | `[aria-label="작품명"]` |
| 3 | 텍스트 기반 | `text=작품명` |
| 4 | 구조적 | `section:has-text("작품명") input` |

실제 구현 시 작가웹 DOM을 다시 상세 조사하여 가장 안정적인 셀렉터를 선택한다.

### 4.2 작품 설명 에디터 처리

작가웹의 작품 설명은 "작품 설명 작성하기" 버튼을 눌러 별도 에디터를 여는 구조이다.
에디터의 내부 구현에 따라 입력 방식이 달라진다.

후보 접근법:
- **contenteditable**: `innerHTML` 직접 설정 + `input` 이벤트 디스패치
- **iframe 에디터**: `page.frame()` 사용하여 iframe 내부 DOM 조작
- **API 직접 호출**: 작가웹의 내부 API를 리버스 엔지니어링하여 직접 호출

### 4.3 에러 복구 전략

| 상황 | 복구 방법 |
|------|-----------|
| 네트워크 타임아웃 | 3회 재시도 후 실패 보고 |
| 세션 만료 | 자동 재로그인 시도 |
| 폼 입력 실패 | 페이지 새로고침 후 재시도 |
| 부분 입력 성공 | 입력된 부분 임시저장 후 실패 필드 보고 |
| Gemini API 오류 | Rate Limit 대기 후 재시도 |

### 4.4 requirements.txt 추가 패키지

```
pydantic-settings>=2.0.0    # config.py에서 사용
```

---

## 5. 테스트 계획

### 5.1 단위 테스트

| 모듈 | 테스트 항목 |
|------|-------------|
| `models/domestic.py` | 모델 생성, 검증, 직렬화 |
| `models/global_product.py` | 모델 생성, 80자 제한 검증 |
| `translator/product_translator.py` | HTML 구조 유지 번역, 키워드 번역 |
| `config.py` | 환경 변수 로딩, 기본값 |

### 5.2 통합 테스트

| 시나리오 | 검증 항목 |
|----------|-----------|
| 로그인 → 작품 목록 조회 | 세션 유지, 목록 정확성 |
| 국내 데이터 추출 | 모든 필드 추출 완전성 |
| 번역 미리보기 | 번역 품질, HTML 유지 |
| 글로벌 탭 입력 | 필드별 입력 정확성 |
| 임시저장 | 저장 후 데이터 유지 |
| 일괄 처리 | 3개 작품 연속 처리 |

### 5.3 E2E 테스트

test 작품(product_id: 7fda9710-76e4-4825-bcf4-ca94fd719f13)을 활용하여
로그인 → 데이터 추출 → 번역 → 글로벌 입력 → 임시저장 전체 과정을 검증한다.

---

> 이 구현 상세 명세서는 GB_INTEGRATION_DESIGN.md 설계안에 기반하며,
> 작가웹(artist.idus.com) 브라우저 탐색에서 확인된 실제 구조를 반영합니다.

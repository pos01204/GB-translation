"""
일본어 번역 프롬프트 템플릿
아이디어스 글로벌 마켓 최적화
"""

JAPANESE_PROMPT = """You are an online seller creating a product description to list your product on idus (아이디어스 in Korean, アイディアス in Japanese), the largest handmade online marketplace in Asia.

Translate the content from Korean to Japanese using the following guidelines.

## 1. Writing Style and Tone
- Use a friendly and warm tone to engage buyers while maintaining the tone and mood of the original content.
- For the seller introduction section, use the title [作家紹介].
- If the artist's name is clear, include it in the format [About XXX] ([XXXについて] in Japanese).
- If the artist's name is not identifiable from the original content, exclude [作家紹介] from the translation.

## 2. Purpose and Context
- Translate all content, including supplementary descriptions (e.g., symbolic meanings, certifications, material significance) unless explicitly prohibited due to cultural relevance.
- Maintain emojis used in the original text in the translation.

## 3. Exclude Content (Korea-specific)
- Korean holidays, seasonal events, and local refund policies
- Pricing in Korean Won (₩ or 원) → Convert specific amounts to "追加料金" instead
- Shipping-related information: 배송기간, 무료배송, 배송비, 배송사, 택배사
- Exchange, refund policies, and shipping lead time information
- Discount and promotion details: 팔로우 쿠폰, 적립금, 추석, 설날, 새해, 발렌타인데이, 화이트데이, 블랙프라이데이, 한정 수량 판매, 타임딜
- If a discount percentage (%) is mentioned, replace it with "特別割引" in Japanese.
- Remove any mentions of receiving event information or coupons by following the artist.

## 4. Production Information
- Include only the production lead time (제작 소요 기간), not the shipping period.
- Production lead time: Time required to make the product ✅ (Include)
- Shipping lead time: Time taken for the product to reach the customer ❌ (Exclude)

## 5. Content Restrictions
- Avoid mentions of: 대량 주문, 많이 살수록 할인, 만원 이상 주문 시 구매 가능, 개별할인, 개인결제, 개별결제
- Do NOT create new content beyond the given source text. Rearrange but do not add new information.

## 6. Platform Terminology
- Sellers are referred to as "artists" (작가 → 作家)
- Products (제품, 상품) should be referred to as "ハンドメイド作品" or "作品", NOT 商品
- Use "・" as a word separator instead of "&"

## 7. Proper Noun & Brand Name Guidelines
- Korean artist names → Transliterate into Japanese phonetics (カタカナ)
- English artist names → Keep in English
- Korean brand names → Write in Japanese phonetics, NOT in English
  Example: 이디엘 → イーディエル (NOT E.D.L)

## 8. Japanese Marketplace Optimization
- Use natural and localized expressions, benchmarking against Minne (ミンネ) and Creema (クリーマ).
- Always add this sentence at the end:
  「もし作品の制作時間や詳細について知りたい場合は、アイディアス(idus)アプリのメッセージ機能を通じてご連絡ください。」

## 9. Final Checklist
- All content is translated from Korean, with no omitted sections unless culturally irrelevant.
- All Korean letters are completely removed.
- Emojis, ASCII art, brackets, and special characters are retained from the original.
- Descriptions follow the tone and style of successful handmade sellers in Japan.

---

Korean Text to Translate:
{text}

---

Japanese Translation:"""


JAPANESE_TITLE_PROMPT = """Translate this Korean product title to Japanese.
Keep it concise and appealing for Japanese handmade marketplace (like Minne, Creema).
Preserve brand names with Japanese phonetics (カタカナ).
Do not add any explanation, just output the translated title.

Korean: {text}

Japanese:"""


JAPANESE_OPTION_PROMPT = """Translate these Korean product options to Japanese.
Keep translations short and clear.
Use Japanese katakana for Korean proper nouns.

Options to translate:
{text}

Japanese translations (one per line):"""

"""
영어 번역 프롬프트 템플릿
아이디어스 글로벌 마켓 최적화
"""

ENGLISH_PROMPT = """You are an online seller creating a product description for idus (아이디어스), the largest handmade online marketplace in Asia.
Sellers are called "artists" on this platform.

Translate the Korean product description into English following this structured format:

## Output Format Example

[About the Artist]
xxxx creates products for home decorations using stained glass techniques with 15 years of experience.

[Item Description]
Stained glass is a traditional technique of glassmaking called soldering by cutting and attaching glass pieces piece by piece.
It's a stained glass lampshade inspired by the curtain, it goes well with various interiors.

[How to Use]
1. Check the components of the lampshade.
2. ...

[Item Details]
- Type: stained glass, home decor
- Color: Green / Brown
- Size: 15cm
- Materials: stained glass, silver, wood
- Components: lampshade, stand base, charger (220v)

[Shipping Information]
International delivery time may vary depending on your location.
On average, delivery takes about 2 weeks after shipping.
For details, please contact via the message function on the idus app.

---

## Translation Guidelines

### Include:
- All product descriptions and features
- Material and craftsmanship details
- Care instructions
- Symbolic meanings and cultural context
- Emojis from original text

### Exclude (Korea-specific content):
- Korean holidays/events (추석, 설날, etc.)
- Prices in Korean Won (₩, 원) → Replace with "additional charges"
- Shipping details: 배송기간, 무료배송, 배송비, 배송사, 택배사
- Exchange and refund policies
- Discount promotions: 팔로우 쿠폰, 적립금, 타임딜
- Percentage discounts (%) → Replace with "Special Discount"

### Section Rules:
- If no relevant content exists for [About the Artist], [How to Use], or [Item Details], skip those sections entirely.
- Do NOT invent information that doesn't exist in the source text.

### Terminology:
- Sellers = "artists" (작가)
- Products = "handmade creations" or "items" (NOT "products" or "goods")
- Use "/" or "・" as separator instead of "&"

### Proper Nouns:
- Korean artist names → Romanize phonetically
- English names → Keep as-is
- Korean brand names → Romanize (do NOT translate)

---

Korean Text to Translate:
{text}

---

English Translation:"""


ENGLISH_TITLE_PROMPT = """Translate this Korean product title to English.
Keep it concise, SEO-friendly, and appealing for international buyers.
Preserve brand names with romanization.
Do not add any explanation, just output the translated title.

Korean: {text}

English:"""


ENGLISH_OPTION_PROMPT = """Translate these Korean product options to English.
Keep translations short and clear.
Romanize Korean proper nouns.

Options to translate:
{text}

English translations (one per line):"""

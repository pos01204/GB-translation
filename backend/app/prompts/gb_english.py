"""
GB 등록용 영어 번역 프롬프트
작가웹 글로벌 탭에 입력할 영어 콘텐츠 생성에 최적화
"""

GB_TITLE_PROMPT_EN = """You are translating a Korean handmade product title for registration
on the global idus marketplace (English).

RULES:
1. Keep it concise and appealing for international buyers
2. Maximum 80 characters
3. Do NOT include brand names or Korean text
4. Use natural English product naming conventions
5. Include key material/style descriptors when helpful
6. Do NOT add quotation marks around the title

Korean title: {text}

English title:"""


GB_DESCRIPTION_PROMPT_EN = """You are translating a Korean handmade product description
for registration on the global idus marketplace (English).

CRITICAL RULES:
1. Preserve ALL HTML tags exactly as they are (<p>, <img>, <br>, <div>, etc.)
2. Only translate the TEXT content inside HTML tags
3. Do NOT translate image URLs or HTML attributes
4. Remove Korea-specific content (Korean won prices, Korean shipping info, Korean holidays)
5. Add at the end: "<p>For production time and details, please contact us via the idus app messaging.</p>"
6. Keep the tone warm and inviting, suitable for international buyers
7. Use "artist" instead of "seller" and "handmade creation" instead of "product" where natural
8. Do NOT include any translator notes or explanations

Korean HTML:
{text}

English HTML (preserve all tags):"""


GB_KEYWORD_PROMPT_EN = """Translate these Korean product keywords to English for the global idus marketplace.
Make them SEO-friendly for international buyers searching on a handmade marketplace.
Output ONLY the translated keywords, one per line, no numbering, no explanations.

Korean keywords:
{text}

English keywords:"""


GB_OPTION_PROMPT_EN = """Translate these Korean product option values to English.
Keep translations concise and standard (e.g., color names, size names).
Output ONLY the translated values, one per line, matching the input order.

Korean option values:
{text}

English option values:"""


GB_DESCRIPTION_REBUILD_PROMPT_EN = """You are creating an English product description for a handmade item
on the global idus marketplace. Create a NEW description from the Korean source data below.

IMPORTANT RULES:
1. Output ONLY HTML. Use <h3> for section headings, <p> for paragraphs
2. Do NOT include any <img> tags — text only, no images
3. Do NOT include Korean text, Korean won prices, or Korea-specific info
4. Structure the description with clear sections for international buyers
5. Tone: warm, artisan-focused (like Etsy listings). Use "artist" not "seller"
6. Include relevant keywords naturally for SEO
7. End with: <p>For production time and details, please contact us via the idus app messaging.</p>

SUGGESTED STRUCTURE:
- <h3>About This Creation</h3> — what makes it special
- <h3>Features</h3> — key selling points
- <h3>Materials & Details</h3> — materials, dimensions, care info
- <h3>Perfect For</h3> — gift ideas, occasions

SOURCE DATA (Korean — use as reference, do NOT translate literally):
{text}

English HTML description (text only, no images):"""


GB_DESCRIPTION_REBUILD_PROMPT_JA = None  # Defined in gb_japanese.py

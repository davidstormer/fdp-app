from unicodedata import normalize


# Roundup Search
def normalize_search_text(text: str) -> str:
    return normalize('NFKD', text or '').encode('ASCII', 'ignore').decode('ASCII')

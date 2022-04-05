import bleach

CUSTOM_TEXT_ALLOWED_TAGS = [
            'a',
            'abbr',
            'acronym',
            'address',
            'b',
            'br',
            'blockquote',
            'em',
            'i',
            'li',
            'ol',
            'p',
            'pre',
            'strong',
            'ul'
        ]


def sanitize_custom_text_html(untrusted_html: str) -> str:
    """Sanitize user submitted text, allowing short-list of html tags for formatting.
    https://bleach.readthedocs.io/en/latest/clean.html#using-bleach-sanitizer-cleaner
    """
    return bleach.clean(
        untrusted_html,
        tags=CUSTOM_TEXT_ALLOWED_TAGS
    )

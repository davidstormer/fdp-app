import bleach

from profiles.models import get_site_setting

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


def global_custom_text_block_context_processor(request) -> dict:
    if request.path.startswith('/admin/'):
        return {}
    elif request.path.startswith('/changing/'):
        return {}
    else:
        return {
            'custom_text_block_global': get_site_setting('custom_text_blocks-global_footer'),
            'custom_text_block_global_right': get_site_setting('custom_text_blocks-global_footer_right'),
        }

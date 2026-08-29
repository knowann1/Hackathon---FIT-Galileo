import gettext
import os
from functools import lru_cache


@lru_cache(maxsize=None)
def get_translator(locale):
    return gettext.translation(
        'messages',
        localedir=os.path.join(os.path.dirname(__file__), 'translations'),
        languages=[locale],
        fallback=True,
    )


def translate(message, locale):
    return get_translator(locale).gettext(message)

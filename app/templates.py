from typing import Any, Dict, Optional
from fastapi import Request
from fastapi.templating import Jinja2Templates
from app.i18n import translate, get_request_lang

templates = Jinja2Templates(directory="app/templates")


def render_template(
    request: Request,
    name: str,
    context: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
):
    """
    Renders a template while injecting internationalization helpers,
    the active language code, and language metadata into the Jinja2 context.
    """
    ctx = context.copy() if context else {}
    lang = get_request_lang(request)

    ctx.setdefault("current_lang", lang)
    ctx.setdefault("_", lambda k, **kw: translate(k, lang=lang, **kw))
    ctx.setdefault("t", lambda k, **kw: translate(k, lang=lang, **kw))
    ctx.setdefault(
        "languages",
        [
            {"code": "en", "label": "English", "flag": "🇬🇧"},
            {"code": "bn", "label": "বাংলা", "flag": "🇧🇩"},
        ],
    )

    return templates.TemplateResponse(
        request=request,
        name=name,
        context=ctx,
        status_code=status_code,
    )

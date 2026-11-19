from typing import Any, Dict, Optional
from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def render_template(
    request: Request,
    name: str,
    context: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
):
    ctx = context.copy() if context else {}
    return templates.TemplateResponse(
        request=request,
        name=name,
        context=ctx,
        status_code=status_code,
    )

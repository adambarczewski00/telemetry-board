from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from starlette.templating import Jinja2Templates


TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


router = APIRouter(prefix="/ui", tags=["ui"])


@router.get("/")
def overview(request: Request):
    return templates.TemplateResponse("overview.html", {"request": request})


@router.get("/assets/{symbol}")
def asset_detail(symbol: str, request: Request):
    return templates.TemplateResponse(
        "asset.html", {"request": request, "symbol": symbol.upper()}
    )


@router.get("/alerts")
def alerts_page(request: Request):
    return templates.TemplateResponse("alerts.html", {"request": request})


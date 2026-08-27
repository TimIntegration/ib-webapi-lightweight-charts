import json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from .config import IB_GATEWAY_URL, IB_GATEWAY_WS, TEST_CONID, futures_base_conid



app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')

# Allow frontend (JS) to fetch data from backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()
app.include_router(router)
from .routers.conids import router as conids_router, get_futures_conid
app.include_router(conids_router)
from .routers.charts import router as charts_router, stream_from_ibkr
app.include_router(charts_router)
from .routers.orders import router as orders_router, _get_option_expirations
app.include_router(orders_router)


@router.get("/", response_class=HTMLResponse)
async def get_index(request: Request, conid: str = TEST_CONID):
    print("rendering index page")
    """Serves the main charting page."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request, "conid": conid},
    )



@app.get("/stream")
async def stream(request: Request, conid: str = TEST_CONID):
    """Server-Sent Events endpoint that forwards live candles from IBKR to the browser."""
    conid = request.query_params.get("conid", conid)

    async def event_generator():
        try:
            async for event in stream_from_ibkr(conid, timeout_seconds=30):
                if await request.is_disconnected():
                    break
                yield {"data": event}
        except Exception as exc:
            print(f"/stream error: {exc}")
            yield {"data": json.dumps({"type": "error", "message": str(exc)})}

    return EventSourceResponse(event_generator())


@router.get('/get-conids')
async def list_conids_for_symbol(request: Request, symbol: str = 'ES'):
    underlyingConid, conids = await get_futures_conid(symbol)
    return templates.TemplateResponse(
        request,
        "conid-table.html",
        {
            "request": request,
            "symbol": symbol,
            "underlyingConid": underlyingConid,
            "conids": conids,
        },
    )


@router.get('/fillConIDsInputs')
async def get_baseconid_and_front_month_conid(request: Request = None, symbol: Optional[str] = 'ES'):
    """Fetches baseConid and conid for the requested symbol using get_futures_conid."""
    underlying_conid, conids = await get_futures_conid(symbol)

    front_month_conid = None
    if conids and len(conids) > 0 and isinstance(conids[0], dict):
        front_month_conid = next(iter(conids[0].values()), None)

    return {
        "baseConid": str(underlying_conid) if underlying_conid is not None else "",
        "front_month_conid": str(front_month_conid) if front_month_conid is not None else ""
    }


@router.get('/get-expiration')
async def get_option_expirations(
    symbol: str = 'ES',
    sec_type: Optional[str] = None
) -> tuple[Optional[str], list[str]]:
    """Returns list of FOP/OPT expirations as (conid, months)."""
    base_conid, months, _, _ = await _get_option_expirations(symbol=symbol, sec_type=sec_type)
    print(f"{months}")
    return base_conid, months





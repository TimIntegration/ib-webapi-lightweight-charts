import json
from pathlib import Path
from fastapi import FastAPI
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from .config import IB_GATEWAY_URL, IB_GATEWAY_WS, TARGET_CONID
from .routers.conids import router as conids_router
from sse_starlette.sse import EventSourceResponse


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
app.include_router(conids_router)
from .routers.charts import router as charts_router, stream_from_ibkr
app.include_router(charts_router)


@router.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    print("rendering index page")
    """Serves the main charting page."""
    return templates.TemplateResponse(request, "index.html", {"request": request})



@app.get("/stream")
async def stream(request: Request):
    """Server-Sent Events endpoint that forwards live candles from IBKR to the browser."""
    conid = request.query_params.get("conid", TARGET_CONID)

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


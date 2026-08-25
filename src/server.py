import os
import httpx
import json
import time
import ssl
import websockets
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

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

@router.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    print("rendering index page")
    """Serves the main charting page."""
    return templates.TemplateResponse(request, "index.html", {"request": request})


app.include_router(router)

IB_GATEWAY_URL = "https://localhost:5000/v1/api"
IB_GATEWAY_WS = "wss://localhost:5000/v1/api/ws"

futures_FUT_conid = {
    # change " to ' e.g. "ES" to 'ES' 
    'ES': '515416632',  # E-mini S&P 500
    'NQ': '11004958',  # E-mini Nasdaq 100
    'GC': '17340718',  # Gold
    'CL': '17340715',  # Crude Oil
    'AAPL': '265598'  # for testing
}

TARGET_CONID = futures_FUT_conid.get('ES')



@app.get("/api/historical")
async def get_historical_bars(conid: str = TARGET_CONID, period: str = "1w", bar_size: str = "5min"):
    """Queries IBKR Gateway for historical data and reformats for TradingView."""
    params = {
        "conid": conid,
        "period": period,       # Options: {Xmin, Xh, Xd, Xw, Xm, Xy}
        "bar": bar_size,        # Candle resolution
        "outsideRth": "true", # Include extended hours
        "barType": "last"     # {last, midprice, bid, ask}
    }
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            # Hit the Client Portal historical data service (hmds) endpoint
            response = await client.get(f"{IB_GATEWAY_URL}/iserver/marketdata/history", params=params)
            ib_data = response.json()
            
            formatted_bars = []
            # IBKR web API wraps historical items inside data array
            if "data" in ib_data:
                for bar in ib_data["data"]:
                    # IBKR 't' timestamp is returned in milliseconds. 
                    # TradingView Lightweight Charts requires seconds.
                    formatted_bars.append({
                        "time": int(bar["t"] / 1000),
                        "open": bar["o"],
                        "high": bar["h"],
                        "low": bar["l"],
                        "close": bar["c"]
                    })
            return formatted_bars
        except Exception as e:
            return {"error": f"Failed to retrieve history: {str(e)}"}



def _parse_tick(tick_data: dict) -> dict:
    '''Extract datetime and price'''
    if "31" not in tick_data:
        return None

    try:
        time_stamp = int(tick_data.get('_updated', int(time.time())))
        last_price = float(tick_data["31"])
    except (TypeError, ValueError):
        return None

    return {
        'time': time_stamp,
        'close': last_price
    }



current_bar = {"time": None, "open": None, "high": None, "low": None, "close": None}


def _aggregate_ticks_to_bars(timestamp, last_price):
    """Converts an IBKR tick into a 1-minute OHLC bar expected by the chart."""
    global current_bar

    bar_time = int(timestamp // 60) * 60

    if current_bar["time"] != bar_time:
        current_bar = {
            "time": bar_time,
            "open": last_price,
            "high": last_price,
            "low": last_price,
            "close": last_price,
        }
    else:
        current_bar["high"] = max(current_bar["high"], last_price)
        current_bar["low"] = min(current_bar["low"], last_price)
        current_bar["close"] = last_price

    return current_bar


def _extract_bytestring_to_dict(byte_string_message):
    """Convert json bytes or string into dictionary"""
    if isinstance(byte_string_message, dict):
        return byte_string_message
    
    # Convert bytes to string if needed
    if isinstance(byte_string_message, bytes):
        try:
            byte_string_message = byte_string_message.decode('utf-8')
        except (UnicodeDecodeError, AttributeError):
            return None
    
    # Parse JSON string
    if isinstance(byte_string_message, str):
        try:
            return json.loads(byte_string_message)
        except json.JSONDecodeError:
            return None
    
    return None


async def stream_from_ibkr(conid: str = TARGET_CONID, timeout_seconds: int = 15):
    """Streams live IBKR data and yields candles, or a heartbeat/status update if only heartbeats arrive."""
    topic = f"smd+{conid}"
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    deadline = time.monotonic() + timeout_seconds

    try:
        async with websockets.connect(IB_GATEWAY_WS, ssl=ssl_context) as websocket_connection:
            await asyncio.sleep(3)
            await websocket_connection.send(f'smd+{conid}+{{"fields":["31"]}}')

            async for message in websocket_connection:
                if time.monotonic() > deadline:
                    yield json.dumps({"type": "status", "message": "No valid IBKR realtime data received before timeout"})
                    break

                print(f"[Raw message] {message}")
                data = _extract_bytestring_to_dict(message)
                if data is None:
                    print("[Warning] Failed to parse message")
                    continue

                if isinstance(data, dict) and (data.get("topic") == topic or "31" in data):
                    tick = _parse_tick(data)
                    print(f"[IBKR WS] processed tick: {tick}")
                    if tick is not None:
                        yield json.dumps({"type": "tick", "message": tick})
                    candle = _aggregate_ticks_to_bars(tick.get('time'), tick.get('close'))
                    print(f"[IBKR WS] processed candle: {candle}")
                    if candle is not None:
                        yield json.dumps({"type": "candle", "message": candle})
                else:
                    # Yield heartbeat/debug info for non-candle messages
                    yield json.dumps({"type": "status", "message": data})
    except Exception as exc:
        print(f"Streaming Error: {exc}")
        yield json.dumps({"type": "error", "message": str(exc)})





from sse_starlette.sse import EventSourceResponse

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


async def get_futures_conid(symbol: str = 'ES') -> list[dict]:
    """Returns the conid for a given futures symbol."""
    endpoint = f"/trsrv/futures?symbols={symbol}"

    async with httpx.AsyncClient(verify=False) as client:
        try:
            # Hit the Client Portal historical data service (hmds) endpoint
            response = await client.get(f"{IB_GATEWAY_URL}{endpoint}")
            if response.status_code == 200:
                data = response.json()
                data_dict = _extract_bytestring_to_dict(data)
                conids = [
                    {contract.get('expirationDate'): contract.get('conid')} for contract in data_dict.get(symbol)]
                return conids
        except Exception as e:
            print(f"Error fetching conid for {symbol}: {str(e)}")


@app.get('/get-conids')
async def list_conids_for_symbol(symbol: str = 'ES'):
    list_of_dict_exp_to_conid = await get_futures_conid(symbol)
    return list_of_dict_exp_to_conid
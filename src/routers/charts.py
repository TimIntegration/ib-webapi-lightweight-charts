import httpx
import json, time, asyncio, websockets, ssl
from fastapi import APIRouter
from .. import utils
from ..config import TEST_CONID, IB_GATEWAY_URL, IB_GATEWAY_WS

router = APIRouter()


@router.get("/api/historical")
async def get_historical_bars(conid: str = TEST_CONID, period: str = "1w", bar_size: str = "5min"):
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
            
            # IBKR web API wraps historical items inside data array.
            formatted_bars = [
                {
                    "time": int(bar["t"] / 1000),
                    "open": bar["o"],
                    "high": bar["h"],
                    "low": bar["l"],
                    "close": bar["c"]
                }
                for bar in ib_data.get("data", [])
            ]
            return formatted_bars
        except Exception as e:
            return {"error": f"Failed to retrieve history: {str(e)}"}



def _parse_tick(tick_data: dict) -> dict:
    '''Extract datetime and price'''
    if "31" not in tick_data:
        return None

    try:
        time_stamp = int(tick_data.get('_updated', int(time.time())))
        price = tick_data["31"]
        if isinstance(price, str) and price.startswith("C"):
            price = price[1:]
        last_price = float(price)
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





async def stream_from_ibkr(conid: str = TEST_CONID, timeout_seconds: int = 15):
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
                data = utils._extract_bytestring_to_dict(message)
                if data is None:
                    print("[Warning] Failed to parse message")
                    continue

                if isinstance(data, dict) and (data.get("topic") == topic or "31" in data):
                    tick = _parse_tick(data)
                    print(f"[IBKR WS] processed tick: {tick}")
                    if tick is None:
                        print("[Warning] Failed to parse market-data tick")
                        continue

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

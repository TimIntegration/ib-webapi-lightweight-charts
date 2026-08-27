Description: Examples of using Interactive Brokers Web API. Using FastAPI and Lightweight Charts. Think of this as a continuation of [simpler examples](https://github.com/TimIntegration/ibweb), refer to that README.md for instruction on how to run the IB Web API Gateway defined in the Dockerfile.

Instructions:
1. Install dependencies
```
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```
2. Start the IB Web API gateway and authenticate on localhost:5000
3. Run the examples
```
uvicorn src.server:app --reload --port 8000
```

Open the dashboard at `http://localhost:8000/`. The FastAPI server uses plain HTTP;
using `https://localhost:8000/` causes Uvicorn to report `Invalid HTTP request received`.

## Live stream sequence

```mermaid
sequenceDiagram
	participant Browser
	participant FastAPI as FastAPI /stream
	participant Generator as event_generator()
	participant Stream as stream_from_ibkr()
	participant IBKR as IBKR Gateway WebSocket
	participant Chart as Lightweight Chart

	Browser->>FastAPI: GET /stream?conid=...
	FastAPI->>Generator: Create SSE event generator
	FastAPI-->>Browser: Open SSE response
	Generator->>Stream: Iterate live events
	Stream->>IBKR: Connect over WSS
	Stream->>IBKR: Subscribe to market data field 31

	loop Until disconnect or timeout
		IBKR-->>Stream: Tick, heartbeat, or status message
		Stream->>Stream: Parse incoming JSON
		alt Valid market-data tick
			Stream->>Stream: Parse tick and aggregate OHLC bar
			Stream-->>Generator: tick event
			Generator-->>Browser: SSE JSON tick
			Stream-->>Generator: candle event
			Generator-->>Browser: SSE JSON candle
			Browser->>Chart: Update candle and last-price badge
		else Heartbeat or other message
			Stream-->>Generator: status event
			Generator-->>Browser: SSE JSON status
		end
	end

	alt Browser disconnects
		Generator->>Generator: Stop forwarding events
	else Stream error
		Stream-->>Generator: error event
		Generator-->>Browser: SSE JSON error
	end
```
let chart = null;
let candleSeries = null;
let eventSource = null;

const chartOptions = {
    // width: container.clientWidth,
    height: 500,
    layout: {
        background: { color: '#151924' },
        textColor: '#848e9c',
        fontFamily: "'Inter', sans-serif"
    },
    grid: {
        vertLines: { color: '#2a2e3d' },
        horzLines: { color: '#2a2e3d' }
    },
    crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal
    },
    rightPriceScale: {
        borderColor: '#2a2e3d'
    },
    timeScale: {
        borderColor: '#2a2e3d',
        timeVisible: true,
        secondsVisible: false
    }
};

const candleOptions = {
    upColor: '#0ecb81',
    downColor: '#f6465d',
    borderUpColor: '#0ecb81',
    borderDownColor: '#f6465d',
    wickUpColor: '#0ecb81',
    wickDownColor: '#f6465d'
};

function initChart() {
    const container = document.getElementById('chart');
    chart = LightweightCharts.createChart(container, chartOptions);

    // Use the newer addCandlestickSeries method if available, otherwise fallback to addSeries with CandlestickSeries
    if (typeof chart.addCandlestickSeries === 'function') {
        candleSeries = chart.addCandlestickSeries(candleOptions);
    } else if (typeof chart.addSeries === 'function' && LightweightCharts && LightweightCharts.CandlestickSeries) {
        candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, candleOptions);
    }

    window.addEventListener('resize', () => {
        if (chart && container) {
            chart.applyOptions({ width: container.clientWidth });
        }
    });
}

async function loadChart() {
    const loadingEl = document.getElementById('loading');
    if (loadingEl) {
        loadingEl.style.opacity = '1';
        loadingEl.style.pointerEvents = 'all';
    }

    try {
        const conid = document.getElementById('conid').value.trim();
        const apiUrl = `${window.location.origin}/api/historical?conid=${encodeURIComponent(conid)}`;
        startStream(conid);
        const response = await fetch(apiUrl);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const historicalData = await response.json();

        if (!chart) {
            initChart();
        }

        if (Array.isArray(historicalData) && historicalData.length > 0) {
            candleSeries.setData(historicalData);
            chart.timeScale().fitContent();
        }
    } catch (err) {
        console.error("Error loading chart data:", err);
    } finally {
        if (loadingEl) {
            setTimeout(() => {
                loadingEl.style.opacity = '0';
                loadingEl.style.pointerEvents = 'none';
            }, 300);
        }
    }
}

function applyStreamCandle(event) {
    if (!event || !event.data) {
        return;
    }

    if (!chart) {
        initChart();
    }

    const payload = JSON.parse(event.data);
    const candle = payload.message || payload;

    if (!candle || candle.time == null || candle.close == null) {
        return;
    }

    candleSeries.update(candle);

    const badge = document.getElementById('priceBadge');
    if (badge) {
        badge.innerHTML = `<span class="badge-dot"></span> Last: ${Number(candle.close).toFixed(2)}`;
    }
}

function startStream(conid) {
    if (eventSource) {
        eventSource.close();
    }

    const streamUrl = `/stream?conid=${encodeURIComponent(conid)}`;
    eventSource = new EventSource(streamUrl);
    eventSource.addEventListener("message", (event) => {
        const payload = JSON.parse(event.data);
        if (payload && payload.type === 'candle') {
            applyStreamCandle({ data: JSON.stringify(payload) });
        }
    });

    eventSource.addEventListener("error", (event) => { console.error('SSE Error:', event); });
    eventSource.addEventListener("open", () => { console.log('SSE Connection Opened'); });
}

function cleanupConnections() {
    if (eventSource) {
        console.log('Closing EventSource connection');
        eventSource.close();
        eventSource = null;
    }
}

window.addEventListener('beforeunload', cleanupConnections);
window.addEventListener('pagehide', cleanupConnections);

document.addEventListener('DOMContentLoaded', () => {
    loadChart();
});


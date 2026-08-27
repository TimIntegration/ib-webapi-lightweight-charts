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
            return historicalData[historicalData.length - 1];
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

async function loadChartAndPrices() {
    const lastBar = await loadChart();
    if (lastBar && lastBar.close !== undefined) {
        const lastPrice = lastBar.close;
        const longEntry = document.getElementById('long-entry');
        const shortEntry = document.getElementById('short-entry');
        if (longEntry) {
            longEntry.value = lastPrice;
        }
        if (shortEntry) {
            shortEntry.value = lastPrice;
        }
    }
    await getExpirations();
    await getStrikes();
}

async function getExpirations() {
    const symbolInput = document.getElementById('symbol');
    const symbol = symbolInput ? symbolInput.value.trim() : 'ES';
    if (!symbol) return [];

    try {
        const response = await fetch(`/get-expiration?symbol=${encodeURIComponent(symbol)}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        let expirations = [];

        if (Array.isArray(data)) {
            if (data.length === 2 && Array.isArray(data[1])) {
                expirations = data[1];
            } else if (data.every(item => typeof item === 'string')) {
                expirations = data;
            }
        } else if (data && Array.isArray(data.months)) {
            expirations = data.months;
        } else if (data && Array.isArray(data.expirations)) {
            expirations = data.expirations;
        }

        const expirationSelects = document.querySelectorAll('select.Expiration, select[name="Expiration"], .Expiration select');
        expirationSelects.forEach(select => {
            select.innerHTML = '';
            expirations.forEach(exp => {
                const option = document.createElement('option');
                option.value = exp;
                option.textContent = exp;
                select.appendChild(option);
            });
            select.onchange = () => getStrikes();
        });

        const rightSelects = document.querySelectorAll('select[class="Right"], select[name="Right"], .Right select');
        rightSelects.forEach(select => {
            select.onchange = () => getStrikes();
        });

        return expirations;
    } catch (err) {
        console.error("Error getting expirations:", err);
        return [];
    }
}

async function getStrikes(symbol, month, right) {
    const symbolInput = document.getElementById('symbol');
    const currentSymbol = symbol || (symbolInput ? symbolInput.value.trim() : 'ES') || 'ES';
    if (!currentSymbol) return [];

    const monthSelect = document.querySelector('select.Expiration, select[name="Expiration"], .Expiration select');
    const currentMonth = month || (monthSelect ? monthSelect.value : '');

    const rightSelect = document.querySelector('select[class="Right"], select[name="Right"], .Right select');
    const currentRight = right || (rightSelect ? rightSelect.value : 'C');

    const params = new URLSearchParams();
    params.append('symbol', currentSymbol);
    if (currentMonth) {
        params.append('month', currentMonth);
    }
    if (currentRight) {
        params.append('right', currentRight);
    }

    try {
        const response = await fetch(`/get-strikes?${params.toString()}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        let strikes = [];

        if (Array.isArray(data)) {
            strikes = data;
        } else if (data && Array.isArray(data.call)) {
            strikes = data.call;
        } else if (data && Array.isArray(data.put)) {
            strikes = data.put;
        } else if (data && Array.isArray(data.strikes)) {
            strikes = data.strikes;
        }

        // Find the strike closest to input#long-entry value
        const longEntryEl = document.getElementById('long-entry');
        const targetPrice = longEntryEl && longEntryEl.value ? parseFloat(longEntryEl.value) : null;
        let closestStrike = null;

        if (targetPrice !== null && !isNaN(targetPrice) && strikes.length > 0) {
            closestStrike = strikes.reduce((prev, curr) => {
                return Math.abs(Number(curr) - targetPrice) < Math.abs(Number(prev) - targetPrice) ? curr : prev;
            }, strikes[0]);
        }

        const strikeSelects = document.querySelectorAll('select.Strikes, select[name="Strikes"], .Strikes select');
        strikeSelects.forEach(select => {
            select.innerHTML = '';
            strikes.forEach(strike => {
                const option = document.createElement('option');
                option.value = strike;
                option.textContent = strike;
                if (closestStrike !== null && String(strike) === String(closestStrike)) {
                    option.selected = true;
                }
                select.appendChild(option);
            });
            if (closestStrike !== null) {
                select.value = closestStrike;
            }
        });

        return strikes;
    } catch (err) {
        console.error("Error getting strikes:", err);
        return [];
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
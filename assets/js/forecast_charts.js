/**
 * Rosario Dairy — Forecast Dashboard Charts
 * Fixed version — matches actual API response format
 */

const COLORS = {
    milk:      { border: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
    yogurt:    { border: '#8b5cf6', bg: 'rgba(139,92,246,0.15)' },
    cheese:    { border: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
    butter:    { border: '#f97316', bg: 'rgba(249,115,22,0.15)' },
    ice_cream: { border: '#ec4899', bg: 'rgba(236,72,153,0.15)' },
};

// Store chart instances to destroy before re-rendering
const chartInstances = {};

function destroyChart(id) {
    if (chartInstances[id]) {
        chartInstances[id].destroy();
        delete chartInstances[id];
    }
}

// ── 1. Top Products Bar Chart (7-Day Forecast) ───────────
async function renderTopProductsChart(canvasId) {
    try {
        const res  = await fetch('../api/get_forecast.php');
        const json = await res.json();

        if (json.status !== 'success' || !json.data || json.data.length === 0) {
            document.getElementById(canvasId).parentElement.innerHTML +=
                '<p class="text-muted text-center mt-3">No forecast data available. Please run the forecast first.</p>';
            return;
        }

        const data     = json.data.slice(0, 10);
        const labels   = data.map(d => d.product_name);
        const values   = data.map(d => parseFloat(d.total_forecast_7d) || 0);
        const bgColors = data.map(d => COLORS[d.category]?.border || '#6b7280');

        destroyChart(canvasId);
        const ctx = document.getElementById(canvasId).getContext('2d');
        chartInstances[canvasId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label:           'Forecasted Units (7 days)',
                    data:            values,
                    backgroundColor: bgColors,
                    borderRadius:    6,
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: { display: false },
                    title:  {
                        display: true,
                        text:    `Top Products by Forecasted Demand (${json.forecast_start} to ${json.forecast_end})`
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        title: { display: true, text: 'Forecasted Units' }
                    }
                }
            }
        });

    } catch (err) {
        console.error('renderTopProductsChart error:', err);
    }
}

// ── 2. 30-Day Forecast Line Chart ─────────────────────────
async function renderForecastChart(canvasId, productId) {
    try {
        const res  = await fetch(`../api/get_forecast.php?product_id=${productId}&days=30`);
        const json = await res.json();

        if (json.status !== 'success' || !json.data || json.data.length === 0) {
            console.warn('No forecast data for product', productId);
            return;
        }

        const data     = json.data;
        const labels   = data.map(d => d.forecast_date);
        const category = data[0].category;
        const col      = COLORS[category] || COLORS.milk;

        destroyChart(canvasId);
        const ctx = document.getElementById(canvasId).getContext('2d');
        chartInstances[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label:           'Predicted Demand',
                        data:            data.map(d => parseFloat(d.predicted_quantity) || 0),
                        borderColor:     col.border,
                        backgroundColor: col.bg,
                        borderWidth:     2.5,
                        fill:            true,
                        tension:         0.4,
                        pointRadius:     3,
                    },
                    {
                        label:       'Upper 95% CI',
                        data:        data.map(d => parseFloat(d.upper_bound_95) || 0),
                        borderColor: 'rgba(150,150,150,0.4)',
                        borderWidth: 1,
                        borderDash:  [4, 4],
                        fill:        false,
                        pointRadius: 0,
                    },
                    {
                        label:           'Lower 95% CI',
                        data:            data.map(d => parseFloat(d.lower_bound_95) || 0),
                        borderColor:     'rgba(150,150,150,0.4)',
                        borderWidth:     1,
                        borderDash:      [4, 4],
                        fill:            '-1',
                        backgroundColor: 'rgba(150,150,150,0.08)',
                        pointRadius:     0,
                    }
                ]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    title:  {
                        display: true,
                        text:    `30-Day Demand Forecast — ${data[0].product_name}`
                    },
                    tooltip: {
                        callbacks: {
                            label: ctx => `${ctx.dataset.label}: ${parseFloat(ctx.raw).toFixed(1)} units`
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { maxRotation: 45, font: { size: 11 } },
                        grid:  { color: 'rgba(0,0,0,0.05)' }
                    },
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Units' }
                    }
                }
            }
        });

    } catch (err) {
        console.error('renderForecastChart error:', err);
    }
}

// ── 3. Inventory Risk Doughnut Chart ─────────────────────
async function renderInventoryRiskChart(canvasId) {
    try {
        const res  = await fetch('../api/get_recommendations.php');
        const json = await res.json();

        if (json.status !== 'success') return;

        const s = json.summary;
        destroyChart(canvasId);
        const ctx = document.getElementById(canvasId).getContext('2d');
        chartInstances[canvasId] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Critical', 'High', 'Medium', 'Low'],
                datasets: [{
                    data:            [s.critical, s.high, s.medium, s.low],
                    backgroundColor: ['#ef4444', '#f97316', '#eab308', '#22c55e'],
                    borderWidth:     2,
                    borderColor:     '#fff'
                }]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' },
                    title:  { display: true, text: 'Inventory Risk Distribution' }
                }
            }
        });

    } catch (err) {
        console.error('renderInventoryRiskChart error:', err);
    }
}

// ── 4. Stock vs Demand Comparison Bar Chart ──────────────
async function renderStockVsDemandChart(canvasId) {
    try {
        const res  = await fetch('../api/get_recommendations.php');
        const json = await res.json();

        if (json.status !== 'success' || !json.data || json.data.length === 0) return;

        const data   = json.data.slice(0, 10);
        const labels = data.map(d => d.product_name);

        destroyChart(canvasId);
        const ctx = document.getElementById(canvasId).getContext('2d');
        chartInstances[canvasId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label:           'Current Stock',
                        data:            data.map(d => parseInt(d.current_stock) || 0),
                        backgroundColor: '#3b82f6',
                        borderRadius:    4,
                    },
                    {
                        label:           'Forecasted Demand (7d)',
                        data:            data.map(d => parseFloat(d.forecasted_demand) || 0),
                        backgroundColor: '#f87171',
                        borderRadius:    4,
                    }
                ]
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    title:  { display: true, text: 'Current Stock vs Forecasted Demand (7 days)' }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Units' }
                    }
                }
            }
        });

    } catch (err) {
        console.error('renderStockVsDemandChart error:', err);
    }
}

// ── 5. Alerts Badge ───────────────────────────────────────
async function loadAlertsBadge() {
    try {
        const res  = await fetch('../api/get_alerts.php');
        const json = await res.json();
        if (json.status !== 'success') return;

        const badge = document.getElementById('alerts-badge');
        if (badge && json.count > 0) {
            badge.textContent = json.count;
            badge.classList.remove('d-none');
        }
    } catch (err) {
        console.error('loadAlertsBadge error:', err);
    }
}

// ── Load Product Forecast (called by dropdown) ────────────
async function loadProductForecast(productId) {
    if (!productId) return;

    // Show loading indicator
    const container = document.getElementById('chart-product-forecast');
    if (container) {
        container.style.opacity = '0.4';
    }

    await renderForecastChart('chart-product-forecast', productId);

    // Restore opacity
    if (container) {
        container.style.opacity = '1';
    }
}

// ── Initialize all charts on DOM ready ───────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadAlertsBadge();

    if (document.getElementById('chart-top-products'))
        renderTopProductsChart('chart-top-products');

    if (document.getElementById('chart-inventory-risk'))
        renderInventoryRiskChart('chart-inventory-risk');

    if (document.getElementById('chart-stock-demand'))
        renderStockVsDemandChart('chart-stock-demand');
});
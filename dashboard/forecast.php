<?php
session_start();
require_once '../includes/db.php';

// Get all products for selector
$products = $pdo->query(
    "SELECT product_id, product_name, category FROM products WHERE is_active=1 ORDER BY category, product_name"
)->fetchAll();
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Forecast Dashboard — Rosario Dairy</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
<style>
  body { background: #f8fafc; }
  .card-metric { border-left: 4px solid; transition: transform .2s; }
  .card-metric:hover { transform: translateY(-2px); }
  .urgency-critical { border-left-color: #ef4444 !important; }
  .urgency-high     { border-left-color: #f97316 !important; }
  .urgency-medium   { border-left-color: #eab308 !important; }
  .urgency-low      { border-left-color: #22c55e !important; }
  .chart-container  { position: relative; height: 350px; }
</style>
</head>
<body>
<div class="container-fluid p-4">

  <!-- Header -->
  <div class="d-flex justify-content-between align-items-center mb-4">
    <div>
      <h2 class="fw-bold mb-0">
        <i class="fa fa-chart-line text-primary me-2"></i>Predictive Analytics Dashboard
      </h2>
      <small class="text-muted">Rosario Dairy | SARIMA Demand Forecasting</small>
    </div>
    <button class="btn btn-primary" onclick="runForecast()">
      <i class="fa fa-sync me-1"></i> Run Forecast
    </button>
  </div>

  <!-- KPI Cards Row -->
  <div class="row g-3 mb-4" id="kpi-row">
    <div class="col-md-3">
      <div class="card card-metric urgency-critical p-3">
        <div class="text-danger small fw-semibold">CRITICAL ALERTS</div>
        <div class="fs-2 fw-bold" id="kpi-critical">—</div>
        <div class="text-muted small">Products needing immediate reorder</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="card card-metric urgency-high p-3">
        <div class="text-warning small fw-semibold">HIGH PRIORITY</div>
        <div class="fs-2 fw-bold" id="kpi-high">—</div>
        <div class="text-muted small">Reorder within 1–2 days</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="card card-metric p-3" style="border-left-color:#3b82f6">
        <div class="text-primary small fw-semibold">PRODUCTS FORECASTED</div>
        <div class="fs-2 fw-bold" id="kpi-forecasted">—</div>
        <div class="text-muted small">Active SARIMA models</div>
      </div>
    </div>
    <div class="col-md-3">
      <div class="card card-metric p-3" style="border-left-color:#8b5cf6">
        <div class="text-purple small fw-semibold">EXPIRING SOON</div>
        <div class="fs-2 fw-bold" id="kpi-expiring">—</div>
        <div class="text-muted small">Units expiring within 7 days</div>
      </div>
    </div>
  </div>

  <!-- Charts Row 1 -->
  <div class="row g-3 mb-4">
    <div class="col-lg-8">
      <div class="card p-3">
        <h6 class="fw-semibold mb-2">Top Products — 7-Day Demand Forecast</h6>
        <div class="chart-container">
          <canvas id="chart-top-products"></canvas>
        </div>
      </div>
    </div>
    <div class="col-lg-4">
      <div class="card p-3">
        <h6 class="fw-semibold mb-2">Inventory Risk Distribution</h6>
        <div class="chart-container">
          <canvas id="chart-inventory-risk"></canvas>
        </div>
      </div>
    </div>
  </div>

  <!-- Product Forecast Detail -->
  <div class="row g-3 mb-4">
    <div class="col-12">
      <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h6 class="fw-semibold mb-0">30-Day Product Forecast</h6>
          <select class="form-select form-select-sm w-auto" id="product-selector"
                  onchange="loadProductForecast(this.value)">
            <option value="">— Select Product —</option>
            <?php foreach ($products as $p): ?>
            <option value="<?= $p['product_id'] ?>">
              <?= htmlspecialchars($p['product_name']) ?>
            </option>
            <?php endforeach; ?>
          </select>
        </div>
        <div class="chart-container">
          <canvas id="chart-product-forecast"></canvas>
        </div>
      </div>
    </div>
  </div>

  <!-- Stock vs Demand -->
  <div class="row g-3 mb-4">
    <div class="col-12">
      <div class="card p-3">
        <h6 class="fw-semibold mb-2">Current Stock vs Forecasted Demand</h6>
        <div class="chart-container">
          <canvas id="chart-stock-demand"></canvas>
        </div>
      </div>
    </div>
  </div>

  <!-- Recommendations Table -->
  <div class="card p-3">
    <h6 class="fw-semibold mb-3">Reorder Recommendations</h6>
    <div id="recommendations-table">
      <div class="text-center text-muted py-3">Loading...</div>
    </div>
  </div>

</div><!-- /container -->

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="../assets/js/forecast_charts.js"></script>
<script>
// Load KPI cards
async function loadKPIs() {
    const [recRes, fcRes] = await Promise.all([
        fetch('../api/get_recommendations.php'),
        fetch('../api/get_forecast.php')
    ]);
    const rec = await recRes.json();
    const fc  = await fcRes.json();

    if (rec.status === 'success') {
        document.getElementById('kpi-critical').textContent = rec.summary.critical;
        document.getElementById('kpi-high').textContent     = rec.summary.high;

        const expiring = rec.data.reduce((s, r) => s + parseInt(r.expiring_soon_qty || 0), 0);
        document.getElementById('kpi-expiring').textContent = expiring;
    }
    if (fc.status === 'success') {
        document.getElementById('kpi-forecasted').textContent = fc.data.length;
    }
}

// Load recommendations table
async function loadRecommendationsTable() {
    const res  = await fetch('../api/get_recommendations.php');
    const json = await res.json();
    if (json.status !== 'success') return;

    const urgencyBadge = u => ({
        critical: '<span class="badge bg-danger">Critical</span>',
        high:     '<span class="badge bg-warning text-dark">High</span>',
        medium:   '<span class="badge bg-info text-dark">Medium</span>',
        low:      '<span class="badge bg-success">Low</span>',
    })[u] || u;

    const rows = json.data.map(r => `
        <tr>
          <td><strong>${r.product_name}</strong></td>
          <td>${urgencyBadge(r.urgency_level)}</td>
          <td>${r.current_stock}</td>
          <td>${parseFloat(r.forecasted_demand).toFixed(0)}</td>
          <td><strong class="text-danger">${r.recommended_qty}</strong></td>
          <td>${r.expiring_soon_qty > 0
                ? `<span class="text-warning">${r.expiring_soon_qty} (${r.earliest_expiry})</span>`
                : '<span class="text-success">None</span>'}</td>
          <td class="small text-muted">${r.recommendation_msg.split(' | ').slice(0, 3).join(' ')}</td>
        </tr>
    `).join('');

    document.getElementById('recommendations-table').innerHTML = `
        <div class="table-responsive">
          <table class="table table-sm table-hover">
            <thead class="table-light">
              <tr>
                <th>Product</th><th>Urgency</th><th>Stock</th>
                <th>Forecast (7d)</th><th>Reorder Qty</th>
                <th>Expiring Soon</th><th>Message</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
}

// Load product forecast (with chart instance management)
let productChartInstance = null;
async function loadProductForecast(productId) {
    if (!productId) return;
    if (productChartInstance) {
        productChartInstance.destroy();
        productChartInstance = null;
    }
    // Call chart renderer from forecast_charts.js
    // (modified to return instance)
    await renderForecastChart('chart-product-forecast', productId);
}

// Run forecast trigger
async function runForecast() {
    const btn = document.querySelector('[onclick="runForecast()"]');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Running...';

    try {
        const res  = await fetch('../api/run_forecast.php');
        const json = await res.json();
        alert(json.status === 'success'
            ? '✅ Forecast updated successfully!'
            : '❌ Error: ' + json.message);
        if (json.status === 'success') location.reload();
    } catch (e) {
        alert('❌ Network error: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa fa-sync me-1"></i> Run Forecast';
    }
}

// Init
loadKPIs();
loadRecommendationsTable();
</script>
</body>
</html>
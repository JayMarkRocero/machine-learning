<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

$host = 'localhost';
$user = 'root';
$pass = '';
$db   = 'rosario_dairy';

try {
    $pdo = new PDO(
        "mysql:host=$host;dbname=$db;charset=utf8mb4",
        $user, $pass,
        [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]
    );
} catch (PDOException $e) {
    echo json_encode(['status' => 'error', 'message' => $e->getMessage()]);
    exit;
}

try {
    // Get forecast date range
    $dateRow   = $pdo->query("
        SELECT MIN(forecast_date) AS start_date
        FROM forecast_results
        WHERE is_latest = 1
    ")->fetch();

    $startDate = $dateRow['start_date'] ?? date('Y-m-d');
    $endDate   = date('Y-m-d', strtotime($startDate . ' +7 days'));

    // Get all recommendations
    $products = $pdo->query("
        SELECT
            rr.recommendation_id,
            rr.product_id,
            p.product_name,
            p.category,
            rr.current_stock,
            rr.recommended_qty,
            rr.urgency_level,
            rr.earliest_expiry,
            rr.expiring_soon_qty,
            rr.recommendation_msg,
            rr.generated_on
        FROM reorder_recommendations rr
        JOIN products p ON rr.product_id = p.product_id
        WHERE rr.status = 'pending'
        ORDER BY
            FIELD(rr.urgency_level, 'critical','high','medium','low'),
            rr.recommended_qty DESC
    ")->fetchAll();

    // Get forecast demand per product separately (avoids HY093 duplicate param error)
    $forecastStmt = $pdo->prepare("
        SELECT ROUND(SUM(predicted_quantity), 0) AS total_demand
        FROM forecast_results
        WHERE product_id = ?
          AND is_latest  = 1
          AND forecast_date BETWEEN ? AND ?
    ");

    $rows = [];
    foreach ($products as $row) {
        $forecastStmt->execute([$row['product_id'], $startDate, $endDate]);
        $fRow = $forecastStmt->fetch();
        $row['forecasted_demand'] = $fRow['total_demand'] ?? 0;
        $rows[] = $row;
    }

    // Count by urgency
    $summary = ['critical' => 0, 'high' => 0, 'medium' => 0, 'low' => 0];
    foreach ($rows as $r) {
        if (isset($summary[$r['urgency_level']])) {
            $summary[$r['urgency_level']]++;
        }
    }

    echo json_encode([
        'status'         => 'success',
        'forecast_start' => $startDate,
        'forecast_end'   => $endDate,
        'summary'        => $summary,
        'count'          => count($rows),
        'data'           => $rows
    ]);

} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['status' => 'error', 'message' => $e->getMessage()]);
}
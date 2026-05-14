<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
require_once '../includes/db.php';

$product_id = isset($_GET['product_id']) ? (int)$_GET['product_id'] : null;
$days       = isset($_GET['days']) ? min((int)$_GET['days'], 30) : 30;

try {
    if ($product_id) {
        // ── Single product: get 30-day forecast ──────────
        // First try from today forward
        $stmt = $pdo->prepare("
            SELECT
                fr.forecast_date,
                fr.predicted_quantity,
                fr.lower_bound_95,
                fr.upper_bound_95,
                fr.mae, fr.rmse, fr.mape,
                p.product_name, p.category
            FROM forecast_results fr
            JOIN products p ON fr.product_id = p.product_id
            WHERE fr.product_id = :pid
              AND fr.is_latest  = 1
            ORDER BY fr.forecast_date ASC
            LIMIT :days
        ");
        $stmt->bindValue(':pid',  $product_id, PDO::PARAM_INT);
        $stmt->bindValue(':days', $days,       PDO::PARAM_INT);
        $stmt->execute();
        $rows = $stmt->fetchAll();

        echo json_encode([
            'status' => 'success',
            'count'  => count($rows),
            'data'   => $rows
        ]);

    } else {
        // ── All products: 7-day summary ──────────────────
        // Get the forecast window (use whatever dates are stored)
        $stmt = $pdo->query("
            SELECT MIN(forecast_date) as min_date, MAX(forecast_date) as max_date
            FROM forecast_results
            WHERE is_latest = 1
        ");
        $range = $stmt->fetch();

        if (!$range || !$range['min_date']) {
            echo json_encode([
                'status' => 'success',
                'data'   => [],
                'message' => 'No forecasts found. Please run the forecast first.'
            ]);
            exit;
        }

        $min_date = $range['min_date'];
        $max_date = $range['max_date'];

        // Get first 7 days of whatever forecasts we have
        $stmt = $pdo->prepare("
            SELECT
                fr.product_id,
                p.product_name,
                p.category,
                ROUND(SUM(fr.predicted_quantity), 0)  AS total_forecast_7d,
                ROUND(AVG(fr.predicted_quantity), 1)  AS avg_daily_forecast
            FROM forecast_results fr
            JOIN products p ON fr.product_id = p.product_id
            WHERE fr.is_latest = 1
              AND fr.forecast_date BETWEEN :start
                  AND DATE_ADD(:start, INTERVAL 7 DAY)
            GROUP BY fr.product_id, p.product_name, p.category
            ORDER BY total_forecast_7d DESC
        ");
        $stmt->execute([':start' => $min_date]);
        $rows = $stmt->fetchAll();

        echo json_encode([
            'status'       => 'success',
            'forecast_from' => $min_date,
            'forecast_to'   => $max_date,
            'data'          => $rows
        ]);
    }

} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode([
        'status'  => 'error',
        'message' => $e->getMessage()
    ]);
}
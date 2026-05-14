<?php
header('Content-Type: application/json');
require_once '../includes/db.php';

try {
    // Critical and high urgency alerts
    $stmt = $pdo->query("
        SELECT
            rr.product_id,
            p.product_name,
            p.category,
            rr.urgency_level,
            rr.current_stock,
            rr.recommended_qty,
            rr.expiring_soon_qty,
            rr.earliest_expiry,
            p.reorder_level,
            ROUND(rr.current_stock / NULLIF(
                (SELECT AVG(predicted_quantity)
                 FROM forecast_results fr2
                 WHERE fr2.product_id = rr.product_id
                   AND fr2.is_latest = 1), 0
            ), 1) AS days_coverage
        FROM reorder_recommendations rr
        JOIN products p ON rr.product_id = p.product_id
        WHERE rr.status = 'pending'
          AND rr.urgency_level IN ('critical', 'high')
        ORDER BY FIELD(rr.urgency_level, 'critical', 'high')
    ");
    $alerts = $stmt->fetchAll();

    echo json_encode([
        'status' => 'success',
        'count'  => count($alerts),
        'data'   => $alerts
    ]);

} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['status' => 'error', 'message' => $e->getMessage()]);
}
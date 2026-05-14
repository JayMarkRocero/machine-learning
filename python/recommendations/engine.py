"""
Reorder Recommendation Engine
Compares SARIMA forecasts against FEFO inventory to generate
intelligent reorder recommendations.
"""

import pandas as pd
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine, text


class RecommendationEngine:

    SAFETY_STOCK_DAYS = 3      # buffer days on top of forecast
    HORIZON_DAYS      = 7      # evaluate demand for next 7 days

    # Urgency thresholds (stock coverage in days)
    CRITICAL_THRESHOLD = 2
    HIGH_THRESHOLD     = 4
    MEDIUM_THRESHOLD   = 7

    def __init__(self, engine):
        self.engine = engine

    def get_current_stock(self) -> pd.DataFrame:
        """Get aggregated FEFO stock per product."""
        query = text("""
            SELECT
                i.product_id,
                p.product_name,
                p.category,
                p.reorder_level,
                SUM(i.current_quantity)                              AS total_stock,
                MIN(i.expiry_date)                                   AS nearest_expiry,
                SUM(CASE WHEN DATEDIFF(i.expiry_date, CURDATE()) <= 7
                         THEN i.current_quantity ELSE 0 END)         AS expiring_7days,
                SUM(CASE WHEN i.expiry_date < CURDATE()
                         THEN i.current_quantity ELSE 0 END)         AS already_expired
            FROM inventory i
            JOIN products p ON i.product_id = p.product_id
            WHERE i.batch_status = 'active'
            GROUP BY i.product_id
        """)
        df = pd.read_sql(query, self.engine)
        return df

    def get_forecast_demand(self, horizon_days: int = 7) -> pd.DataFrame:
        """Get total forecasted demand per product for next N days."""
        today = date.today()
        end   = today + timedelta(days=horizon_days)

        query = text("""
            SELECT
                product_id,
                SUM(predicted_quantity) AS forecasted_demand,
                AVG(predicted_quantity) AS avg_daily_demand
            FROM forecast_results
            WHERE is_latest = 1
              AND forecast_date BETWEEN :start AND :end
            GROUP BY product_id
        """)
        df = pd.read_sql(
            query, self.engine,
            params={"start": today, "end": end}
        )
        return df

    def calculate_recommendation(self, row: pd.Series) -> dict:
        """
        Core logic:
        recommended_qty = forecasted_demand + safety_stock - current_stock
        """
        current_stock    = int(row.get("total_stock", 0))
        forecasted_demand = float(row.get("forecasted_demand", 0))
        avg_daily        = float(row.get("avg_daily_demand", 0))
        safety_stock     = int(avg_daily * self.SAFETY_STOCK_DAYS)
        expiring_soon    = int(row.get("expiring_7days", 0))
        nearest_expiry   = row.get("nearest_expiry")

        # Net demand considering expiring stock
        effective_stock  = current_stock - expiring_soon
        effective_stock  = max(0, effective_stock)

        shortfall        = forecasted_demand + safety_stock - effective_stock
        recommended_qty  = max(0, int(shortfall))

        # Days of stock coverage
        coverage_days    = (effective_stock / avg_daily) if avg_daily > 0 else 999

        # Urgency classification
        if coverage_days <= self.CRITICAL_THRESHOLD:
            urgency = "critical"
        elif coverage_days <= self.HIGH_THRESHOLD:
            urgency = "high"
        elif coverage_days <= self.MEDIUM_THRESHOLD:
            urgency = "medium"
        else:
            urgency = "low"

        # Force at least LOW if recommended_qty > 0
        if recommended_qty > 0 and urgency == "low":
            urgency = "medium"

        # Generate human-readable message
        msg = self._build_message(
            row["product_name"],
            forecasted_demand,
            current_stock,
            effective_stock,
            recommended_qty,
            urgency,
            expiring_soon,
            nearest_expiry,
            coverage_days,
            horizon_days=self.HORIZON_DAYS
        )

        return {
            "product_id":        int(row["product_id"]),
            "generated_on":      datetime.now(),
            "current_stock":     current_stock,
            "forecasted_demand": round(forecasted_demand, 2),
            "horizon_days":      self.HORIZON_DAYS,
            "safety_stock":      safety_stock,
            "recommended_qty":   recommended_qty,
            "urgency_level":     urgency,
            "earliest_expiry":   nearest_expiry,
            "expiring_soon_qty": expiring_soon,
            "recommendation_msg": msg
        }

    def _build_message(self, name, demand, stock, eff_stock,
                       rec_qty, urgency, exp_soon,
                       nearest_exp, coverage, horizon_days) -> str:
        lines = [
            f"Predicted demand for {name} over the next {horizon_days} days: "
            f"{demand:.0f} units.",
            f"Current stock: {stock} units."
        ]
        if exp_soon > 0:
            lines.append(
                f"⚠ {exp_soon} units expiring within 7 days "
                f"(earliest: {nearest_exp}). Effective usable stock: {eff_stock} units."
            )
        if rec_qty > 0:
            lines.append(f"Recommended reorder quantity: {rec_qty} units.")
        else:
            lines.append("Stock is sufficient. No reorder needed at this time.")

        urgency_labels = {
            "critical": "🔴 CRITICAL — Immediate reorder required.",
            "high":     "🟠 HIGH — Reorder within 1–2 days.",
            "medium":   "🟡 MEDIUM — Reorder within the week.",
            "low":      "🟢 LOW — Stock level adequate."
        }
        lines.append(urgency_labels.get(urgency, ""))
        lines.append(f"Estimated stock coverage: {coverage:.1f} days.")
        return " | ".join(lines)

    def generate_all_recommendations(self):
        """Generate and save recommendations for all products."""
        stock_df    = self.get_current_stock()
        forecast_df = self.get_forecast_demand(self.HORIZON_DAYS)

        merged = stock_df.merge(forecast_df, on="product_id", how="left")
        merged["forecasted_demand"] = merged["forecasted_demand"].fillna(0)
        merged["avg_daily_demand"]  = merged["avg_daily_demand"].fillna(0)

        recs = [self.calculate_recommendation(row) for _, row in merged.iterrows()]

        # Save to DB
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE reorder_recommendations SET status = 'dismissed' "
                "WHERE status = 'pending'"
            ))
            for r in recs:
                conn.execute(text("""
                    INSERT INTO reorder_recommendations
                      (product_id, generated_on, current_stock,
                       forecasted_demand, horizon_days, safety_stock,
                       recommended_qty, urgency_level, earliest_expiry,
                       expiring_soon_qty, recommendation_msg)
                    VALUES
                      (:product_id, :generated_on, :current_stock,
                       :forecasted_demand, :horizon_days, :safety_stock,
                       :recommended_qty, :urgency_level, :earliest_expiry,
                       :expiring_soon_qty, :recommendation_msg)
                """), r)

        print(f"  ✓ Generated {len(recs)} recommendations")
        return recs
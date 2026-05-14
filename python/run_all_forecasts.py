import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
import pandas as pd
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine, text

# Add parent directory to path for imports
sys.path.insert(0, 'C:/xampp/htdocs/SARIMA ML/python')

from forecasting.preprocessor import DataPreprocessor
from forecasting.sarima_model  import SARIMAForecaster
from recommendations.engine    import RecommendationEngine

DB_URL           = "mysql+pymysql://root:@localhost:3306/rosario_dairy"
FORECAST_HORIZON = 30  # days


def run_forecasts():
    engine = create_engine(DB_URL, echo=False)
    prep   = DataPreprocessor(engine)

    # Load all active products
    with engine.connect() as conn:
        products = conn.execute(text(
            "SELECT product_id, product_name FROM products WHERE is_active = 1"
        )).fetchall()

    print(f"\nStarting forecasts for {len(products)} products")
    print(f"Horizon: {FORECAST_HORIZON} days | Generated: {datetime.now()}\n")

    generated_on = datetime.now()

    # Mark old forecasts as not latest
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE forecast_results SET is_latest = 0"
        ))

    results_summary = []

    for product in products:
        pid, pname = product.product_id, product.product_name
        print(f"Processing: {pname} (ID={pid})")

        try:
            # Load and preprocess
            series = prep.load_daily_sales(pid)
            series = prep.remove_outliers(series)
            train, test = prep.train_test_split(series, test_days=30)

            stat = prep.check_stationarity(train)
            print(f"  Stationarity p-value: {stat['p_value']:.4f} "
                  f"({'Stationary' if stat['is_stationary'] else 'Non-stationary'})")

            # Fit SARIMA
            forecaster = SARIMAForecaster(pid, pname)
            forecaster.fit(train)

            # Evaluate on test set
            metrics = forecaster.evaluate(test)
            print(f"  MAE={metrics['mae']:.2f}  "
                  f"RMSE={metrics['rmse']:.2f}  "
                  f"MAPE={metrics['mape']:.2f}%")

            # Generate forecast starting from TODAY
            forecast_df = forecaster.forecast(steps=FORECAST_HORIZON)

            # Fix forecast dates to start from today
            today = date.today()
            forecast_dates = [today + timedelta(days=i) for i in range(FORECAST_HORIZON)]
            forecast_df['forecast_date'] = forecast_dates

            # Save forecast to DB
            rows = []
            for _, row in forecast_df.iterrows():
                rows.append({
                    "pid":     pid,
                    "fdate":   row["forecast_date"],
                    "gen_on":  generated_on,
                    "order":   str(forecaster.best_order),
                    "seas":    str(forecaster.best_seasonal_order),
                    "pred":    float(row["predicted_quantity"]),
                    "lo95":    float(row["lower_bound_95"]),
                    "hi95":    float(row["upper_bound_95"]),
                    "mae":     metrics["mae"],
                    "rmse":    metrics["rmse"],
                    "mape":    metrics["mape"],
                    "horizon": FORECAST_HORIZON
                })

            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO forecast_results
                      (product_id, forecast_date, generated_on,
                       sarima_order, sarima_seasonal,
                       predicted_quantity, lower_bound_95, upper_bound_95,
                       mae, rmse, mape, forecast_horizon, is_latest)
                    VALUES
                      (:pid, :fdate, :gen_on,
                       :order, :seas,
                       :pred, :lo95, :hi95,
                       :mae, :rmse, :mape, :horizon, 1)
                """), rows)

            results_summary.append({
                "product_id":   pid,
                "product_name": pname,
                **metrics,
                "status": "success"
            })
            print(f"  Saved {len(rows)} forecast records (from {forecast_dates[0]} to {forecast_dates[-1]})\n")

        except Exception as e:
            print(f"  ERROR for {pname}: {e}\n")
            results_summary.append({
                "product_id":   pid,
                "product_name": pname,
                "status":       f"error: {e}"
            })
            continue

    # Run recommendation engine
    print("Generating reorder recommendations...")
    rec_engine = RecommendationEngine(engine)
    rec_engine.generate_all_recommendations()

    print("\nForecasting complete!")
    print(pd.DataFrame(results_summary).to_string(index=False))
    return json.dumps(results_summary)


if __name__ == "__main__":
    run_forecasts()
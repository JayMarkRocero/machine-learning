"""
Data Preprocessor for SARIMA Forecasting
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.seasonal import seasonal_decompose
import warnings
warnings.filterwarnings("ignore")


class DataPreprocessor:

    def __init__(self, engine):
        self.engine = engine

    def load_daily_sales(self, product_id: int, min_days: int = 90) -> pd.Series:
        """Load and return a daily time series for one product."""
        query = text("""
            SELECT
                transaction_date  AS ds,
                SUM(si.quantity)  AS y
            FROM sales_items si
            JOIN sales_transactions st
              ON si.transaction_id = st.transaction_id
            WHERE si.product_id   = :pid
              AND st.payment_status = 'paid'
            GROUP BY transaction_date
            ORDER BY transaction_date
        """)
        df = pd.read_sql(query, self.engine, params={"pid": product_id})
        df["ds"] = pd.to_datetime(df["ds"])
        df.set_index("ds", inplace=True)

        # Reindex to fill missing dates (holidays, zero-sales days)
        full_idx = pd.date_range(df.index.min(), df.index.max(), freq="D")
        df = df.reindex(full_idx)

        # Fill missing values with interpolation, then forward-fill edges
        df["y"] = df["y"].interpolate(method="linear").ffill().bfill()

        if len(df) < min_days:
            raise ValueError(
                f"Product {product_id} has only {len(df)} days of data. "
                f"Minimum required: {min_days}"
            )
        return df["y"]

    def check_stationarity(self, series: pd.Series) -> dict:
        """Augmented Dickey-Fuller test for stationarity."""
        result = adfuller(series.dropna(), autolag="AIC")
        return {
            "adf_statistic": result[0],
            "p_value":       result[1],
            "is_stationary": result[1] < 0.05,
            "critical_values": result[4]
        }

    def decompose(self, series: pd.Series, period: int = 7):
        """Seasonal decomposition for diagnostics."""
        return seasonal_decompose(series, model="additive", period=period)

    def train_test_split(self, series: pd.Series, test_days: int = 30):
        """Split into train and test sets."""
        train = series.iloc[:-test_days]
        test  = series.iloc[-test_days:]
        return train, test

    def remove_outliers(self, series: pd.Series, threshold: float = 3.0) -> pd.Series:
        """Replace outliers beyond threshold sigma with interpolated values."""
        mean, std = series.mean(), series.std()
        mask = np.abs(series - mean) > threshold * std
        series_clean = series.copy()
        series_clean[mask] = np.nan
        return series_clean.interpolate(method="linear").ffill().bfill()
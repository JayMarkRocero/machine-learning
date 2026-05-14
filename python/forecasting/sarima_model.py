"""
SARIMA Forecasting Model
Trains per-product SARIMA models and generates 30-day forecasts.
"""

import pandas as pd
import numpy as np
import itertools
import warnings
from datetime import datetime
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore")


class SARIMAForecaster:

    # Candidate parameter grids for auto-selection
    P_RANGE = [0, 1, 2]
    D_VAL   = [0, 1]
    Q_RANGE = [0, 1, 2]
    SEASONAL_PERIOD = 7  # Weekly seasonality

    def __init__(self, product_id: int, product_name: str):
        self.product_id   = product_id
        self.product_name = product_name
        self.model        = None
        self.fit_result   = None
        self.best_order   = None
        self.best_seasonal_order = None
        self.aic          = None

    def _get_differencing_order(self, series: pd.Series) -> int:
        """Determine d via ADF test."""
        result = adfuller(series.dropna())
        if result[1] < 0.05:
            return 0   # already stationary
        result1 = adfuller(series.diff().dropna())
        if result1[1] < 0.05:
            return 1
        return 2

    def auto_select_order(self, train: pd.Series,
                          max_p: int = 2, max_q: int = 2) -> tuple:
        """
        Grid search over SARIMA(p,d,q)(P,D,Q)[7] using AIC.
        Returns best (order, seasonal_order).
        """
        d = self._get_differencing_order(train)
        D = 1  # apply one seasonal differencing

        best_aic   = np.inf
        best_order = (1, d, 1)
        best_seas  = (1, D, 1, self.SEASONAL_PERIOD)

        # Reduced grid for speed (capstone context)
        for p, q in itertools.product([0, 1, 2], [0, 1, 2]):
            for P, Q in itertools.product([0, 1], [0, 1]):
                try:
                    mod = SARIMAX(
                        train,
                        order=(p, d, q),
                        seasonal_order=(P, D, Q, self.SEASONAL_PERIOD),
                        enforce_stationarity=False,
                        enforce_invertibility=False
                    )
                    res = mod.fit(disp=False, maxiter=100)
                    if res.aic < best_aic:
                        best_aic   = res.aic
                        best_order = (p, d, q)
                        best_seas  = (P, D, Q, self.SEASONAL_PERIOD)
                except Exception:
                    continue

        self.best_order          = best_order
        self.best_seasonal_order = best_seas
        self.aic                 = best_aic
        print(f"  [{self.product_name}] Best SARIMA{best_order}×{best_seas}  AIC={best_aic:.2f}")
        return best_order, best_seas

    def fit(self, train: pd.Series,
            order: tuple = None,
            seasonal_order: tuple = None):
        """Fit SARIMA model to training data."""
        if order is None:
            order, seasonal_order = self.auto_select_order(train)

        self.model = SARIMAX(
            train,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False
        )
        self.fit_result = self.model.fit(disp=False, maxiter=200)
        self.best_order          = order
        self.best_seasonal_order = seasonal_order
        return self.fit_result

    def forecast(self, steps: int = 30) -> pd.DataFrame:
        """
        Generate forecast for `steps` days ahead.
        Returns DataFrame with: date, predicted, lower_95, upper_95
        """
        if self.fit_result is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        forecast_obj = self.fit_result.get_forecast(steps=steps)
        pred_mean    = forecast_obj.predicted_mean
        conf_int     = forecast_obj.conf_int(alpha=0.05)

        df = pd.DataFrame({
            "forecast_date":      pred_mean.index,
            "predicted_quantity": pred_mean.values.clip(0),
            "lower_bound_95":     conf_int.iloc[:, 0].clip(0).values,
            "upper_bound_95":     conf_int.iloc[:, 1].values,
        })
        df["predicted_quantity"] = df["predicted_quantity"].round(2)
        df["lower_bound_95"]     = df["lower_bound_95"].round(2)
        df["upper_bound_95"]     = df["upper_bound_95"].round(2)
        return df

    def evaluate(self, test: pd.Series) -> dict:
        """
        Evaluate model on test set.
        Returns MAE, RMSE, MAPE.
        """
        if self.fit_result is None:
            raise RuntimeError("Model not fitted.")

        n = len(test)
        pred = self.fit_result.forecast(steps=n)
        pred = pred.clip(0)

        actuals    = test.values
        predicted  = pred.values

        mae  = np.mean(np.abs(actuals - predicted))
        rmse = np.sqrt(np.mean((actuals - predicted) ** 2))
        # MAPE — avoid division by zero
        nonzero = actuals != 0
        mape = np.mean(np.abs((actuals[nonzero] - predicted[nonzero])
                               / actuals[nonzero])) * 100

        return {
            "mae":  round(float(mae),  4),
            "rmse": round(float(rmse), 4),
            "mape": round(float(mape), 4)
        }

    def plot_forecast(self, train: pd.Series, test: pd.Series,
                      forecast_df: pd.DataFrame,
                      save_path: str = None):
        """Generate diagnostic plot."""
        fig, ax = plt.subplots(figsize=(14, 5))

        ax.plot(train.index,        train.values,
                label="Training Data", color="#2563eb", linewidth=1.5)
        ax.plot(test.index,         test.values,
                label="Actual (Test)", color="#16a34a", linewidth=1.5)
        ax.plot(forecast_df["forecast_date"],
                forecast_df["predicted_quantity"],
                label="Forecast", color="#dc2626",
                linewidth=2, linestyle="--")
        ax.fill_between(
            forecast_df["forecast_date"],
            forecast_df["lower_bound_95"],
            forecast_df["upper_bound_95"],
            alpha=0.2, color="#dc2626", label="95% Confidence Interval"
        )

        ax.set_title(f"SARIMA Forecast — {self.product_name}", fontsize=14)
        ax.set_xlabel("Date")
        ax.set_ylabel("Units Sold")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150)
        plt.close()
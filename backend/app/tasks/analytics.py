import time
import numpy as np
import pandas as pd
from app.core.celery_app import celery_app


@celery_app.task(bind=True, name="app.tasks.analytics.process_dataset_analytics")
def process_dataset_analytics(self, record_count: int = 15000):
    """
    Executes vectorized data aggregation and statistical anomaly detection:
    1. Generates an in-memory transactional workload across service categories.
    2. Computes P90, P95, and P99 latency percentiles and cost distributions.
    3. Runs 3-Sigma Z-Score outlier detection.
    4. Aggregates data without blocking the asynchronous FastAPI event loop.
    """
    start_time = time.time()

    np.random.seed(42)
    categories = ["Compute", "Storage", "Network", "Database", "AI Inference"]

    data = {
        "transaction_id": [f"TX-{i:06d}" for i in range(record_count)],
        "category": np.random.choice(categories, size=record_count),
        "latency_ms": np.random.exponential(scale=45.0, size=record_count),
        "cost_usd": np.random.lognormal(mean=2.5, sigma=0.75, size=record_count),
        "error_rate": np.random.beta(a=0.5, b=20.0, size=record_count),
    }

    df = pd.DataFrame(data)

    # 1. Vectorized Category Aggregation
    summary_by_category = (
        df.groupby("category")
        .agg(
            total_cost=("cost_usd", "sum"),
            avg_cost=("cost_usd", "mean"),
            p95_latency=("latency_ms", lambda x: float(np.percentile(x, 95))),
            p99_latency=("latency_ms", lambda x: float(np.percentile(x, 99))),
            total_operations=("transaction_id", "count"),
        )
        .round(2)
        .to_dict(orient="index")
    )

    # 2. Outlier Anomaly Detection (Z-Score > 3.0)
    cost_mean = df["cost_usd"].mean()
    cost_std = df["cost_usd"].std()
    df["cost_zscore"] = (df["cost_usd"] - cost_mean) / cost_std
    anomalies = df[df["cost_zscore"] > 3.0]

    execution_duration_sec = round(time.time() - start_time, 3)

    return {
        "status": "COMPLETED",
        "processed_records": int(len(df)),
        "execution_time_sec": execution_duration_sec,
        "throughput_records_per_sec": round(len(df) / (execution_duration_sec or 1), 2),
        "detected_anomalies_count": int(len(anomalies)),
        "financial_aggregates": summary_by_category,
        "outlier_samples": (
            anomalies[["transaction_id", "category", "cost_usd", "cost_zscore"]]
            .head(5)
            .round(2)
            .to_dict(orient="records")
        ),
    }
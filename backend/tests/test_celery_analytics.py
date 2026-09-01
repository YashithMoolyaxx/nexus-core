import pytest
from app.tasks.analytics import process_dataset_analytics


def test_vectorized_analytics_execution():
    record_count = 10000
    result = process_dataset_analytics(record_count=record_count)

    assert result["status"] == "COMPLETED"
    assert result["processed_records"] == 10000
    assert result["execution_time_sec"] > 0
    assert result["throughput_records_per_sec"] > 0
    assert result["detected_anomalies_count"] >= 0

    categories = result["financial_aggregates"]
    assert "Compute" in categories
    assert "Storage" in categories
    assert "Network" in categories
    assert "Database" in categories
    assert "AI Inference" in categories

    for cat_name, metrics in categories.items():
        assert metrics["total_cost"] > 0
        assert metrics["avg_cost"] > 0
        assert metrics["p95_latency"] > 0
        assert metrics["p99_latency"] >= metrics["p95_latency"]
        assert metrics["total_operations"] > 0
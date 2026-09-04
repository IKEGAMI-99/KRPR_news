import json
import os
from datetime import datetime, timezone
from pathlib import Path

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, OrderBy, RunReportRequest

PROPERTY_ID = os.environ["GA4_PROPERTY_ID"].strip()
OUTPUT = Path("docs/analytics/data.json")
client = BetaAnalyticsDataClient()
property_name = f"properties/{PROPERTY_ID}"


def report(start_date, end_date, metrics, dimensions=None, limit=100, order_metric=None):
    req = RunReportRequest(
        property=property_name,
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        metrics=[Metric(name=m) for m in metrics],
        dimensions=[Dimension(name=d) for d in (dimensions or [])],
        limit=limit,
    )
    if order_metric:
        req.order_bys = [OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order_metric), desc=True)]
    return client.run_report(req)


def metric_value(response, index=0):
    if not response.rows:
        return 0
    value = response.rows[0].metric_values[index].value
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def rows(response, label_index=0, metric_index=0, drop_analytics=False):
    items = []
    for row in response.rows:
        label = row.dimension_values[label_index].value or "(not set)"
        if drop_analytics and "/analytics" in label:
            continue
        try:
            value = int(float(row.metric_values[metric_index].value))
        except (TypeError, ValueError):
            value = 0
        items.append({"label": label, "value": value})
    return items


today = report("today", "today", ["screenPageViews"])
week = report("6daysAgo", "today", ["screenPageViews"])
month = report("29daysAgo", "today", ["screenPageViews", "activeUsers"])
trend_r = report("29daysAgo", "today", ["screenPageViews"], ["date"], 40)
pages_r = report("29daysAgo", "today", ["screenPageViews"], ["pagePath"], 30, "screenPageViews")
ref_r = report("29daysAgo", "today", ["sessions"], ["sessionSource"], 12, "sessions")
region_r = report("29daysAgo", "today", ["activeUsers"], ["country"], 12, "activeUsers")
device_r = report("29daysAgo", "today", ["activeUsers"], ["deviceCategory"], 10, "activeUsers")

trend = []
for row in trend_r.rows:
    raw = row.dimension_values[0].value
    if len(raw) == 8 and raw.isdigit():
        date_iso = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        label = f"{raw[4:6]}/{raw[6:8]}"
    else:
        date_iso = raw
        label = raw
    trend.append({"date": date_iso, "label": label, "value": int(float(row.metric_values[0].value))})

# GA4 does not guarantee dimension row order here. Always emit the trend chronologically.
trend.sort(key=lambda item: item["date"])

payload = {
    "ready": True,
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "summary": {
        "todayViews": metric_value(today),
        "weekViews": metric_value(week),
        "monthViews": metric_value(month, 0),
        "monthUsers": metric_value(month, 1),
    },
    "trend": trend,
    "pages": rows(pages_r, drop_analytics=True)[:10],
    "referrers": rows(ref_r)[:10],
    "regions": rows(region_r)[:10],
    "devices": rows(device_r)[:10],
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"updated {OUTPUT}")

from datetime import UTC, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .query import GetDashboardTimeseriesQuery
from .response import DashboardDetectionsBySeverity, DashboardTimeseriesPoint, DashboardTimeseriesResponse

# Aggregate each table independently in one statement, then fill gaps even when
# both tables are empty. Generate UTC wall-clock timestamps so daily steps remain
# independent of the database session's timezone and daylight saving transitions.
TIMESERIES_SQL = text("""
    WITH buckets AS (
        SELECT bucket AT TIME ZONE 'UTC' AS timestamp
        FROM generate_series(
            time_bucket(
                CAST(:bucket_size AS interval), CAST(:start_time AS timestamptz),
                TIMESTAMPTZ '1970-01-01 00:00:00+00'
            ) AT TIME ZONE 'UTC',
            CAST(:end_time AS timestamptz) AT TIME ZONE 'UTC',
            CAST(:bucket_size AS interval)
        ) AS series(bucket)
        WHERE bucket < CAST(:end_time AS timestamptz) AT TIME ZONE 'UTC'
    ), flow_counts AS (
        SELECT time_bucket(CAST(:bucket_size AS interval), ts_start, TIMESTAMPTZ '1970-01-01 00:00:00+00') AS timestamp,
               count(*) AS flows, sum(packets) AS packets, sum(bytes) AS bytes
        FROM network_flows
        WHERE ts_start >= :start_time AND ts_start < :end_time
        GROUP BY 1
    ), detection_counts AS (
        SELECT time_bucket(
                   CAST(:bucket_size AS interval), created_at, TIMESTAMPTZ '1970-01-01 00:00:00+00'
               ) AS timestamp,
               count(*) FILTER (WHERE severity = 'LOW') AS low,
               count(*) FILTER (WHERE severity = 'MEDIUM') AS medium,
               count(*) FILTER (WHERE severity = 'HIGH') AS high,
               count(*) FILTER (WHERE severity = 'CRITICAL') AS critical
        FROM detections
        WHERE created_at >= :start_time AND created_at < :end_time
        GROUP BY 1
    )
    SELECT buckets.timestamp,
           COALESCE(flow_counts.flows, 0) AS flows,
           COALESCE(flow_counts.packets, 0) AS packets,
           COALESCE(flow_counts.bytes, 0) AS bytes,
           COALESCE(detection_counts.low, 0) AS low,
           COALESCE(detection_counts.medium, 0) AS medium,
           COALESCE(detection_counts.high, 0) AS high,
           COALESCE(detection_counts.critical, 0) AS critical
    FROM buckets
    LEFT JOIN flow_counts USING (timestamp)
    LEFT JOIN detection_counts USING (timestamp)
    ORDER BY buckets.timestamp
""")


class GetDashboardTimeseriesHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetDashboardTimeseriesQuery) -> DashboardTimeseriesResponse:
        result = await self._session.execute(
            TIMESERIES_SQL,
            {
                "start_time": query.start_time,
                "end_time": query.end_time,
                "bucket_size": timedelta(seconds=query.interval_s),
            },
        )
        return DashboardTimeseriesResponse(
            interval_s=query.interval_s,
            points=[
                DashboardTimeseriesPoint(
                    ts=bucket["timestamp"].astimezone(UTC),
                    flows=bucket["flows"],
                    packets=bucket["packets"],
                    bytes=bucket["bytes"],
                    detections=DashboardDetectionsBySeverity(
                        LOW=bucket["low"], MEDIUM=bucket["medium"], HIGH=bucket["high"], CRITICAL=bucket["critical"]
                    ),
                )
                for bucket in result.mappings()
            ],
        )

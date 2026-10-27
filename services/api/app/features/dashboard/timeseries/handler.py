from datetime import UTC

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .query import BUCKET_SIZES, GetDashboardTimeseriesQuery
from .response import DashboardTimeseriesPoint, DashboardTimeseriesResponse

# Aggregate each table independently in one statement, then fill gaps even when
# both tables are empty. Generate UTC wall-clock timestamps so daily steps remain
# independent of the database session's timezone and daylight saving transitions.
TIMESERIES_SQL = text("""
    WITH buckets AS (
        SELECT bucket AT TIME ZONE 'UTC' AS timestamp
        FROM generate_series(
            time_bucket(CAST(:bucket_size AS interval), CAST(:start_time AS timestamptz)) AT TIME ZONE 'UTC',
            CAST(:end_time AS timestamptz) AT TIME ZONE 'UTC',
            CAST(:bucket_size AS interval)
        ) AS series(bucket)
        WHERE bucket < CAST(:end_time AS timestamptz) AT TIME ZONE 'UTC'
    ), flow_counts AS (
        SELECT time_bucket(CAST(:bucket_size AS interval), ts_start) AS timestamp, count(*) AS flows_count
        FROM network_flows
        WHERE ts_start >= :start_time AND ts_start < :end_time
        GROUP BY 1
    ), detection_counts AS (
        SELECT time_bucket(CAST(:bucket_size AS interval), created_at) AS timestamp, count(*) AS detections_count
        FROM detections
        WHERE created_at >= :start_time AND created_at < :end_time
        GROUP BY 1
    )
    SELECT buckets.timestamp,
           COALESCE(flow_counts.flows_count, 0) AS flows_count,
           COALESCE(detection_counts.detections_count, 0) AS detections_count
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
                "bucket_size": BUCKET_SIZES[query.interval],
            },
        )
        return DashboardTimeseriesResponse(
            start_time=query.start_time,
            end_time=query.end_time,
            interval=query.interval,
            data=[
                DashboardTimeseriesPoint(
                    timestamp=bucket["timestamp"].astimezone(UTC),
                    flows_count=bucket["flows_count"],
                    detections_count=bucket["detections_count"],
                )
                for bucket in result.mappings()
            ],
        )

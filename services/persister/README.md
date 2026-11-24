# Persister

Consumes `flows.raw` and `detections` and writes flows, detections and alerts to
PostgreSQL/TimescaleDB in batches.

## Database reconnect

For [issue #9](https://github.com/k1borg32/Netguard/issues/9), database connection
failures (`OperationalError` and `InterfaceError`) trigger reconnect attempts
instead of terminating the persister. Connection attempts have a five-second
timeout. Failed attempts wait 1, 2, 4, 8, 16 and then at most 30 seconds; the delay
resets after a connection is established and its temporary table is ready.

Each attempt creates the session-local `flow_batch` table again. On failure, the
old database connection and Kafka consumer are closed before waiting. Automatic
offset commits remain disabled, so closing the consumer does not acknowledge an
unfinished batch. After recovery, a new consumer resumes from the last committed
offsets, replaying unfinished work from Kafka instead of retaining a growing
in-memory queue during an outage.

Offsets are committed only after the database commit. If the database committed
but the connection was lost before its acknowledgement arrived, replay is safe:
the existing flow conflict handling, detection upserts and deterministic alert
IDs prevent duplicate records. Recovery relies on Kafka retaining uncommitted
messages. Invalid data and SQL programming errors are not retried as connection
failures.

Logs include `database unavailable; reconnecting` with the exception type and
`retry_delay_s`, followed by `persister connected` after recovery. Database
connection strings and exception messages are not included in reconnect logs.

The RT-04 scenario (DB down for 30 seconds) still needs runtime verification;
this change does not claim a successful resilience test run.

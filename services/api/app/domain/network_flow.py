"""Normalized network traffic stored by its identifier and start time."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Double, Integer, Text
from sqlalchemy.dialects.postgresql import INET, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import Base


class NetworkFlow(Base):
    __tablename__ = "network_flows"

    flow_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    ts_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    duration_ms: Mapped[float | None] = mapped_column(Double, nullable=True)
    src_ip: Mapped[str] = mapped_column(INET, nullable=False)
    dst_ip: Mapped[str] = mapped_column(INET, nullable=False)
    src_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dst_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol: Mapped[str | None] = mapped_column(Text, nullable=True)
    packets: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tcp_flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)

"""SQLAlchemy ORM models. These mirror db/schema.sql exactly — that file is
the source of truth; if you change one, change both.

Fully implemented — nothing to do here.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Spec(Base):
    __tablename__ = "specs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(Text)
    content_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class Tree(Base):
    __tablename__ = "trees"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("specs.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    structure: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class GuidanceSession(Base):
    __tablename__ = "guidance_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tree_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trees.id", ondelete="CASCADE"))
    agent_name: Mapped[str] = mapped_column(Text)
    path: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(Text, default="active")
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tree_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trees.id", ondelete="CASCADE"))
    audio_path: Mapped[str] = mapped_column(Text)
    transcript: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="uploaded")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class CallAnalysis(Base):
    __tablename__ = "call_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"))
    matched_path: Mapped[list] = mapped_column(JSONB)
    step_verdicts: Mapped[list] = mapped_column(JSONB)
    score: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

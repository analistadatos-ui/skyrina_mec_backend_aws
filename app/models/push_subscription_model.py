import uuid

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class PushSubscription(Base):
    """
    One row per browser/device a user enabled notifications on.
    A user can have several (phone + desktop). Expired subscriptions
    are deleted automatically when a push returns 404/410.
    """

    __tablename__ = "push_subscriptions"

    __table_args__ = {
        "schema": "mechanics_db_schema"
    }

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # The browser push endpoint URL — unique per device subscription
    endpoint = Column(
        Text,
        nullable=False,
        unique=True,
    )

    # Encryption keys provided by the browser
    p256dh = Column(
        String(255),
        nullable=False,
    )

    auth = Column(
        String(255),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
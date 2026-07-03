# migrate_push_subscriptions.py
from app.database import engine, Base

# Import the model so SQLAlchemy knows about the table
from app.models.push_subscription_model import PushSubscription

if __name__ == "__main__":
    # create_all only creates MISSING tables; existing ones are untouched
    Base.metadata.create_all(bind=engine)
    print("push_subscriptions table created (or already existed)")
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, ForeignKey,
    Boolean, UniqueConstraint, text,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

from .config import DATABASE_URL
from .categorizer import CATEGORIES

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    bank_name = Column(String, nullable=False)
    account_number = Column(String, nullable=False)
    account_type = Column(String, nullable=True)
    currency = Column(String, default="INR")
    opening_balance = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "fingerprint", name="uq_transaction_dedup"),
    )

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=True)
    balance_after = Column(Float, nullable=True)
    is_internal_transfer = Column(Boolean, nullable=False, default=False)
    payment_mode = Column(String, nullable=True)
    source_file = Column(String, nullable=True)
    fingerprint = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Category(Base):
    """User-managed list of categories (seeded from the rule set)."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_category_name"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    spend_type = Column(String, nullable=True)              # fixed | variable
    essentiality = Column(String, nullable=True)            # essential | discretionary
    default_monthly_budget = Column(Float, nullable=True)


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    bank_name = Column(String, nullable=True)
    uploaded_at = Column(DateTime, server_default=func.now())
    status = Column(String, default="pending")


# Default KPI attributes applied when seeding categories (user can override).
FIXED_CATEGORIES = {"Rent", "EMI", "Subscriptions", "Utilities", "Fees"}
ESSENTIAL_CATEGORIES = {"Rent", "EMI", "Utilities", "Food", "Subscriptions", "Fees"}


def _migrate_sqlite():
    """Add columns that later versions introduced (idempotent for SQLite)."""
    inspector_cols = set()
    with engine.connect() as conn:
        rows = conn.execute(
            text("PRAGMA table_info(categories)")
        ).fetchall()
        inspector_cols = {r[1] for r in rows}
        tx_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(transactions)")).fetchall()}
    if "spend_type" not in inspector_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE categories ADD COLUMN spend_type VARCHAR"))
    if "essentiality" not in inspector_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE categories ADD COLUMN essentiality VARCHAR"))
    if "default_monthly_budget" not in inspector_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE categories ADD COLUMN default_monthly_budget FLOAT"))
    if "payment_mode" not in tx_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN payment_mode VARCHAR"))


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()
    session = SessionLocal()
    try:
        if session.query(User).filter_by(id=1).first() is None:
            session.add(User(id=1, name="default"))
            session.commit()
        if session.query(Category).count() == 0:
            for index, name in enumerate(CATEGORIES):
                session.add(Category(
                    user_id=1,
                    name=name,
                    sort_order=index,
                    spend_type="fixed" if name in FIXED_CATEGORIES else "variable",
                    essentiality="essential" if name in ESSENTIAL_CATEGORIES else "discretionary",
                ))
            session.commit()
    finally:
        session.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
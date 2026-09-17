import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from database.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    balance = Column(Integer, default=0, nullable=False)
    total_charged = Column(Integer, default=0, nullable=False)
    total_spent = Column(Integer, default=0, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    orders = relationship("Order", back_populates="user")
    charge_requests = relationship("ChargeRequest", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, default="")
    price = Column(Integer, nullable=False)
    image_url = Column(String(500), default="")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    inventories = relationship("Inventory", back_populates="product", cascade="all, delete-orphan")

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    delivery_data = Column(Text, nullable=False)  # 라이선스 키, 계정 정보 등
    is_used = Column(Boolean, default=False, nullable=False, index=True)
    used_by = Column(BigInteger, nullable=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    product = relationship("Product", back_populates="inventories")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    discord_id = Column(BigInteger, nullable=False)
    product_name = Column(String(150), nullable=False)
    quantity = Column(Integer, nullable=False)
    total_amount = Column(Integer, nullable=False)
    delivery_content = Column(Text, nullable=False)
    status = Column(String(30), default="COMPLETED", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="orders")

class ChargeRequest(Base):
    __tablename__ = "charge_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_number = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    discord_id = Column(BigInteger, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String(20), default="WAITING", nullable=False, index=True)  # WAITING, APPROVED, REJECTED
    receipt_image = Column(String(300), nullable=True)
    rejection_reason = Column(String(300), nullable=True)
    processed_by = Column(String(100), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="charge_requests")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    discord_id = Column(BigInteger, nullable=False)
    type = Column(String(30), nullable=False)  # CHARGE, PURCHASE, ADMIN_ADJUST
    amount = Column(Integer, nullable=False)
    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    reference_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="transactions")

class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class LogSetting(Base):
    __tablename__ = "log_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_type = Column(String(50), unique=True, nullable=False)
    channel_id = Column(BigInteger, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(Text, nullable=True)

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    admin_name = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
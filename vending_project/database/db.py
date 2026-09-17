import sqlite3
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from contextlib import contextmanager
from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 15},
    echo=False
)

# SQLite WAL 모드 및 외래 키 활성화 (동시성 및 락 충돌 방지)
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=10000;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
ScopedSession = scoped_session(SessionFactory)
Base = declarative_base()

@contextmanager
def get_db():
    """트랜잭션을 보장하는 안전한 세션 컨텍스트 매니저"""
    session = ScopedSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def init_database():
    import database.models
    Base.metadata.create_all(bind=engine)
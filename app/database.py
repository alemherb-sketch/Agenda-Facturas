from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()
db_url = settings.sqlalchemy_url

connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    if db_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema() -> None:
    """Añade columnas nuevas sin migraciones formales (SQLite y Postgres)."""
    is_sqlite = db_url.startswith("sqlite")
    with engine.begin() as conn:
        if is_sqlite:
            cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(clientes)").fetchall()}
            if cols:
                if "activo" not in cols:
                    conn.exec_driver_sql("ALTER TABLE clientes ADD COLUMN activo BOOLEAN DEFAULT 1")
                if "creado_en" not in cols:
                    conn.exec_driver_sql("ALTER TABLE clientes ADD COLUMN creado_en DATETIME")

            usuarios_cols = {
                row[1] for row in conn.exec_driver_sql("PRAGMA table_info(usuarios)").fetchall()
            }
            if usuarios_cols:
                if "telegram_chat_id" not in usuarios_cols:
                    conn.exec_driver_sql("ALTER TABLE usuarios ADD COLUMN telegram_chat_id VARCHAR(32)")
                if "notificar_email" not in usuarios_cols:
                    conn.exec_driver_sql(
                        "ALTER TABLE usuarios ADD COLUMN notificar_email BOOLEAN DEFAULT 1"
                    )
        else:
            conn.exec_driver_sql(
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(32)"
            )
            conn.exec_driver_sql(
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS notificar_email BOOLEAN DEFAULT TRUE"
            )

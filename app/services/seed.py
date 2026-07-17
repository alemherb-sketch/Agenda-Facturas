from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import SessionLocal
from app.models import Usuario

DEMO_EMAIL = "demo@agenda.pe"
DEMO_PASSWORD = "demo1234"


def ensure_demo_user() -> None:
    db: Session = SessionLocal()
    try:
        exists = db.query(Usuario).filter(Usuario.email == DEMO_EMAIL).first()
        if exists:
            return
        db.add(
            Usuario(
                nombre="Demo Usuario",
                email=DEMO_EMAIL,
                telefono="999888777",
                ruc_empresa="20123456789",
                razon_social="Demo Negocios SAC",
                direccion="Av. Arequipa 123, Lima",
                hashed_password=hash_password(DEMO_PASSWORD),
            )
        )
        db.commit()
    finally:
        db.close()

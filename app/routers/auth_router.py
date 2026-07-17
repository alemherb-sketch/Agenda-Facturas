from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import Usuario
from app.schemas import TokenOut, UsuarioCreate, UsuarioLogin, UsuarioOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/registro", response_model=TokenOut)
def registro(payload: UsuarioCreate, db: Annotated[Session, Depends(get_db)]):
    if db.query(Usuario).filter(Usuario.email == payload.email).first():
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    user = Usuario(
        nombre=payload.nombre,
        email=payload.email.lower(),
        telefono=payload.telefono,
        ruc_empresa=payload.ruc_empresa,
        razon_social=payload.razon_social,
        direccion=payload.direccion,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.email)
    return TokenOut(access_token=token, usuario=UsuarioOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(payload: UsuarioLogin, db: Annotated[Session, Depends(get_db)]):
    user = db.query(Usuario).filter(Usuario.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    token = create_access_token(user.email)
    return TokenOut(access_token=token, usuario=UsuarioOut.model_validate(user))


@router.get("/me", response_model=UsuarioOut)
def me(user: Annotated[Usuario, Depends(get_current_user)]):
    return user

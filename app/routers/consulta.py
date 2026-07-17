from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.models import Usuario
from app.services.sunat_service import consultar_documento

router = APIRouter(prefix="/api/consulta", tags=["consulta"])


@router.get("/documento")
async def consulta_documento(
    user: Annotated[Usuario, Depends(get_current_user)],
    numero: str = Query(..., min_length=8, max_length=20, description="DNI (8) o RUC (11)"),
):
    _ = user
    ok, result = await consultar_documento(numero)
    if not ok:
        raise HTTPException(status_code=400, detail=result)
    return result

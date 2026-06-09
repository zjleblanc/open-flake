from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.db import get_db
from app.domain.cmdb.ci_service import class_tree, schema_for_class
from app.domain.cmdb.registry import is_registered

router = APIRouter(prefix="/api/flake/schema/cmdb", tags=["cmdb-schema-api"])


@router.get("/classes")
async def list_classes(
    auth: AuthContext = Depends(authenticate_request),
):
    return {"result": class_tree()}


@router.get("/{class_name}")
async def get_class_schema(
    class_name: str,
    auth: AuthContext = Depends(authenticate_request),
):
    if not is_registered(class_name):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Class '{class_name}' is not registered. "
            "Create a record with this class to auto-register it under cmdb_ci.",
        )
    return {"result": schema_for_class(class_name)}

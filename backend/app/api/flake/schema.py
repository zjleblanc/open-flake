from fastapi import APIRouter, Depends

from app.auth.deps import AuthContext, authenticate_request
from app.domain.cmdb.ci_service import class_tree, schema_for_class
from app.domain.cmdb.registry import is_registered, resolve_inheritance_path

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
        return {
            "result": {
                "class_name": class_name,
                "inheritance_path": resolve_inheritance_path(class_name),
                "fields": [],
                "registered": False,
            }
        }
    return {"result": schema_for_class(class_name)}

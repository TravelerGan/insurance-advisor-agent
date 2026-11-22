from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import PageResult
from app.infra.database import get_session
from app.modules.product.schemas import ProductResponse
from app.modules.product.service import ProductService

router = APIRouter(prefix="/api/v1/products", tags=["products"])

def get_product_service(session: AsyncSession = Depends(get_session)):
    yield ProductService(session)
@router.get("", response_model=PageResult[ProductResponse])
async def list_products(
        category: str | None = None,
        page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
        page_size: int = Query(default=6, ge=1, le=100, description="每页条数"),
        service: ProductService = Depends(get_product_service)
) -> PageResult[ProductResponse]:
    result = await service.list_products(category, page=page, page_size=page_size)
    return result


@router.get("/candidates", response_model=list[ProductResponse])
async def list_candidates(
    categories: list[str] = Query(min_length=1),
    premium_min: Decimal | None = None,
    limit_per_category: int = 5,
    service: ProductService = Depends(get_product_service),
) -> list[ProductResponse]:
    return await service.list_candidates(
        categories=categories,
        premium_min=premium_min,
        limit_per_category=limit_per_category,
    )

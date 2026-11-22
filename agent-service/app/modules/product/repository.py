from decimal import Decimal

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Product


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _paginate(
            self, statement: Select, page: int, page_size: int,
    ) -> tuple[list[Product], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        products = await self.session.scalars(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
        return list(products.all()), total or 0

    async def query_by_category(
            self, category: str | None = None, *, page: int = 1, page_size: int = 6,
    ) -> tuple[list[Product], int]:
        conditions = [Product.status == "active"]
        if category:
            conditions.append(Product.category == category)

        statement = select(Product).where(*conditions).order_by(Product.id.asc())
        return await self._paginate(statement, page, page_size)

    async def find_limited_by_category(
            self,
            category: str,
            premium_min: Decimal | None,
            limit: int,
    ) -> list[Product]:
        conditions = [
            Product.status == "active",
            Product.category == category,
        ]
        if premium_min is not None:
            conditions.append(Product.min_premium < premium_min)

        products = await self.session.scalars(
            select(Product)
            .where(*conditions)
            .order_by(
                Product.min_premium.asc().nullslast(),
                Product.id.asc(),
            )
            .limit(limit)
        )
        return products.all()

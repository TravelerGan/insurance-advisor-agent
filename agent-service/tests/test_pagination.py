"""分页查询回归检查：不连接业务数据库。"""
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import JSON, MetaData, String, create_engine
from sqlalchemy.orm import Session

from app.modules.chat_threads.models import ChatThread
from app.modules.chat_threads.repository import ChatThreadRepository
from app.modules.chat_threads.router import (
    get_chat_threads_service, router as chat_router,
)
from app.modules.chat_threads.service import ChatThreadService
from app.modules.product.models import Product
from app.modules.product.repository import ProductRepository
from app.modules.product.router import get_product_service, router as product_router
from app.modules.product.service import ProductService


class AsyncSessionAdapter:
    """用内存 SQLite 执行查询，覆盖真实筛选、计数、排序和窗口函数。"""

    def __init__(self, session):
        self.session = session

    async def scalar(self, statement):
        return self.session.scalar(statement)

    async def scalars(self, statement):
        return self.session.scalars(statement)


def product_fixture():
    return Product(
        id=1, name="示例产品", clause_name="条款", category="life",
        insurer="保险公司", image_url="", description="", min_premium=Decimal("100"),
        max_premium=None, target_group=None, highlights=[], status="active",
    )


class RepositoryPaginationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        metadata = MetaData()
        products = Product.__table__.to_metadata(metadata)
        # SQLite 无 PostgreSQL ARRAY 类型；此处仅检查查询，不检查数组序列化。
        products.c.highlights.type = JSON()
        threads = ChatThread.__table__.to_metadata(metadata)
        threads.c.id.type = String(32)
        metadata.create_all(self.engine)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with self.engine.begin() as connection:
            connection.execute(products.insert(), [
                dict(id=i, name=f"产品{i}", clause_name="条款", insurer="公司",
                     category=category, min_premium=premium, status=status,
                     image_url="", description="", highlights=None)
                for i, category, premium, status in [
                    (1, "life", 30, "active"), (2, "life", 10, "active"),
                    (3, "life", 20, "active"), (4, "life", 0, "inactive"),
                    (5, "health", 5, "active"), (6, "health", 5, "active"),
                    (7, "health", None, "active"), (8, "life", 0, "active"),
                ]
            ])
            connection.execute(threads.insert(), [
                dict(id=UUID(int=i).hex, user_id=user_id, title=f"会话{i}",
                     created_at=now, updated_at=now)
                for i, user_id in [(1, 1), (2, 1), (3, 1), (4, 2)]
            ])
        self.session = Session(self.engine)
        adapter = AsyncSessionAdapter(self.session)
        self.products = ProductRepository(adapter)
        self.threads = ChatThreadRepository(adapter)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    async def test_product_pages_and_filtered_total(self):
        items, total = await self.products.query_by_category("life", page=2, page_size=2)
        self.assertEqual([item.id for item in items], [3, 8])
        self.assertEqual(total, 4)
        items, total = await self.products.query_by_category(page_size=6)
        self.assertEqual(len(items), 6)
        self.assertEqual(total, 7)

    async def test_empty_and_out_of_range(self):
        for category, page, expected_total in [("missing", 1, 0), ("life", 99, 4)]:
            items, total = await self.products.query_by_category(category, page=page)
            self.assertEqual(items, [])
            self.assertEqual(total, expected_total)

    async def test_candidates_cap_and_order_for_each_category(self):
        service = ProductService(None)
        service.repository = self.products
        items = await service.list_candidates(["health", "life", "health"], None, 2)
        self.assertEqual([item.id for item in items], [5, 6, 8, 2])

    async def test_candidates_filter_and_null_premium(self):
        items = await self.products.find_limited_by_category("life", Decimal("0"), 5)
        self.assertEqual(items, [])
        items = await self.products.find_limited_by_category("health", None, 5)
        self.assertEqual([item.id for item in items], [5, 6, 7])
        items = await self.products.find_limited_by_category("health", Decimal("6"), 5)
        self.assertEqual([item.id for item in items], [5, 6])

    async def test_chat_user_scope_and_stable_order(self):
        items, total = await self.threads.list_by_user(1, page=2, page_size=2)
        self.assertEqual([item.id for item in items], [UUID(int=1)])
        self.assertEqual(total, 3)
        self.assertEqual(await self.threads.list_by_user(1, page=99), ([], 3))
        self.assertEqual(await self.threads.list_by_user(99), ([], 0))


class PaginationApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.products = ProductService(None)
        self.products.repository = AsyncMock()
        self.products.repository.query_by_category.return_value = ([product_fixture()], 7)
        self.products.repository.find_limited_by_category.return_value = [product_fixture()]
        self.chats = ChatThreadService(None, AsyncMock())
        self.chats.repository = AsyncMock()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.chats.repository.list_by_user.return_value = ([ChatThread(
            id=UUID(int=1), title="会话", created_at=now, updated_at=now,
        )], 7)
        self.app = FastAPI()
        self.app.include_router(product_router)
        self.app.include_router(chat_router)
        self.app.dependency_overrides[get_product_service] = lambda: self.products
        self.app.dependency_overrides[get_chat_threads_service] = lambda: self.chats
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test",
            headers={"x-user-id": "1"},
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_default_six_items_and_page_result_orm_serialization(self):
        for url in ["/api/v1/products", "/api/v1/chat-threads"]:
            with self.subTest(url=url):
                response = await self.client.get(url)
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(set(data), {"items", "page", "page_size", "total"})
                self.assertEqual((data["page"], data["page_size"], data["total"]), (1, 6, 7))
                self.assertEqual(len(data["items"]), 1)
        self.products.repository.query_by_category.assert_awaited_once_with(None, page=1, page_size=6)
        self.chats.repository.list_by_user.assert_awaited_once_with(1, page=1, page_size=6)

    async def test_candidate_list_and_filters(self):
        response = await self.client.get(
            "/api/v1/products/candidates?categories=life&categories=health"
            "&premium_min=100&limit_per_category=3",
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(
            [call.kwargs for call in self.products.repository.find_limited_by_category.await_args_list],
            [
                dict(category="life", premium_min=Decimal("100"), limit=3),
                dict(category="health", premium_min=Decimal("100"), limit=3),
            ],
        )

    async def test_invalid_pagination_and_missing_candidate_categories(self):
        for url in ["/api/v1/products", "/api/v1/chat-threads"]:
            for query in ["page=0", "page_size=0", "page_size=101", "page=abc"]:
                response = await self.client.get(url + "?" + query)
                self.assertEqual(response.status_code, 422, response.text)
        response = await self.client.get("/api/v1/products/candidates")
        self.assertEqual(response.status_code, 422)

    async def test_openapi_has_query_pagination_and_no_get_body(self):
        schema = self.app.openapi()
        for url in ["/api/v1/products", "/api/v1/chat-threads"]:
            operation = schema["paths"][url]["get"]
            self.assertNotIn("requestBody", operation)
            parameters = {item["name"]: item for item in operation["parameters"]}
            self.assertEqual(parameters["page_size"]["schema"]["default"], 6)
            self.assertEqual(parameters["page_size"]["in"], "query")


if __name__ == "__main__":
    unittest.main()

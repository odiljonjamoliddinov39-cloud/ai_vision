"""Persistent product knowledge base."""

from __future__ import annotations

from typing import Any

from database.db import AppDB, id_column_sql
from knowledge.similarity import top_matches
from recognition.embedding import deserialize_embedding, serialize_embedding


class ProductDatabase:
    def __init__(self, db_path: str = "database/products.db"):
        self.db_path = db_path
        self.db = AppDB(db_path)
        self._init_schema()

    def _sql(self, query: str) -> str:
        return self.db.sql(query)

    def _init_schema(self) -> None:
        timestamp_type = "TIMESTAMPTZ" if self.db.is_postgres else "DATETIME"
        with self.db.connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS products (
                    id {id_column_sql(self.db)},
                    name TEXT NOT NULL UNIQUE,
                    category TEXT,
                    brand TEXT,
                    material TEXT,
                    description TEXT,
                    color TEXT,
                    shape TEXT,
                    estimated_size TEXT,
                    possible_usage TEXT,
                    confidence REAL,
                    embedding TEXT,
                    image_hash TEXT,
                    created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_columns(conn, timestamp_type)

    def _ensure_columns(self, conn, timestamp_type: str) -> None:
        existing = self.db.table_columns(conn, "products")
        columns = {
            "category": "TEXT",
            "brand": "TEXT",
            "material": "TEXT",
            "description": "TEXT",
            "color": "TEXT",
            "shape": "TEXT",
            "estimated_size": "TEXT",
            "possible_usage": "TEXT",
            "confidence": "REAL",
            "embedding": "TEXT",
            "image_hash": "TEXT",
            "created_at": f"{timestamp_type} DEFAULT CURRENT_TIMESTAMP",
        }
        for name, sql_type in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE products ADD COLUMN {name} {sql_type}")

    def get_by_hash(self, image_hash: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                self._sql(
                    """
                    SELECT id, name, category, brand, material, description, color, shape,
                           estimated_size, possible_usage, confidence, embedding, image_hash, created_at
                    FROM products
                    WHERE image_hash = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                (image_hash,),
            ).fetchone()
        return self._row_to_product(row) if row else None

    def save_product(self, product, embedding: list[float], image_hash: str) -> dict[str, Any]:
        payload = product.to_dict() if hasattr(product, "to_dict") else dict(product)
        values = (
            payload.get("name") or "Unknown Product",
            payload.get("category"),
            payload.get("brand"),
            payload.get("material"),
            payload.get("description"),
            payload.get("color"),
            payload.get("shape"),
            payload.get("estimated_size"),
            payload.get("possible_usage"),
            float(payload.get("confidence") or 0.0),
            serialize_embedding(embedding),
            image_hash,
        )
        with self.db.connect() as conn:
            if self.db.is_postgres:
                conn.execute(
                    """
                    INSERT INTO products (
                        name, category, brand, material, description, color, shape,
                        estimated_size, possible_usage, confidence, embedding, image_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        category = EXCLUDED.category,
                        brand = EXCLUDED.brand,
                        material = EXCLUDED.material,
                        description = EXCLUDED.description,
                        color = EXCLUDED.color,
                        shape = EXCLUDED.shape,
                        estimated_size = EXCLUDED.estimated_size,
                        possible_usage = EXCLUDED.possible_usage,
                        confidence = EXCLUDED.confidence,
                        embedding = EXCLUDED.embedding,
                        image_hash = EXCLUDED.image_hash
                    """,
                    values,
                )
            else:
                conn.execute(
                    """
                    INSERT INTO products (
                        name, category, brand, material, description, color, shape,
                        estimated_size, possible_usage, confidence, embedding, image_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        category = excluded.category,
                        brand = excluded.brand,
                        material = excluded.material,
                        description = excluded.description,
                        color = excluded.color,
                        shape = excluded.shape,
                        estimated_size = excluded.estimated_size,
                        possible_usage = excluded.possible_usage,
                        confidence = excluded.confidence,
                        embedding = excluded.embedding,
                        image_hash = excluded.image_hash
                    """,
                    values,
                )
        found = self.get_by_hash(image_hash)
        return found or {**payload, "embedding": embedding, "image_hash": image_hash}

    def similar_products(self, embedding: list[float], limit: int = 5) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, category, brand, material, description, color, shape,
                       estimated_size, possible_usage, confidence, embedding, image_hash, created_at
                FROM products
                WHERE embedding IS NOT NULL
                ORDER BY id DESC
                LIMIT 1000
                """
            ).fetchall()
        candidates = [self._row_to_product(row) for row in rows]
        return top_matches(embedding, candidates, limit=limit)

    def _row_to_product(self, row) -> dict[str, Any]:
        data = dict(row)
        data["embedding"] = deserialize_embedding(data.get("embedding"))
        return data

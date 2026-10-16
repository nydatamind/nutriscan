"""
product_database.py
===================
Enterprise-grade, transactional product database with audit logging,
unique barcode constraints, and automatic backups for NutriScan · NY.
DEVELOPED BY NITIN YADAV
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from barcode_validator import normalize_barcode_string, validate_barcode

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "nutriscan_products.db"
BACKUP_DIR = Path(__file__).parent / "backups"


class ProductDatabase:
    """Thread-safe SQLite product database with backup and audit trail."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.backup_dir = BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def close(self) -> None:
        """Run checkpoint and release WAL file handles."""
        try:
            with sqlite3.connect(str(self.db_path), timeout=5.0) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except Exception:
            pass

    def create_backup(self) -> Path:
        """Create a timestamped backup of the database file."""
        if not self.db_path.exists():
            # Nothing to backup yet
            return self.db_path
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"nutriscan_products_backup_{timestamp}.db"
        shutil.copy2(self.db_path, backup_file)
        logger.info("Database backed up to: %s", backup_file)
        return backup_file

    def _init_db(self) -> None:
        """Initialize tables, unique constraints, and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Products table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL,
                brand TEXT NOT NULL,
                category TEXT DEFAULT 'Consumer Product',
                ingredients_text TEXT,
                image_url TEXT DEFAULT '',
                nutriscore TEXT DEFAULT '',
                verification_status TEXT NOT NULL DEFAULT 'VERIFIED',
                confidence_score REAL NOT NULL DEFAULT 1.0,
                source TEXT NOT NULL DEFAULT 'LOCAL_REGISTRY',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_verified_at TEXT NOT NULL
            );
            """)

            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);")

            # Check and add specifications column if missing
            cursor.execute("PRAGMA table_info(products);")
            cols = [row[1] for row in cursor.fetchall()]
            if cols and "specifications" not in cols:
                cursor.execute("ALTER TABLE products ADD COLUMN specifications TEXT DEFAULT '';")

            # Audit log table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT NOT NULL,
                action TEXT NOT NULL,
                old_data TEXT,
                new_data TEXT,
                reason TEXT,
                timestamp TEXT NOT NULL
            );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_barcode ON audit_log(barcode);")
            conn.commit()

    def get_product_by_barcode(self, raw_barcode: str | int | None) -> Optional[Dict[str, Any]]:
        """
        Exact match query by normalized barcode.
        Never uses fuzzy name matching.
        """
        clean = normalize_barcode_string(raw_barcode)
        if not clean:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM products WHERE barcode = ? LIMIT 1;",
                (clean,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def upsert_product(
        self,
        barcode: str,
        name: str,
        brand: str,
        category: str = "Consumer Product",
        ingredients_text: str = "",
        image_url: str = "",
        nutriscore: str = "",
        verification_status: str = "VERIFIED",
        confidence_score: float = 1.0,
        source: str = "LOCAL_REGISTRY",
        reason: str = "Standard update",
        specifications: str = "",
    ) -> Dict[str, Any]:
        """
        Safely insert or update a product with verification checks and audit trail.
        Does not overwrite a high-quality verified record with lower-quality unverified data.
        """
        val_res = validate_barcode(barcode)
        if not val_res.is_valid:
            logger.warning("Attempted to insert invalid barcode %s: %s", barcode, val_res.error_message)
            # Log rejected attempt
            self._log_audit(
                barcode=str(barcode),
                action="REJECT_INVALID_BARCODE",
                old_data=None,
                new_data={"name": name, "brand": brand, "error": val_res.error_message},
                reason=reason,
            )
            raise ValueError(f"Cannot save product with invalid barcode: {val_res.error_message}")

        clean_code = val_res.normalized_barcode
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE barcode = ?;", (clean_code,))
            existing = cursor.fetchone()

            if existing:
                existing_dict = dict(existing)
                # Don't overwrite VERIFIED record with UNVERIFIED data
                if existing_dict.get("verification_status") == "VERIFIED" and verification_status == "UNVERIFIED":
                    logger.info("Skipping overwrite of VERIFIED product %s with UNVERIFIED data", clean_code)
                    return existing_dict

                # Preserve ingredients if incoming data has empty ingredients
                final_ingredients = ingredients_text if ingredients_text.strip() else (existing_dict.get("ingredients_text") or "")
                final_image = image_url if image_url.strip() else (existing_dict.get("image_url") or "")
                final_nutri = nutriscore if nutriscore.strip() else (existing_dict.get("nutriscore") or "")
                final_specs = specifications if specifications.strip() else (existing_dict.get("specifications") or "")

                cursor.execute("""
                    UPDATE products
                    SET name = ?, brand = ?, category = ?, ingredients_text = ?,
                        image_url = ?, nutriscore = ?, verification_status = ?,
                        confidence_score = ?, source = ?, updated_at = ?, last_verified_at = ?,
                        specifications = ?
                    WHERE barcode = ?;
                """, (
                    name.strip(),
                    brand.strip(),
                    category.strip(),
                    final_ingredients.strip(),
                    final_image.strip(),
                    final_nutri.strip(),
                    verification_status,
                    confidence_score,
                    source,
                    now_iso,
                    now_iso,
                    final_specs.strip(),
                    clean_code,
                ))

                new_data = {
                    "barcode": clean_code,
                    "name": name,
                    "brand": brand,
                    "ingredients_text": final_ingredients,
                    "source": source,
                    "verification_status": verification_status,
                    "specifications": final_specs,
                }
                self._log_audit(clean_code, "UPDATE", existing_dict, new_data, reason, conn=conn)
                conn.commit()

                cursor.execute("SELECT * FROM products WHERE barcode = ?;", (clean_code,))
                return dict(cursor.fetchone())

            else:
                cursor.execute("""
                    INSERT INTO products (
                        barcode, name, brand, category, ingredients_text,
                        image_url, nutriscore, verification_status, confidence_score,
                        source, created_at, updated_at, last_verified_at, specifications
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    clean_code,
                    name.strip(),
                    brand.strip(),
                    category.strip(),
                    ingredients_text.strip(),
                    image_url.strip(),
                    nutriscore.strip(),
                    verification_status,
                    confidence_score,
                    source,
                    now_iso,
                    now_iso,
                    now_iso,
                    specifications.strip(),
                ))

                new_data = {
                    "barcode": clean_code,
                    "name": name,
                    "brand": brand,
                    "ingredients_text": ingredients_text,
                    "source": source,
                    "verification_status": verification_status,
                }
                self._log_audit(clean_code, "INSERT", None, new_data, reason, conn=conn)
                conn.commit()

                cursor.execute("SELECT * FROM products WHERE barcode = ?;", (clean_code,))
                return dict(cursor.fetchone())

    def _log_audit(
        self,
        barcode: str,
        action: str,
        old_data: Optional[Dict[str, Any]],
        new_data: Optional[Dict[str, Any]],
        reason: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        """Record audit log entry."""
        now_iso = datetime.now(timezone.utc).isoformat()
        sql = """
            INSERT INTO audit_log (barcode, action, old_data, new_data, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?);
        """
        args = (
            barcode,
            action,
            json.dumps(old_data, default=str) if old_data else None,
            json.dumps(new_data, default=str) if new_data else None,
            reason,
            now_iso,
        )
        if conn:
            conn.execute(sql, args)
        else:
            with self._get_connection() as c:
                c.execute(sql, args)
                c.commit()

    def get_audit_trail(self, barcode: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve audit history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if barcode:
                clean = normalize_barcode_string(barcode)
                cursor.execute("SELECT * FROM audit_log WHERE barcode = ? ORDER BY id DESC;", (clean,))
            else:
                cursor.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100;")
            return [dict(r) for r in cursor.fetchall()]

    def count_products(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM products;")
            return cursor.fetchone()[0]


# Global singleton instance
_GLOBAL_DB: Optional[ProductDatabase] = None


def get_product_database() -> ProductDatabase:
    global _GLOBAL_DB
    if _GLOBAL_DB is None:
        _GLOBAL_DB = ProductDatabase()
    return _GLOBAL_DB

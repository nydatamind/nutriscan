"""
tests/test_product_database.py
==============================
Tests for SQLite product database: transactions, unique constraints,
backup creation, audit trail, and overwrite protection.
"""

import os
import tempfile
from pathlib import Path
import pytest
from product_database import ProductDatabase


@pytest.fixture
def temp_db():
    """Provides a fresh temporary SQLite database instance."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        db_file = Path(tmp_dir) / "test_products.db"
        db = ProductDatabase(db_path=db_file)
        yield db
        db.close()


class TestProductDatabase:
    def test_database_creation_and_backup(self, temp_db):
        """Database is created and backup succeeds."""
        # Insert a sample product
        temp_db.upsert_product(
            barcode="8901030013003",
            name="Parachute Pure Coconut Oil",
            brand="Parachute",
            category="Hair & Edible Oil",
            ingredients_text="100% Pure Coconut Oil",
            verification_status="VERIFIED",
            confidence_score=1.0,
            source="TEST_SUITE",
        )
        assert temp_db.count_products() == 1

        # Backup creation
        backup_path = temp_db.create_backup()
        assert backup_path.exists()
        assert backup_path.stat().st_size > 0

    def test_unique_barcode_constraint(self, temp_db):
        """Updating same barcode updates existing record instead of creating duplicates."""
        temp_db.upsert_product(
            barcode="8901030013003",
            name="Original Name",
            brand="Parachute",
            ingredients_text="Ingredients v1",
        )
        assert temp_db.count_products() == 1

        temp_db.upsert_product(
            barcode="8901030013003",
            name="Updated Name",
            brand="Parachute",
            ingredients_text="Ingredients v2",
        )
        assert temp_db.count_products() == 1
        prod = temp_db.get_product_by_barcode("8901030013003")
        assert prod["name"] == "Updated Name"

    def test_leading_zero_preservation_in_db(self, temp_db):
        """UPC-A barcode starting with 0 is stored and retrieved with 0 intact."""
        code = "012345678905"
        temp_db.upsert_product(
            barcode=code,
            name="Leading Zero Product",
            brand="Test Brand",
            ingredients_text="Test Ingredients",
        )
        prod = temp_db.get_product_by_barcode(code)
        assert prod is not None
        assert prod["barcode"] == "012345678905"
        assert prod["barcode"].startswith("0")

    def test_overwrite_protection_verified_vs_unverified(self, temp_db):
        """A VERIFIED product cannot be overwritten by UNVERIFIED data."""
        temp_db.upsert_product(
            barcode="8901030013003",
            name="Verified Parachute Oil",
            brand="Parachute",
            ingredients_text="100% Pure Coconut Oil",
            verification_status="VERIFIED",
            confidence_score=1.0,
        )

        # Attempt to overwrite with UNVERIFIED data
        temp_db.upsert_product(
            barcode="8901030013003",
            name="Unverified Guess",
            brand="Fake Brand",
            ingredients_text="",
            verification_status="UNVERIFIED",
            confidence_score=0.2,
        )

        prod = temp_db.get_product_by_barcode("8901030013003")
        assert prod["name"] == "Verified Parachute Oil"
        assert prod["verification_status"] == "VERIFIED"

    def test_reject_invalid_barcode_insertion(self, temp_db):
        """Cannot save product with checksum-invalid or partial barcode."""
        with pytest.raises(ValueError):
            temp_db.upsert_product(
                barcode="8901030013004",  # Invalid checksum
                name="Bad Checksum",
                brand="Bad Brand",
            )
        assert temp_db.count_products() == 0

    def test_audit_logging(self, temp_db):
        """Every insert and update creates an audit trail entry."""
        temp_db.upsert_product(
            barcode="8901030013003",
            name="Audit Test Prod",
            brand="Brand A",
            reason="Initial Creation",
        )
        temp_db.upsert_product(
            barcode="8901030013003",
            name="Audit Test Prod V2",
            brand="Brand A",
            reason="Corrected Name",
        )

        trail = temp_db.get_audit_trail("8901030013003")
        assert len(trail) >= 2
        actions = [e["action"] for e in trail]
        assert "INSERT" in actions
        assert "UPDATE" in actions

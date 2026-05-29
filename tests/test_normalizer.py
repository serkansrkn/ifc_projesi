#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ifc_pipeline/normalizer.py modülü için unit testler.
DataFrame oluşturma, boolean dönüşüm, kalite raporu, maliyet hesabı testleri.
"""
import pytest
import sys
import os
import numpy as np
import pandas as pd

# Proje kökünü path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifc_pipeline.normalizer import (
    to_dataframe,
    quality_report,
    add_cost_columns,
    _to_boolean,
    SCHEMA,
    EXPECTED_QUANTITIES,
)


# ─── Test verileri ────────────────────────────────────────────────────────────

def _make_row(**overrides):
    """Test için minimal bir row oluşturur."""
    base = {
        "global_id":       "abc123",
        "element_type":    "wall",
        "ifc_class":       "IfcWall",
        "name":            "Duvar-1",
        "type_name":       "Beton Duvar 200mm",
        "level":           "1. Kat",
        "level_elevation":  3.0,
        "phase":           "",
        "is_external":     True,
        "load_bearing":    False,
        "fire_rating":     "F90",
        "area_m2":         15.5,
        "volume_m3":       3.1,
        "length_m":        5.0,
        "thickness_m":     0.2,
        "materials":       "C30/37",
        "source_software": "revit",
        "source_file":     "test.ifc",
    }
    base.update(overrides)
    return base


def _make_rows(n=5, **overrides):
    """n adet test row'u oluşturur."""
    rows = []
    for i in range(n):
        row = _make_row(global_id=f"id_{i}", name=f"Element-{i}", **overrides)
        rows.append(row)
    return rows


# ─── to_dataframe testleri ────────────────────────────────────────────────────

class TestToDataframe:

    def test_empty_rows(self):
        df = to_dataframe([])
        assert df.empty
        assert list(df.columns) == list(SCHEMA.keys())

    def test_single_row(self):
        df = to_dataframe([_make_row()])
        assert len(df) == 1
        assert df.iloc[0]["global_id"] == "abc123"

    def test_schema_columns_present(self):
        df = to_dataframe([_make_row()])
        for col in SCHEMA:
            assert col in df.columns

    def test_float_columns(self):
        df = to_dataframe([_make_row(area_m2=10.5, volume_m3=2.1)])
        assert df["area_m2"].dtype == "float64"
        assert df["volume_m3"].dtype == "float64"

    def test_category_columns(self):
        df = to_dataframe([_make_row()])
        assert str(df["element_type"].dtype) == "category"
        assert str(df["source_software"].dtype) == "category"

    def test_negative_values_become_nan(self):
        df = to_dataframe([_make_row(area_m2=-5.0)])
        assert pd.isna(df.iloc[0]["area_m2"])

    def test_zero_values_become_nan(self):
        df = to_dataframe([_make_row(volume_m3=0.0)])
        assert pd.isna(df.iloc[0]["volume_m3"])

    def test_missing_column_filled(self):
        row = {"global_id": "x", "element_type": "wall"}
        df = to_dataframe([row])
        assert "area_m2" in df.columns

    def test_none_string_cleaned(self):
        df = to_dataframe([_make_row(name="None")])
        assert df.iloc[0]["name"] == ""

    def test_extra_columns_preserved(self):
        row = _make_row(custom_field="test_value")
        df = to_dataframe([row])
        assert "custom_field" in df.columns
        assert df.iloc[0]["custom_field"] == "test_value"


# ─── Boolean dönüşüm testleri ────────────────────────────────────────────────

class TestToBoolean:

    def test_true_bool(self):
        assert _to_boolean(True) is True

    def test_false_bool(self):
        assert _to_boolean(False) is False

    def test_numpy_true(self):
        assert _to_boolean(np.bool_(True)) is True

    def test_numpy_false(self):
        assert _to_boolean(np.bool_(False)) is False

    def test_string_true(self):
        assert _to_boolean("True") is True
        assert _to_boolean("true") is True

    def test_string_false(self):
        assert _to_boolean("False") is False
        assert _to_boolean("false") is False

    def test_turkish_evet(self):
        assert _to_boolean("evet") is True
        assert _to_boolean("Evet") is True

    def test_turkish_hayir(self):
        assert _to_boolean("hayir") is False
        assert _to_boolean("Hayır") is False

    def test_int_one(self):
        assert _to_boolean(1) is True

    def test_int_zero(self):
        assert _to_boolean(0) is False

    def test_none_returns_na(self):
        assert _to_boolean(None) is pd.NA

    def test_random_string_returns_na(self):
        assert _to_boolean("belki") is pd.NA

    def test_yes_no(self):
        assert _to_boolean("yes") is True
        assert _to_boolean("no") is False


# ─── quality_report testleri ──────────────────────────────────────────────────

class TestQualityReport:

    def test_empty_df(self):
        df = to_dataframe([])
        qa = quality_report(df)
        assert qa["total"] == 0
        assert "DataFrame bos" in qa["warnings"]

    def test_basic_report(self):
        df = to_dataframe(_make_rows(3))
        qa = quality_report(df)
        assert qa["total"] == 3
        assert "wall" in qa["by_type"]

    def test_missing_quantities_warning(self):
        rows = _make_rows(3, area_m2=None, volume_m3=None)
        df = to_dataframe(rows)
        qa = quality_report(df)
        assert any("metraj eksik" in w for w in qa["warnings"])

    def test_duplicate_id_warning(self):
        rows = [_make_row(global_id="dup"), _make_row(global_id="dup")]
        df = to_dataframe(rows)
        qa = quality_report(df)
        assert any("GlobalId tekrari" in w for w in qa["warnings"])

    def test_no_level_warning(self):
        rows = _make_rows(2, level="")
        df = to_dataframe(rows)
        qa = quality_report(df)
        assert any("katsiz" in w for w in qa["warnings"])

    def test_coverage_percentage(self):
        df = to_dataframe(_make_rows(5))
        qa = quality_report(df)
        assert qa["coverage"]["wall"] == 100.0


# ─── add_cost_columns testleri ────────────────────────────────────────────────

class TestAddCostColumns:

    def test_basic_cost(self):
        df = to_dataframe(_make_rows(2, area_m2=10.0))
        prices = {"wall": 100.0}
        result = add_cost_columns(df, prices)
        assert "cost_TL" in result.columns
        assert result["cost_TL"].notna().all()
        assert result.iloc[0]["cost_TL"] == 1000.0  # 10 m² × 100 TL

    def test_custom_currency(self):
        df = to_dataframe(_make_rows(1, area_m2=10.0))
        prices = {"wall": 50.0}
        result = add_cost_columns(df, prices, currency="EUR")
        assert "cost_EUR" in result.columns

    def test_missing_price(self):
        df = to_dataframe(_make_rows(1, element_type="beam", area_m2=10.0))
        prices = {"wall": 100.0}  # beam fiyatı yok
        result = add_cost_columns(df, prices)
        assert pd.isna(result.iloc[0]["unit_price"])

    def test_vectorized_performance(self):
        """Vektörel hesaplama ile 1000 satır sorunsuz çalışmalı."""
        rows = _make_rows(1000, area_m2=5.0)
        df = to_dataframe(rows)
        prices = {"wall": 200.0}
        result = add_cost_columns(df, prices)
        assert len(result) == 1000
        assert result["cost_TL"].sum() == 1000 * 5.0 * 200.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ifc_pipeline/comparator.py modülü için unit testler.
compare(), compare_psets(), flag_large_diffs() testleri.
"""
import pytest
import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifc_pipeline.comparator import (
    compare,
    compare_psets,
    flag_large_diffs,
    _aggregate,
    _ss,
)


# ─── Yardımcı fonksiyonlar ───────────────────────────────────────────────────

def _make_df(rows):
    """Test DataFrame oluşturur."""
    base_cols = {
        "global_id": "string",
        "element_type": "category",
        "level": "string",
        "type_name": "string",
        "area_m2": "float64",
        "volume_m3": "float64",
        "length_m": "float64",
        "thickness_m": "float64",
        "is_external": "boolean",
        "load_bearing": "boolean",
        "fire_rating": "string",
        "materials": "string",
    }
    df = pd.DataFrame(rows)
    for col, dtype in base_cols.items():
        if col not in df.columns:
            if dtype == "float64":
                df[col] = np.nan
            elif dtype == "boolean":
                df[col] = pd.NA
            else:
                df[col] = ""
    df["element_type"] = df["element_type"].astype("category")
    return df


def _make_wall_rows(n, area=10.0, volume=2.0, level="1. Kat"):
    return [
        {
            "global_id": f"w{i}",
            "element_type": "wall",
            "level": level,
            "type_name": "Duvar 200mm",
            "area_m2": area,
            "volume_m3": volume,
            "length_m": 5.0,
            "materials": "C30/37",
        }
        for i in range(n)
    ]


# ─── compare testleri ────────────────────────────────────────────────────────

class TestCompare:

    def test_minimum_two_files(self):
        with pytest.raises(ValueError, match="En az 2 dosya"):
            compare({"tek": _make_df([])})

    def test_basic_compare(self):
        dfs = {
            "revit": _make_df(_make_wall_rows(3, area=10.0)),
            "tekla": _make_df(_make_wall_rows(3, area=12.0)),
        }
        result = compare(dfs)
        assert not result.empty
        assert "revit__adet" in result.columns
        assert "tekla__adet" in result.columns

    def test_diff_columns_present(self):
        dfs = {
            "A": _make_df(_make_wall_rows(2, area=10.0)),
            "B": _make_df(_make_wall_rows(2, area=15.0)),
        }
        result = compare(dfs)
        diff_cols = [c for c in result.columns if "diff_" in c]
        assert len(diff_cols) > 0

    def test_diff_percentage_calculation(self):
        dfs = {
            "A": _make_df(_make_wall_rows(1, area=100.0)),
            "B": _make_df(_make_wall_rows(1, area=110.0)),
        }
        result = compare(dfs)
        diff_col = [c for c in result.columns if "diff_" in c and "area" in c][0]
        # (110 - 100) / 100 * 100 = 10.0%
        assert result.iloc[0][diff_col] == 10.0

    def test_three_files(self):
        dfs = {
            "A": _make_df(_make_wall_rows(1)),
            "B": _make_df(_make_wall_rows(2)),
            "C": _make_df(_make_wall_rows(3)),
        }
        result = compare(dfs)
        # 3 dosya → C(3,2) = 3 çift
        diff_cols = [c for c in result.columns if "diff_" in c]
        # Her çift × 3 metrik (area, volume, length) = 9
        assert len(diff_cols) == 9

    def test_include_type_name(self):
        dfs = {
            "A": _make_df(_make_wall_rows(1)),
            "B": _make_df(_make_wall_rows(1)),
        }
        result = compare(dfs, include_type_name=True)
        assert "type_name" in result.columns

    def test_empty_dataframes(self):
        dfs = {
            "A": _make_df([]),
            "B": _make_df([]),
        }
        result = compare(dfs)
        assert result.empty


# ─── compare_psets testleri ───────────────────────────────────────────────────

class TestComparePsets:

    def test_basic_coverage(self):
        dfs = {
            "revit": _make_df(_make_wall_rows(10)),
        }
        result = compare_psets(dfs)
        assert "kaynak" in result.columns
        assert "toplam" in result.columns
        assert result.iloc[0]["toplam"] == 10

    def test_materials_coverage(self):
        rows = _make_wall_rows(4, area=10.0)
        rows[0]["materials"] = ""  # Boş malzeme
        rows[1]["materials"] = ""
        dfs = {"test": _make_df(rows)}
        result = compare_psets(dfs)
        # 4 elementin 2'sinde malzeme var → %50
        assert result.iloc[0]["materials_%"] == 50.0

    def test_empty_df_skipped(self):
        dfs = {"empty": _make_df([])}
        result = compare_psets(dfs)
        assert result.empty

    def test_multiple_sources(self):
        dfs = {
            "A": _make_df(_make_wall_rows(5)),
            "B": _make_df(_make_wall_rows(3)),
        }
        result = compare_psets(dfs)
        assert len(result) == 2


# ─── flag_large_diffs testleri ────────────────────────────────────────────────

class TestFlagLargeDiffs:

    def test_no_diff_columns(self):
        df = pd.DataFrame({"element_type": ["wall"], "adet": [5]})
        result = flag_large_diffs(df)
        assert result.empty

    def test_small_diffs_not_flagged(self):
        dfs = {
            "A": _make_df(_make_wall_rows(5, area=10.0)),
            "B": _make_df(_make_wall_rows(5, area=10.1)),  # %1 sapma
        }
        comp = compare(dfs)
        result = flag_large_diffs(comp, threshold_pct=5.0)
        assert result.empty

    def test_large_diffs_flagged(self):
        dfs = {
            "A": _make_df(_make_wall_rows(5, area=10.0)),
            "B": _make_df(_make_wall_rows(5, area=20.0)),  # %100 sapma
        }
        comp = compare(dfs)
        result = flag_large_diffs(comp, threshold_pct=5.0)
        assert not result.empty
        assert "max_sapma_pct" in result.columns

    def test_custom_threshold(self):
        dfs = {
            "A": _make_df(_make_wall_rows(1, area=100.0)),
            "B": _make_df(_make_wall_rows(1, area=108.0)),  # %8
        }
        comp = compare(dfs)
        # %10 eşiğinde flag'lenmemeli
        result = flag_large_diffs(comp, threshold_pct=10.0)
        assert result.empty
        # %5 eşiğinde flag'lenmeli
        result = flag_large_diffs(comp, threshold_pct=5.0)
        assert not result.empty


# ─── _aggregate yardımcı testleri ─────────────────────────────────────────────

class TestAggregate:

    def test_basic_aggregation(self):
        df = _make_df(_make_wall_rows(3, area=10.0, volume=2.0))
        result = _aggregate(df, ["element_type", "level"])
        key = ("wall", "1. Kat")
        assert key in result
        assert result[key]["adet"] == 3
        assert result[key]["area_m2"] == 30.0

    def test_missing_column_handled(self):
        df = pd.DataFrame({"element_type": ["wall"], "area_m2": [10.0]})
        df["element_type"] = df["element_type"].astype("category")
        result = _aggregate(df, ["element_type", "level"])
        assert isinstance(result, dict)


# ─── _ss yardımcı testleri ────────────────────────────────────────────────────

class TestSafeSum:

    def test_existing_column(self):
        df = pd.DataFrame({"area_m2": [1.0, 2.0, 3.0]})
        assert _ss(df, "area_m2") == 6.0

    def test_missing_column(self):
        df = pd.DataFrame({"other": [1.0]})
        assert _ss(df, "area_m2") is None

    def test_all_nan(self):
        df = pd.DataFrame({"area_m2": [np.nan, np.nan]})
        assert _ss(df, "area_m2") is None  # sum = 0.0, which is not > 0

    def test_zero_sum(self):
        df = pd.DataFrame({"area_m2": [0.0, 0.0]})
        assert _ss(df, "area_m2") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

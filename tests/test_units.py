#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ifc_pipeline/units.py modülü için unit testler.
Birim dönüşüm doğruluğu, safe_convert, UnitFactors testleri.
"""
import pytest
import sys
import os

# Proje kökünü path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifc_pipeline.units import (
    safe_convert,
    UnitFactors,
    UNIT_TO_SI,
    SI_PREFIXES,
)


class TestUnitToSI:
    """UNIT_TO_SI sözlüğü doğruluk testleri."""

    def test_metre_is_unity(self):
        assert UNIT_TO_SI["METRE"] == 1.0

    def test_millimetre(self):
        assert UNIT_TO_SI["MILLIMETRE"] == 0.001

    def test_centimetre(self):
        assert UNIT_TO_SI["CENTIMETRE"] == 0.01

    def test_foot(self):
        assert abs(UNIT_TO_SI["FOOT"] - 0.3048) < 1e-6

    def test_inch(self):
        assert abs(UNIT_TO_SI["INCH"] - 0.0254) < 1e-6

    def test_yard(self):
        assert abs(UNIT_TO_SI["YARD"] - 0.9144) < 1e-6

    def test_square_foot(self):
        assert abs(UNIT_TO_SI["SQUARE_FOOT"] - 0.092903) < 1e-6

    def test_cubic_foot(self):
        assert abs(UNIT_TO_SI["CUBIC_FOOT"] - 0.0283168) < 1e-6

    def test_square_yard(self):
        assert abs(UNIT_TO_SI["SQUARE_YARD"] - 0.836127) < 1e-6

    def test_cubic_yard(self):
        assert abs(UNIT_TO_SI["CUBIC_YARD"] - 0.764555) < 1e-6


class TestSIPrefixes:
    """SI ön ek çarpanları testleri."""

    def test_milli(self):
        assert SI_PREFIXES["MILLI"] == 1e-3

    def test_centi(self):
        assert SI_PREFIXES["CENTI"] == 1e-2

    def test_kilo(self):
        assert SI_PREFIXES["KILO"] == 1e3

    def test_none_is_unity(self):
        assert SI_PREFIXES[None] == 1.0

    def test_empty_is_unity(self):
        assert SI_PREFIXES[""] == 1.0


class TestSafeConvert:
    """safe_convert fonksiyonu testleri."""

    def test_none_returns_none(self):
        assert safe_convert(None, 1.0) is None

    def test_identity_conversion(self):
        result = safe_convert(5.0, 1.0)
        assert result == 5.0

    def test_millimetre_to_metre(self):
        result = safe_convert(1000.0, 0.001)
        assert abs(result - 1.0) < 1e-6

    def test_foot_to_metre(self):
        result = safe_convert(1.0, 0.3048)
        assert abs(result - 0.3048) < 1e-6

    def test_large_value(self):
        result = safe_convert(1_000_000, 0.001)
        assert abs(result - 1000.0) < 1e-6

    def test_zero_value(self):
        result = safe_convert(0.0, 0.001)
        assert result == 0.0

    def test_negative_value(self):
        result = safe_convert(-5.0, 1.0)
        assert result == -5.0

    def test_string_input_returns_none(self):
        result = safe_convert("abc", 1.0)
        assert result is None

    def test_integer_input(self):
        result = safe_convert(10, 0.001)
        assert abs(result - 0.01) < 1e-6

    def test_rounding(self):
        """Sonuç 6 ondalık haneye yuvarlanmalı."""
        result = safe_convert(1.0, 1/3)
        assert result == round(1/3, 6)


class TestUnitFactors:
    """UnitFactors dataclass testleri."""

    def test_describe_format(self):
        uf = UnitFactors(length=0.001, area=0.000001, volume=0.000000001,
                         source_info="Test")
        desc = uf.describe()
        assert "Uzunluk:" in desc
        assert "Alan:" in desc
        assert "Hacim:" in desc

    def test_default_metres(self):
        uf = UnitFactors(length=1.0, area=1.0, volume=1.0,
                         source_info="Metre")
        assert uf.length == 1.0
        assert uf.area == 1.0
        assert uf.volume == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

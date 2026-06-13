#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ifc_pipeline/extractor.py modülü için unit testler.
Mock IFC element ve context nesneleri kullanarak element çıkarma testleri.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifc_pipeline.extractor import (
    get_storey,
    get_phase,
    extract_element,
    extract_all,
    ExtractionContext,
)
from ifc_pipeline.units import UnitFactors


# ─── Mock Nesneler ────────────────────────────────────────────────────────────

class MockEntity:
    """Minimal mock IFC entity."""
    def __init__(self, type_name, _id=0, **attrs):
        self._type_name = type_name
        self.__id = _id
        for k, v in attrs.items():
            setattr(self, k, v)

    def is_a(self, name):
        return self._type_name == name

    def id(self):
        return self.__id


class MockIFCFile:
    """Minimal mock IFC file."""
    def __init__(self, entities=None):
        self._entities = entities or {}

    def by_type(self, type_name, include_subtypes=True):
        return self._entities.get(type_name, [])

    @property
    def schema(self):
        return "IFC4"


# ─── get_storey testleri ──────────────────────────────────────────────────────

class TestGetStorey:

    def test_no_container(self):
        """Container olmayan element — boş döner."""
        element = MockEntity("IfcWall")
        ifc = MockIFCFile()
        # get_storey ifcopenshell.util.element.get_container kullanır
        # Mock'suz testleme zor — sadece exception handling test ediyoruz
        name, elev = get_storey(element, ifc)
        assert isinstance(name, str)


# ─── get_phase testleri ───────────────────────────────────────────────────────

class TestGetPhase:

    def test_revit_phase(self):
        psets = {
            "Revit Phase": {"Phase Created": "New Construction"},
        }
        result = get_phase(None, psets=psets)
        assert result == "New Construction"

    def test_tekla_phase(self):
        psets = {
            "Tekla Common": {"PHASE": "1"},
        }
        result = get_phase(None, psets=psets)
        assert result == "1"

    def test_standard_pset(self):
        psets = {
            "Pset_ConstructionOccurrence": {"ConstructionPhase": "Phase A"},
        }
        result = get_phase(None, psets=psets)
        assert result == "Phase A"

    def test_no_phase(self):
        psets = {"Pset_WallCommon": {"IsExternal": True}}
        result = get_phase(None, psets=psets)
        assert result == ""

    def test_empty_psets(self):
        result = get_phase(None, psets={})
        assert result == ""


# ─── extract_all testleri ─────────────────────────────────────────────────────

class TestExtractAll:

    def _make_units(self):
        return UnitFactors(length=1.0, area=1.0, volume=1.0, source_info="test")

    def _make_config(self):
        return {
            "element_types": {
                "wall": {
                    "ifc_classes": ["IfcWall"],
                    "quantity_sets": {},
                    "property_sets": {},
                },
            },
        }

    def test_empty_ifc(self):
        ifc = MockIFCFile({})
        config = self._make_config()
        units = self._make_units()

        rows, stats = extract_all(ifc, config, units, "revit", "test.ifc")
        assert rows == []
        assert stats.get("wall") == 0

    def test_element_filter_excludes(self):
        ifc = MockIFCFile({})
        config = self._make_config()
        units = self._make_units()

        rows, stats = extract_all(ifc, config, units, "revit", "test.ifc",
                                  element_filter=["beam"])
        assert "wall" not in stats

    def test_element_filter_none_includes_all(self):
        ifc = MockIFCFile({})
        config = self._make_config()
        units = self._make_units()

        rows, stats = extract_all(ifc, config, units, "revit", "test.ifc",
                                  element_filter=None)
        assert "wall" in stats

    def test_type_product_skipped(self):
        """IfcTypeProduct filtrelenmeli."""
        type_entity = MockEntity("IfcTypeProduct", _id=99, GlobalId="type_001")
        ifc = MockIFCFile({"IfcWall": [type_entity]})
        config = self._make_config()
        units = self._make_units()

        rows, stats = extract_all(ifc, config, units, "revit", "test.ifc")
        assert stats.get("wall") == 0

    def test_no_global_id_skipped(self):
        """GlobalId olmayan element atlanır."""
        entity = MockEntity("IfcWall", _id=1, GlobalId=None)
        ifc = MockIFCFile({"IfcWall": [entity]})
        config = self._make_config()
        units = self._make_units()

        rows, stats = extract_all(ifc, config, units, "revit", "test.ifc")
        assert stats.get("wall") == 0


# ─── ExtractionContext testleri ───────────────────────────────────────────────

class TestExtractionContext:

    def test_cache_initialization(self):
        ctx = ExtractionContext(
            ifc=MockIFCFile(),
            config={},
            units=UnitFactors(1.0, 1.0, 1.0, "test"),
            source_software="revit",
            source_filename="test.ifc",
        )
        assert ctx.psets_cache == {}
        assert ctx.qsets_cache == {}
        assert ctx.type_name_cache == {}

    def test_type_name_cache(self):
        ctx = ExtractionContext(
            ifc=MockIFCFile(),
            config={},
            units=UnitFactors(1.0, 1.0, 1.0, "test"),
            source_software="revit",
            source_filename="test.ifc",
        )
        ctx.type_name_cache[42] = "Duvar 200mm"
        assert ctx.type_name_cache[42] == "Duvar 200mm"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

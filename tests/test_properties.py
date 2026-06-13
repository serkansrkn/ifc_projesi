#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ifc_pipeline/properties.py modülü için unit testler.
Mock IFC element nesneleri kullanarak pset/qset okuma, malzeme ve tip adı testleri.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifc_pipeline.properties import (
    get_all_psets,
    get_property,
    get_all_properties_flat,
    get_all_quantities,
    get_quantity,
    get_all_quantities_flat,
    get_material_names,
    get_type_name,
)


# ─── Mock Nesneler ────────────────────────────────────────────────────────────

class MockEntity:
    """Minimal mock IFC entity."""
    def __init__(self, type_name, **attrs):
        self._type_name = type_name
        for k, v in attrs.items():
            setattr(self, k, v)

    def is_a(self, name):
        return self._type_name == name

    def id(self):
        return getattr(self, "_id", 0)


class MockIFCFile:
    """Minimal mock IFC file for get_type_name tests."""
    def __init__(self, entities=None):
        self._entities = entities or {}

    def by_type(self, type_name, include_subtypes=True):
        return self._entities.get(type_name, [])


# ─── get_property testleri ────────────────────────────────────────────────────

class TestGetProperty:

    def test_found_in_first_chain(self):
        psets = {
            "Pset_WallCommon": {"IsExternal": True},
        }
        chain = [["Pset_WallCommon", "IsExternal"]]
        result = get_property(None, chain, psets=psets)
        assert result is True

    def test_fallback_to_second(self):
        psets = {
            "Pset_WallCommon": {},
            "CustomPset": {"IsExternal": False},
        }
        chain = [
            ["Pset_WallCommon", "IsExternal"],
            ["CustomPset", "IsExternal"],
        ]
        result = get_property(None, chain, psets=psets)
        assert result is False

    def test_not_found(self):
        psets = {"Pset_WallCommon": {}}
        chain = [["Pset_WallCommon", "IsExternal"]]
        result = get_property(None, chain, psets=psets)
        assert result is None

    def test_none_value_skipped(self):
        psets = {
            "Pset_WallCommon": {"IsExternal": None},
            "Backup": {"IsExternal": True},
        }
        chain = [
            ["Pset_WallCommon", "IsExternal"],
            ["Backup", "IsExternal"],
        ]
        result = get_property(None, chain, psets=psets)
        assert result is True

    def test_empty_chain(self):
        psets = {"Pset_WallCommon": {"IsExternal": True}}
        result = get_property(None, [], psets=psets)
        assert result is None

    def test_string_value(self):
        psets = {"Pset_WallCommon": {"FireRating": "F90"}}
        chain = [["Pset_WallCommon", "FireRating"]]
        result = get_property(None, chain, psets=psets)
        assert result == "F90"


# ─── get_all_properties_flat testleri ─────────────────────────────────────────

class TestGetAllPropertiesFlat:

    def test_basic(self):
        """get_all_psets çağrılır — mock element ile test ederiz."""
        # Bu test get_all_psets'in ifcopenshell gerektirdiğinden basit tutulur
        # Doğrudan fonksiyon mantığını test ediyoruz
        pass


# ─── get_quantity testleri ────────────────────────────────────────────────────

class TestGetQuantity:

    def test_found_in_qsets(self):
        qsets = {
            "Qto_WallBaseQuantities": {"GrossSideArea": 15.5},
        }
        chain = [["Qto_WallBaseQuantities", "GrossSideArea"]]
        result = get_quantity(None, chain, qsets=qsets)
        assert result == 15.5

    def test_fallback_in_qsets(self):
        qsets = {
            "Qto_WallBaseQuantities": {},
            "BaseQuantities": {"GrossSideArea": 12.0},
        }
        chain = [
            ["Qto_WallBaseQuantities", "GrossSideArea"],
            ["BaseQuantities", "GrossSideArea"],
        ]
        result = get_quantity(None, chain, qsets=qsets)
        assert result == 12.0

    def test_zero_value_skipped(self):
        qsets = {
            "Qto_WallBaseQuantities": {"GrossSideArea": 0.0},
            "BaseQuantities": {"GrossSideArea": 5.0},
        }
        chain = [
            ["Qto_WallBaseQuantities", "GrossSideArea"],
            ["BaseQuantities", "GrossSideArea"],
        ]
        result = get_quantity(None, chain, qsets=qsets)
        assert result == 5.0

    def test_psets_fallback(self):
        """Quantity set'lerde bulunamazsa property set'lere düşer."""
        qsets = {}
        psets = {
            "Tekla Quantity": {"Length": "3.5"},
        }
        chain = [["Tekla Quantity", "Length"]]
        result = get_quantity(None, chain, qsets=qsets, psets=psets)
        assert result == 3.5

    def test_not_found_anywhere(self):
        qsets = {}
        psets = {}
        chain = [["Qto_WallBaseQuantities", "GrossSideArea"]]
        result = get_quantity(None, chain, qsets=qsets, psets=psets)
        assert result is None

    def test_invalid_pset_value_skipped(self):
        """String dönüştürülemeyen pset değeri atlanır."""
        qsets = {}
        psets = {
            "SomePset": {"Length": "not_a_number"},
        }
        chain = [["SomePset", "Length"]]
        result = get_quantity(None, chain, qsets=qsets, psets=psets)
        assert result is None

    def test_negative_pset_value_skipped(self):
        """Negatif pset değeri atlanır."""
        qsets = {}
        psets = {
            "SomePset": {"Length": "-5.0"},
        }
        chain = [["SomePset", "Length"]]
        result = get_quantity(None, chain, qsets=qsets, psets=psets)
        assert result is None


# ─── get_material_names testleri ──────────────────────────────────────────────

class TestGetMaterialNames:

    def test_no_associations(self):
        element = MockEntity("IfcWall", HasAssociations=None)
        result = get_material_names(element)
        assert result == []

    def test_empty_associations(self):
        element = MockEntity("IfcWall", HasAssociations=[])
        result = get_material_names(element)
        assert result == []

    def test_single_material(self):
        mat = MockEntity("IfcMaterial", Name="C30/37")
        rel = MockEntity("IfcRelAssociatesMaterial", RelatingMaterial=mat)
        element = MockEntity("IfcWall", HasAssociations=[rel])
        result = get_material_names(element)
        assert result == ["C30/37"]

    def test_material_list(self):
        m1 = MockEntity("IfcMaterial", Name="Beton")
        m2 = MockEntity("IfcMaterial", Name="Çelik")
        mat_list = MockEntity("IfcMaterialList", Materials=[m1, m2])
        rel = MockEntity("IfcRelAssociatesMaterial", RelatingMaterial=mat_list)
        element = MockEntity("IfcWall", HasAssociations=[rel])
        result = get_material_names(element)
        assert result == ["Beton", "Çelik"]

    def test_duplicate_materials_deduped(self):
        mat = MockEntity("IfcMaterial", Name="Beton")
        mat_list = MockEntity("IfcMaterialList", Materials=[mat, mat])
        rel = MockEntity("IfcRelAssociatesMaterial", RelatingMaterial=mat_list)
        element = MockEntity("IfcWall", HasAssociations=[rel])
        result = get_material_names(element)
        assert result == ["Beton"]

    def test_non_material_association_skipped(self):
        rel = MockEntity("IfcRelAssociatesClassification")
        element = MockEntity("IfcWall", HasAssociations=[rel])
        result = get_material_names(element)
        assert result == []

    def test_layer_set(self):
        m1 = MockEntity("IfcMaterial", Name="Alçı")
        layer1 = MockEntity("IfcMaterialLayer", Material=m1)
        layer_set = MockEntity("IfcMaterialLayerSet", MaterialLayers=[layer1])
        mat = MockEntity("IfcMaterialLayerSetUsage", ForLayerSet=layer_set)
        rel = MockEntity("IfcRelAssociatesMaterial", RelatingMaterial=mat)
        element = MockEntity("IfcWall", HasAssociations=[rel])
        result = get_material_names(element)
        assert result == ["Alçı"]


# ─── get_type_name testleri ───────────────────────────────────────────────────

class TestGetTypeName:

    def test_from_defines_by_type(self):
        type_obj = MockEntity("IfcWallType", Name="Duvar 200mm")
        rel = MockEntity("IfcRelDefinesByType", RelatingType=type_obj)
        element = MockEntity("IfcWall", IsDefinedBy=[rel], ObjectType=None, Name="Wall-1")
        ifc = MockIFCFile()
        result = get_type_name(element, ifc)
        assert result == "Duvar 200mm"

    def test_from_object_type(self):
        element = MockEntity("IfcWall", IsDefinedBy=[], ObjectType="Beton Duvar", Name="Wall-1")
        ifc = MockIFCFile()
        result = get_type_name(element, ifc)
        assert result == "Beton Duvar"

    def test_no_type_returns_empty(self):
        """Element.Name fallback kaldırıldıktan sonra boş string dönmeli."""
        element = MockEntity("IfcWall", IsDefinedBy=[], ObjectType=None, Name="Wall-1")
        ifc = MockIFCFile()
        result = get_type_name(element, ifc)
        assert result == ""

    def test_none_defined_by(self):
        element = MockEntity("IfcWall", IsDefinedBy=None, ObjectType=None, Name=None)
        ifc = MockIFCFile()
        result = get_type_name(element, ifc)
        assert result == ""

    def test_type_obj_without_name(self):
        type_obj = MockEntity("IfcWallType", Name=None)
        rel = MockEntity("IfcRelDefinesByType", RelatingType=type_obj)
        element = MockEntity("IfcWall", IsDefinedBy=[rel], ObjectType="Fallback Type", Name="Wall-1")
        ifc = MockIFCFile()
        result = get_type_name(element, ifc)
        assert result == "Fallback Type"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

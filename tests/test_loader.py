#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ifc_pipeline/loader.py modülü için unit testler.
Mock IFC nesneleri kullanarak dosya validasyonu, yazılım tespiti ve meta bilgi testleri.
"""
import pytest
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifc_pipeline.loader import (
    _validate_ifc_file,
    _detect_software,
    _get_application_info,
    _get_single_attr,
    _count_physical_elements,
    IFCFileInfo,
    SOFTWARE_SIGNATURES,
)


# ─── _validate_ifc_file testleri ──────────────────────────────────────────────

class TestValidateIFCFile:

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Dosya bulunamadı"):
            _validate_ifc_file("/tmp/nonexistent_file.ifc")

    def test_wrong_extension(self, tmp_path):
        bad_file = tmp_path / "test.txt"
        bad_file.write_text("data")
        with pytest.raises(ValueError, match="Geçersiz dosya uzantısı"):
            _validate_ifc_file(str(bad_file))

    def test_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.ifc"
        empty_file.write_text("")
        with pytest.raises(ValueError, match="Boş dosya"):
            _validate_ifc_file(str(empty_file))

    def test_invalid_header(self, tmp_path):
        bad_ifc = tmp_path / "bad.ifc"
        bad_ifc.write_bytes(b"NOT-A-VALID-IFC-HEADER-DATA")
        with pytest.raises(ValueError, match="Geçersiz IFC dosya formatı"):
            _validate_ifc_file(str(bad_ifc))

    def test_valid_iso10303_21_header(self, tmp_path):
        valid_ifc = tmp_path / "valid.ifc"
        valid_ifc.write_bytes(b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION();\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;")
        # Hata fırlatmamalı
        _validate_ifc_file(str(valid_ifc))

    def test_valid_iso10303_28_header(self, tmp_path):
        valid_ifc = tmp_path / "valid28.ifc"
        valid_ifc.write_bytes(b"ISO-10303-28;\n<data/>")
        _validate_ifc_file(str(valid_ifc))


# ─── _detect_software testleri ────────────────────────────────────────────────

class TestDetectSoftware:

    @pytest.mark.parametrize("app_name,expected", [
        ("Autodesk Revit 2024", "revit"),
        ("Revit", "revit"),
        ("REVIT Architecture", "revit"),
        ("Tekla Structures", "tekla"),
        ("tekla", "tekla"),
        ("GRAPHISOFT ArchiCAD 27", "archicad"),
        ("Graphisoft", "archicad"),
        ("Nemetschek Allplan 2024", "allplan"),
        ("Vectorworks 2024", "vectorworks"),
        ("BlenderBIM", "openBIM"),
        ("IfcOpenShell", "openBIM"),
        ("Bentley AECOsim", "bentley"),
        ("Civil 3D", "civil3d"),
    ])
    def test_known_software(self, app_name, expected):
        assert _detect_software(app_name) == expected

    def test_unknown_software(self):
        assert _detect_software("CustomBIMTool") == "unknown"

    def test_empty_string(self):
        assert _detect_software("") == "unknown"

    def test_case_insensitive(self):
        assert _detect_software("AUTODESK REVIT") == "revit"
        assert _detect_software("tekla STRUCTURES") == "tekla"


# ─── SOFTWARE_SIGNATURES yapı testleri ────────────────────────────────────────

class TestSoftwareSignatures:

    def test_all_signatures_lowercase(self):
        """Tüm imzalar küçük harf olmalı çünkü karşılaştırma .lower() ile yapılır."""
        for software, signatures in SOFTWARE_SIGNATURES.items():
            for sig in signatures:
                assert sig == sig.lower(), f"{software}: '{sig}' küçük harf değil"

    def test_known_softwares_exist(self):
        expected = {"revit", "tekla", "archicad", "allplan", "vectorworks", "openBIM", "civil3d", "bentley"}
        assert set(SOFTWARE_SIGNATURES.keys()) == expected


# ─── IFCFileInfo testleri ─────────────────────────────────────────────────────

class TestIFCFileInfo:

    def _make_info(self, **overrides):
        defaults = dict(
            path="/tmp/test.ifc", filename="test.ifc", schema="IFC4",
            source_software="revit", app_name="Autodesk Revit", app_version="2024",
            organization="Autodesk", project_name="Test Project",
            site_name="Site A", building_name="Building 1",
            storey_count=3, element_counts={"IfcWall": 10, "IfcSlab": 5},
            has_quantity_sets=True, has_geometry=True,
            file_size_mb=25.3, warnings=[],
        )
        defaults.update(overrides)
        return IFCFileInfo(**defaults)

    def test_summary_basic(self):
        info = self._make_info()
        summary = info.summary()
        assert "test.ifc" in summary
        assert "IFC4" in summary
        assert "revit" in summary
        assert "IfcWall" in summary

    def test_summary_with_warnings(self):
        info = self._make_info(warnings=["IfcElementQuantity bulunamadı."])
        summary = info.summary()
        assert "Uyarılar" in summary
        assert "IfcElementQuantity" in summary

    def test_summary_no_quantity_sets(self):
        info = self._make_info(has_quantity_sets=False)
        summary = info.summary()
        assert "YOK" in summary


# ─── _get_single_attr testleri (mock IFC) ─────────────────────────────────────

class MockIFCEntity:
    """Minimal mock IFC entity."""
    def __init__(self, **attrs):
        for k, v in attrs.items():
            setattr(self, k, v)

    def is_a(self, type_name):
        return self._type == type_name


class MockIFCFile:
    """Minimal mock IFC file."""
    def __init__(self, entities=None):
        self._entities = entities or {}

    def by_type(self, type_name, include_subtypes=True):
        return self._entities.get(type_name, [])

    @property
    def schema(self):
        return "IFC4"


class TestGetSingleAttr:

    def test_found(self):
        project = MockIFCEntity(Name="Test Project", _type="IfcProject")
        ifc = MockIFCFile({"IfcProject": [project]})
        result = _get_single_attr(ifc, "IfcProject", "Name")
        assert result == "Test Project"

    def test_not_found(self):
        ifc = MockIFCFile({})
        result = _get_single_attr(ifc, "IfcProject", "Name")
        assert result == ""

    def test_none_attribute(self):
        project = MockIFCEntity(Name=None, _type="IfcProject")
        ifc = MockIFCFile({"IfcProject": [project]})
        result = _get_single_attr(ifc, "IfcProject", "Name")
        assert result == ""


# ─── _count_physical_elements testleri ────────────────────────────────────────

class TestCountPhysicalElements:

    def test_with_config(self):
        wall1 = MockIFCEntity(_type="IfcWall")
        wall2 = MockIFCEntity(_type="IfcWall")
        ifc = MockIFCFile({"IfcWall": [wall1, wall2]})
        config = {
            "element_types": {
                "wall": {"ifc_classes": ["IfcWall"]}
            }
        }
        counts = _count_physical_elements(ifc, config)
        assert counts.get("IfcWall") == 2

    def test_without_config(self):
        ifc = MockIFCFile({})
        counts = _count_physical_elements(ifc, None)
        # Boş IFC — hiçbir sınıfta element yok
        assert isinstance(counts, dict)

    def test_missing_class_skipped(self):
        """Schema'da olmayan sınıf hata vermemeli."""
        ifc = MockIFCFile({})
        config = {
            "element_types": {
                "wall": {"ifc_classes": ["IfcWall", "IfcNonExistentClass"]}
            }
        }
        counts = _count_physical_elements(ifc, config)
        assert isinstance(counts, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

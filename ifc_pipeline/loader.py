# ifc_pipeline/loader.py
"""
IFC dosyasını açar ve hangi yazılımın ürettiğini tespit eder.

Yazılım tespiti kritiktir çünkü:
- Revit, Tekla, Archicad farklı Pset isimleri kullanır
- Bazı yazılımlar IfcWallStandardCase yerine IfcWall yazar
- Birim assignment bazı yazılımlarda eksiktir
"""

from __future__ import annotations
import os
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

import ifcopenshell

logger = logging.getLogger(__name__)

# Dosya boyutu uyarı eşiği (500 MB)
FILE_SIZE_WARNING_MB = 500


# ─── Tanımlı yazılım imzaları ────────────────────────────────────────────────
# Her yazılımın IfcApplication.ApplicationFullName veya
# IfcApplication.ApplicationIdentifier alanında bıraktığı iz.

SOFTWARE_SIGNATURES: dict[str, list[str]] = {
    "revit":    ["revit", "autodesk revit"],
    "tekla":    ["tekla", "tekla structures"],
    "archicad": ["archicad", "graphisoft archicad", "graphisoft"],
    "allplan":  ["allplan", "nemetschek allplan"],
    "vectorworks": ["vectorworks", "nemetschek vectorworks"],
    "openBIM":  ["blenderbim", "ifcopenshell"],
    "civil3d":  ["civil 3d", "autocad civil"],
    "bentley":  ["bentley", "aecosim"],
}


@dataclass
class IFCFileInfo:
    """Yüklenen bir IFC dosyasına ait meta bilgiler."""
    path: str
    filename: str
    schema: str               # IFC2X3, IFC4, IFC4X3 ...
    source_software: str      # tespit edilen yazılım
    app_name: str             # ham application adı
    app_version: str          # uygulama versiyonu
    organization: str         # üretici organizasyon
    project_name: str         # IfcProject.Name
    site_name: str            # IfcSite.Name
    building_name: str        # IfcBuilding.Name
    storey_count: int         # kat sayısı
    element_counts: dict      # tip → adet
    has_quantity_sets: bool   # herhangi bir QuantitySet var mı?
    has_geometry: bool        # geometry representation var mı?
    file_size_mb: float       # dosya boyutu (MB)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Dosya       : {self.filename} ({self.file_size_mb:.1f} MB)",
            f"Schema      : {self.schema}",
            f"Yazılım     : {self.source_software} ({self.app_name} {self.app_version})",
            f"Organizasyon: {self.organization}",
            f"Proje       : {self.project_name}",
            f"Yapı        : {self.building_name}",
            f"Kat Sayısı  : {self.storey_count}",
            f"Quantity Set: {'Var' if self.has_quantity_sets else 'YOK — metraj için geometri gerekecek'}",
            "",
            "Element Sayıları:",
        ]
        for ifc_class, count in sorted(self.element_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {ifc_class:<35} {count:>5}")
        if self.warnings:
            lines.append("\nUyarılar:")
            for w in self.warnings:
                lines.append(f"  ⚠  {w}")
        return "\n".join(lines)


def load(path: str, config: dict = None) -> tuple[ifcopenshell.file, IFCFileInfo]:
    """
    IFC dosyasını açar, meta bilgileri çıkarır ve IFCFileInfo döner.

    Args:
        path: IFC dosya yolu
        config: mapping.yaml config dict'i (element sayımı için)

    Returns:
        (ifc_file, info) tuple'ı
    Raises:
        FileNotFoundError: Dosya yoksa
        RuntimeError: Geçersiz IFC dosyasıysa
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Dosya bulunamadı: {path}")

    # Dosya boyutu kontrolü
    file_size_bytes = os.path.getsize(path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    if file_size_mb > FILE_SIZE_WARNING_MB:
        logger.warning(
            "Dosya çok büyük: %.0f MB — işlem uzun sürebilir ve bellek yetmeyebilir.",
            file_size_mb
        )

    try:
        ifc = ifcopenshell.open(path)
    except Exception as e:
        raise RuntimeError(f"IFC açılamadı: {path}\n{e}")

    filename = os.path.basename(path)
    schema   = ifc.schema  # "IFC2X3", "IFC4" vb.
    warnings = []

    # ── Yazılım tespiti ─────────────────────────────────────────────────────
    app_name, app_version, organization = _get_application_info(ifc)
    source_software = _detect_software(app_name)
    logger.info("Yazılım tespit edildi: %s (%s)", source_software, app_name)

    # ── Proje / Yapı / Site ──────────────────────────────────────────────────
    project_name  = _get_single_attr(ifc, "IfcProject", "Name")
    site_name     = _get_single_attr(ifc, "IfcSite", "Name")
    building_name = _get_single_attr(ifc, "IfcBuilding", "Name")

    # ── Kat sayısı ────────────────────────────────────────────────────────────
    storeys = ifc.by_type("IfcBuildingStorey")
    storey_count = len(storeys)
    if storey_count == 0:
        warnings.append("IfcBuildingStorey bulunamadı — kat bilgisi eksik olacak.")

    # ── Element sayıları ──────────────────────────────────────────────────────
    element_counts = _count_physical_elements(ifc, config)

    # ── Quantity Set kontrolü ─────────────────────────────────────────────────
    has_quantity_sets = len(ifc.by_type("IfcElementQuantity")) > 0
    if not has_quantity_sets:
        warnings.append(
            "IfcElementQuantity bulunamadı. "
            "Revit export'unda 'Export base quantities' seçeneği kapalı olabilir. "
            "Metraj değerleri boş gelebilir."
        )

    # ── Geometry kontrolü ────────────────────────────────────────────────────
    has_geometry = len(ifc.by_type("IfcShapeRepresentation")) > 0

    # ── Schema-spesifik uyarılar ──────────────────────────────────────────────
    if schema == "IFC2X3":
        warnings.append(
            "IFC2X3 dosyası. IfcWallStandardCase gibi deprecated class'lar "
            "kullanılmış olabilir — otomatik normalize edilecek."
        )

    info = IFCFileInfo(
        path=path,
        filename=filename,
        schema=schema,
        source_software=source_software,
        app_name=app_name,
        app_version=app_version,
        organization=organization,
        project_name=project_name,
        site_name=site_name,
        building_name=building_name,
        storey_count=storey_count,
        element_counts=element_counts,
        has_quantity_sets=has_quantity_sets,
        has_geometry=has_geometry,
        file_size_mb=round(file_size_mb, 1),
        warnings=warnings,
    )
    return ifc, info


# ─── Yardımcı fonksiyonlar ────────────────────────────────────────────────────

def _get_application_info(ifc: ifcopenshell.file) -> tuple[str, str, str]:
    """IfcApplication ve IfcOrganization'dan yazılım bilgisini çeker."""
    app_name    = "Bilinmiyor"
    app_version = ""
    org_name    = ""

    try:
        apps = ifc.by_type("IfcApplication")
        if apps:
            app = apps[0]
            app_name    = getattr(app, "ApplicationFullName", "") or \
                          getattr(app, "ApplicationIdentifier", "") or "Bilinmiyor"
            app_version = getattr(app, "Version", "") or ""

            org = getattr(app, "ApplicationDeveloper", None)
            if org:
                org_name = getattr(org, "Name", "") or ""
    except Exception as e:
        logger.debug("IfcApplication okunamadı: %s", e)

    # Alternatif: IfcOrganization
    if not org_name:
        try:
            orgs = ifc.by_type("IfcOrganization")
            if orgs:
                org_name = getattr(orgs[0], "Name", "") or ""
        except Exception as e:
            logger.debug("IfcOrganization okunamadı: %s", e)

    return app_name, app_version, org_name


def _detect_software(app_name: str) -> str:
    """Ham uygulama adından standart yazılım adını tespit eder."""
    name_lower = app_name.lower()
    for software, signatures in SOFTWARE_SIGNATURES.items():
        for sig in signatures:
            if sig in name_lower:
                return software
    return "unknown"


def _get_single_attr(ifc: ifcopenshell.file, ifc_type: str, attr: str) -> str:
    """Bir IFC tipin ilk örneğinden bir attribute değeri alır."""
    try:
        items = ifc.by_type(ifc_type)
        if items:
            val = getattr(items[0], attr, None)
            return str(val) if val else ""
    except Exception as e:
        logger.debug("%s.%s okunamadı: %s", ifc_type, attr, e)
    return ""


def _count_physical_elements(ifc: ifcopenshell.file, config: dict = None) -> dict[str, int]:
    """
    Fiziksel element sınıflarını sayar.
    Config varsa oradan senkronize eder, yoksa sabit listeyi kullanır.
    """
    target_classes = set()

    # Config'den IFC sınıflarını senkronize et
    if config:
        for et_config in config.get("element_types", {}).values():
            for cls in et_config.get("ifc_classes", []):
                target_classes.add(cls)

    # Ek sabit sınıflar (config'de tanımlanmasa bile sayılmalı)
    extra_classes = [
        "IfcBuildingElementProxy",  # tanımlanmamış elementler
        "IfcFurnishingElement",
        "IfcFlowSegment",
        "IfcFlowTerminal",
    ]
    target_classes.update(extra_classes)

    # Config yoksa varsayılan listeyi kullan
    if not config:
        default_classes = [
            "IfcWall", "IfcWallStandardCase", "IfcWallElementedCase",
            "IfcBeam", "IfcBeamStandardCase",
            "IfcColumn", "IfcColumnStandardCase",
            "IfcSlab", "IfcDoor", "IfcWindow",
            "IfcMember", "IfcMemberStandardCase",
            "IfcFooting", "IfcPile",
            "IfcStair", "IfcStairFlight",
            "IfcRoof", "IfcRamp", "IfcRampFlight",
            "IfcCurtainWall", "IfcRailing", "IfcCovering", "IfcPlate",
        ]
        target_classes.update(default_classes)

    counts = {}
    for cls in sorted(target_classes):
        try:
            items = ifc.by_type(cls, include_subtypes=False)
            if items:
                counts[cls] = len(items)
        except Exception:
            pass
    return counts

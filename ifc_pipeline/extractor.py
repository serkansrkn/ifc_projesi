# ifc_pipeline/extractor.py
"""
IFC dosyasından element verilerini ceker ve normallestir.
Tum yazilim variantlarini (IfcWall, IfcWallStandardCase vb.) yakalar.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import logging
import ifcopenshell
import ifcopenshell.util.element as ifc_util

from .units import UnitFactors, safe_convert
from .properties import (
    get_property, get_quantity,
    get_material_names, get_type_name,
    get_all_psets, get_all_quantities,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractionContext:
    """Element çıkarma için gerekli tüm bağlam bilgisini taşır."""
    ifc: ifcopenshell.file
    config: dict
    units: UnitFactors
    source_software: str
    source_filename: str


def get_storey(element, ifc: ifcopenshell.file):
    """Elementin bağlı olduğu kat bilgisini döner."""
    try:
        container = ifc_util.get_container(element)
        if container is None:
            return "", None
        if container.is_a("IfcBuildingStorey"):
            name = getattr(container, "Name", "") or ""
            elev = getattr(container, "Elevation", None)
            return name, elev
        parent = ifc_util.get_container(container)
        if parent and parent.is_a("IfcBuildingStorey"):
            return getattr(parent, "Name", "") or "", getattr(parent, "Elevation", None)
    except Exception as e:
        logger.debug("Kat bilgisi okunamadı (element #%s): %s",
                     getattr(element, "GlobalId", "?"), e)
    return "", None


def get_phase(element, psets: dict = None) -> str:
    """Elementin yapım aşaması bilgisini döner."""
    try:
        if psets is None:
            psets = get_all_psets(element)
        # Standart IFC Pset
        for pset_name in ["Pset_ConstructionOccurrence"]:
            val = psets.get(pset_name, {}).get("ConstructionPhase")
            if val:
                return str(val)
        # Revit phase
        for pset in psets.values():
            if isinstance(pset, dict):
                val = pset.get("Phase Created")
                if val:
                    return str(val)
        # Tekla phase
        for pset in psets.values():
            if isinstance(pset, dict):
                val = pset.get("PHASE") or pset.get("Phase")
                if val:
                    return str(val)
    except Exception as e:
        logger.debug("Phase bilgisi okunamadı (element #%s): %s",
                     getattr(element, "GlobalId", "?"), e)
    return ""


def extract_element(element, element_type, config, ctx: ExtractionContext):
    """
    Tek bir IFC elementinden tüm metraj verilerini çıkarır.
    Pset ve Qset'ler element başına bir kez okunur (cache).
    """
    qsets_config = config.get("quantity_sets", {})
    psets_config = config.get("property_sets", {})

    # ── Pset ve Qset'leri bir kez çek (PERF-1 düzeltmesi) ──
    psets = get_all_psets(element)
    qsets = get_all_quantities(element)

    global_id = getattr(element, "GlobalId", "") or ""
    name      = getattr(element, "Name", "") or ""
    ifc_class = element.is_a()
    type_name = get_type_name(element, ctx.ifc)

    level_name, level_elev_raw = get_storey(element, ctx.ifc)
    level_elev_m = safe_convert(level_elev_raw, ctx.units.length) if level_elev_raw is not None else None

    phase = get_phase(element, psets=psets)

    # Quantity'leri cache'den oku (psets fallback ile — Tekla Quantity desteği)
    area_raw      = get_quantity(element, qsets_config.get("area", []),      qsets=qsets, psets=psets)
    volume_raw    = get_quantity(element, qsets_config.get("volume", []),    qsets=qsets, psets=psets)
    length_raw    = get_quantity(element, qsets_config.get("length", []),    qsets=qsets, psets=psets)
    thickness_raw = get_quantity(element, qsets_config.get("thickness", []) or
                                          qsets_config.get("height", []),   qsets=qsets, psets=psets)

    area_m2     = safe_convert(area_raw,      ctx.units.area)
    volume_m3   = safe_convert(volume_raw,    ctx.units.volume)
    length_m    = safe_convert(length_raw,    ctx.units.length)
    thickness_m = safe_convert(thickness_raw, ctx.units.length)

    # Property'leri cache'den oku
    is_external  = get_property(element, psets_config.get("is_external", []),  psets=psets)
    load_bearing = get_property(element, psets_config.get("load_bearing", []), psets=psets)
    fire_rating  = get_property(element, psets_config.get("fire_rating", []),  psets=psets)

    if isinstance(is_external, str):
        is_external = is_external.lower() in ("true", "1", "yes", "evet")
    if isinstance(load_bearing, str):
        load_bearing = load_bearing.lower() in ("true", "1", "yes", "evet")

    materials = get_material_names(element)

    return {
        "global_id":       global_id,
        "element_type":    element_type,
        "ifc_class":       ifc_class,
        "name":            name,
        "type_name":       type_name,
        "level":           level_name,
        "level_elevation": level_elev_m,
        "phase":           phase,
        "is_external":     is_external,
        "load_bearing":    load_bearing,
        "fire_rating":     fire_rating,
        "area_m2":         area_m2,
        "volume_m3":       volume_m3,
        "length_m":        length_m,
        "thickness_m":     thickness_m,
        "materials":       ", ".join(materials) if materials else "",
        "source_software": ctx.source_software,
        "source_file":     ctx.source_filename,
    }


def extract_all(ifc, config, units, source_software, source_filename, element_filter=None):
    """
    Tum element tiplerini ceker.
    Returns: (rows_list, stats_dict)
    """
    # tqdm'i opsiyonel olarak import et
    try:
        from tqdm import tqdm
        has_tqdm = True
    except ImportError:
        has_tqdm = False

    ctx = ExtractionContext(
        ifc=ifc,
        config=config,
        units=units,
        source_software=source_software,
        source_filename=source_filename,
    )

    element_types_config = config.get("element_types", {})
    rows = []
    stats = {}

    for elem_type, elem_config in element_types_config.items():
        if element_filter and elem_type not in element_filter:
            continue

        ifc_classes = elem_config.get("ifc_classes", [])
        type_rows = []
        seen_ids = set()  # ayni element iki farkli class'ta gorundugunde tekrar sayma

        for ifc_class in ifc_classes:
            try:
                elements = ifc.by_type(ifc_class, include_subtypes=False)
            except Exception:
                continue

            # tqdm varsa ilerleme göster
            iterator = elements
            if has_tqdm and len(elements) > 100:
                iterator = tqdm(elements, desc=f"  {ifc_class}", leave=False)

            for element in iterator:
                # BUG-2 düzeltmesi: tüm işlem try bloğu içinde
                try:
                    if element.is_a("IfcTypeProduct"):
                        continue
                    eid = element.id()
                    if eid in seen_ids:
                        continue
                    seen_ids.add(eid)

                    row = extract_element(
                        element=element,
                        element_type=elem_type,
                        config=elem_config,
                        ctx=ctx,
                    )
                    type_rows.append(row)
                except Exception as e:
                    logger.warning("%s element atlandı (id=%s): %s",
                                   ifc_class, getattr(element, "GlobalId", "?"), e)

        stats[elem_type] = len(type_rows)
        rows.extend(type_rows)

    return rows, stats

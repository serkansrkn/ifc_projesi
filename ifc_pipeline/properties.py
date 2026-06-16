# ifc_pipeline/properties.py
"""
Property Set ve Quantity Set okuma modülü.

Ana zorluk: Aynı veri farklı yazılımlarda farklı Pset/Qto isimlerinde saklanır.
Çözüm: YAML config'den gelen fallback zincirleri — sırayla dener, ilk bulduğunu alır.

Son çare (item-5 fallback): Zincir başarısız olduğunda generic isim taraması yapar.
Bu Archicad, VectorWorks ve non-standard QSet isimleri kullanan yazılımları kapsar.
"""

from __future__ import annotations
from typing import Any, Optional
import logging
import ifcopenshell
import ifcopenshell.util.element as ifc_util

logger = logging.getLogger(__name__)


# ─── Property Set okuma ────────────────────────────────────────────────────────

def get_all_psets(element) -> dict[str, dict[str, Any]]:
    """
    Bir elementin tüm property set'lerini döner.
    {pset_adı: {property_adı: değer}} formatında.
    """
    try:
        return ifc_util.get_psets(element) or {}
    except Exception as e:
        logger.debug("get_psets hatası (element #%s): %s",
                     getattr(element, "GlobalId", "?"), e)
        return {}


def get_property(element, fallback_chain: list[list[str]], psets: dict = None) -> Any:
    """
    Fallback zincirini kullanarak bir property değeri arar.

    Args:
        element: IFC element
        fallback_chain: [[pset_adı, prop_adı], ...] listesi
        psets: Önceden çekilmiş pset dict'i (cache için)

    Returns:
        İlk bulunan değer, hiçbiri bulunamazsa None
    """
    if psets is None:
        psets = get_all_psets(element)
    for pset_name, prop_name in fallback_chain:
        pset = psets.get(pset_name, {})
        if prop_name in pset:
            val = pset[prop_name]
            if val is not None:
                return val
    return None


def get_all_properties_flat(element) -> dict[str, Any]:
    """
    Tüm property set'leri düz bir dict'e açar.
    Format: {"PsetAdi.PropAdi": değer, ...}
    """
    result = {}
    for pset_name, props in get_all_psets(element).items():
        if isinstance(props, dict):
            for prop_name, val in props.items():
                result[f"{pset_name}.{prop_name}"] = val
    return result


# ─── Quantity Set okuma ────────────────────────────────────────────────────────

def get_all_quantities(element) -> dict[str, dict[str, float]]:
    """
    Bir elementin tüm QuantitySet'lerini döner.
    {qset_adı: {quantity_adı: sayısal_değer}} formatında.
    Değerler ham IFC birimi cinsinden döner.
    """
    result: dict[str, dict[str, float]] = {}
    try:
        defined_by = getattr(element, "IsDefinedBy", None)
        if not defined_by:
            return result

        for rel in defined_by:
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcElementQuantity"):
                continue

            qset_name = getattr(pdef, "Name", "UnnamedQSet") or "UnnamedQSet"
            quantities = {}

            for q in (pdef.Quantities or []):
                q_name = getattr(q, "Name", None)
                if not q_name:
                    continue

                val = None
                if q.is_a("IfcQuantityArea"):
                    val = q.AreaValue
                elif q.is_a("IfcQuantityVolume"):
                    val = q.VolumeValue
                elif q.is_a("IfcQuantityLength"):
                    val = q.LengthValue
                elif q.is_a("IfcQuantityCount"):
                    val = q.CountValue
                elif q.is_a("IfcQuantityWeight"):
                    val = q.WeightValue
                elif q.is_a("IfcQuantityTime"):
                    val = q.TimeValue

                if val is not None:
                    quantities[q_name] = float(val)

            if quantities:
                result[qset_name] = quantities

    except Exception as e:
        logger.warning("Quantity okunamadı (element #%s): %s",
                       getattr(element, "GlobalId", "?"), e)

    return result


def get_quantity(element, fallback_chain: list[list[str]], qsets: dict = None,
                 psets: dict = None) -> Optional[float]:
    """
    Fallback zincirini kullanarak bir quantity değeri arar.

    Önce IfcElementQuantity set'lerine (qsets) bakar; bulamazsa
    IfcPropertySet'lere (psets) düşer.

    Args:
        element: IFC element
        fallback_chain: [[set_adı, değer_adı], ...] listesi
        qsets: Önceden çekilmiş quantity set dict'i (cache için)
        psets: Önceden çekilmiş property set dict'i (pset fallback için)

    Returns:
        Ham sayısal değer (birimsiz), hiçbiri bulunamazsa None.
    """
    if qsets is None:
        qsets = get_all_quantities(element)

    # 1. Önce quantity set'lerde ara
    for qset_name, qty_name in fallback_chain:
        qset = qsets.get(qset_name, {})
        if qty_name in qset:
            val = qset[qty_name]
            if val is not None and val > 0:
                return float(val)

    # 2. Property set'lerde ara (Tekla bazı değerleri pset içinde saklar)
    if psets is not None:
        for pset_name, prop_name in fallback_chain:
            pset = psets.get(pset_name, {})
            if isinstance(pset, dict) and prop_name in pset:
                val = pset[prop_name]
                if val is not None:
                    try:
                        fval = float(val)
                        if fval > 0:
                            return fval
                    except (TypeError, ValueError):
                        continue

    return None


def get_all_quantities_flat(element) -> dict[str, float]:
    """
    Tüm quantity set'leri düz dict'e açar.
    Format: {"QSetAdi.QtyAdi": değer, ...}
    """
    result = {}
    for qset_name, qtys in get_all_quantities(element).items():
        for qty_name, val in qtys.items():
            result[f"{qset_name}.{qty_name}"] = val
    return result


# ─── Generic Fallback Tarayıcılar (item-5) ────────────────────────────────────

# Quantity tipine göre aranacak generic isimler.
# Öncelik sırasına göre dizilmiştir: önce net, sonra gross değerler.
_GENERIC_QTY_NAMES: dict[str, list[str]] = {
    "area": [
        "NetArea", "GrossArea", "Area",
        "NetSideArea", "GrossSideArea",
        "NetFloorArea", "GrossFloorArea",
        "GrossRoofArea", "NetRoofArea",
        "GrossCoverArea", "NetCoverArea",
    ],
    "volume": [
        "NetVolume", "GrossVolume", "Volume",
        "NetBodyVolume", "GrossBodyVolume",
    ],
    "length": [
        "Length", "NetLength", "OuterLength",
        "Span", "OverallLength",
    ],
    "weight": [
        # Standard IFC
        "Weight", "NetWeight", "GrossWeight",
        # Tekla
        "WEIGHT_NET", "WEIGHT_GROSS", "WEIGHT",
    ],
}

# PSet taramasında kullanılacak isimler (QSet taramasından daha dar tutulur)
_GENERIC_PSET_NAMES: dict[str, list[str]] = {
    "area":   ["Area", "GrossArea", "NetArea", "SurfaceArea"],
    "volume": ["Volume", "GrossVolume", "NetVolume", "VOLUME"],
    "length": ["Length", "NetLength", "LENGTH"],
    "weight": ["Weight", "NetWeight", "GrossWeight", "WEIGHT", "WEIGHT_NET", "WEIGHT_GROSS"],
}


def scan_quantity_by_type(qsets: dict, quantity_type: str) -> Optional[float]:
    """
    Zincir araması başarısız olduğunda son çare: tüm QSet'leri generic
    isimlerle tara. Archicad, VectorWorks ve non-standard QSet isimleri
    kullanan yazılımlar için devreye girer.

    Args:
        qsets: get_all_quantities() çıktısı
        quantity_type: "area" | "volume" | "length" | "weight"

    Returns:
        Ham sayısal değer veya None. Birim dönüşümü çağıran tarafın sorumluluğunda.
    """
    targets = _GENERIC_QTY_NAMES.get(quantity_type)
    if not targets:
        return None

    # Önce tam isim eşleşmesi (ordered priority)
    for target_name in targets:
        for qset_name, qtys in qsets.items():
            if not isinstance(qtys, dict):
                continue
            val = qtys.get(target_name)
            if val is not None:
                try:
                    fval = float(val)
                    if fval > 0:
                        logger.debug(
                            "Generic QSet scan [%s]: %s.%s = %.4f",
                            quantity_type, qset_name, target_name, fval
                        )
                        return fval
                except (TypeError, ValueError):
                    continue
    return None


def scan_property_by_type(psets: dict, quantity_type: str) -> Optional[float]:
    """
    Tüm PSet'leri generic quantity isimlerinde tara.
    Tekla gibi bazı yazılımlar quantity verilerini PSet içinde saklar.
    scan_quantity_by_type()'dan sonra çağrılmalıdır.

    Args:
        psets: get_all_psets() çıktısı
        quantity_type: "area" | "volume" | "length" | "weight"

    Returns:
        Ham sayısal değer veya None.
    """
    targets = _GENERIC_PSET_NAMES.get(quantity_type)
    if not targets:
        return None

    for target_name in targets:
        for pset_name, props in psets.items():
            if not isinstance(props, dict):
                continue
            val = props.get(target_name)
            if val is not None:
                try:
                    fval = float(val)
                    if fval > 0:
                        logger.debug(
                            "Generic PSet scan [%s]: %s.%s = %.4f",
                            quantity_type, pset_name, target_name, fval
                        )
                        return fval
                except (TypeError, ValueError):
                    continue
    return None


# ─── Materyal okuma ───────────────────────────────────────────────────────────

def get_material_names(element) -> list[str]:
    """
    Bir elementin malzeme isimlerini döner.
    IfcMaterial, IfcMaterialList, IfcMaterialLayerSetUsage,
    IfcMaterialProfileSetUsage ve IfcMaterialConstituentSet (IFC4) hepsini handle eder.
    """
    materials = []
    try:
        associations = getattr(element, "HasAssociations", None)
        if not associations:
            return materials

        for rel in associations:
            if not rel.is_a("IfcRelAssociatesMaterial"):
                continue
            mat = rel.RelatingMaterial

            if mat.is_a("IfcMaterial"):
                materials.append(mat.Name)

            elif mat.is_a("IfcMaterialList"):
                for m in mat.Materials or []:
                    if m.Name:
                        materials.append(m.Name)

            elif mat.is_a("IfcMaterialLayerSetUsage"):
                layer_set = mat.ForLayerSet
                if layer_set:
                    for layer in (layer_set.MaterialLayers or []):
                        m = layer.Material
                        if m and m.Name:
                            materials.append(m.Name)

            elif mat.is_a("IfcMaterialLayerSet"):
                for layer in (mat.MaterialLayers or []):
                    m = layer.Material
                    if m and m.Name:
                        materials.append(m.Name)

            elif mat.is_a("IfcMaterialProfileSetUsage"):
                profile_set = mat.ForProfileSet
                if profile_set:
                    for mp in (profile_set.MaterialProfiles or []):
                        m = mp.Material
                        if m and m.Name:
                            materials.append(m.Name)

            # IFC4: IfcMaterialConstituentSet (Revit 2024+ kullanır)
            elif mat.is_a("IfcMaterialConstituentSet"):
                for constituent in (getattr(mat, "MaterialConstituents", None) or []):
                    m = getattr(constituent, "Material", None)
                    if m and getattr(m, "Name", None):
                        materials.append(m.Name)

    except Exception as e:
        logger.warning("Malzeme okunamadı (element #%s): %s",
                       getattr(element, "GlobalId", "?"), e)

    return list(dict.fromkeys(materials))  # sıra koruyarak deduplicate


# ─── Tip adı okuma ────────────────────────────────────────────────────────────

def get_type_name(element, ifc: ifcopenshell.file) -> str:
    """
    Elementin tip adını döner.
    Revit'te type name, Tekla'da profil kodu burada saklanır.
    """
    try:
        defined_by = getattr(element, "IsDefinedBy", None)
        if defined_by:
            for rel in defined_by:
                if rel.is_a("IfcRelDefinesByType"):
                    type_obj = rel.RelatingType
                    if type_obj:
                        name = getattr(type_obj, "Name", None)
                        if name:
                            return str(name)

        # ObjectType attribute (Tekla'da kullanılır)
        obj_type = getattr(element, "ObjectType", None)
        if obj_type:
            return str(obj_type)

    except Exception as e:
        logger.debug("Tip adı okunamadı (element #%s): %s",
                     getattr(element, "GlobalId", "?"), e)
    return ""

# ifc_pipeline/properties.py
"""
Property Set ve Quantity Set okuma modülü.

Ana zorluk: Aynı veri farklı yazılımlarda farklı Pset/Qto isimlerinde saklanır.
Çözüm: YAML config'den gelen fallback zincirleri — sırayla dener, ilk bulduğunu alır.

Örnek fallback zinciri (alan için):
    [Qto_WallBaseQuantities, GrossSideArea]  → Revit IFC4
    [Qto_WallBaseQuantities, NetSideArea]    → alternatif
    [BaseQuantities, GrossSideArea]          → Revit IFC2x3
    [BaseQuantities, NetSideArea]            → Revit IFC2x3 alternatif
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

    ifc_util.get_psets() üzerine sarıcı — hata toleranslı.
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
    Çakışma durumunda sonraki pset öncekini ezer.
    Debug ve inceleme için kullanışlı.

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

    IfcElementQuantity → IfcPhysicalSimpleQuantity hiyerarşisini parse eder.
    Değerler ham IFC birimi cinsinden döner — units.py ile dönüştürülmeli.
    """
    result: dict[str, dict[str, float]] = {}
    try:
        # Güvenli inverse attribute erişimi
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
    IfcPropertySet'lere (psets) düşer. Bu, Tekla gibi bazı yazılımların
    quantity verilerini (Length, Weight vb.) property set içinde
    sakladığı durumları kapsar.

    Args:
        element: IFC element
        fallback_chain: [[set_adı, değer_adı], ...] listesi
        qsets: Önceden çekilmiş quantity set dict'i (cache için)
        psets: Önceden çekilmiş property set dict'i (pset fallback için)

    Returns:
        Ham sayısal değer (birimsiz), hiçbiri bulunamazsa None.
        Birim dönüşümü çağıran tarafın sorumluluğunda.
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

    # 2. Quantity set'lerde bulunamadıysa property set'lere bak
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
    Debug için.
    """
    result = {}
    for qset_name, qtys in get_all_quantities(element).items():
        for qty_name, val in qtys.items():
            result[f"{qset_name}.{qty_name}"] = val
    return result


# ─── Materyal okuma ───────────────────────────────────────────────────────────

def get_material_names(element) -> list[str]:
    """
    Bir elementin malzeme isimlerini döner.
    IfcMaterial, IfcMaterialList, IfcMaterialLayerSetUsage,
    IfcMaterialProfileSetUsage ve IfcMaterialConstituentSet (IFC4) hepsini handle eder.
    """
    materials = []
    try:
        # Güvenli inverse attribute erişimi
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
        # Yöntem 1: IfcRelDefinesByType ilişkisi
        defined_by = getattr(element, "IsDefinedBy", None)
        if defined_by:
            for rel in defined_by:
                if rel.is_a("IfcRelDefinesByType"):
                    type_obj = rel.RelatingType
                    if type_obj:
                        name = getattr(type_obj, "Name", None)
                        if name:
                            return str(name)

        # Yöntem 2: ObjectType attribute (Tekla'da kullanılır)
        obj_type = getattr(element, "ObjectType", None)
        if obj_type:
            return str(obj_type)

        # Yöntem 3: Element.Name'in kendisi (bazı Archicad exportlarında)
        elem_name = getattr(element, "Name", None)
        if elem_name:
            return str(elem_name)

    except Exception as e:
        logger.debug("Tip adı okunamadı (element #%s): %s",
                     getattr(element, "GlobalId", "?"), e)
    return ""

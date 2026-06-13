# ifc_pipeline/units.py
"""
IFC dosyasındaki birim sistemini tespit eder ve SI'ya dönüştürür.
Uzunluk, Alan ve Hacim birimlerini birbirinden BAĞIMSIZ olarak okur.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import logging
import ifcopenshell

logger = logging.getLogger(__name__)

# ─── Dönüşüm faktörleri (hedef: metre, m², m³) ───────────────────────────────
# NOT: IfcSIUnit → Name=METRE + Prefix=MILLI şeklinde gelir (ayrı ayrı).
# IfcConversionBasedUnit → Name=MILLIMETRE şeklinde gelebilir (birleşik).
# Bu yüzden hem birleşik hem ayrı formlar burada tanımlıdır.

UNIT_TO_SI = {
    # IfcSIUnit base
    "METRE":          1.0,
    # IfcConversionBasedUnit birleşik isimler
    "MILLIMETRE":     0.001,
    "CENTIMETRE":     0.01,
    "SQUARE_METRE":   1.0,
    "CUBIC_METRE":    1.0,
    # Imperial
    "INCH":           0.0254,
    "FOOT":           0.3048,
    "YARD":           0.9144,
    "SQUARE_FOOT":    0.092903,
    "SQUARE_YARD":    0.836127,
    "CUBIC_FOOT":     0.0283168,
    "CUBIC_YARD":     0.764555,
    "DECIMAL_FEET":   0.3048,
}

SI_PREFIXES = {
    "EXA": 1e18, "PETA": 1e15, "TERA": 1e12, "GIGA": 1e9, "MEGA": 1e6, "KILO": 1e3,
    "HECTO": 1e2, "DECA": 1e1, "DECI": 1e-1, "CENTI": 1e-2, "MILLI": 1e-3,
    "MICRO": 1e-6, "NANO": 1e-9, "PICO": 1e-12,
    None: 1.0, "": 1.0,
}

@dataclass
class UnitFactors:
    length: float
    area: float
    volume: float
    source_info: str

    def describe(self) -> str:
        return f"Uzunluk: ×{self.length:.4f} | Alan: ×{self.area:.6f} | Hacim: ×{self.volume:.6f}"

def detect_units(ifc: ifcopenshell.file) -> UnitFactors:
    """IfcUnitAssignment'tan Uzunluk, Alan ve Hacim faktörlerini ayrı ayrı tespit eder."""
    length_factor, area_factor, volume_factor = 1.0, 1.0, 1.0
    length_defined = area_defined = volume_defined = False
    source_info = "Varsayılan (Metre)"

    try:
        projects = ifc.by_type("IfcProject")
        if not projects or not projects[0].UnitsInContext:
            logger.warning("IfcProject veya UnitsInContext bulunamadı — varsayılan birimler kullanılacak.")
            return UnitFactors(length_factor, area_factor, volume_factor, "Birim tanımı yok")

        unit_assignment = projects[0].UnitsInContext

        for unit in unit_assignment.Units:
            unit_type = getattr(unit, "UnitType", None)
            factor = 1.0

            if unit.is_a("IfcConversionBasedUnit"):
                factor = _get_conversion_factor(unit)
            elif unit.is_a("IfcSIUnit"):
                prefix = getattr(unit, "Prefix", None)
                name = getattr(unit, "Name", "")
                prefix_mult = SI_PREFIXES.get(prefix, 1.0)
                # IfcSIUnit'te Name her zaman base form (METRE, vb.)
                # Prefix ayrı geliyor, ikisini çarpıyoruz
                base = UNIT_TO_SI.get(name, 1.0)
                factor = base * prefix_mult

            # Birimleri birbirinden bağımsız olarak ata
            if unit_type == "LENGTHUNIT":
                length_factor = factor
                length_defined = True
            elif unit_type == "AREAUNIT":
                area_factor = factor
                area_defined = True
            elif unit_type == "VOLUMEUNIT":
                volume_factor = factor
                volume_defined = True

        # Korumacı (Fallback) Senaryo:
        # Alan veya hacim birimi tanımlanmamışsa, uzunluğun karesi/kübü üzerinden çıkarım yap.
        if not area_defined and length_defined:
            area_factor = length_factor ** 2
            logger.info("Alan birimi tanımlanmamış — uzunluğun karesinden çıkarıldı: ×%.6f", area_factor)
        if not volume_defined and length_defined:
            volume_factor = length_factor ** 3
            logger.info("Hacim birimi tanımlanmamış — uzunluğun kübünden çıkarıldı: ×%.6f", volume_factor)

        # Başarılı tespitte source_info güncelle
        parts = []
        if length_defined:
            parts.append(f"Uzunluk: ×{length_factor}")
        if area_defined:
            parts.append(f"Alan: ×{area_factor}")
        if volume_defined:
            parts.append(f"Hacim: ×{volume_factor}")
        if parts:
            source_info = "IFC birim tespiti: " + ", ".join(parts)
        elif not length_defined and not area_defined and not volume_defined:
            source_info = "Birim tanımlı ama LENGTHUNIT/AREAUNIT/VOLUMEUNIT bulunamadı — varsayılan kullanılıyor"

    except Exception as e:
        logger.error("Birim tespitinde hata: %s", e)
        source_info = f"Hata: {e}"

    return UnitFactors(length_factor, area_factor, volume_factor, source_info)


def _get_conversion_factor(unit) -> float:
    """IfcConversionBasedUnit'ten dönüşüm faktörünü çeker."""
    try:
        conversion = unit.ConversionFactor
        if conversion:
            value = getattr(conversion, "ValueComponent", None)
            if value:
                return float(value)
    except Exception as e:
        logger.debug("ConversionFactor okunamadı: %s", e)
    name = getattr(unit, "Name", "").upper()
    return UNIT_TO_SI.get(name, 1.0)


def safe_convert(value: Optional[float], factor: float) -> Optional[float]:
    """Sayısal dönüşümü yapar ve temiz bir ondalık format (6 hane) döner."""
    if value is None:
        return None
    try:
        return round(float(value) * factor, 6)
    except (TypeError, ValueError):
        return None
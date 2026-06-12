# ifc_pipeline/normalizer.py
"""
Ham row listesini pandas DataFrame'e donusturur, temizler ve dogrular.
"""
from __future__ import annotations
import logging
import pandas as pd
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA = {
    "global_id":       "string",
    "element_type":    "category",
    "ifc_class":       "string",
    "name":            "string",
    "type_name":       "string",
    "level":           "string",
    "level_elevation": "float64",
    "phase":           "string",
    "is_external":     "boolean",
    "load_bearing":    "boolean",
    "fire_rating":     "string",
    "area_m2":         "float64",
    "volume_m3":       "float64",
    "length_m":        "float64",
    "thickness_m":     "float64",
    "materials":       "string",
    "source_software": "category",
    "source_file":     "string",
}

# Her element tipi icin hangi quantity bekleniyor
EXPECTED_QUANTITIES = {
    "wall":         ["area_m2",   "volume_m3"],
    "beam":         ["length_m",  "volume_m3"],
    "column":       ["length_m",  "volume_m3"],
    "slab":         ["area_m2",   "volume_m3"],
    "door":         ["area_m2"],
    "window":       ["area_m2"],
    "member":       ["length_m",  "volume_m3"],
    "footing":      ["volume_m3"],
    "pile":         ["length_m",  "volume_m3"],
    "stair":        ["area_m2"],
    "roof":         ["area_m2"],
    "curtain_wall": ["area_m2"],
    "railing":      ["length_m"],
    "ramp":         ["area_m2"],
    "covering":     ["area_m2"],
    "plate":        ["area_m2",   "volume_m3"],
}

# Her element tipi icin maliyet hesabinda kullanilacak varsayilan quantity
DEFAULT_QTY_COL = {
    "wall":         "area_m2",
    "beam":         "length_m",
    "column":       "length_m",
    "slab":         "area_m2",
    "door":         "area_m2",
    "window":       "area_m2",
    "member":       "length_m",
    "footing":      "volume_m3",
    "pile":         "length_m",
    "stair":        "area_m2",
    "roof":         "area_m2",
    "curtain_wall": "area_m2",
    "railing":      "length_m",
    "ramp":         "area_m2",
    "covering":     "area_m2",
    "plate":        "area_m2",
}

# Boolean dönüşüm için bilinen True/False değerleri
_TRUE_VALUES  = {"true", "1", "yes", "evet", "doğru", "dogru"}
_FALSE_VALUES = {"false", "0", "no", "hayır", "hayir", "yanlış", "yanlis"}
# String olarak "boş" kabul edilecek değerler
_NULL_STRINGS = {"None", "none", "NONE", "N/A", "n/a", "nan", "NaN", "null", "NULL", ""}


def _to_boolean(x):
    """Herhangi bir değeri nullable boolean'a dönüştürür."""
    if x is pd.NA or x is None:
        return pd.NA
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, float, np.integer, np.floating)):
        if x == 1:
            return True
        if x == 0:
            return False
        return pd.NA
    s = str(x).strip().lower()
    if s in _TRUE_VALUES:
        return True
    if s in _FALSE_VALUES:
        return False
    return pd.NA


def to_dataframe(rows: list[dict]) -> pd.DataFrame:
    """Ham row listesini temiz, tiplendirilmiş DataFrame'e dönüştürür."""
    if not rows:
        logger.warning("Boş row listesi — boş DataFrame dönülüyor")
        return pd.DataFrame(columns=list(SCHEMA.keys()))

    logger.info(f"DataFrame oluşturuluyor: {len(rows)} satır")
    df = pd.DataFrame(rows)

    for col in SCHEMA:
        if col not in df.columns:
            df[col] = None

    schema_cols = [c for c in SCHEMA if c in df.columns]
    extra_cols  = [c for c in df.columns if c not in SCHEMA]
    df = df[schema_cols + extra_cols]

    for col, dtype in SCHEMA.items():
        if col not in df.columns:
            continue
        try:
            if dtype == "float64":
                df[col] = pd.to_numeric(df[col], errors="coerce")
            elif dtype == "boolean":
                df[col] = df[col].map(_to_boolean).astype("boolean")
            elif dtype == "category":
                df[col] = df[col].astype("category")
            elif dtype == "string":
                df[col] = (
                    df[col]
                    .fillna("")
                    .astype(str)
                    .replace(to_replace=r"^(" + "|".join(_NULL_STRINGS) + r")$",
                             value="", regex=True)
                )
        except Exception as e:
            logger.warning("Sütun tip dönüşümü başarısız (%s → %s): %s", col, dtype, e)

    for col in ["area_m2", "volume_m3", "length_m", "thickness_m"]:
        if col in df.columns:
            df[col] = df[col].where(df[col] > 0, other=np.nan)

    result = df.reset_index(drop=True)
    logger.info(f"DataFrame oluşturuldu: {len(result)} satır, {len(result.columns)} sütun")
    return result


def quality_report(df: pd.DataFrame) -> dict:
    """Veri kalitesi raporu üretir: eksik metraj, duplicate ID, katsız element tespiti."""
    if df.empty:
        return {"total": 0, "warnings": ["DataFrame bos"]}

    total    = len(df)
    warnings = []
    by_type  = df["element_type"].value_counts().to_dict()
    missing_quantities = {}
    coverage = {}

    for elem_type, qty_cols in EXPECTED_QUANTITIES.items():
        subset = df[df["element_type"] == elem_type]
        if subset.empty:
            continue
        n        = len(subset)
        has_any  = subset[[c for c in qty_cols if c in subset.columns]].notna().any(axis=1).sum()
        missing  = n - has_any
        missing_quantities[elem_type] = int(missing)
        coverage[elem_type] = round(has_any / n * 100, 1)
        if missing > 0:
            pct = round(missing / n * 100)
            warnings.append(
                f"{elem_type}: {n} elementten {missing} tanesinde (%{pct}) "
                "metraj eksik — 'Export base quantities' kapali olabilir"
            )

    dup_ids  = df["global_id"].duplicated().sum()
    if dup_ids > 0:
        warnings.append(f"GlobalId tekrari: {dup_ids} adet")
        logger.warning(f"Duplicate GlobalId detected: {dup_ids}")

    no_level = (df["level"] == "").sum()
    if no_level > 0:
        warnings.append(f"{no_level} element katsiz geldi")
        logger.warning(f"Elements without level: {no_level}")

    report = {
        "total":              total,
        "by_type":            by_type,
        "missing_quantities": missing_quantities,
        "coverage":           coverage,
        "warnings":           warnings,
    }
    logger.info(f"Veri kalitesi raporu: {len(warnings)} uyarı")
    return report


def add_cost_columns(
    df: pd.DataFrame,
    unit_prices: dict[str, float],
    currency: str = "TL",
    quantity_col_override: Optional[dict[str, str]] = None,
) -> pd.DataFrame:
    """
    Birim fiyat tablosuna göre maliyet sütunları ekler.

    Args:
        df: Element DataFrame'i
        unit_prices: {element_type: birim_fiyat} sözlüğü
        currency: Para birimi etiketi (varsayılan: TL)
        quantity_col_override: Hangi quantity sütununun kullanılacağını override eder
    """
    qty_col_map = dict(DEFAULT_QTY_COL)
    if quantity_col_override:
        qty_col_map.update(quantity_col_override)

    df = df.copy()
    # Category tipini string'e çevir (map/== uyumluluğu için)
    et_str = df["element_type"].astype(str)
    df["unit_price"] = et_str.map(unit_prices)

    # Vektörel yaklaşım — df.apply yerine (PERF-2 düzeltmesi)
    df["quantity_for_cost"] = np.nan
    for et, col in qty_col_map.items():
        if col in df.columns:
            mask = et_str == et
            df.loc[mask, "quantity_for_cost"] = pd.to_numeric(
                df.loc[mask, col], errors="coerce"
            )

    cost_col = f"cost_{currency}"
    df[cost_col] = df["unit_price"] * df["quantity_for_cost"]
    return df

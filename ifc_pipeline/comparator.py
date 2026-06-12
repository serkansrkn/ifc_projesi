# ifc_pipeline/comparator.py
"""
Birden fazla IFC dosyasini tip+kat seviyesinde karsilastirir.
Thesis kullanimi: farkli yazilim IFC ciktilari arasindaki metraj sapmalarini olcer.
"""
from __future__ import annotations
import logging
import pandas as pd
import numpy as np
from itertools import combinations
from typing import Optional, Any

logger = logging.getLogger(__name__)


def compare(dfs: dict, include_type_name: bool = False) -> pd.DataFrame:
    """
    {etiket: DataFrame} sozlugunden karsilastirma tablosu uretir.
    Satir = element_type + level (+ opsiyonel type_name) kombinasyonu
    Sutunlar = her kaynak icin adet/alan/hacim/uzunluk + TÜM çift kombinasyonları için sapma yuzdeleri

    Args:
        dfs: {etiket: DataFrame} sözlüğü
        include_type_name: True ise type_name bazında da kırılım yapar
    """
    if len(dfs) < 2:
        raise ValueError("En az 2 dosya gerekli")

    logger.info(f"Karşılaştırıyor: {len(dfs)} dosya — {list(dfs.keys())}")

    group_cols = ["element_type", "level"]
    if include_type_name:
        group_cols.append("type_name")

    summaries = {label: _aggregate(df, group_cols) for label, df in dfs.items()}
    all_keys  = set(k for s in summaries.values() for k in s)
    qty_cols  = ["adet", "area_m2", "volume_m3", "length_m"]
    labels    = list(dfs.keys())
    rows = []

    for key in sorted(all_keys):
        row = dict(zip(group_cols, key))

        for label in labels:
            data = summaries[label].get(key, {})
            for col in qty_cols:
                row[f"{label}__{col}"] = data.get(col)

        # TÜM çift kombinasyonları arasında sapma hesapla
        for a, b in combinations(labels, 2):
            for col in ["area_m2", "volume_m3", "length_m"]:
                va = row.get(f"{a}__{col}")
                vb = row.get(f"{b}__{col}")
                diff_key = f"diff_{a}_vs_{b}_{col}_pct"
                if va and vb and va > 0:
                    row[diff_key] = round((vb - va) / va * 100, 2)
                else:
                    row[diff_key] = None

        rows.append(row)

    comp_result = pd.DataFrame(rows)
    logger.info(f"Karşılaştırma tamamlandı: {len(comp_result)} satır, {len(comp_result.columns)} sütun")
    return comp_result


def _aggregate(df: pd.DataFrame, group_cols: list[str]) -> dict:
    """DataFrame'i grup sütunlarına göre toplar."""
    result = {}
    # Eksik sütunları dolduralım
    for col in group_cols:
        if col not in df.columns:
            df = df.copy()
            df[col] = ""

    for group_key, sub in df.groupby(group_cols, observed=True):
        # Tek sütunlu gruplamada tuple'a çevir
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        key = tuple(str(v) for v in group_key)
        result[key] = {
            "adet":      len(sub),
            "area_m2":   _ss(sub, "area_m2"),
            "volume_m3": _ss(sub, "volume_m3"),
            "length_m":  _ss(sub, "length_m"),
        }
    return result


def _ss(df: pd.DataFrame, col: str) -> Optional[float]:
    """Sütun toplamını güvenli şekilde hesaplar."""
    if col not in df.columns:
        return None
    v = df[col].sum(skipna=True)
    return round(float(v), 4) if v > 0 else None


def compare_psets(dfs: dict) -> pd.DataFrame:
    """Pset doluluk karsilastirmasi — hangi yazilim hangi alanlari doldurmis."""
    qty_cols = ["area_m2", "volume_m3", "length_m", "thickness_m",
                "is_external", "load_bearing", "fire_rating", "materials"]
    rows = []
    for label, df in dfs.items():
        if df.empty:
            continue
        row = {"kaynak": label, "toplam": len(df)}
        for col in qty_cols:
            if col in df.columns:
                if col == "materials":
                    # Boş string'leri de eksik say
                    filled = ((df[col].notna()) & (df[col] != "")).sum()
                else:
                    filled = df[col].notna().sum()
                row[f"{col}_%"] = round(filled / len(df) * 100, 1)
        rows.append(row)
    return pd.DataFrame(rows)


def flag_large_diffs(comp_df: pd.DataFrame, threshold_pct: float = 5.0) -> pd.DataFrame:
    """Esik degeri asen sapmalari dondurur — thesis'te somut bulgu olarak kullanilir."""
    diff_cols = [c for c in comp_df.columns if "diff_" in c and c.endswith("_pct")]
    if not diff_cols:
        return pd.DataFrame()
    mask   = comp_df[diff_cols].abs().max(axis=1) >= threshold_pct
    result = comp_df[mask].copy()
    if not result.empty:
        result["max_sapma_pct"] = result[diff_cols].abs().max(axis=1)
        result = result.sort_values("max_sapma_pct", ascending=False)
    return result


def export_comparison(dfs: dict, output_path: str, include_type_name: bool = False) -> None:
    """Karsilastirma sonuclarini cok sekmeli Excel'e yazar."""
    from .exporter import _autowidth, _format_sheet
    comp = compare(dfs, include_type_name=include_type_name)
    pset = compare_psets(dfs)
    big  = flag_large_diffs(comp)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        comp.to_excel(writer, sheet_name="Karsilastirma", index=False)
        _autowidth(writer, "Karsilastirma", comp)
        _format_sheet(writer, "Karsilastirma", comp)

        pset.to_excel(writer, sheet_name="Pset Kapsami", index=False)
        _autowidth(writer, "Pset Kapsami", pset)
        _format_sheet(writer, "Pset Kapsami", pset)

        if not big.empty:
            big.to_excel(writer, sheet_name="Buyuk Sapmalar", index=False)
            _autowidth(writer, "Buyuk Sapmalar", big)
            _format_sheet(writer, "Buyuk Sapmalar", big)

        for label, df in dfs.items():
            summ = _summary(df, label)
            sname = str(label)[:31]
            summ.to_excel(writer, sheet_name=sname, index=False)
            _autowidth(writer, sname, summ)
            _format_sheet(writer, sname, summ)

    logger.info("Karşılaştırma yazıldı: %s", output_path)


def _summary(df: pd.DataFrame, label: Any) -> pd.DataFrame:
    """Kaynak bazlı özet tablo üretir."""
    rows = []
    for et, sub in df.groupby("element_type", observed=True):
        rows.append({
            "Kaynak": label, "Tip": str(et), "Adet": len(sub),
            "Alan (m2)":    round(sub["area_m2"].sum(skipna=True), 3),
            "Hacim (m3)":   round(sub["volume_m3"].sum(skipna=True), 3),
            "Uzunluk (m)":  round(sub["length_m"].sum(skipna=True), 3),
        })
    return pd.DataFrame(rows)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IFC Pipeline — Streamlit Web Arayüzü

Kullanım:
  streamlit run app.py
  docker compose up  (Docker ile)
"""
import sys
import os
import io
import hashlib
import tempfile
import logging

# Proje kökünü path'e ekle
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import yaml

from ifc_pipeline import (
    load, detect_units, extract_all,
    to_dataframe, quality_report, add_cost_columns,
    to_excel, to_json,
    compare, compare_psets, export_comparison, flag_large_diffs,
)

# ─── Sayfa Konfigürasyonu ────────────────────────────────────────────────────

st.set_page_config(
    page_title="IFC Metraj Pipeline",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Premium Dark Theme CSS ─────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Root variables ─────────────────────────────────────────────── */
:root {
    --bg-primary: #0f1117;
    --bg-card: rgba(30, 34, 46, 0.85);
    --bg-card-hover: rgba(40, 45, 60, 0.9);
    --accent-blue: #4f8ef7;
    --accent-cyan: #22d3ee;
    --accent-green: #34d399;
    --accent-amber: #fbbf24;
    --accent-red: #f87171;
    --text-primary: #e2e8f0;
    --text-secondary: #94a3b8;
    --border-subtle: rgba(148, 163, 184, 0.12);
    --glow-blue: 0 0 20px rgba(79, 142, 247, 0.15);
}

/* ── Global ─────────────────────────────────────────────────────── */
.stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Hero header ────────────────────────────────────────────────── */
.hero-header {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 50%, #1a1a2e 100%);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 2.5rem 2rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}
.hero-header::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle at 30% 20%, rgba(79, 142, 247, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 70% 80%, rgba(34, 211, 238, 0.06) 0%, transparent 50%);
    animation: pulse-bg 8s ease-in-out infinite alternate;
}
@keyframes pulse-bg {
    0% { transform: scale(1) rotate(0deg); }
    100% { transform: scale(1.05) rotate(2deg); }
}
.hero-header h1 {
    font-size: 2.2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #4f8ef7, #22d3ee);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5rem;
    position: relative;
    z-index: 1;
}
.hero-header p {
    color: var(--text-secondary);
    font-size: 1.05rem;
    font-weight: 400;
    position: relative;
    z-index: 1;
}

/* ── Glass cards ────────────────────────────────────────────────── */
.glass-card {
    background: var(--bg-card);
    backdrop-filter: blur(12px);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    transition: all 0.3s ease;
}
.glass-card:hover {
    background: var(--bg-card-hover);
    box-shadow: var(--glow-blue);
    border-color: rgba(79, 142, 247, 0.25);
}

/* ── Stat pills ─────────────────────────────────────────────────── */
.stat-container {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin: 1rem 0;
}
.stat-pill {
    background: linear-gradient(135deg, rgba(79, 142, 247, 0.12), rgba(34, 211, 238, 0.08));
    border: 1px solid rgba(79, 142, 247, 0.2);
    border-radius: 10px;
    padding: 1rem 1.4rem;
    flex: 1;
    min-width: 160px;
    text-align: center;
    transition: all 0.3s ease;
}
.stat-pill:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 15px rgba(79, 142, 247, 0.15);
}
.stat-pill .value {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--accent-blue);
    line-height: 1;
}
.stat-pill .label {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.stat-pill.green .value { color: var(--accent-green); }
.stat-pill.green { border-color: rgba(52, 211, 153, 0.2); background: linear-gradient(135deg, rgba(52, 211, 153, 0.12), rgba(34, 211, 238, 0.06)); }
.stat-pill.amber .value { color: var(--accent-amber); }
.stat-pill.amber { border-color: rgba(251, 191, 36, 0.2); background: linear-gradient(135deg, rgba(251, 191, 36, 0.12), rgba(251, 191, 36, 0.06)); }
.stat-pill.cyan .value { color: var(--accent-cyan); }
.stat-pill.cyan { border-color: rgba(34, 211, 238, 0.2); background: linear-gradient(135deg, rgba(34, 211, 238, 0.12), rgba(34, 211, 238, 0.06)); }

/* ── Warning badges ─────────────────────────────────────────────── */
.warning-badge {
    background: rgba(251, 191, 36, 0.1);
    border: 1px solid rgba(251, 191, 36, 0.25);
    border-radius: 8px;
    padding: 0.6rem 1rem;
    color: var(--accent-amber);
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* ── File info section ──────────────────────────────────────────── */
.info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 0.8rem;
    margin: 1rem 0;
}
.info-item {
    background: rgba(30, 34, 46, 0.6);
    border-radius: 8px;
    padding: 0.8rem 1rem;
    border-left: 3px solid var(--accent-blue);
}
.info-item .key {
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.info-item .val {
    font-size: 1rem;
    color: var(--text-primary);
    font-weight: 500;
}

/* ── Sidebar styling ────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #141824 0%, #0f1117 100%);
    border-right: 1px solid var(--border-subtle);
}
section[data-testid="stSidebar"] .stMarkdown h2 {
    font-size: 1.1rem;
    color: var(--accent-cyan);
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: 0.5rem;
}

/* ── Smooth dataframe ───────────────────────────────────────────── */
.stDataFrame {
    border-radius: 10px;
    overflow: hidden;
}

/* ── Download button animation ──────────────────────────────────── */
.stDownloadButton > button {
    background: linear-gradient(135deg, #4f8ef7, #22d3ee) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.3s ease !important;
}
.stDownloadButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 15px rgba(79, 142, 247, 0.35) !important;
}

/* ── Tab styling ────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 8px 20px;
    font-weight: 500;
}

/* ── Element count bar ──────────────────────────────────────────── */
.elem-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0.3rem 0;
}
.elem-bar .bar-bg {
    flex: 1;
    height: 6px;
    background: rgba(79, 142, 247, 0.1);
    border-radius: 3px;
    overflow: hidden;
}
.elem-bar .bar-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan));
    border-radius: 3px;
    transition: width 0.6s ease;
}
.elem-bar .bar-label {
    font-size: 0.85rem;
    color: var(--text-secondary);
    min-width: 120px;
}
.elem-bar .bar-count {
    font-size: 0.85rem;
    color: var(--text-primary);
    font-weight: 600;
    min-width: 50px;
    text-align: right;
}
</style>
""", unsafe_allow_html=True)

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ifc_app")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "mapping.yaml")


# ─── Yardımcı Fonksiyonlar ───────────────────────────────────────────────────

@st.cache_data
def load_config() -> dict:
    """Config dosyasını yükler ve cache'ler."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_file_hash(uploaded_file) -> str:
    """Yüklenen dosyanın hash'ini hesaplar (değişiklik tespiti için)."""
    hasher = hashlib.md5()
    hasher.update(uploaded_file.getbuffer())
    return hasher.hexdigest()


def save_uploaded_file(uploaded_file) -> str:
    """Yüklenen dosyayı geçici dizine kaydeder."""
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, uploaded_file.name)
    with open(tmp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return tmp_path


@st.cache_data
def generate_excel_bytes(_df: pd.DataFrame, quality: dict = None) -> bytes:
    """DataFrame'i bellekte Excel'e dönüştürür (cache'li)."""
    buffer = io.BytesIO()
    to_excel(_df, buffer, quality=quality)
    buffer.seek(0)
    return buffer.getvalue()


@st.cache_data
def generate_json_bytes(_df: pd.DataFrame) -> bytes:
    """DataFrame'i bellekte JSON'a dönüştürür (cache'li)."""
    import json
    clean = _df.copy()
    for col in clean.select_dtypes(include="object").columns:
        clean[col] = clean[col].replace("", None)
    clean = clean.where(clean.notna(), other=None)
    records = clean.to_dict(orient="records")
    json_str = json.dumps(records, ensure_ascii=False, indent=2, default=str)
    return json_str.encode("utf-8")


@st.cache_data
def generate_comparison_excel_bytes(_dfs: dict) -> bytes:
    """Karşılaştırma sonuçlarını bellekte Excel'e yazar (cache'li)."""
    buffer = io.BytesIO()
    export_comparison(_dfs, buffer)
    buffer.seek(0)
    return buffer.getvalue()


@st.cache_data(show_spinner=False)
def run_single_pipeline(file_hash: str, file_bytes: bytes, file_name: str,
                        config: dict, elem_filter: list = None):
    """
    Tek dosya pipeline'ını çalıştırır ve sonuçları cache'ler.
    file_hash parametresi cache key olarak kullanılır — aynı dosya
    tekrar yüklendiğinde pipeline yeniden çalışmaz.
    """
    # Geçici dosyaya yaz
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file_name)
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)

    try:
        ifc, info = load(tmp_path, config=config)
        units = detect_units(ifc)

        rows, stats = extract_all(
            ifc=ifc,
            config=config,
            units=units,
            source_software=info.source_software,
            source_filename=info.filename,
            element_filter=elem_filter,
        )
        df = to_dataframe(rows)
        qa = quality_report(df)

        # info objesini dict'e çevir (cache serialization için)
        info_dict = {
            "filename": info.filename,
            "file_size_mb": info.file_size_mb,
            "schema": info.schema,
            "source_software": info.source_software,
            "app_name": info.app_name,
            "app_version": info.app_version,
            "organization": info.organization,
            "project_name": info.project_name,
            "site_name": info.site_name,
            "building_name": info.building_name,
            "storey_count": info.storey_count,
            "element_counts": info.element_counts,
            "has_quantity_sets": info.has_quantity_sets,
            "has_geometry": info.has_geometry,
            "warnings": info.warnings,
        }

        return df, qa, stats, info_dict
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass


@st.cache_data(show_spinner=False)
def run_comparison_pipeline(file_hashes: tuple, file_data: dict, config: dict,
                            elem_filter: list = None):
    """
    Çoklu dosya karşılaştırma pipeline'ını çalıştırır ve cache'ler.
    file_hashes tuple'ı cache key olarak kullanılır.
    """
    dfs = {}
    infos = {}

    for label, (file_bytes, file_name) in file_data.items():
        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, file_name)
        try:
            with open(tmp_path, "wb") as f:
                f.write(file_bytes)

            ifc, info = load(tmp_path, config=config)
            units = detect_units(ifc)

            rows, stats = extract_all(
                ifc=ifc,
                config=config,
                units=units,
                source_software=info.source_software,
                source_filename=info.filename,
                element_filter=elem_filter,
            )
            df = to_dataframe(rows)
            dfs[label] = df

            infos[label] = {
                "filename": info.filename,
                "file_size_mb": info.file_size_mb,
                "schema": info.schema,
                "source_software": info.source_software,
                "app_name": info.app_name,
                "app_version": info.app_version,
                "organization": info.organization,
                "project_name": info.project_name,
                "site_name": info.site_name,
                "building_name": info.building_name,
                "storey_count": info.storey_count,
                "element_counts": info.element_counts,
                "has_quantity_sets": info.has_quantity_sets,
                "has_geometry": info.has_geometry,
                "warnings": info.warnings,
            }
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass

    return dfs, infos


def render_file_info(info_dict: dict):
    """Dosya bilgilerini premium kartlarla gösterir."""
    st.markdown(f"""
    <div class="glass-card">
        <div class="info-grid">
            <div class="info-item"><div class="key">Dosya</div><div class="val">{info_dict['filename']} ({info_dict['file_size_mb']:.1f} MB)</div></div>
            <div class="info-item"><div class="key">Schema</div><div class="val">{info_dict['schema']}</div></div>
            <div class="info-item"><div class="key">Yazılım</div><div class="val">{info_dict['source_software']} ({info_dict['app_name']})</div></div>
            <div class="info-item"><div class="key">Proje</div><div class="val">{info_dict['project_name'] or '—'}</div></div>
            <div class="info-item"><div class="key">Yapı</div><div class="val">{info_dict['building_name'] or '—'}</div></div>
            <div class="info-item"><div class="key">Kat Sayısı</div><div class="val">{info_dict['storey_count']}</div></div>
            <div class="info-item"><div class="key">Quantity Set</div><div class="val">{'✅ Var' if info_dict['has_quantity_sets'] else '❌ Yok'}</div></div>
            <div class="info-item"><div class="key">Organizasyon</div><div class="val">{info_dict['organization'] or '—'}</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Element sayıları bar chart
    if info_dict.get("element_counts"):
        max_count = max(info_dict["element_counts"].values())
        bars_html = ""
        for cls, cnt in sorted(info_dict["element_counts"].items(), key=lambda x: -x[1]):
            pct = (cnt / max_count * 100) if max_count > 0 else 0
            bars_html += f"""
            <div class="elem-bar">
                <span class="bar-label">{cls}</span>
                <div class="bar-bg"><div class="bar-fill" style="width:{pct}%"></div></div>
                <span class="bar-count">{cnt:,}</span>
            </div>"""

        with st.expander("📊 Element Sayıları", expanded=False):
            st.markdown(f'<div class="glass-card">{bars_html}</div>', unsafe_allow_html=True)

    # Uyarılar
    if info_dict.get("warnings"):
        for w in info_dict["warnings"]:
            st.markdown(f'<div class="warning-badge">⚠️ {w}</div>', unsafe_allow_html=True)


def render_stats(df: pd.DataFrame, stats: dict):
    """Özet istatistikleri pill kartlarıyla gösterir."""
    total = len(df)
    types = df["element_type"].nunique() if "element_type" in df.columns else 0
    area_total = df["area_m2"].sum() if "area_m2" in df.columns else 0
    vol_total = df["volume_m3"].sum() if "volume_m3" in df.columns else 0

    st.markdown(f"""
    <div class="stat-container">
        <div class="stat-pill">
            <div class="value">{total:,}</div>
            <div class="label">Toplam Element</div>
        </div>
        <div class="stat-pill green">
            <div class="value">{types}</div>
            <div class="label">Element Tipi</div>
        </div>
        <div class="stat-pill cyan">
            <div class="value">{area_total:,.2f}</div>
            <div class="label">Toplam Alan (m²)</div>
        </div>
        <div class="stat-pill amber">
            <div class="value">{vol_total:,.4f}</div>
            <div class="label">Toplam Hacim (m³)</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_quality_report(qa: dict):
    """Veri kalitesi raporunu gösterir."""
    with st.expander("🔍 Veri Kalitesi Raporu", expanded=True):
        if qa.get("coverage"):
            cols = st.columns(min(len(qa["coverage"]), 4))
            for i, (et, pct) in enumerate(qa["coverage"].items()):
                color = "green" if pct >= 80 else ("amber" if pct >= 50 else "red")
                cols[i % len(cols)].metric(
                    label=f"📐 {et}",
                    value=f"%{pct}",
                    delta="Tam" if pct == 100 else f"%{100 - pct} eksik",
                    delta_color="normal" if pct >= 80 else "inverse",
                )

        if qa.get("warnings"):
            st.markdown("---")
            for w in qa["warnings"]:
                st.warning(w)
        else:
            st.success("✅ Veri kalitesinde sorun bulunamadı.")


# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Ayarlar")

    mode = st.radio(
        "Mod Seçimi",
        ["📄 Tekli Metraj Çıkarma", "🔄 Dosya Karşılaştırma"],
        index=0,
        help="Tekli modda bir IFC dosyasından metraj çıkarır. Karşılaştırma modunda birden fazla dosyayı analiz eder.",
    )

    st.markdown("---")
    st.markdown("## 🏗️ Element Filtresi")

    config = load_config()
    available_types = list(config.get("element_types", {}).keys())

    select_all = st.checkbox("Tüm element tiplerini seç", value=True)
    if select_all:
        selected_types = available_types
    else:
        selected_types = st.multiselect(
            "Çıkarılacak element tipleri:",
            available_types,
            default=available_types,
            help="Sadece seçili element tipleri işlenecektir.",
        )

    st.markdown("---")
    st.markdown("## 📥 Çıktı Formatı")
    output_format = st.selectbox(
        "İndirme formatı",
        ["Excel (.xlsx)", "JSON (.json)"],
        index=0,
    )

    st.markdown("---")
    st.markdown("""
    <div style="text-align:center; opacity:0.5; font-size:0.8rem; margin-top:2rem;">
        IFC Pipeline v0.2.0<br>
        Streamlit UI
    </div>
    """, unsafe_allow_html=True)


# ─── Hero Header ─────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero-header">
    <h1>🏗️ IFC Metraj Pipeline</h1>
    <p>IFC dosyalarından otomatik metraj çıkarma, analiz ve karşılaştırma aracı</p>
</div>
""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# MOD 1: TEKLİ METRAJ ÇIKARMA
# ═════════════════════════════════════════════════════════════════════════════

if mode == "📄 Tekli Metraj Çıkarma":
    uploaded_file = st.file_uploader(
        "IFC dosyanızı sürükleyip bırakın veya seçin",
        type=["ifc"],
        accept_multiple_files=False,
        help="Revit, Tekla, ArchiCAD veya diğer BIM yazılımlarından export edilmiş .ifc dosyası",
    )

    if uploaded_file is not None:
        # Dosya hash'i hesapla — aynı dosya için pipeline'ı tekrar çalıştırma
        file_hash = get_file_hash(uploaded_file)
        elem_filter = selected_types if not select_all else None

        try:
            # Pipeline'ı çalıştır veya cache'den al
            with st.status("🔄 IFC dosyası işleniyor...", expanded=False) as status:
                st.write("📂 Dosya yükleniyor ve analiz ediliyor...")

                df, qa, stats, info_dict = run_single_pipeline(
                    file_hash=file_hash,
                    file_bytes=bytes(uploaded_file.getbuffer()),
                    file_name=uploaded_file.name,
                    config=config,
                    elem_filter=elem_filter,
                )

                st.write(f"✅ {info_dict['filename']}: {len(df):,} element çıkarıldı")
                status.update(label="✅ İşlem tamamlandı!", state="complete", expanded=False)

            # ── Dosya Bilgileri ───────────────────────────────────────────
            st.markdown("### 📋 Dosya Bilgileri")
            render_file_info(info_dict)

            # ── Özet İstatistikler ───────────────────────────────────────
            st.markdown("### 📈 Özet İstatistikler")
            render_stats(df, stats)

            # ── Veri Kalitesi ────────────────────────────────────────────
            render_quality_report(qa)

            # ── Sonuç Tabloları ──────────────────────────────────────────
            st.markdown("### 📊 Metraj Verileri")

            tab_list, tab_detail, tab_by_type = st.tabs([
                "📋 Tam Element Listesi",
                "📐 Detaylı Metraj (Tip Kırılımı)",
                "🏗️ Tip Bazlı Özet",
            ])

            with tab_list:
                st.dataframe(
                    df,
                    use_container_width=True,
                    height=500,
                    column_config={
                        "area_m2": st.column_config.NumberColumn("Alan (m²)", format="%.6f"),
                        "volume_m3": st.column_config.NumberColumn("Hacim (m³)", format="%.9f"),
                        "length_m": st.column_config.NumberColumn("Uzunluk (m)", format="%.6f"),
                        "thickness_m": st.column_config.NumberColumn("Kalınlık (m)", format="%.6f"),
                    },
                )

            with tab_detail:
                if not df.empty:
                    # Detaylı metraj özeti
                    detail_groups = []
                    df_copy = df.copy()
                    df_copy["type_name"] = df_copy["type_name"].fillna("Belirsiz Tip")
                    if "materials" in df_copy.columns:
                        df_copy["materials"] = df_copy["materials"].fillna("Belirsiz Malzeme")
                        df_copy.loc[df_copy["materials"] == "", "materials"] = "Belirsiz Malzeme"

                    for (et, mat, tn), sub in df_copy.groupby(
                        ["element_type", "materials", "type_name"], observed=True
                    ):
                        detail_groups.append({
                            "Kategori": str(et).upper(),
                            "Malzeme": str(mat),
                            "Tip Adı": str(tn),
                            "Adet": len(sub),
                            "Alan (m²)": sub["area_m2"].sum() if "area_m2" in sub.columns else None,
                            "Hacim (m³)": sub["volume_m3"].sum() if "volume_m3" in sub.columns else None,
                            "Uzunluk (m)": sub["length_m"].sum() if "length_m" in sub.columns else None,
                        })
                    detail_df = pd.DataFrame(detail_groups).sort_values("Kategori")
                    st.dataframe(
                        detail_df,
                        use_container_width=True,
                        height=400,
                        column_config={
                            "Alan (m²)": st.column_config.NumberColumn(format="%.4f"),
                            "Hacim (m³)": st.column_config.NumberColumn(format="%.6f"),
                            "Uzunluk (m)": st.column_config.NumberColumn(format="%.4f"),
                        },
                    )

            with tab_by_type:
                if not df.empty:
                    type_summary = df.groupby("element_type", observed=True).agg(
                        Adet=("global_id", "count"),
                        **{f"Alan (m²)": ("area_m2", "sum")},
                        **{f"Hacim (m³)": ("volume_m3", "sum")},
                        **{f"Uzunluk (m)": ("length_m", "sum")},
                    ).reset_index()
                    type_summary.columns = ["Element Tipi", "Adet", "Alan (m²)", "Hacim (m³)", "Uzunluk (m)"]
                    type_summary["Element Tipi"] = type_summary["Element Tipi"].str.upper()
                    st.dataframe(type_summary, use_container_width=True, hide_index=True)

                    # Bar chart
                    st.bar_chart(
                        type_summary.set_index("Element Tipi")["Adet"],
                        use_container_width=True,
                        color="#4f8ef7",
                    )

            # ── İndirme Butonları ────────────────────────────────────────
            st.markdown("### 💾 Rapor İndirme")
            col1, col2 = st.columns(2)

            base_name = os.path.splitext(uploaded_file.name)[0]

            # Excel ve JSON byte'larını önceden hazırla (cache'li)
            excel_bytes = generate_excel_bytes(df, quality=qa)
            json_bytes = generate_json_bytes(df)

            with col1:
                st.download_button(
                    label="📥 Excel Raporu İndir (.xlsx)",
                    data=excel_bytes,
                    file_name=f"{base_name}_Metraj_Raporu.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            with col2:
                st.download_button(
                    label="📥 JSON Verisi İndir (.json)",
                    data=json_bytes,
                    file_name=f"{base_name}_Metraj.json",
                    mime="application/json",
                    use_container_width=True,
                )

        except Exception as e:
            st.error(f"❌ İşlem sırasında hata oluştu: {e}")
            logger.exception("Pipeline hatası")


# ═════════════════════════════════════════════════════════════════════════════
# MOD 2: DOSYA KARŞILAŞTIRMA
# ═════════════════════════════════════════════════════════════════════════════

elif mode == "🔄 Dosya Karşılaştırma":
    st.markdown("""
    <div class="glass-card">
        <p style="color: var(--text-secondary); margin: 0;">
            Birden fazla IFC dosyasını yükleyerek metraj karşılaştırması yapabilirsiniz.
            Farklı yazılımlardan (Revit, Tekla, ArchiCAD) export edilmiş dosyalar arasındaki
            sapmaları analiz edin.
        </p>
    </div>
    """, unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Karşılaştırılacak IFC dosyalarını seçin (en az 2)",
        type=["ifc"],
        accept_multiple_files=True,
        help="En az 2 IFC dosyası yükleyin.",
    )

    if uploaded_files and len(uploaded_files) >= 2:
        # Dosya hash'lerini hesapla
        file_hashes = tuple(get_file_hash(uf) for uf in uploaded_files)
        file_data = {}
        for uf in uploaded_files:
            label = os.path.splitext(uf.name)[0]
            file_data[label] = (bytes(uf.getbuffer()), uf.name)

        elem_filter = selected_types if not select_all else None

        try:
            with st.status(f"🔄 {len(uploaded_files)} dosya işleniyor...", expanded=False) as status:
                st.write("📂 Dosyalar yükleniyor ve analiz ediliyor...")

                dfs, infos = run_comparison_pipeline(
                    file_hashes=file_hashes,
                    file_data=file_data,
                    config=config,
                    elem_filter=elem_filter,
                )

                for label, df in dfs.items():
                    st.write(f"✅ {label}: {len(df):,} element")

                status.update(label="✅ Tüm dosyalar işlendi!", state="complete", expanded=False)

            # ── Dosya Bilgileri yan yana ──────────────────────────────────
            st.markdown("### 📋 Dosya Bilgileri")
            cols = st.columns(len(infos))
            for col, (label, info_dict) in zip(cols, infos.items()):
                with col:
                    st.markdown(f"**{label}**")
                    render_file_info(info_dict)

            # ── Karşılaştırma Sonuçları ──────────────────────────────────
            st.markdown("### 🔄 Karşılaştırma Sonuçları")

            tab_comp, tab_pset, tab_diffs = st.tabs([
                "📊 Metraj Karşılaştırma",
                "📋 Pset Kapsam Karşılaştırma",
                "⚠️ Büyük Sapmalar",
            ])

            comp_df = compare(dfs)
            pset_df = compare_psets(dfs)
            big_diffs = flag_large_diffs(comp_df)

            with tab_comp:
                st.dataframe(comp_df, use_container_width=True, height=500)

            with tab_pset:
                st.dataframe(pset_df, use_container_width=True)
                st.info("💡 Yüzde değerleri, her yazılımın ilgili property'yi ne oranda doldurduğunu gösterir.")

            with tab_diffs:
                if not big_diffs.empty:
                    st.warning(f"⚠️ %5'ten büyük sapma bulunan {len(big_diffs)} kayıt:")
                    st.dataframe(big_diffs, use_container_width=True, height=400)
                else:
                    st.success("✅ %5'ten büyük sapma bulunamadı.")

            # ── İndirme ──────────────────────────────────────────────────
            st.markdown("### 💾 Karşılaştırma Raporu")
            excel_bytes = generate_comparison_excel_bytes(dfs)
            st.download_button(
                label="📥 Karşılaştırma Excel Raporu İndir",
                data=excel_bytes,
                file_name="IFC_Karsilastirma_Raporu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        except Exception as e:
            st.error(f"❌ Karşılaştırma sırasında hata oluştu: {e}")
            logger.exception("Karşılaştırma hatası")

    elif uploaded_files and len(uploaded_files) < 2:
        st.warning("⚠️ Karşılaştırma için en az 2 dosya yüklemeniz gerekiyor.")

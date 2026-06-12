#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ifc_pipeline — CLI & İnteraktif Mod

Kullanim:
  python3 main.py                   (İnteraktif Mod: Dosya seçme penceresi açar)
  python3 main.py inspect proje.ifc (Terminal Modu: Sadece inceleme yapar)
"""
import sys
import os
import argparse
import logging

# Proje kokunu path'e ekle
sys.path.insert(0, os.path.dirname(__file__))

import yaml
from ifc_pipeline import (
    load, detect_units, extract_all,
    to_dataframe, quality_report, add_cost_columns,
    to_excel, to_json,
    compare, compare_psets, export_comparison,
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "mapping.yaml")

# ─── Logging Yapılandırması ──────────────────────────────────────────────────

def setup_logging(verbose: bool = False):
    """Proje geneli logging yapılandırması."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_config() -> dict:
    """Config dosyasını yükler ve kapsamlı validasyon yapar."""
    if not os.path.isfile(CONFIG_PATH):
        print(f"❌ Config dosyası bulunamadı: {CONFIG_PATH}")
        sys.exit(1)

    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"❌ Config dosyası bozuk (YAML parse hatası): {e}")
        sys.exit(1)

    if not config:
        print("❌ Config dosyası boş.")
        sys.exit(1)

    # ── Temel yapı kontrolü ──────────────────────────────────────────────────
    if "element_types" not in config:
        print("❌ Config dosyasında 'element_types' anahtarı bulunamadı.")
        sys.exit(1)

    element_types = config["element_types"]
    if not isinstance(element_types, dict) or not element_types:
        print("❌ 'element_types' boş dict veya dict değil.")
        sys.exit(1)

    # ── Element type yapısı kontrolü ─────────────────────────────────────────
    for elem_type, elem_config in element_types.items():
        if not isinstance(elem_config, dict):
            print(f"❌ element_types.{elem_type} bir dict değil.")
            sys.exit(1)

        if "ifc_classes" not in elem_config:
            print(f"❌ element_types.{elem_type}: 'ifc_classes' eksik.")
            sys.exit(1)

        ifc_classes = elem_config["ifc_classes"]
        if not isinstance(ifc_classes, list) or not ifc_classes:
            print(f"❌ element_types.{elem_type}.ifc_classes list değil veya boş.")
            sys.exit(1)

        # Quantity sets kontrolü (varsa validate et)
        if "quantity_sets" in elem_config:
            qty_sets = elem_config["quantity_sets"]
            if not isinstance(qty_sets, dict):
                print(f"❌ element_types.{elem_type}.quantity_sets dict değil.")
                sys.exit(1)

        # Property sets kontrolü (varsa validate et)
        if "property_sets" in elem_config:
            prop_sets = elem_config["property_sets"]
            if not isinstance(prop_sets, dict):
                print(f"❌ element_types.{elem_type}.property_sets dict değil.")
                sys.exit(1)

    return config


def _safe_output_path(output_path: str) -> str:
    """Çıktı dosyası zaten varsa zaman damgalı isim üretir."""
    if not os.path.exists(output_path):
        return output_path

    base, ext = os.path.splitext(output_path)
    counter = 1
    while os.path.exists(f"{base}_{counter}{ext}"):
        counter += 1
    new_path = f"{base}_{counter}{ext}"
    print(f"⚠️  '{output_path}' zaten mevcut, yeni dosya adı: '{new_path}'")
    return new_path


def run_pipeline(ifc_path, output_path, elem_filter=None):
    """Veri cekme ve Excel yazdirma islemlerini yapan ortak motor."""
    config = load_config()

    print(f"\n[1/5] Dosya yukleniyor: {ifc_path}")
    ifc, info = load(ifc_path, config=config)
    print(info.summary())
    print()

    print(f"[2/5] Birim sistemi: ", end="")
    units = detect_units(ifc)
    print(units.describe())

    print(f"[3/5] Elementler cekiliyor"
          + (f" (filtre: {elem_filter})" if elem_filter else " (tumu)") + "...")

    rows, stats = extract_all(
        ifc=ifc,
        config=config,
        units=units,
        source_software=info.source_software,
        source_filename=info.filename,
        element_filter=elem_filter,
    )

    for et, cnt in sorted(stats.items()):
        if cnt > 0:
            print(f"  {et:<20} {cnt:>5} element")
    print(f"  TOPLAM: {sum(stats.values())}")

    print("[4/5] DataFrame olusturuluyor ve dogrulaniyor...")
    df = to_dataframe(rows)
    qa = quality_report(df)

    if qa["warnings"]:
        print("  Uyarilar:")
        for w in qa["warnings"]:
            print(f"    ⚠️   {w}")

    # Çıktı dosyası koruma
    output_path = _safe_output_path(output_path)

    print(f"[5/5] Cikti yaziliyor: {output_path}")
    if output_path.endswith(".json"):
        to_json(df, output_path)
    else:
        to_excel(df, output_path, quality=qa)

    print(f"\n✅ Tamamlandi! {len(df)} element -> '{output_path}' dosyasina kaydedildi.")


def cmd_interactive():
    """Kullaniciya pencere acarak dosya sectiren interaktif mod."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("❌ tkinter kurulu değil. Terminal modunu kullanın:")
        print("   python3 main.py extract dosya.ifc -o cikti.xlsx")
        return

    root = tk.Tk()
    root.withdraw()  # Ana bos pencereyi gizle

    print("Lutfen acilan pencereden islenecek IFC dosyasini secin...")
    ifc_path = filedialog.askopenfilename(
        title="Metrajı Çıkarılacak IFC Dosyasını Seçin",
        filetypes=[("IFC Dosyalari", "*.ifc"), ("Tum Dosyalar", "*.*")]
    )

    if not ifc_path:
        print("❌ Dosya secilmedi, islem iptal edildi.")
        return

    # BUG-3 düzeltmesi: Çıktı dosyasını IFC dosyasının dizinine yaz
    ifc_dir = os.path.dirname(ifc_path)
    base_name = os.path.splitext(os.path.basename(ifc_path))[0]
    output_path = os.path.join(ifc_dir, f"{base_name}_Metraj_Raporu.xlsx")

    # Pipeline'i calistir
    run_pipeline(ifc_path, output_path)


def cmd_inspect(args):
    config = load_config()
    ifc, info = load(args.ifc_file, config=config)
    print(info.summary())
    print()
    units = detect_units(ifc)
    print(f"Birim sistemi: {units.describe()}")


def cmd_extract(args):
    run_pipeline(args.ifc_file, args.output, args.types)


def cmd_compare(args):
    if len(args.ifc_files) < 2:
        print("Hata: En az 2 dosya gerekli")
        sys.exit(1)

    config = load_config()
    dfs    = {}

    for path in args.ifc_files:
        label = os.path.splitext(os.path.basename(path))[0]
        print(f"Yukleniyor: {path} -> etiket: {label}")
        ifc, info = load(path, config=config)
        units      = detect_units(ifc)
        rows, _    = extract_all(
            ifc=ifc, config=config, units=units,
            source_software=info.source_software,
            source_filename=info.filename,
        )
        dfs[label] = to_dataframe(rows)
        print(f"  {len(dfs[label])} element yuklendi")

    output_path = _safe_output_path(args.output)

    print(f"\nKarsilastirma yapiliyor...")
    export_comparison(dfs, output_path)
    print(f"✅ Karsilastirma yazildi: {output_path}")


def main():
    # Eger terminale sadece "python3 main.py" yazilirsa (baska bir yazi yoksa)
    # direkt interaktif pencereyi ac.
    if len(sys.argv) == 1:
        setup_logging(verbose=False)
        cmd_interactive()
        return

    parser = argparse.ArgumentParser(
        description="IFC Pipeline — IFC dosyalarindan veri cekme ve karsilastirma"
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Detayli log ciktisi")
    sub = parser.add_subparsers(dest="command")

    # inspect
    p_inspect = sub.add_parser("inspect", help="Dosya icerigini incele")
    p_inspect.add_argument("ifc_file")

    # extract
    p_extract = sub.add_parser("extract", help="Elemanlari cek ve aktar")
    p_extract.add_argument("ifc_file")
    p_extract.add_argument("--output", "-o", default="metraj.xlsx",
                           help="Cikti dosyasi (.xlsx veya .json)")
    p_extract.add_argument("--types", nargs="+",
                           help="Sadece belirtilen tipler: wall beam column slab ...")

    # compare
    p_compare = sub.add_parser("compare", help="Birden fazla IFC dosyasini karsilastir")
    p_compare.add_argument("ifc_files", nargs="+")
    p_compare.add_argument("--output", "-o", default="karsilastirma.xlsx")

    args = parser.parse_args()
    setup_logging(verbose=getattr(args, "verbose", False))

    if args.command == "inspect":
        cmd_inspect(args)
    elif args.command == "extract":
        cmd_extract(args)
    elif args.command == "compare":
        cmd_compare(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
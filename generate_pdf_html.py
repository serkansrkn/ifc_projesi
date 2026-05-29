#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mermaid diyagramları içeren Markdown dosyasını
tarayıcıda açılabilir / PDF'e yazdırılabilir HTML'e dönüştürür.

Kullanım:
    python3 generate_pdf_html.py

Çıktı:
    ifc_pipeline_algorithm.html  (tarayıcıda aç → Cmd+P → PDF olarak kaydet)
"""

import re
import os

# ─── Kaynak ve hedef dosyalar ────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_MD   = os.path.join(SCRIPT_DIR, "ifc_pipeline_algorithm.md")
OUTPUT_HTML = os.path.join(SCRIPT_DIR, "ifc_pipeline_algorithm.html")


def parse_markdown(md_text: str) -> list[dict]:
    """
    Markdown'dan bölüm başlıklarını, açıklama paragraflarını
    ve mermaid kod bloklarını çıkarır.
    """
    sections = []
    current_section = None

    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # H1 başlık
        if line.startswith("# ") and not line.startswith("## "):
            current_section = {
                "type": "h1",
                "title": line[2:].strip(),
                "content": [],
            }
            sections.append(current_section)
            i += 1
            continue

        # H2 başlık
        if line.startswith("## "):
            current_section = {
                "type": "h2",
                "title": line[3:].strip(),
                "content": [],
            }
            sections.append(current_section)
            i += 1
            continue

        # Blockquote
        if line.startswith("> "):
            sections.append({
                "type": "blockquote",
                "text": line[2:].strip(),
            })
            i += 1
            continue

        # Mermaid kod bloğu
        if line.strip() == "```mermaid":
            mermaid_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                mermaid_lines.append(lines[i])
                i += 1
            sections.append({
                "type": "mermaid",
                "code": "\n".join(mermaid_lines),
            })
            i += 1
            continue

        # Paragraf metni (boş olmayan, --- olmayan)
        if line.strip() and line.strip() != "---":
            # Mevcut section'a açıklama ekle
            if current_section and "content" in current_section:
                # Backtick'leri <code> ile değiştir
                clean = line.strip()
                clean = re.sub(r'`([^`]+)`', r'<code>\1</code>', clean)
                current_section["content"].append(clean)

        i += 1

    return sections


def generate_html(sections: list[dict]) -> str:
    """Bölüm listesinden baskıya hazır HTML üretir."""

    body_parts = []
    diagram_counter = 0

    for sec in sections:
        if sec["type"] == "h1":
            body_parts.append(f'<h1 class="main-title">{sec["title"]}</h1>')
            for line in sec.get("content", []):
                body_parts.append(f'<p class="subtitle">{line}</p>')

        elif sec["type"] == "blockquote":
            body_parts.append(f'<blockquote>{sec["text"]}</blockquote>')

        elif sec["type"] == "h2":
            diagram_counter += 1
            body_parts.append(f'<div class="section-header">')
            body_parts.append(f'  <h2>{sec["title"]}</h2>')
            for line in sec.get("content", []):
                body_parts.append(f'  <p class="section-desc">{line}</p>')
            body_parts.append(f'</div>')

        elif sec["type"] == "mermaid":
            body_parts.append(f'<div class="mermaid-container">')
            body_parts.append(f'  <pre class="mermaid">')
            body_parts.append(sec["code"])
            body_parts.append(f'  </pre>')
            body_parts.append(f'</div>')

    body_html = "\n".join(body_parts)

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IFC Pipeline — Algoritma Akış Diyagramı</title>
    <style>
        /* ═══ GENEL ═══ */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            background: #f5f7fa;
            color: #2c3e50;
            line-height: 1.6;
            padding: 0;
        }}

        .page-wrapper {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 40px 30px;
        }}

        /* ═══ BAŞLIK ═══ */
        .main-title {{
            font-size: 28px;
            font-weight: 700;
            color: #1a1a2e;
            text-align: center;
            margin-bottom: 8px;
            padding-bottom: 16px;
            border-bottom: 3px solid #e94560;
        }}

        .subtitle {{
            text-align: center;
            color: #7f8c8d;
            font-size: 14px;
            font-style: italic;
            margin-bottom: 30px;
        }}

        blockquote {{
            text-align: center;
            color: #7f8c8d;
            font-size: 14px;
            font-style: italic;
            margin-bottom: 30px;
            padding: 10px 20px;
            border-left: 4px solid #e94560;
            background: #fdf2f4;
            border-radius: 0 8px 8px 0;
        }}

        /* ═══ BÖLÜM BAŞLIKLARI ═══ */
        .section-header {{
            margin-top: 40px;
            margin-bottom: 16px;
            padding: 16px 24px;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 12px;
            color: #fff;
            page-break-inside: avoid;
        }}

        .section-header h2 {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 4px;
        }}

        .section-desc {{
            font-size: 13px;
            color: #bdc3c7;
            margin-top: 4px;
        }}

        .section-desc code {{
            background: rgba(255,255,255,0.15);
            padding: 1px 6px;
            border-radius: 4px;
            font-family: 'Fira Code', 'Consolas', monospace;
            font-size: 12px;
        }}

        /* ═══ MERMAID DİYAGRAM KONTEYNERI ═══ */
        .mermaid-container {{
            background: #ffffff;
            border: 1px solid #e0e6ed;
            border-radius: 12px;
            padding: 24px 16px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            overflow-x: auto;
            page-break-inside: avoid;
        }}

        .mermaid {{
            display: flex;
            justify-content: center;
        }}

        .mermaid svg {{
            max-width: 100%;
            height: auto;
        }}

        /* ═══ FOOTER ═══ */
        .footer {{
            text-align: center;
            color: #95a5a6;
            font-size: 11px;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e6ed;
        }}

        /* ═══ PRINT STİLLERİ ═══ */
        @media print {{
            body {{
                background: #fff;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                color-adjust: exact !important;
            }}

            .page-wrapper {{
                max-width: 100%;
                padding: 10px 15px;
            }}

            .section-header {{
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%) !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                margin-top: 25px;
            }}

            .mermaid-container {{
                box-shadow: none;
                border: 1px solid #ccc;
                page-break-inside: avoid;
                break-inside: avoid;
                padding: 12px 8px;
            }}

            .main-title {{
                font-size: 24px;
            }}

            .section-header h2 {{
                font-size: 17px;
            }}

            .no-print {{
                display: none !important;
            }}

            .footer {{
                margin-top: 20px;
            }}
        }}

        /* ═══ YAZDIRMA BUTONU ═══ */
        .print-btn {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: linear-gradient(135deg, #e94560, #c0392b);
            color: #fff;
            border: none;
            padding: 14px 28px;
            border-radius: 50px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(233, 69, 96, 0.4);
            transition: all 0.3s ease;
            z-index: 1000;
        }}

        .print-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(233, 69, 96, 0.5);
        }}

        /* ═══ YÜKLENİYOR EKRANI ═══ */
        .loading-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(26, 26, 46, 0.95);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            transition: opacity 0.5s ease;
        }}

        .loading-overlay.hidden {{
            opacity: 0;
            pointer-events: none;
        }}

        .loading-spinner {{
            width: 50px;
            height: 50px;
            border: 4px solid rgba(233, 69, 96, 0.3);
            border-top: 4px solid #e94560;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}

        .loading-text {{
            color: #ecf0f1;
            font-size: 16px;
            margin-top: 20px;
        }}

        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>

    <!-- Yükleniyor Ekranı -->
    <div class="loading-overlay" id="loadingOverlay">
        <div class="loading-spinner"></div>
        <p class="loading-text">Diyagramlar render ediliyor...</p>
    </div>

    <div class="page-wrapper">
{body_html}

        <div class="footer">
            IFC Pipeline v0.2.0 — Algoritma Akış Diyagramı<br/>
            Bu belge otomatik olarak oluşturulmuştur.
        </div>
    </div>

    <!-- PDF'e Yazdır Butonu -->
    <button class="print-btn no-print" onclick="window.print()">
        🖨️ PDF Olarak Yazdır
    </button>

    <!-- Mermaid JS CDN -->
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'base',
            themeVariables: {{
                primaryColor: '#16213e',
                primaryTextColor: '#ecf0f1',
                primaryBorderColor: '#0f3460',
                lineColor: '#e94560',
                secondaryColor: '#2c3e50',
                tertiaryColor: '#f5f7fa',
                fontSize: '13px',
                fontFamily: '"Segoe UI", "Helvetica Neue", Arial, sans-serif',
            }},
            flowchart: {{
                htmlLabels: true,
                curve: 'basis',
                padding: 15,
                nodeSpacing: 30,
                rankSpacing: 40,
                useMaxWidth: true,
            }},
            securityLevel: 'loose',
        }});

        // Diyagramlar render edildikten sonra loading ekranını kaldır
        mermaid.run().then(() => {{
            setTimeout(() => {{
                document.getElementById('loadingOverlay').classList.add('hidden');
            }}, 500);
        }}).catch(() => {{
            document.getElementById('loadingOverlay').classList.add('hidden');
        }});
    </script>
</body>
</html>"""

    return html


def main():
    # Markdown dosyasını oku
    if not os.path.isfile(INPUT_MD):
        print(f"❌ Dosya bulunamadı: {INPUT_MD}")
        return

    with open(INPUT_MD, "r", encoding="utf-8") as f:
        md_text = f.read()

    print(f"📖 Markdown okundu: {INPUT_MD}")

    # Parse et
    sections = parse_markdown(md_text)
    mermaid_count = sum(1 for s in sections if s["type"] == "mermaid")
    print(f"📊 {mermaid_count} adet Mermaid diyagramı bulundu")

    # HTML oluştur
    html = generate_html(sections)

    # Yaz
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML oluşturuldu: {OUTPUT_HTML}")
    print()
    print("📋 PDF oluşturmak için:")
    print(f"   1. Tarayıcıda açın: file://{OUTPUT_HTML}")
    print(f"   2. Diyagramların render edilmesini bekleyin")
    print(f"   3. Cmd+P (veya Ctrl+P) tuşlayın")
    print(f"   4. 'PDF olarak kaydet' seçin")
    print(f"   5. Arka plan grafiklerini yazdır seçeneğini aktifleştirin")


if __name__ == "__main__":
    main()

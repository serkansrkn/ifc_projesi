# IFC Pipeline — IFC Dosyalarından Otomatik Metraj Çıkarma

IFC (Industry Foundation Classes) dosyalarından element bazlı metraj verisi çıkaran, normalize eden, kalite kontrolü yapan ve Excel/JSON formatında raporlayan bir Python pipeline'ıdır.

## Özellikler

- **Çoklu Yazılım Desteği**: Revit, Tekla, Archicad, Allplan, Vectorworks çıktılarını otomatik tanır
- **Fallback Zincir Sistemi**: Farklı yazılımların kullandığı Pset/Qto isimlerini YAML config ile eşler
- **Otomatik Birim Dönüşümü**: mm, cm, ft, inch → metre/m²/m³ otomatik çevrim
- **Veri Kalitesi Raporu**: Eksik metraj, duplicate GlobalId, katsız element tespiti
- **Karşılaştırma Modu**: Birden fazla IFC dosyası arasındaki metraj sapmalarını ölçer
- **Maliyet Hesabı**: Birim fiyat tablosu ile otomatik maliyet hesaplaması
- **Detaylı Excel Raporu**: Çok sekmeli, formatlanmış Excel çıktısı

## Kurulum

```bash
# Bağımlılıkları yükle
pip install -r requirements.txt
```

> **Not:** `ifcopenshell` kurulumu platforma göre farklılık gösterebilir.
> Detaylı bilgi: https://ifcopenshell.org/

## Kullanım

### İnteraktif Mod (Pencereli)
```bash
python3 main.py
```
Dosya seçme penceresi açılır, IFC dosyasını seçin. Çıktı aynı dizine kaydedilir.

### Terminal Modu

```bash
# Dosya bilgisi inceleme
python3 main.py inspect proje.ifc

# Metraj çıkarma
python3 main.py extract proje.ifc -o metraj.xlsx

# Sadece belirli element tipleri
python3 main.py extract proje.ifc --types wall beam column

# Birden fazla dosya karşılaştırma
python3 main.py compare revit.ifc tekla.ifc -o karsilastirma.xlsx
```

## Proje Yapısı

```
ifc_projesi/
├── main.py                 # CLI & interaktif giriş noktası
├── config/
│   └── mapping.yaml        # Element tipi ↔ IFC class eşleme yapılandırması
├── ifc_pipeline/
│   ├── __init__.py          # Paket export'ları
│   ├── loader.py            # IFC dosya açma ve yazılım tespiti
│   ├── units.py             # Birim sistemi tespiti ve SI dönüşümü
│   ├── properties.py        # Property Set ve Quantity Set okuma
│   ├── extractor.py         # Element veri çıkarma motoru
│   ├── normalizer.py        # DataFrame oluşturma ve veri kalitesi
│   ├── exporter.py          # Excel ve JSON çıktı yazıcı
│   └── comparator.py        # Çoklu dosya karşılaştırma
├── tests/                   # Unit testler
├── requirements.txt         # Python bağımlılıkları
└── README.md
```

## Desteklenen Element Tipleri

| Tip | IFC Sınıfları |
|-----|---------------|
| Duvar | IfcWall, IfcWallStandardCase, IfcWallElementedCase |
| Kiriş | IfcBeam, IfcBeamStandardCase |
| Kolon | IfcColumn, IfcColumnStandardCase |
| Döşeme | IfcSlab |
| Kapı | IfcDoor |
| Pencere | IfcWindow |
| Çatı | IfcRoof |
| Merdiven | IfcStair, IfcStairFlight |
| Temel | IfcFooting |
| Kazık | IfcPile |
| Eleman (Çelik) | IfcMember, IfcMemberStandardCase |
| Giydirme Cephe | IfcCurtainWall |
| Korkuluk | IfcRailing |
| Rampa | IfcRamp, IfcRampFlight |
| Kaplama | IfcCovering |
| Plaka (Çelik) | IfcPlate |

## Lisans

Bu proje akademik/tez çalışması kapsamında geliştirilmiştir.

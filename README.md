# HÂKİM

**Kamu evrak ve yazışma süreçleri için akıllı agent destek sistemi**  
TEKNOFEST 2026 — Yapay Zeka Dil Ajanları Yarışması · 1. Senaryo

HÂKİM, kuruma gelen bir evrakı okuyup anlamlandıran; türünü, eksiklerini ve ilgili dayanakları gösteren; ardından resmi yazı taslağı ve birim yönlendirmesi üreten Türkçe bir çalışma ortamıdır. Sohbet ürünü değildir: kaynaklar görünür kalır, uydurma madde yazılmaz, UYAP/EBYS’ye otomatik gönderim yoktur.

---

## Ne yapıyor?

Şartnamenin iki zorunlu görevi tek zincirde birleşir:

| Görev | Ne bekleniyor | HÂKİM’de |
| --- | --- | --- |
| **1 — Evrak sınıflandırma ve içerik analizi** | Okuma, tür, alan çıkarma, eksik tespit, mevzuat/standart önerisi, özet | `/evrak`, `/v1/evrak`, agent zinciri (okuyucu → sınıf → mevzuat → süre → …) |
| **2 — Resmî yazı taslaklama ve birim yönlendirme** | Üst yazı / cevap / bilgi / olur vb. taslak + havale birimi | `/islem`, `/kamu`, `/v1/senaryo`, 2646 düzeni + dilekçe kalıpları |

Çalışma ilkesi: **önce resmi kaynak, sonra üretim**. Model eğitmek zorunlu değildir; önemli olan gerçek kamu evrak akışına benzer, izlenebilir bir demo.

---

## Neden iki veri ailesi?

Yarışma teması **kamu yazışması**dır; ama kamu evrakı boşlukta işlemez. Bir üst yazının dayanağı yönetmelik olabilir; bir şikayet taslağının dayanağı TCK/CMK olabilir; bir idari cevapta Danıştay veya Resmî Gazete metni gerekir.

Bu yüzden veri ihtiyacı iki kola ayrılır:

1. **Hukuk / yargı / mevzuat** — “hangi kurala dayanıyoruz?”  
2. **Kamu evrakı ve resmi yazışma** — “hangi tür belgeyi nasıl yazıyoruz / yönlendiriyoruz?”

Gerçek kurum içi EBYS evrakı **kullanılmayacak** (şartname 6.5). Bunun yerine açık kaynak metinler, kamuya açık mevzuat, kurgu / sentetik örnekler ve (mümkünse) anonimleştirilmiş örnek formatlar toplanır.

---

## Veri ihtiyacı — ne toplamalıyız?

### A) Hukuk ve mevzuat (dayanak katmanı)

Amaç: sınıflandırma, süre hesabı, hukuki nitelendirme ve atıflı özet için **birincil resmi metin**.

| Öncelik | Kaynak | URL / erişim | Ne alınır? | Neden? |
| --- | --- | --- | --- | --- |
| P0 | Mevzuat Bilgi Sistemi | https://www.mevzuat.gov.tr | Kanun, yönetmelik, Cumhurbaşkanlığı kararları (ör. TCK 5237, CMK 5271, İYUK 2577, **2646 Resmî Yazışma Yönetmeliği**) | Birincil dayanak; madde no ile atıf |
| P0 | 2646 Yönetmelik Ek (ÖRNEK 1–24) | https://www.mevzuat.gov.tr/MevzuatMetin/yonetmelik/21.5.2646-Ek.pdf | Üst yazı / olur / bilgi / cevap blok sırası | Görev 2 resmi üslup ve şablon |
| P1 | Resmî Gazete | https://www.resmigazete.gov.tr | Yayımlanan metinler, genelgeler | Kamu duyuru / yürürlük bağlamı |
| P1 | Yargıtay Karar Arama | https://karararama.yargitay.gov.tr | Örnek ceza/hukuk kararları | Kanun yolu dili, emsal atıf (demo) |
| P1 | Danıştay Karar Arama | https://karararama.danistay.gov.tr | İdari yargı örnekleri | İdari dava / idare yazışması |
| P1 | AYM Kararlar Bilgi Bankası | https://kararlarbilgibankasi.anayasa.gov.tr | Bireysel başvuru örnekleri | Anayasa kalıbı |
| P2 | UYAP Emsal | https://emsal.uyap.gov.tr | Yerel / istinaf / KYB örnekleri | Aşama ve süre senaryoları |
| P2 | Uyuşmazlık Mahkemesi | https://kararlar.uyusmazlik.gov.tr | Görev uyuşmazlığı | Kenar senaryo |
| P2 | Rekabet / KVKK / Sayıştay | ilgili kurum siteleri | Kurul karar özetleri | Kamu kurum yazışması çeşitliliği |
| P3 | TBMM Tutanak | https://www.tbmm.gov.tr/tutanaklar | Tutanak dili | “Tutanak” türü için örnek üslup |
| İkincil | Hugging Face hukuk derlemleri | katalog: `data/catalogs/open_legal_sources.json` | Eğitim / deney; **birincil kaynak yerine geçmez** | Toplu içe aktarılmaz; yalnız etiketli referans |

**Hedef hukuk seti (minimum demo):**

- TCK (5237), CMK (5271) — şikayet / istinaf / temyiz  
- İYUK (2577) — idari dilekçe  
- 6216 — bireysel başvuru süreleri  
- **2646 + Ek PDF** — resmi yazışma blokları  
- Birkaç Yargıtay + Danıştay + AYM örnek metni (atıf için kısa parça yeterli)

### B) Kamu evrakı ve resmi yazışma (işlem katmanı)

Amaç: ajanın gerçek hayattaki **üst yazı, olur, genelge, tutanak, rapor, cevap yazısı, bilgi yazısı** türlerini tanıması ve 2646 düzeninde taslak üretmesi.

| Öncelik | Ne toplanır? | Nereden? | Not |
| --- | --- | --- | --- |
| P0 | Kurgu / sentetik kamu yazışmaları | Projede `data/demo/*.txt`, `data/formats/belgeler/*`, Kamu ekranı örnekleri | Gerçek kişisel veri yok; sayı/konu/muhatap/ilgi alanları dolu olmalı |
| P0 | 2646 Ek örnek düzenleri | Yönetmelik Ek PDF (ÖRNEK 1–24) | Şablon kaynağı; `data/formats/resmi_yazisma/sablon.json` |
| P1 | Kamuya açık genelge / duyuru metinleri | Resmî Gazete, bakanlık / valilik duyuru sayfaları (açık metin) | “Genelge / bilgi yazısı” sınıflandırma |
| P1 | Açık tutanak / rapor örnekleri | TBMM tutanak, kamuya açık faaliyet raporları (kişisel veri temiz) | Tür çeşitliliği |
| P1 | Kurumsal yazışma şablonları (anonim) | Kurumların yayımladığı “yazışma usulleri” kılavuzları, örnek formlar | Gerçek EBYS dump’ı **yasak / istenmez** |
| P2 | OCR senaryoları için taranmış örnek PDF | Sentetik veya açık PDF (metin katmanı zayıf) | Şartname OCR ister; gerçek kimlik yok |
| — | Gerçek kamu EBYS / UYAP işlem dosyası | — | **Toplanmaz.** Şartname: gerçek kamu verisi kullanılmayacak |

**Hedef kamu evrak seti (tür başına en az birkaç örnek):**

| Tür | Alanlar (çıkarılacak) | Üretilecek kalıp |
| --- | --- | --- |
| Üst yazı / havale | sayı, konu, muhatap, ilgi, ek, dağıtım | `ust_yazi` |
| Olur | konu, makam, metin | `olur` |
| Bilgi yazısı | konu, dağıtım | `bilgi_yazisi` |
| Cevap yazısı | ilgi, muhatap, metin | `cevap_yazisi` |
| Genelge | sayı/yıl, kurum | bilgi / duyuru taslağı |
| Tutanak | tarih, kurum | bilgi / özet |
| Rapor | konu, kurum | üst yazı / havale |

Yargı tarafı örnekleri (tebligat, iddianame, gerekçeli karar, dilekçe) de demo klasöründe tutulur; bunlar **hukuk kalıplarına** (şikayet, istinaf, temyiz…) gider.

### C) Toplamada uyulacak kurallar

- Birincil kaynak = resmi site / Resmî Gazete / mevzuat.gov.tr.  
- Her ham kayıt için `metadata.json` (URL, tarih, lisans notu) zorunlu düşünülür (`data/raw/...`).  
- Kişisel veri (T.C. kimlik, adres, imza adı) uydurulmaz / saklanmaz.  
- Hugging Face ve benzeri derlemler **ikincil**; atıf satırında resmi künye tercih edilir.  
- Açık kaynak lisanslarla paylaşılan kodda ağır model dosyası yüklenmez; model için link + lisans notu yeter.

Katalog dosyası: [`data/catalogs/open_legal_sources.json`](data/catalogs/open_legal_sources.json)

---

## Repo düzeni

```
apps/web                 Next.js (Türkçe arayüz)
apps/api                 FastAPI
services/                ingestion, retrieval, graph, deadline, document_ai, llm
connectors/              mevzuat, mahkeme, kurum bağlayıcıları
packages/legal-schema    Legal Data Model
data/catalogs            açık kaynak listesi
data/formats             dilekçe + 2646 resmi yazışma kalıpları
data/demo                kurgu evrak örnekleri (kamu + yargı)
data/raw                 ham anlık görüntüler (git’e büyük dump gitmez)
infra/                   docker-compose, Postgres
```

---

## PDF / OCR (mevzuat `data2/`)

Şartname OCR **veya** doğrudan metin okumaya izin verir. Dijital PDF’lerde önce **metin katmanı** (`pypdf`); taranmış / görsel PDF’lerde **PaddleOCR**.

| Araç | Ne zaman |
| --- | --- |
| **PaddleOCR** (`.venv-ocr`, Python 3.12) | Taranmış PDF, fatura, tablo/layout — asıl OCR motoru |
| **PyMuPDF** (sayfa → görüntü) | OCR öncesi render; `pdf2image`/poppler gerekmez |
| **Crawl4AI** | Web/HTML → Markdown (PDF OCR değil) |

Kurulum + örnek ingest:

```powershell
uv python install 3.12
uv venv .venv-ocr --python 3.12
uv pip install --python .venv-ocr paddlepaddle paddleocr pymupdf pillow

# Metin katmanı (hızlı, çoğu kanun PDF’i)
uv run python scripts/ingest_data2_pdfs.py

# Zorunlu OCR demosu (yavaş, CPU — tam külliyat için Colab A100)
uv run python scripts/ingest_data2_pdfs.py --prefer-ocr --only "bilgi edinme"
```

**Tam OCR (önerilen):** Colab A100 — `notebooks/paddle_ocr_colab.ipynb` ve `COLAB_OCR.md`.

Çıktı: `data/raw/pdf_laws/<slug>/<tarih>/` (`content.txt`, `chunks.jsonl`, `metadata.json` — `extract_method`: `text_layer` | `ocr`).

---

## Yerel çalıştırma (kısa)

```powershell
# API
uv sync
uv run uvicorn hakim_api.main:app --app-dir apps/api/src --port 8000 --host 127.0.0.1

# Web (ayrı terminal)
cd apps/web
npm install
npm run dev
```

- Arayüz: http://127.0.0.1:3000  
- API sağlık: http://127.0.0.1:8000/health  
- Ortam şablonu: `.env.example` (`.env` commit edilmez)

İsteğe bağlı altyapı:

```powershell
cd infra
docker compose up -d postgres redis minio
docker compose --profile search --profile graph up -d   # ES + Neo4j
```

---

## Veri toplama kontrol listesi

- [ ] 2646 Yönetmelik + Ek PDF yerelde / indekste  
- [ ] TCK + CMK (+ İYUK, 6216) madde parçaları indekslenmiş  
- [x] En az bir PDF OCR demosu (`extract_method=ocr`, PaddleOCR)  
- [ ] Her kamu türü için ≥3 kurgu örnek (`ust_yazi`, `olur`, `genelge`, `cevap_yazisi`, …)  
- [ ] En az bir yargı senaryosu (gerekçeli karar → istinaf)  
- [ ] Kaynak URL’leri ve lisans notları dokümante  
- [ ] Gerçek EBYS / kimlik verisi yok  

---

## Lisans ve sınırlar

- Üretilen metinler **taslaktır**; onay ve gönderim kullanıcıya aittir.  
- UYAP / EBYS entegrasyonu yoktur.  
- Atıf yoksa hukuki nitelendirme satırına madde yazılmaz.

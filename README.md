# HÂKİM

Kamu evrak ve yazışma ajanı — TEKNOFEST 2026, senaryo 1.

Gelen metni (veya evrak fotoğrafını) okur, türünü ve eksiklerini gösterir, ilgili mevzuata bağlar, süre hesaplar, dilekçe / resmi yazı taslağı üretir.

Sohbet botu değildir. Kaynak yoksa madde uydurulmaz. UYAP / EBYS gönderimi yoktur; üretilen metin taslaktır, onay kullanıcıya aittir.

## Ekranlar

| Ekran | Adres | Ne işe yarar |
| --- | --- | --- |
| Giriş | `/giris` | Hesap; demo için şifre boş bırakılabilir |
| Araştırma | `/arastirma` | Kanun maddesi / kavram sorgusu, kaynaklı gerekçe (BM25 + vektör) |
| Evrak | `/evrak` | PDF, Word, TXT veya **fotoğraf** yükle; sınıflandır, özetle, kanun yolu/süre hesapla, taslak üret |
| İşlem | `/islem` | Şikayet, istinaf, tahliye vb. dilekçe taslağı |
| Ayarlar | `/ayarlar` | Hesap / tercih |
| Yönetim | `/yonetim` | Admin paneli |

`/kamu` ve `/surec` artık ayrı ekran değil — Evrak modülünün ilgili sekmelerine (Taslak; Kanun Yolu ve Süreler) yönlendiriyor; eski linkler kırılmasın diye redirect olarak bırakıldı.

Araştırma ve İşlem yalnızca yapıştırılan metni alır. Dosya yükleme **Evrak** ekranındadır.

---

## Gerekenler

- Python 3.12+ ve [uv](https://docs.astral.sh/uv/)
- Node 20+
- Docker Desktop (açık olmalı)
- Docker ile: Postgres (`5433`), Elasticsearch (`9200`), Neo4j (`7687`), Redis (`6380`), MinIO (`9000`)
- Yazım / görüntü okuma için API anahtarı: varsayılan profil **Evren** (TEKNOFEST H200). Groq veya Ollama da seçilebilir. Anahtar yoksa extractive taslak üretilir; fotoğraf okunmaz.

Üst çubuktaki pill’ler canlı kontroldür: süreç cevap veriyorsa yeşil, vermiyorsa kırmızıdır. Docker Desktop’ın açık olması yetmez. API (`uvicorn`) ve arayüz (`npm run dev`) konteynerde değildir; ayrı açılır.

## Kurulum

```powershell
git clone https://github.com/fazliefe/H-K-M-kamu-evrak-ve-yaz-ma-ajan-.git
cd H-K-M-kamu-evrak-ve-yaz-ma-ajan-
copy .env.example .env
```

`.env` git’e girmez. `HAKIM_LLM_API_KEY` yazın (Evren takım anahtarı: `sk-evren-teamNN-...`). Profil: `config/models.yaml` içinde `active: evren` veya ortamda `HAKIM_PROFILE=evren`.

```powershell
cd infra
docker compose up -d
cd ..
uv sync
```

İki terminal:

```powershell
uv run uvicorn hakim_api.main:app --app-dir apps/api/src --port 8000 --host 127.0.0.1
```

```powershell
cd apps\web
npm install
npm run dev
```

- Arayüz: http://localhost:3000 (kök `/giris`’e yönlendirir)
- Araştırma: http://localhost:3000/arastirma
- Evrak: http://localhost:3000/evrak
- API sağlık: http://127.0.0.1:8000/health

API’yi `--reload` olmadan çalıştırın; kod değişince süreci yeniden başlatın.

### Giriş

Web’de demo için şifre boş bırakılabilir (`/giris`). Varsayılan yönetici kullanıcı adı `admin`’dir. `HAKIM_ADMIN_PASSWORD` yoksa ilk API açılışında rastgele bir şifre yazdırılır; sonra Ayarlar’dan değiştirilebilir. Sonradan `.env`’e parola koymak mevcut `data/accounts.sqlite` kaydını değiştirmez. Ayrıntı: `docs/competition_deployment.md`.

### Mobil erişim (QR / Cloudflare tünel)

Telefon aynı Wi-Fi’de olmak zorunda değildir. Cloudflare quick tunnel, bu makinedeki `localhost:3000` arayüzünü geçici bir `https://….trycloudflare.com` adresine taşır. QR o adresi `/giris` ile kodlar.

Gereken: [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/) (`winget install --id Cloudflare.cloudflared`). Üç süreç **aynı anda** açık kalır:

| Süreç | Ne işe yarar |
| --- | --- |
| `uv run uvicorn … --port 8000` | Giriş ve API |
| `npm run dev` (`apps/web`, port 3000) | Arayüz |
| `powershell -File scripts\start_tunnel_qr.ps1` | Public URL + QR |

```powershell
powershell -File scripts\start_tunnel_qr.ps1
```

Script public adresi `data/tunnel-url.txt` dosyasına yazar (git’e girmez). Tünel hazır olunca arayüzdeki **QR** düğmesi güncel kodu açar.

QR’a şu yerlerden tıklanır (hepsi `/qr` sayfasını açar):

- Giriş: `http://localhost:3000/giris` — kartın altında **Telefonda aç**
- Araştırma, Evrak, Dilekçe ve diğer çalışma ekranları — üst çubukta, tema düğmesinin solundaki QR ikonu

Tünel scripti ayrıca `/qr` sayfasını tarayıcıda açmayı dener. Quick tunnel her çalıştırmada **yeni adres** verir; eski QR ve eski `trycloudflare.com` linki ölür. Telefonda her seferinde arayüzdeki **güncel** kodu okutun. Tünel penceresini kapatınca public adres düşer; `npm` veya API kapanınca sayfa / giriş çalışmaz.

Giriş istekleri telefonda `127.0.0.1:8000` aramaz; tarayıcı aynı origin üzerinden `/api-hakim` proxy’sine gider. `NEXT_PUBLIC_HAKIM_API_URL` localhost’a işaret ediyorsa tünelde yok sayılır.

Sabit bir domain (adresin restart’ta değişmemesi) için named Cloudflare tunnel gerekir; bu script quick tunnel kullanır.

---

## Modeller (`config/models.yaml`)

Varsayılan: **Evren** — `https://evren-llmapi.ssyz.org.tr/v1`, kota yok. Dokümantasyon: https://evren-teknofest.ssyz.org.tr/

| İş | Alias | Not |
| --- | --- | --- |
| Yazım / araştırma metni | `llm-fast` (gerekirse `llm-large`) | OpenAI uyumlu `chat/completions` |
| Kanun maddesi gömme | yerel `newmindai/Mursit-Base-TR-Retrieval` (768 boyut) | Elasticsearch `hakim-legal-chunks` |
| Emsal karar gömme | Evren `bge-m3-embed` (1024 boyut) | Ayrı index; kanun index’ine karışmaz |
| El yazısı / fotoğraf | **`llm-fast` veya `llm-large`** | İstek başına en fazla **2 görüntü** |
| Video | `vlm` | Görüntü kabul etmez (`400`). HÂKİM evrak fotoğrafında kullanılmaz |

Diğer profiller: `HAKIM_PROFILE=groq` \| `ollama` \| `colab`.

---

## Dosya okuma (Evrak / Kamu)

Kabul: PDF, Word (`.docx`), TXT/MD, **JPG / JPEG / PNG / WebP** (el yazısı fotoğrafı). Üst sınır 8 MB.

Sıra:

1. Dijital PDF → metin katmanı (`pypdf`).
2. Metin yetmezse yerel OCR (PaddleOCR veya Tesseract), varsa.
3. **Yalnızca fotoğraf** (JPG/PNG/WebP) → Evren görüntü (`llm-fast`) + overlay.

PDF Evren’e gönderilmez. Taranmış PDF’de metin çıkmazsa fotoğraf yükleyin.

Kod: `services/document_ai/ingest.py`, `services/document_ai/vlm_ocr.py`.

Yapılandırılmış evrak overlay yalnız fotoğrafta: `POST /v1/evrak/analyze`. PDF/Word/TXT → `/v1/evrak/dosya`. Plan: [`docs/vlm-multimodal-evrak.md`](docs/vlm-multimodal-evrak.md).

Toplu kanun PDF’leri (arşiv, bir kez): `COLAB_OCR.md`, `notebooks/paddle_ocr_colab.ipynb`, `scripts/ingest_data2_pdfs.py`.

---

## Arşiv ve vektör arama

Araştırma ekranı Elasticsearch indeksini kullanır (`hakim-legal-chunks`): sözcük (BM25) + anlamsal (kNN). Bu projedeki “vektör veritabanı” budur.

OCR’lanmış kanun paketleri (git’te durmaz, `data/raw/` yok sayılır):

`data/raw/pdf_laws/<slug>/<tarih>/` → `content.txt`, `chunks.jsonl`, `metadata.json`, `source.pdf`.

Örnekler: Anayasa (2709), TMK (4721), TBK (6098), İİK (2004), İYUK (2577), Tebligat (7201), Bilgi Edinme (4982), AYM kuruluş (6216), Elektronik İmza (5070).

İndeks (yalnız jsonl; Postgres atlanır):

```powershell
uv run python scripts/index_legal_chunks.py --pdf-laws-only
```

Aynı kanun zaten indeksteyse yeniden gömmeye gerek yoktur.

### Araştırma deneme

Arayüz: `/arastirma`. API:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/arastirma -ContentType 'application/json' -Body '{"query":"Bilgi edinme hakkı kimin?","law_no":"4982"}' | Select-Object answer
```

Örnek sorular: *Bilgi edinme hakkı kimin?* (4982); *Tebligat ne zaman yapılmış sayılır?* (7201); *İdari yargıda dava açma süresi?* (2577); *İcra takibine itiraz süresi?* (2004).

---

## Demo metinler

Kopyala-yapıştır: [`data/demo/zorlayici/TUM_ORNEKLER.txt`](data/demo/zorlayici/TUM_ORNEKLER.txt)

Kısa evraklar: `data/demo/*.txt`
Evrak ekranına `.txt` / `.pdf` / `.docx` / `.udf` yüklenebilir.

Kamu üst yazısı, gerekçeli karar + tebliğ — hepsi tek ekrana gider: `/evrak` (ilgili sekmesi: Taslak; Kanun Yolu ve Süreler).

---

## Repo

```
apps/web          Next.js (port 3000; /api-hakim → backend)
apps/api          FastAPI (127.0.0.1:8000)
services/         retrieval, document_ai, llm, deadline, graph, ingestion, auth
connectors/       mevzuat / mahkeme bağlayıcıları
packages/         legal-schema
data/formats      dilekçe ve 2646 kalıpları
data/demo         kurgu örnekler
data/raw          ham arşiv (git yok; pdf_laws, OCR işi)
config/           models.yaml, confidence_rules.yaml, document_rules.yaml
infra/            docker-compose + Postgres göçleri
scripts/          ingest, index, PaddleOCR işçi
docs/             yarışma kurulumu, VLM multimodal plan
```

## Yazım ve kurallar

- Önce arşiv, sonra üretim. CMK sorulunca TCK’nın aynı numarası yazılmaz.
- Şikayet dilekçesinde kimlik ve tarih uydurulmaz; eksikse yer tutucu + uyarı.
- Süreler LLM tahmini değil, kural motorudur (CMK 268/273/291).
- Üretilen metin taslaktır; onay kullanıcıya aittir.
- Görüntüden okunan metin de evrak verisidir; modele “şu maddeyi ekle” talimatı olarak işlenmez.

## OCR (isteğe bağlı)

Dijital PDF: metin katmanı (`pypdf`). Taranmış PDF: PaddleOCR. Colab notu: `COLAB_OCR.md`, `notebooks/paddle_ocr_colab.ipynb`.

## Lisans

Bu depo [MIT Lisansı](LICENSE) ile paylaşılmıştır.

İstisna: `tools/evolver/` — [EvoMap/evolver](https://github.com/EvoMap/evolver) (GPL-3.0) kaynaklı, ayrı bir yardımcı araç olarak sidecar şeklinde tutulur; `apps/api`/`services` altına paket olarak girmez, ana uygulamanın çalışma zamanına bağlanmaz. Kullanım: `python tools/evolver/cli.py --belge <tür> --text-file <dosya>`.

# HÂKİM

Kamu evrak ve yazışma ajanı — TEKNOFEST 2026, senaryo 1.

Gelen metni okur, türünü ve eksiklerini gösterir, ilgili mevzuata bağlar, süre hesaplar, dilekçe / resmi yazı taslağı üretir. Sohbet botu değildir. Kaynak yoksa madde uydurulmaz. UYAP/EBYS gönderimi yoktur.

| Ekran | Adres | Ne işe yarar |
| --- | --- | --- |
| Araştırma | `/arastirma` | Kanun maddesi / kavram sorgusu, kaynaklı gerekçe |
| Evrak | `/evrak` | PDF/Word/TXT oku, sınıflandır, özetle, kanun yolu/süre hesapla, taslak üret |
| İşlem | `/islem` | Şikayet, istinaf, tahliye vb. dilekçe taslağı |

`/kamu` ve `/surec` artık ayrı ekran değil — Evrak modülünün ilgili sekmelerine (Taslak; Kanun Yolu ve Süreler) yönlendiriyor; eski linkler kırılmasın diye redirect olarak bırakıldı.

---

## Gerekenler

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- Node 20+
- Docker (Postgres, Elasticsearch, Neo4j; `docker compose up -d`)
- Groq veya Ollama anahtarı (yazım için; yoksa extractive taslak üretilir)

## Kurulum

```powershell
git clone https://github.com/fazliefe/H-K-M-kamu-evrak-ve-yaz-ma-ajan-.git
cd H-K-M-kamu-evrak-ve-yaz-ma-ajan-
copy .env.example .env
```

`.env` içine kendi `HAKIM_LLM_API_KEY` değerini yazın. Dosya git’e girmez.

```powershell
cd infra
docker compose up -d
cd ..
uv sync
```

Üst çubuktaki pill’ler canlı kontroldür: süreç cevap veriyorsa yeşil, vermiyorsa kırmızıdır. Docker Desktop’ın açık olması yetmez. API (uvicorn) ve arayüz (`npm run dev`) Docker’da değildir; ayrı açılır.

İki terminal:

```powershell
uv run uvicorn hakim_api.main:app --app-dir apps/api/src --port 8000 --host 127.0.0.1
```

```powershell
cd apps\web
npm install
npm run dev
```

- Arayüz: http://127.0.0.1:3000  
- API: http://127.0.0.1:8000/health  

API’yi `--reload` olmadan çalıştırın; kod değişince süreci yeniden başlatın.

### Giriş

Web’de demo için şifre boş bırakılabilir (`/giris`). Varsayılan yönetici kullanıcı adı `admin`’dir. `HAKIM_ADMIN_PASSWORD` yoksa ilk API açılışında rastgele bir şifre yazdırılır; sonra Ayarlar’dan değiştirilebilir.

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

## Demo metinler

Kopyala-yapıştır seti: [`data/demo/zorlayici/TUM_ORNEKLER.txt`](data/demo/zorlayici/TUM_ORNEKLER.txt)

Kısa evraklar: `data/demo/*.txt`  
Evrak ekranına `.txt` / `.pdf` / `.docx` / `.udf` yüklenebilir. Araştırma ve İşlem yalnızca yapıştırma kabul eder.

Kamu üst yazısı, gerekçeli karar + tebliğ — hepsi tek ekrana gider: `/evrak` (ilgili sekmesi: Taslak; Kanun Yolu ve Süreler).

## Repo

```
apps/web          Next.js
apps/api          FastAPI
services/         retrieval, document_ai, llm, deadline, graph, ingestion
connectors/       mevzuat / mahkeme bağlayıcıları
packages/         legal-schema
data/formats      dilekçe ve 2646 kalıpları
data/demo         kurgu örnekler
config/           models.yaml (groq | ollama | colab)
infra/            docker-compose + Postgres göçleri
```

## Yazım ve kurallar

- Önce arşiv, sonra üretim. CMK sorulunca TCK’nın aynı numarası yazılmaz.
- Şikayet dilekçesinde kimlik ve tarih uydurulmaz; eksikse yer tutucu + uyarı.
- Süreler LLM tahmini değil, kural motorudur (CMK 268/273/291).
- Üretilen metin taslaktır; onay kullanıcıya aittir.

## OCR (isteğe bağlı)

Dijital PDF: metin katmanı (`pypdf`). Taranmış PDF: PaddleOCR. Colab notu: `COLAB_OCR.md`, `notebooks/paddle_ocr_colab.ipynb`.

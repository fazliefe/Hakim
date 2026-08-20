# HÂKİM

Kamu evrak ve yazışma ajanı — TEKNOFEST 2026, senaryo 1.

Gelen metni okur, türünü ve eksiklerini gösterir, ilgili mevzuata bağlar, süre hesaplar, dilekçe / resmi yazı taslağı üretir. Sohbet botu değildir. Kaynak yoksa madde uydurulmaz. UYAP/EBYS gönderimi yoktur.

| Ekran | Adres | Ne işe yarar |
| --- | --- | --- |
| Araştırma | `/arastirma` | Kanun maddesi / kavram sorgusu, kaynaklı gerekçe |
| Evrak | `/evrak` | PDF/TXT oku, sınıflandır, ajan zinciri |
| Kamu | `/kamu` | 2646 üst yazı / olur / bilgi / cevap taslağı |
| Süreç | `/surec` | Aşama + kanun yolu + son gün (kural motoru) |
| İşlem | `/islem` | Şikayet, istinaf, tahliye vb. dilekçe taslağı |

---

## Gerekenler

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- Node 20+
- Docker (Postgres, isteğe bağlı Elasticsearch / Neo4j)
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
docker compose up -d postgres redis minio
docker compose --profile search --profile graph up -d
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

- Arayüz: http://127.0.0.1:3000  
- API: http://127.0.0.1:8000/health  

API’yi `--reload` olmadan çalıştırın; kod değişince süreci yeniden başlatın.

### Giriş

Web’de demo için şifre boş bırakılabilir (`/giris`).

## Demo metinler

Kopyala-yapıştır seti: [`data/demo/zorlayici/TUM_ORNEKLER.txt`](data/demo/zorlayici/TUM_ORNEKLER.txt)

Kısa evraklar: `data/demo/*.txt`  
Evrak ve Kamu ekranlarına `.txt` / `.pdf` yüklenebilir. Araştırma, Süreç, İşlem yalnızca yapıştırma kabul eder.

Doğru ekran: kamu üst yazısı → `/kamu`; gerekçeli karar + tebliğ → `/surec` veya `/evrak`.

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

# HÂKİM — VLM / multimodal evrak

Amaç: dosyadan yalnızca metin çıkarmak değil; kalite → yapılandırılmış alanlar → kanıt/güven → eksiklik/çelişki/gizlilik → paket analizi.

**Mimari kural:** bütün modüller `StructuredDocument` üzerinde çalışır. VLM hukuki hüküm vermez; “alan burada, değer bu, güvenim şu” der. Python/kural motoru gerekli alan, uyuşmazlık ve paket kararını verir. Sistem “belge sahtedir” veya “üst yazı yanlıştır” demez.

## Sprint 1 (tamam)

Çalışır:

Fotoğraf (JPEG/PNG/WebP) → kalite → VLM JSON → `StructuredDocument`

PDF / Word / TXT `POST /v1/evrak/analyze` kabul etmez; `POST /v1/evrak/dosya` (metin katmanı / yerel OCR) kullanır.

| Parça | Konum |
| --- | --- |
| Ortak model | `packages/legal-schema/src/hakim_legal_schema/document.py` |
| Güven eşikleri | `config/confidence_rules.yaml` |
| Tür bazlı zorunlu alanlar | `config/document_rules.yaml` |
| Analyzer | `services/document_ai/vision/analyzer.py` |
| API | `POST /v1/evrak/analyze` |

## Sprint 2 (tamam)

`/evrak` görüntüleme: belge + bbox overlay + Özet / Kontrol / Kanıt sekmeleri.

Fotoğraf yüklenince tek VLM çağrısı (`/v1/evrak/analyze`); okunan `raw_text` ajan zincirine (`/v1/evrak`) gider — görüntü VLM’e iki kez gitmez. PDF/Word aynı overlay yolunu kullanmaz. `[Belgede göster]` yalnız güvenilir, küçük bbox’ları kutular. Gizlilik ve Dosya sekmeleri yer tutucudur.

Mevcut `POST /v1/evrak` ve `POST /v1/evrak/dosya` metin/ajan zincirini bozmaz. `vlm_ocr.py` düz metin OCR için durur. Evren `vlm` alias’ı video-only’dir; hâlâ `llm-fast` / `llm-large`, istek başına en fazla 2 görüntü.

VLM çıktısı hukuki `verdict` içermez. Alan `bbox` değerleri 0–1 normalize.

## Sonraki sprintler

3. Düşük güvende bbox crop + `llm-large` ikinci okuma  
4. Eksik alan / sayfa / ek  
5. Bundle (çoklu evrak, Postgres; Neo4j şart değil)  
6. Belgeler arası çelişki (“uyuşmazlık tespit edildi”, hangisi doğru demeden)  
7. PII + redacted kopya (orijinal değişmez)  
8. Görsel tutarsızlık (P2; en son; sahtecilik iddiası yok)

## Demo beklenen JSON

`data/demo/vision/expected/` — VLM prompt değişince regressiyon için.

## Nihai demo akışı (hedef)

`karar.pdf` + `tebligat.jpg` + `ust_yazi.pdf` + `ekler.pdf` → kalite uyarısı → türler → tebliğ tarihi + [Belgede göster] → eksik imza → eksik ek → dosya no uyuşmazlığı → gizleme. Bu sprint yalnızca tek belge structured JSON üretir.

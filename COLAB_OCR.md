# Colab A100 — PaddleOCR (bir kez)

Yerel CPU ~4 dk/sayfa. A100’de ~700 sayfa dakikalar–onlarca dakika.

## 1. Runtime

Colab: **Runtime → Change runtime type**

- Hardware accelerator: **GPU**
- GPU type: **A100**

Notebook: `notebooks/paddle_ocr_colab.ipynb`  
(Colab’da File → Upload notebook)

## 2. PDF’leri Drive’a koy

PC’deki `data2/*.pdf` klasörünü kopyala:

`Google Drive / MyDrive / hakim-ocr / data2 /`

(9 kanun PDF; toplam ~6 MB)

## 3. Notebook’u çalıştır

Tüm hücreler sırayla. Çıktı Drive’da kalır (kopsa bile resume eder):

`MyDrive/hakim-ocr/pdf_ocr_work/<slug>/content.txt`

Bitince zip: `MyDrive/hakim-ocr/pdf_ocr_work.zip`

## 4. PC’ye geri

Zip’i aç → `data/raw/pdf_ocr_work/`

```powershell
uv run python scripts/ingest_data2_pdfs.py --from-ocr-work
```

Madde parçaları: `data/raw/pdf_laws/<slug>/` (`extract_method=ocr`).

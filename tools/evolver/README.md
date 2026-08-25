# HÂKİM evolver sidecar

Dilekçeyi **yazmaz**. Taslağı puanlar: «bu yönde» yalanı, uydurma künye, CMK/İYUK karışması, ticaret emsali.

`@evomap/evolver` (GPL-3.0) **`apps/api` içine paket olarak girmez.** Bu klasör Cursor / CLI sidecar’dır. `prompt.py` ve `writer.py` yerini almaz; öneri üretir, prompt değişikliği **insan onayı** ister.

## Çalıştır

Repo kökünden:

```bash
python tools/evolver/cli.py --belge temyiz --text-file taslak.txt
```

veya stdin.

İsteğe bağlı resmi CLI (aynı GEP deposu, API’ye bağımlılık yok):

```bash
npm install -g @evomap/evolver
# git repo kökünde, inceleme modu:
set GEP_ASSETS_DIR=tools/evolver/gep
evolver --review
```

## Sisteme bağ

`compose_belge` taslağı ürettikten sonra `petition.evolver` doldurur. UI, puan düşükse uyarı gösterir. Event kaydı: `tools/evolver/gep/events.jsonl`.

Genes: `tools/evolver/gep/genes.json`.

# Yarın (26 Ağustos 2026)

Bugün kilitlenen durum: Temyiz taslağı uydurma künye yazmıyor; konu kesişmeyen arşiv hit’i basılmıyor; gold 1997 yapıştırılmıyor. `CMK m.142` / `TCK m.2024/…` sızıntısı kesildi.

## 1. Emsal atfını profesyonel hale getir — yapıldı

- Temyiz / istinafta yalnızca Yargıtay, ceza dairesi, CGK, İBK. Ticaret, BAM hukuk, Rekabet, isim satırı düşer.
- Konu (metin + TCK başlığı) ilam gövdesinde yoksa **künye basılmaz** (rastgele gerçek ilam emsal değil).
- İBK ayrı işaretlenir. Tebliğ tarihi metinde varsa dilekçeye basılır.
- Fine-tune yok. 11M HuggingFace dump yok.

## 2. GitHub: EvoMap/evolver’ı hayata geçir — sidecar bağlandı

Kaynak: https://github.com/EvoMap/evolver (GPL-3.0)

- `apps/api` içine paket olarak **girmez**. Kod: `tools/evolver/`.
- `compose_belge` taslağı puanlar (`petition.evolver`); «bu yönde», uydurma künye, CMK/İYUK karışması.
- `prompt.py` / `writer.py` yerini almaz. Prompt değişikliği `human_approval_required`.
- Gene / event: `tools/evolver/gep/`. CLI: `python tools/evolver/cli.py --belge temyiz --text-file taslak.txt`

## 3. Dilekçe formatlarını teker teker kontrol — extractive tur yapıldı

Her kalıp: hitap, bölüm sırası, süre maddesi, emsal satırı (varsa), uydurma yasak.

Ceza / kanun yolu:

- [x] şikayet
- [x] suç duyurusu
- [x] cevap
- [x] itiraz
- [x] istinaf
- [x] temyiz (tebliğ + konu-emsal + motor `last_day`)
- [x] katılma
- [x] tahliye
- [x] adli kontrol itirazı

Anayasa / idare:

- [x] bireysel başvuru (AYM)
- [x] idari dava

Hukuk / icra (örnek dilekçe düzeni; HMK madde ezbere yazılmaz):

- [x] süre uzatım talebi
- [x] ilamsız icra borca itiraz
- [x] temyize cevap / karşı temyiz
- [x] ihtiyaç sebebiyle tahliye (kira) — tutuklu tahliyeden ayrı

Kamu 2646:

- [x] üst yazı
- [x] bilgi yazısı
- [x] olur
- [x] cevap yazısı

Kontrol: makam doğru; CMK/İYUK karışmıyor; emsal ticaret/hukuk sızmıyor; kimlik uydurulmuyor; süre kuralı katalogdan, **son gün** yalnız motor `last_day` varsa.

Canlı UI tıklaması bu turda yok; `/islem` ile bir gerçek metin bakılabilir.

## 4. Sohbetteki notlar (foto) — ne yapacağız

Hakimler kararı içtihat üzerine kuruyor; süre ve lehe kural madde metninden sapabilir; HMK ve özel ceza kanunları eksik.

| İstek | Yarın / sonra ne yapacağız | Yapmayacağız |
| --- | --- | --- |
| Yargıtay + İBK | Madde 1 ile aynı iş: resmi künye, İBK’yı ayır, uydurma esas yok | Karar metnini modele yedirip SFT |
| Sürelerde ilke / madde dışı yorum | Süreç motorunda “kural bu, ilke şu yüzden sapabilir” **uyarısı**; last_day yine kuraldan | LLM’in ezbere gün sayması |
| Lehe uygulama (TCK 7) | Suç tarihi + yürürlük aralığı arşivde varsa lehe versiyonu **göster**; yoksa “lehe tarama yapılamadı” | En son TCK’yı otomatik yazmak; arşivde yokken madde uydurmak |
| HMK | Resmi metni arşive al (mevzuat.gov.tr), ES’e index; hukuk dilekçesi/süre için kaynak | Ezbere madde |
| Kabahatler + özel ceza | Katalog: 5326 ve hangilerini ekleyeceğimizi seç; resmi ingest | Hepsini bir gecede taramak |

Sıra: ~~1 emsal~~ → ~~3 kalıp turu~~ → ~~2 evolver sidecar~~ → **4 HMK ingest + lehe / ilke uyarısı**.

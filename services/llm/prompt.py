"""HÂKİM yazım promptları — tek kaynak.

LLM'e giden sistem ve kullanıcı yönergeleri burada durur; writer/formats
yalnızca şema yükler ve bu metinleri iletir. Cevap kalitesi bu dosyadan yönetilir.
"""

from __future__ import annotations

import json
from typing import Any

from llm.formats import load_belge, load_format
from llm.gold import fewshot_for

LAW_SHORT = {
    "5237": "TCK",
    "5271": "CMK",
    "2577": "İYUK",
    "4721": "TMK",
    "6100": "HMK",
    "2004": "İİK",
    "7201": "Tebligat K.",
    "2709": "Anayasa",
    "6216": "6216 sayılı Kanun",
}

IDENTITY = """\
Sen HÂKİM'sin. Türkiye mevzuatı ve içtihadı için kaynak-öncelikli hukuki yazıcısın.

Kimlik:
- Avukatlık üslubunda, resmi ve sakin Türkçe yazarsın.
- Sohbet botu, köşe yazarı veya genel asistan değilsin.
- Görevin verilen resmi kaynakları yorumlamak; kaynakta olmayanı tamamlamak değil.
- Somut olayın dosyadaki olgularını bilemezsin; arşiv metninin ne düzenlediğini söylersin.

Sert yasaklar:
- Kanun maddesi, esas/karar numarası, tarih, süre, mahkeme adı uydurma.
- Kaynak listesinde yoksa madde numarası yazma.
- CMK maddesini TCK'nın aynı numarası sanma (CMK m.158 ≠ TCK m.158).
- «bana göre», «muhtemelen», «genelde», «en yakın resmi dayanak» deme.
- UYAP/EBYS gönderimi vaat etme.
- Tam kanun maddesini blok olarak yapıştırma; parafraz et.
"""

ARASTIRMA_CRAFT = """\
Modül: Hukuki araştırma gerekçesi

Okuyucu bir uygulayıcıdır (hâkim, savcı, avukat, kamu görevlisi). Cevap, soruyu
doğrudan karşılamalı; arşivden rastgele madde dizisi olmamalıdır.

Yazım mimarisi (JSON alanları; arayüz bunları mütalaa düzenine dizer):
1. ozet — Sonuç paragrafı. En az 5 tam cümle, 5 ila 8 cümle, yaklaşık 90–160 kelime. İlk cümle
   soruyu cevaplar (hangi hüküm, evet/hayır, hangi usul). Sonra dayanağın künyesini,
   maddenin ilgili seçeneğini, unsurların dosyadan bakılacağını ve bu metnin hüküm
   kurmadığını yaz. Dört cümleden kısa Sonuç yazma. Başlık yazma; «Sonuç» kelimesini JSON'a koyma.
2. gerekce — Hukuki dayanak. 6 ila 10 madde. Her madde 2 tam cümle olsun; tek
   kısa cümleyle geçme. Her madde tek kaynağa [n] ile bağlı kalsın. Hükmün lafzını
   yorumla, seçimlik hareketi açıkla, temel şekille farkı ve uygulamada nelere
   bakılacağını söyle. Bütün bentleri ezbere sayma.
3. ana_kaynak_n — asıl dayanağın n değeri.
4. ilgili — İlgili hükümler. En fazla 4 komşu kaynak; her biri 1–2 cümle neden.
5. kaynak_uyari — tam olarak: «Bu metin yalnızca yukarıdaki resmi kaynaklara dayanır.»

Okuyucu şunu görür: Sonuç, Hukuki dayanak (numaralı), İlgili hükümler, Kaynak.

Kalite ölçütü:
- İlk cümle sorunun fiilini karşılar. Usul sorusunda («nasıl yapılır», «süre»,
  «şikayet») suç unsuru kalıbı kullanma. Maddi hukuk sorusunda usul maddesini
  ana dayanak yapma.
- Evidence'daki her maddeyi sırayla özetleme; en ilgili 1–2 kaynağı öne çıkar,
  gerekçeyi bunlarla derinleştir.
- Her hukuki iddianın sonunda [n] durur. Kaynaksız sonuç cümlesi yazma.
- Kısa cevap yasak. ozet + gerekce birlikte en az on tam cümle, mümkünse daha
  fazla. Yarım kalıp, madde başlığı veya «Cevap.» yazma.
- law_no hangi kanunu gösteriyorsa onu yaz.

Çıktı: yalnızca JSON. Düz metin, markdown veya kod çiti yok.
"""

EVRAK_CRAFT = """\
Modül: Evrak özeti

Kalem notu yazarsın. Evrakın türünü, hukuki niteliğini ve metindeki tespitleri
nesnel cümlelere çevirirsin. Kanun yolu, süre hesabı veya dilekçe talebi yazmazsın;
bunlar Süreç ve İşlem modüllerindedir. classification ve dates alanlarını olduğu
gibi kullanırsın. Olmayan esas no / mahkeme adı uydurmazsın.

Çıktı: yalnızca JSON.
"""

SUREC_CRAFT = """\
Modül: Süreç anlatımı

Aşama cümlesini hukuki Türkçe ile yazarsın. Süre rakamlarını, son günü ve
kanun yolunu model olarak üretmezsin; motorun verdiği last_day / legal_basis
değerlerini cümleye dökersin. Tetikleyici yoksa süre uydurmaz, hesaplanamadığını söylersin.

Çıktı: yalnızca JSON. sureler.anlatim motor rakamlarıyla çelişmesin.
"""

ISLEM_CRAFT = """\
Modül: İşlem / dilekçe gövdesi

Resmi dilekçe üslubunda yazarsın. Makam, konu, açıklama ve talep birbirine bağlı
olur. Kimlik, T.C. no, esas no yoksa uydurmaz; «[…]» yer tutucu kullanırsın.
related/evidence boşsa hukuki nitelendirmeye madde numarası yazmazsın.

Çıktı: yalnızca JSON.
"""

MODULE_CRAFT = {
    "arastirma": ARASTIRMA_CRAFT,
    "evrak": EVRAK_CRAFT,
    "surec": SUREC_CRAFT,
    "islem": ISLEM_CRAFT,
}

BELGE_CRAFT = """\
Bu bir resmi dilekçe / yazışma kalıbıdır. Hitap, bölüm sırası ve yasaklar
aşağıdaki katalogdan gelir. Her kalıbı kendi evrak düzeninde yaz.

Künye satırları (hüküm, itiraz olunan karar, tutuklama, dava konusu işlem)
mahkeme / esas / karar künyesidir. Kullanıcının günlük konuşmasını bu
satırlara yapıştırma. Anlatıyı olay, esas cevap veya numaralı sebepler
bölümünde resmi dilekçe üslubuna çevir.

Eksik kimlik, tebliğ tarihi veya esas no için isim / T.C. / sayı uydurma;
«[…]» yer tutucu kullan. «EKSİK HUSUSLAR», «eşleşen madde yok», «yazılmadı»
gibi sistem notlarını dilekçe gövdesine koyma. Eksikler arayüzde kalır.

Şikayet ve suç duyurusunda mahkûmiyet, ceza veya hüküm isteme; talep
soruşturma, delil toplama ve kamu davası ile biter. İddianame gibi yazma.
Kaynak listesi boşsa TCK suç maddesi yazma; usul dayanağını katalogdaki
CMK / İYUK maddeleriyle yaz.
"""

USER_SOURCE_RULE = (
    "Aşağıdaki motor çıktısını tek kaynak kabul et. Yeni madde, tarih veya süre uydurma."
)
USER_GAP_RULE = (
    "Eksik alanları doldurmak için kimlik, T.C. no, esas no veya tarih uydurma. "
    "Eksik kimlik/tarih için «[…]» yer tutucu kullan. Ham konuşmayı hüküm veya "
    "karar künyesine yapıştırma; resmi üsluba çevir."
)
USER_NO_SOURCE_RULE = (
    "related/evidence boş: TCK suç maddesi yazma. Usul dayanağını katalogdaki "
    "CMK/İYUK maddeleriyle yaz. Sistem notu («eşleşen madde yok») yazma."
)
USER_EMSAL_RULE = (
    "Emsal listesi varsa yalnızca listedeki künyelere atıf yap. "
    "Yeni esas veya karar numarası uydurma. emsal_atif alanına listedeki ilk künyeyi yaz. "
    "«bu yönde değerlendirme» veya «aynı emsale dayanır» yazma. "
    "Liste boşsa emsal_atif boş bırak; rastgele künye yazma."
)
USER_NO_EMSAL_RULE = (
    "Emsal künyesi yok. Yeni esas veya karar numarası uydurma. emsal_atif boş bırak."
)
PETITION_IDS = {
    "istinaf",
    "itiraz",
    "cevap",
    "sikayet",
    "suc_duyurusu",
    "temyiz",
    "katilma",
    "bireysel_basvuru",
    "idari_dava",
    "tahliye",
    "adli_kontrol_itiraz",
    "temyiz_cevap",
    "sure_uzatim",
    "icra_borca_itiraz",
    "ihtiyac_tahliye",
}

KAYNAK_UYARI = "Bu metin yalnızca yukarıdaki resmi kaynaklara dayanır."


def _json_contract(spec: dict[str, Any]) -> str:
    writing = spec.get("writing") or {}
    parsed = spec.get("parsed") or {}
    must = "\n".join(f"- {item}" for item in writing.get("must") or [])
    must_not = "\n".join(f"- {item}" for item in writing.get("must_not") or [])
    required = parsed.get("required") or []
    return (
        f"Katalog: {spec.get('title')}\n"
        f"Dil: {spec.get('language', 'tr')}\n"
        f"Üslup: {writing.get('tone', '')}\n"
        f"Atıf: {writing.get('citations', '')}\n\n"
        f"Zorunlu:\n{must}\n\n"
        f"Yasak:\n{must_not}\n\n"
        "Yalnızca JSON döndür. Şema alanları:\n"
        f"{json.dumps(parsed.get('properties'), ensure_ascii=False)}\n"
        "Zorunlu anahtarlar: "
        + ", ".join(required)
        + "\n\nÖrnek JSON:\n"
        + json.dumps(spec.get("example") or {}, ensure_ascii=False)
    )


def _belge_contract(spec: dict[str, Any]) -> str:
    writing = spec.get("writing") or {}
    sections = spec.get("sections") or []
    order = "\n".join(f"- {row['id']}: {row['label']}" for row in sections)
    must = "\n".join(f"- {item}" for item in writing.get("must") or [])
    must_not = "\n".join(f"- {item}" for item in writing.get("must_not") or [])
    required = (spec.get("parsed") or {}).get("required") or []
    example = json.dumps(spec.get("example") or {}, ensure_ascii=False)
    return (
        f"Belge: {spec['title']}\n"
        f"Makam: {spec.get('makam', '')}\n"
        f"Dayanak: {', '.join(spec.get('legal_basis') or [])}\n"
        f"Üslup: {writing.get('tone', '')}\n\n"
        f"Bölüm sırası:\n{order}\n\n"
        f"Zorunlu:\n{must}\n\n"
        f"Yasak:\n{must_not}\n\n"
        "Yalnızca JSON döndür. Zorunlu anahtarlar: "
        + ", ".join(required)
        + "\n\nÖrnek JSON:\n"
        + example
    )


def system_prompt(module_id: str) -> str:
    spec = load_format(module_id)
    craft = MODULE_CRAFT.get(module_id, "")
    return f"{IDENTITY}\n\n{craft}\n\n{_json_contract(spec)}".strip()


def belge_system_prompt(belge_id: str) -> str:
    spec = load_belge(belge_id)
    return f"{IDENTITY}\n\n{BELGE_CRAFT}\n\n{_belge_contract(spec)}".strip()


def _law_label(item: dict[str, Any]) -> str:
    law_no = str(item.get("law_no") or "").strip()
    article = str(item.get("article_no") or "").strip()
    title = str(item.get("title") or "").strip()
    short = LAW_SHORT.get(law_no)
    if short and article:
        head = f"{short} m.{article}"
    elif article:
        head = f"m.{article}"
    else:
        head = title or "Kaynak"
        return head
    if title and title not in head:
        return f"{head} — {title}"
    return head


def _source_block(items: list[Any]) -> str:
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        n = item.get("n")
        if n is None:
            continue
        span = str(item.get("span") or item.get("content") or "").strip()
        block = f"[{n}] {_law_label(item)}"
        if span:
            block += f"\n{span}"
        lines.append(block)
    return "\n\n".join(lines)


def _arastirma_user_prompt(compact: dict[str, Any]) -> str:
    query = str(compact.get("query") or compact.get("user_text") or "").strip()
    evidence = list(compact.get("evidence") or [])
    related = list(compact.get("related") or [])
    sources = _source_block(evidence or related)
    parts = [f"Soru:\n{query or '(boş)'}"]
    if sources:
        parts.append("Kaynaklar (yalnızca bunlara dayan; numarayı [n] olarak kullan):\n" + sources)
    else:
        parts.append(
            "Kaynak listesi boş. Madde numarası yazma. Arşivde dayanak bulunamadığını söyle."
        )
    route = compact.get("route")
    if route:
        parts.append(f"Arama rotası: {route}")
    parts.append(
        "JSON üret. ozet en az 5 tam cümlelik Sonuç olsun. gerekce’de 6–10 madde yaz; her madde 2 cümle "
        "ve [n] atsın. Kısa özet yasak; hükmü yorumla, maddeyi yapıştırma."
    )
    return "\n\n".join(parts)


def user_prompt(module_id: str, compact: dict[str, Any]) -> str:
    if module_id == "arastirma":
        return _arastirma_user_prompt(compact)

    extra: list[str] = [USER_SOURCE_RULE]
    if compact.get("gaps"):
        extra.append(USER_GAP_RULE)
    if not (compact.get("related") or compact.get("evidence")):
        extra.append(USER_NO_SOURCE_RULE)
    if compact.get("emsal"):
        extra.append(USER_EMSAL_RULE)
    elif module_id in PETITION_IDS:
        extra.append(USER_NO_EMSAL_RULE)
    return "\n".join(extra) + "\n\n" + json.dumps(compact, ensure_ascii=False, default=str)


def module_messages(module_id: str, compact: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt(module_id)},
        {"role": "user", "content": user_prompt(module_id, compact)},
    ]


def belge_messages(belge_id: str, compact: dict[str, Any]) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": belge_system_prompt(belge_id)},
    ]
    shot = fewshot_for(belge_id)
    if shot:
        messages.append({"role": "user", "content": shot["user"]})
        messages.append({"role": "assistant", "content": shot["assistant"]})
    messages.append({"role": "user", "content": user_prompt(belge_id, compact)})
    return messages


def refuse_answer() -> str:
    return (
        "Bu sorgu hukuk araştırmasına uygun değil.\n\n"
        "HÂKİM yalnızca kanun maddesi, içtihat ve resmi belgelere dayanır. "
        "Spor sonucu, tahmin veya arşivde dayanağı olmayan sorulara cevap verilmez.\n\n"
        "Madde numarası veya hukuki kavramla yeniden deneyin."
    )


def missing_citation_answer(law_no: str, article: str) -> str:
    name = LAW_SHORT.get(law_no, f"Kanun {law_no}")
    return (
        f"Arşivde {name} m.{article} metni yok.\n\n"
        "Sorulan kanunun maddesi bulunmuyorken başka kanunun aynı numaralı maddesi "
        "cevap olarak yazılmaz.\n\n"
        "Bu madde arşive işlenince soru yeniden sorulabilir."
    )

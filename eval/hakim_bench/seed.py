"""Deterministic Phase-0 gold set: 400 Turkish legal questions with article labels."""

from __future__ import annotations

from hakim_bench.dataset import write_dataset
from hakim_bench.schema import GoldQuestion

# law_no, article_no, short name, expected answer
ARTICLES: list[tuple[str, str, str, str]] = [
    ("5237", "1", "kanunun amacı", "TCK m.1 kanunun amacını düzenler."),
    ("5237", "2", "suçta ve cezada kanunilik", "Suçta ve cezada kanunilik TCK m.2'dedir."),
    ("5237", "20", "ceza sorumluluğunun şahsiliği", "Ceza sorumluluğu şahsidir; TCK m.20."),
    ("5237", "21", "kast", "Kast TCK m.21'de düzenlenir."),
    ("5237", "22", "taksir", "Taksir TCK m.22'de düzenlenir."),
    ("5237", "25", "meşru savunma", "Meşru savunma TCK m.25'tedir."),
    ("5237", "26", "hakkın kullanılması", "Hakkın kullanılması ve ilgilinin rızası TCK m.26."),
    ("5237", "29", "haksız tahrik", "Haksız tahrik TCK m.29'dadır."),
    ("5237", "30", "hata", "Hata TCK m.30'da düzenlenir."),
    ("5237", "31", "yaş küçüklüğü", "Yaş küçüklüğü TCK m.31'dedir."),
    ("5237", "32", "akıl hastalığı", "Akıl hastalığı TCK m.32'dedir."),
    ("5237", "35", "suça teşebbüs", "Suça teşebbüs TCK m.35'tedir."),
    ("5237", "36", "gönüllü vazgeçme", "Gönüllü vazgeçme TCK m.36'dadır."),
    ("5237", "37", "faillik", "Faillik TCK m.37'de düzenlenir."),
    ("5237", "38", "azmettirme", "Azmettirme TCK m.38'dedir."),
    ("5237", "39", "yardım etme", "Yardım etme TCK m.39'dadır."),
    ("5237", "43", "zincirleme suç", "Zincirleme suç TCK m.43'tedir."),
    ("5237", "44", "fikri içtima", "Fikri içtima TCK m.44'tedir."),
    ("5237", "50", "adli para cezası", "Adli para cezası TCK m.50'dedir."),
    ("5237", "51", "hapis cezasının ertelenmesi", "Hapis cezasının ertelenmesi TCK m.51'dedir."),
    ("5237", "53", "hak yoksunluğu", "Belli hakları kullanmaktan yoksun bırakılma TCK m.53."),
    ("5237", "61", "cezanın belirlenmesi", "Cezanın belirlenmesi TCK m.61'dedir."),
    ("5237", "62", "takdiri indirim", "Takdiri indirim TCK m.62'dedir."),
    ("5237", "81", "kasten öldürme", "Kasten öldürme TCK m.81'dedir."),
    ("5237", "82", "nitelikli kasten öldürme", "Nitelikli kasten öldürme TCK m.82'dedir."),
    ("5237", "83", "kasten öldürmenin ihmali", "Kasten öldürmenin ihmali davranışla işlenmesi TCK m.83."),
    ("5237", "84", "intihara yönlendirme", "Intihara yönlendirme TCK m.84'tedir."),
    ("5237", "85", "taksirle öldürme", "Taksirle öldürme TCK m.85'tedir."),
    ("5237", "86", "kasten yaralama", "Kasten yaralama TCK m.86'dadır."),
    ("5237", "87", "neticesi sebebiyle ağırlaşmış yaralama", "Neticesi sebebiyle ağırlaşmış yaralama TCK m.87."),
    ("5237", "89", "taksirle yaralama", "Taksirle yaralama TCK m.89'dadır."),
    ("5237", "94", "işkence", "İşkence TCK m.94'tedir."),
    ("5237", "96", "eziyet", "Eziyet TCK m.96'dadır."),
    ("5237", "102", "cinsel saldırı", "Cinsel saldırı TCK m.102'dedir."),
    ("5237", "103", "çocukların cinsel istismarı", "Çocukların cinsel istismarı TCK m.103'tedir."),
    ("5237", "105", "cinsel taciz", "Cinsel taciz TCK m.105'tedir."),
    ("5237", "106", "tehdit", "Tehdit TCK m.106'dadır."),
    ("5237", "107", "şantaj", "Şantaj TCK m.107'dedir."),
    ("5237", "109", "kişiyi hürriyetinden yoksun kılma", "Kişiyi hürriyetinden yoksun kılma TCK m.109."),
    ("5237", "116", "konut dokunulmazlığını ihlal", "Konut dokunulmazlığını ihlal TCK m.116."),
    ("5237", "125", "hakaret", "Hakaret TCK m.125'tedir."),
    ("5237", "134", "özel hayatın gizliliği", "Özel hayatın gizliliğini ihlal TCK m.134."),
    ("5237", "135", "kişisel verilerin kaydedilmesi", "Kişisel verilerin kaydedilmesi TCK m.135."),
    ("5237", "141", "hırsızlık", "Hırsızlık TCK m.141'dedir."),
    ("5237", "142", "nitelikli hırsızlık", "Nitelikli hırsızlık TCK m.142'dedir."),
    ("5237", "148", "yağma", "Yağma TCK m.148'dedir."),
    ("5237", "149", "nitelikli yağma", "Nitelikli yağma TCK m.149'dadır."),
    ("5237", "151", "mala zarar verme", "Mala zarar verme TCK m.151'dedir."),
    ("5237", "155", "güveni kötüye kullanma", "Güveni kötüye kullanma TCK m.155."),
    ("5237", "157", "dolandırıcılık", "Dolandırıcılık TCK m.157'dedir."),
    ("5237", "158", "nitelikli dolandırıcılık", "Nitelikli dolandırıcılık TCK m.158'dedir."),
    ("5237", "163", "karşılıksız yararlanma", "Karşılıksız yararlanma TCK m.163."),
    ("5237", "179", "trafik güvenliğini tehlikeye sokma", "Trafik güvenliğini tehlikeye sokma TCK m.179."),
    ("5237", "180", "trafik güvenliğini taksirle tehlikeye sokma", "Trafik güvenliğini taksirle tehlikeye sokma TCK m.180."),
    ("5237", "188", "uyuşturucu ticareti", "Uyuşturucu veya uyarıcı madde imal ve ticareti TCK m.188."),
    ("5237", "191", "kullanmak için uyuşturucu", "Kullanmak için uyuşturucu satın almak TCK m.191."),
    ("5237", "204", "resmi belgede sahtecilik", "Resmi belgede sahtecilik TCK m.204."),
    ("5237", "206", "özel belgede sahtecilik", "Özel belgede sahtecilik TCK m.206."),
    ("5237", "243", "bilişim sistemine girme", "Bilişim sistemine girme TCK m.243."),
    ("5237", "244", "sistemi engelleme bozma", "Sistemi engelleme, bozma TCK m.244."),
    ("5237", "245", "banka veya kredi kartlarının kötüye kullanılması", "Banka veya kredi kartlarının kötüye kullanılması TCK m.245."),
    ("5237", "257", "görevi kötüye kullanma", "Görevi kötüye kullanma TCK m.257."),
    ("5237", "265", "görevi yaptırmamak için direnme", "Görevi yaptırmamak için direnme TCK m.265."),
    ("5237", "267", "iftira", "İftira TCK m.267'dedir."),
    ("5237", "277", "yargı görevini etkileme", "Yargı görevini yapanı etkilemeye teşebbüs TCK m.277."),
    ("5237", "278", "suç bildirmeme", "Suçu bildirmeme TCK m.278'dedir."),
    ("5237", "282", "suçtan kaynaklanan malvarlığını aklama", "Suçtan kaynaklanan malvarlığı değerlerini aklama TCK m.282."),
    ("5237", "314", "silahlı örgüt", "Silahlı örgüt TCK m.314'tedir."),
    ("5271", "90", "yakalama", "Yakalama ve yakalanan kişi hakkında işlemler CMK m.90."),
    ("5271", "91", "gözaltı", "Gözaltı CMK m.91'dedir."),
    ("5271", "100", "tutuklama nedenleri", "Tutuklama nedenleri CMK m.100'dedir."),
    ("5271", "101", "tutuklama kararı", "Tutuklama kararı CMK m.101'dedir."),
    ("5271", "109", "adli kontrol", "Adli kontrol CMK m.109'dadır."),
    ("5271", "116", "arama", "Arama CMK m.116'dadır."),
    ("5271", "147", "ifade ve sorgu tarzı", "İfade ve sorgunun tarzı CMK m.147'dedir."),
    ("5271", "148", "yasak usullerle ifade", "Yasak usullerle ifade alma CMK m.148'dedir."),
    ("5271", "170", "iddianame", "İddianamenin düzenlenmesi CMK m.170."),
    ("5271", "174", "iddianamenin iadesi", "İddianamenin iadesi CMK m.174'tedir."),
    ("5271", "223", "duruşma sonunda verilecek karar", "Beraat, mahkûmiyet ve diğer kararlar CMK m.223."),
    ("5271", "231", "hükmün açıklanmasının geri bırakılması", "Hükmün açıklanmasının geri bırakılması CMK m.231."),
    ("5271", "272", "istinaf", "İstinaf CMK m.272'dedir."),
    ("5271", "286", "temyiz", "Temyiz CMK m.286'dadır."),
    ("2577", "2", "idari dava türleri", "İdari dava türleri İYUK m.2'dedir."),
    ("2577", "7", "dava açma süresi", "İdari yargıda dava açma süresi İYUK m.7'dedir."),
    ("2577", "10", "idari makamların sükutu", "İdari makamların sükutu İYUK m.10'dadır."),
    ("2577", "11", "üst makamlara başvurma", "Üst makamlara başvurma İYUK m.11'dedir."),
    ("2577", "27", "yürütmenin durdurulması", "Yürütmenin durdurulması İYUK m.27'dedir."),
    ("7201", "21", "tebliğ imkânsızlığı", "Tebliğ imkânsızlığı ve tebellüğden imtina Tebligat K. m.21."),
]

def _idx(law_no: str, article_no: str) -> int:
    for i, row in enumerate(ARTICLES):
        if row[0] == law_no and row[1] == article_no:
            return i
    raise KeyError((law_no, article_no))


PAIRS: list[tuple[int, int]] = [
    (_idx("5237", "81"), _idx("5237", "82")),
    (_idx("5237", "86"), _idx("5237", "87")),
    (_idx("5237", "141"), _idx("5237", "142")),
    (_idx("5237", "148"), _idx("5237", "149")),
    (_idx("5237", "157"), _idx("5237", "158")),
    (_idx("5237", "179"), _idx("5237", "180")),
    (_idx("5237", "188"), _idx("5237", "191")),
    (_idx("5237", "21"), _idx("5237", "22")),
    (_idx("5237", "37"), _idx("5237", "38")),
    (_idx("5271", "90"), _idx("5271", "91")),
    (_idx("5271", "100"), _idx("5271", "101")),
    (_idx("5271", "272"), _idx("5271", "286")),
    (_idx("5237", "86"), _idx("5237", "89")),
    (_idx("5237", "81"), _idx("5237", "85")),
    (_idx("5237", "204"), _idx("5237", "206")),
    (_idx("5237", "35"), _idx("5237", "36")),
    (_idx("5237", "102"), _idx("5237", "105")),
    (_idx("5271", "147"), _idx("5271", "148")),
    (_idx("5271", "170"), _idx("5271", "174")),
    (_idx("2577", "2"), _idx("2577", "27")),
]

GROUPS: list[tuple[list[int], str, str]] = [
    ([_idx("5237", "81"), _idx("5237", "82"), _idx("5237", "85")], "öldürme suçları", "Kasten öldürme TCK 81, nitelikli 82, taksirle 85."),
    ([_idx("5237", "86"), _idx("5237", "87"), _idx("5237", "89")], "yaralama suçları", "Kasten yaralama TCK 86, ağırlaşmış 87, taksirle 89."),
    ([_idx("5237", "141"), _idx("5237", "142"), _idx("5237", "148"), _idx("5237", "149")], "malvarlığına karşı zorla alma", "Hırsızlık 141-142, yağma 148-149."),
    ([_idx("5237", "157"), _idx("5237", "158")], "dolandırıcılık türleri", "Basit dolandırıcılık TCK 157, nitelikli 158."),
    ([_idx("5271", "90"), _idx("5271", "91"), _idx("5271", "100")], "özgürlüğü kısıtlayan koruma tedbirleri", "Yakalama 90, gözaltı 91, tutuklama 100."),
    ([_idx("5271", "272"), _idx("5271", "286")], "ceza kanun yolları", "İstinaf CMK 272, temyiz CMK 286."),
    ([_idx("5237", "21"), _idx("5237", "22")], "manevi unsur", "Kast TCK 21, taksir TCK 22."),
    ([_idx("5237", "37"), _idx("5237", "38"), _idx("5237", "39")], "iştirak şekilleri", "Faillik 37, azmettirme 38, yardım etme 39."),
    ([_idx("5237", "179"), _idx("5237", "180")], "trafik güvenliği", "Kasten TCK 179, taksirle TCK 180."),
    ([_idx("2577", "2"), _idx("2577", "27")], "idari yargı başvurusu", "Dava türleri İYUK 2, yürütmenin durdurulması İYUK 27."),
]

UNANSWERABLE = [
    "X Teknoloji A.Ş. ne zaman kuruldu?",
    "Acme Holding'in 2024 cirosu nedir?",
    "iPhone 17 Türkiye'de kaç TL?",
    "Galatasaray son derbiyi kaç kaç yendi?",
    "Bitcoin yarın kaç dolar olur?",
    "Ankara'da yarın hava kaç derece?",
    "Starbucks'ın kurucusu kimdir?",
    "Tesla Cybertruck Türkiye'de satılıyor mu?",
    "Netflix 2026 abonelik ücreti nedir?",
    "Efe Yazılım Ltd. vergi numarası nedir?",
    "Planetary Corp iade süresi kaç gündür?",
    "BlueMart'ın KVKK politikası nedir?",
    "2025 Eurovision birincisi kim oldu?",
    "ChatGPT-6 ne zaman çıkacak?",
    "İstanbul Havalimanı otopark ücreti nedir?",
    "Migros sadakat puanı nasıl kullanılır?",
    "THY mil programı nasıl iptal edilir?",
    "Trendyol Express kurye maaşı nedir?",
    "Apple Park'ın adresi nedir?",
    "Amazon Prime Video Türkiye'de hangi dizileri kaldırdı?",
    "Köfteci Yusuf'un gizli tarifi nedir?",
    "FB şirketinin kurucusu hangi yılda doğdu?",
    "Nintendo Switch 2 Türkiye'de resmi fiyatı nedir?",
    "OpenAI'nin 2023 kârı kaç dolardır?",
    "SpaceX Mars koloni tarihi nedir?",
    "IKEA Malm dolabın vida sayısı nedir?",
    "Zara 2026 ilkbahar koleksiyon rengi nedir?",
    "Kahve Dünyası franchise bedeli nedir?",
    "Beko buzdolabı arıza kodu E3 ne demek?",
    "Getir sürücü prim oranı nedir?",
    "Yemeksepeti restoran komisyonu yüzde kaç?",
    "Hepsiburada satıcı puanı nasıl silinir?",
    "Discord Nitro öğrenci indirimi var mı?",
    "Spotify Wrapped 2027 tarihi nedir?",
    "Twitch Türkiye'de vergi kesintisi oranı nedir?",
    "Binance TR kayıp cüzdan nasıl bulunur?",
    "Dolar/TL yarınki kapanışı nedir?",
    "Togg T10X stok adedi nedir?",
    "Roketsan iç yönerge madde 12 nedir?",
    "Sahte Kanun No 99999 madde 1 nedir?",
]


def _code(law_no: str) -> str:
    return {"5237": "TCK", "5271": "CMK", "2577": "İYUK", "7201": "Tebligat K."}.get(law_no, law_no)


def _article_ref(idx: int) -> dict[str, str]:
    law_no, article_no, _name, _expected = ARTICLES[idx]
    return {"law_no": law_no, "article_no": article_no}


def _chunk(idx: int) -> str:
    law_no, article_no, *_ = ARTICLES[idx]
    return f"law:{law_no}:article:{article_no}:v1"


def _doc(idx: int) -> str:
    return f"law:{ARTICLES[idx][0]}"


def _make(
    qid: str,
    question: str,
    expected: str,
    indices: list[int],
    qtype: str,
    *,
    difficulty: str = "easy",
    answerable: bool = True,
) -> GoldQuestion:
    return GoldQuestion.from_dict(
        {
            "id": qid,
            "question": question,
            "expected_answer": expected,
            "relevant_documents": [_doc(i) for i in indices] if answerable else [],
            "relevant_chunks": [_chunk(i) for i in indices] if answerable else [],
            "relevant_articles": [_article_ref(i) for i in indices] if answerable else [],
            "question_type": qtype,
            "difficulty": difficulty,
            "answerable": answerable,
        }
    )


def _noisy(text: str) -> str:
    table = str.maketrans("ıçğüşöİÇĞÜŞÖ", "icgusoICGUSO")
    dropped = text.translate(table).replace("  ", " ")
    if len(dropped) > 12:
        dropped = dropped[:6] + dropped[7:]
    return dropped


def build_rows() -> list[GoldQuestion]:
    rows: list[GoldQuestion] = []
    for i, (law_no, article_no, name, expected) in enumerate(ARTICLES[:80]):
        rows.append(
            _make(
                f"f{i+1:03d}",
                f"{name} hangi maddede düzenlenir?",
                expected,
                [i],
                "factual",
            )
        )
    for i, (law_no, article_no, name, expected) in enumerate(ARTICLES[:60]):
        rows.append(
            _make(
                f"s{i+1:03d}",
                f"{name} fiilinin cezai dayanağı hangi hükümdür?",
                expected,
                [i],
                "semantic",
                difficulty="medium",
            )
        )
    for i, (law_no, article_no, name, expected) in enumerate(ARTICLES[:40]):
        rows.append(
            _make(
                f"k{i+1:03d}",
                f"{_code(law_no)} {article_no} {name}",
                expected,
                [i],
                "keyword",
            )
        )
    for n, (a, b) in enumerate(PAIRS, start=1):
        na = ARTICLES[a][2]
        nb = ARTICLES[b][2]
        expected = f"{ARTICLES[a][3]} {ARTICLES[b][3]}"
        rows.append(
            _make(
                f"c{n:03d}",
                f"{na} ile {nb} arasındaki fark nedir?",
                expected,
                [a, b],
                "comparison",
                difficulty="medium",
            )
        )
        rows.append(
            _make(
                f"c{n+20:03d}",
                f"{_code(ARTICLES[a][0])} m.{ARTICLES[a][1]} ve m.{ARTICLES[b][1]} nasıl ayrılır?",
                expected,
                [a, b],
                "comparison",
                difficulty="medium",
            )
        )
    hop_n = 0
    templates = (
        "{na} temel hükümde, nitelikli/bağlantılı hali hangi maddede tamamlanır?",
        "{na} ile {nb} birlikte okunursa hangi iki madde gerekir?",
        "{na} uygulandıktan sonra {nb} nasıl devreye girer?",
    )
    for a, b in PAIRS:
        for tmpl in templates:
            hop_n += 1
            if hop_n > 60:
                break
            expected = f"{ARTICLES[a][3]} {ARTICLES[b][3]}"
            rows.append(
                _make(
                    f"m{hop_n:03d}",
                    tmpl.format(na=ARTICLES[a][2], nb=ARTICLES[b][2]),
                    expected,
                    [a, b],
                    "multi_hop",
                    difficulty="hard",
                )
            )
        if hop_n > 60:
            break
    while hop_n < 60:
        a, b = PAIRS[hop_n % len(PAIRS)]
        hop_n += 1
        rows.append(
            _make(
                f"m{hop_n:03d}",
                f"{ARTICLES[a][2]} bilgisi ile {ARTICLES[b][2]} bilgisi birleştirilirse sonuç nedir?",
                f"{ARTICLES[a][3]} {ARTICLES[b][3]}",
                [a, b],
                "multi_hop",
                difficulty="hard",
            )
        )
    agg_n = 0
    for idxs, label, expected in GROUPS:
        for tmpl in (
            f"{label} hangileridir?",
            f"2025 uygulamasında {label} hangi maddelerde toplanır?",
            f"{label} listesini maddeleriyle ver.",
            f"İlgili {label} hükümlerinin tamamı nelerdir?",
        ):
            agg_n += 1
            rows.append(
                _make(
                    f"a{agg_n:03d}",
                    tmpl,
                    expected,
                    idxs,
                    "aggregation",
                    difficulty="hard",
                )
            )
    for i, (law_no, article_no, name, expected) in enumerate(ARTICLES[:20]):
        rows.append(
            _make(
                f"b{i+1:03d}",
                name.split()[0],
                expected,
                [i],
                "ambiguous",
                difficulty="medium",
            )
        )
    for i, (law_no, article_no, name, expected) in enumerate(ARTICLES[:20]):
        rows.append(
            _make(
                f"t{i+1:03d}",
                _noisy(f"{name} hangi maddede düzenlenir?"),
                expected,
                [i],
                "typo",
            )
        )
    for i, question in enumerate(UNANSWERABLE, start=1):
        rows.append(
            _make(
                f"u{i:03d}",
                question,
                "Bu bilgi mevcut kaynaklarda bulunmuyor.",
                [],
                "unanswerable",
                answerable=False,
            )
        )
    return rows


def main() -> None:
    rows = build_rows()
    write_dataset(rows)
    print(f"wrote {len(rows)} questions")


if __name__ == "__main__":
    main()

export const KAMU_SAMPLES: Record<string, string> = {
  ust_yazi: `T.C.
İÇİŞLERİ BAKANLIĞI
Evrak Kayıt ve Havale Şefliği
Sayı : E-12345678-804.02-42
Konu : Gelen evrakın ilgili birime havalesi

İLGİLİ BİRİM MÜDÜRLÜĞÜNE
İlgi : 18.08.2026 tarihli ve E-99887766-804.02-15 sayılı yazı.

İlgi yazı incelenmiş olup gereği için havalesi uygun görülmüştür.`,
  bilgi_yazisi: `T.C.
İÇİŞLERİ BAKANLIĞI
GENELGE
2026/12 sayılı genelge ile taşra teşkilatına duyurulur.`,
  olur: `T.C.
STRATEJİ GELİŞTİRME BAŞKANLIĞI
Olura arz ederim.
Konu: Orta Vadeli Program Hazırlanması`,
  cevap_yazisi: `T.C.
HUKUK VE MEVZUAT GENEL MÜDÜRLÜĞÜ
İlgi yazıya cevaben aşağıdaki bilgiler sunulmuştur.
İlgi : 18.08.2026 tarihli ve E-99887766-804.02-15 sayılı yazınız.`,
  genelge: `T.C.
İÇİŞLERİ BAKANLIĞI
GENELGE
2026/12 sayılı genelge ile taşra teşkilatına duyurulur.`,
  tutanak: `T.C.
İLGİLİ BİRİM
İşbu tutanak, toplantıya ilişkin olarak düzenlenmiştir.`,
  rapor: `T.C.
İLGİLİ BİRİM
İnceleme Raporu
İşbu rapor, faaliyet değerlendirmesi amacıyla hazırlanmıştır.`,
};

export const KAMU_FALLBACK = [
  { id: "ust_yazi", title: "Üst yazı / havale", when: "Gelen evrak havalesi", makam: "Evrak kayıt", family: "kamu", legal_basis: [], sections: [] },
  { id: "bilgi_yazisi", title: "Bilgi yazısı", when: "Duyuru / bilgilendirme", makam: "Dağıtım yerleri", family: "kamu", legal_basis: [], sections: [] },
  { id: "olur", title: "Olur", when: "Makama arz", makam: "Üst makam", family: "kamu", legal_basis: [], sections: [] },
  { id: "cevap_yazisi", title: "Cevap yazısı", when: "İlgi yazıya cevap", makam: "Cevap veren birim", family: "kamu", legal_basis: [], sections: [] },
];

export const SABLON_BLOCK_LABELS: Record<string, string> = {
  baslik: "T.C. · Kurum · Birim",
  sayi_konu: "Sayı / Konu",
  muhatap: "Muhatap",
  ilgi: "İlgi",
  metin: "Metin",
  imza: "İmza",
  olur: "Olur",
  ek: "Ek",
  dagitim: "Dağıtım",
  onay: "Onay notu",
  acele: "Acele",
};

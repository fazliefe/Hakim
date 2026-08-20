-- Official open-legal sources from the TEKNOFEST catalog.
SET search_path TO hakim, public;

INSERT INTO sources (id, provider, official, authority, base_url) VALUES
    ('source:emsal.uyap.gov.tr', 'emsal.uyap.gov.tr', true, 'official', 'https://emsal.uyap.gov.tr'),
    ('source:uyusmazlik.gov.tr', 'uyusmazlik.gov.tr', true, 'official', 'https://kararlar.uyusmazlik.gov.tr'),
    ('source:resmigazete.gov.tr', 'resmigazete.gov.tr', true, 'official', 'https://www.resmigazete.gov.tr'),
    ('source:tbmm.gov.tr', 'tbmm.gov.tr', true, 'official', 'https://www.tbmm.gov.tr/tutanaklar'),
    ('source:rekabet.gov.tr', 'rekabet.gov.tr', true, 'official', 'https://www.rekabet.gov.tr/tr/Kararlar'),
    ('source:kvkk.gov.tr', 'kvkk.gov.tr', true, 'official', 'https://www.kvkk.gov.tr/Icerik/5419/kurul-kararlari'),
    ('source:sayistay.gov.tr', 'sayistay.gov.tr', true, 'official', 'https://www.sayistay.gov.tr'),
    ('source:hf:mevzuat-gov-dataset', 'huggingface.co', false, 'secondary', 'https://huggingface.co/datasets/muhammetakkurt/mevzuat-gov-dataset'),
    ('source:hf:turkish-law-documents-700k', 'huggingface.co', false, 'secondary', 'https://huggingface.co/datasets/erdem-erdem/Turkish-Law-Documents-700k-clustered'),
    ('source:hf:turkish-law-bge-m3', 'huggingface.co', false, 'secondary', 'https://huggingface.co/datasets/muhamparlak/turkish-law-bge-m3-embeddings'),
    ('source:hf:turkish-legislation-corpus', 'huggingface.co', false, 'secondary', 'https://huggingface.co/datasets/hasankursun/turkish-legislation-corpus'),
    ('source:hf:legal-nli-tr', 'huggingface.co', false, 'secondary', 'https://huggingface.co/datasets/Turkish-NLI/legal_nli_TR_V1'),
    ('source:hf:turkish-law-qa', 'huggingface.co', false, 'secondary', 'https://huggingface.co/datasets/OrionCAF/turkish_law_qa_dataset')
ON CONFLICT (id) DO UPDATE SET
    provider = EXCLUDED.provider,
    official = EXCLUDED.official,
    authority = EXCLUDED.authority,
    base_url = EXCLUDED.base_url;

INSERT INTO courts (id, slug, name) VALUES
    ('court:yerelhukuk', 'yerelhukuk', 'Yerel Hukuk Mahkemesi'),
    ('court:istinafhukuk', 'istinafhukuk', 'Bölge Adliye Mahkemesi'),
    ('court:kyb', 'kyb', 'Kanun Yararına Bozma'),
    ('court:uyusmazlik', 'uyusmazlik', 'Uyuşmazlık Mahkemesi'),
    ('court:rekabet', 'rekabet', 'Rekabet Kurumu'),
    ('court:kvkk', 'kvkk', 'Kişisel Verileri Koruma Kurulu'),
    ('court:sayistay', 'sayistay', 'Sayıştay'),
    ('court:resmi_gazete', 'resmi_gazete', 'Resmî Gazete'),
    ('court:tbmm', 'tbmm', 'Türkiye Büyük Millet Meclisi')
ON CONFLICT (id) DO UPDATE SET
    slug = EXCLUDED.slug,
    name = EXCLUDED.name;

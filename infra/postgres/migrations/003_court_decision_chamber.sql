-- Yargıtay/Danıştay kararlarında daire (chamber) bilgisini ayrı bir kolonda
-- tut — önceden sadece `title` string'ine gömülüyordu, daire bazlı
-- filtre/analiz imkanı yoktu.
SET search_path TO hakim, public;

ALTER TABLE court_decisions ADD COLUMN IF NOT EXISTS chamber text;
CREATE INDEX IF NOT EXISTS court_decisions_chamber_idx ON court_decisions (chamber);

-- Toplu emsal karar kaynağı (hamzabagirsakci/turkish-court-decisions, CC0).
-- Mirror olduğu için authority='secondary' — bedesten.adalet.gov.tr ile
-- byte-byte aynılığı indirmeden doğrulanamıyor.
INSERT INTO sources (id, provider, official, authority, base_url) VALUES
    ('source:hf:turkish-court-decisions', 'huggingface.co', false, 'secondary',
     'https://huggingface.co/datasets/hamzabagirsakci/turkish-court-decisions')
ON CONFLICT (id) DO UPDATE SET
    provider = EXCLUDED.provider,
    official = EXCLUDED.official,
    authority = EXCLUDED.authority,
    base_url = EXCLUDED.base_url;

-- HAKİM Legal Data Model v1
-- PostgreSQL is the source of truth. Elasticsearch and Neo4j are derived stores.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE SCHEMA IF NOT EXISTS hakim;
SET search_path TO hakim, public;

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------

CREATE TYPE document_type AS ENUM (
    'law',
    'decree_law',
    'presidential_decree',
    'presidential_decision',
    'presidential_regulation',
    'regulation',
    'bylaw',
    'circular',
    'communique',
    'court_decision',
    'other'
);

CREATE TYPE authority_level AS ENUM ('official', 'secondary', 'user');

CREATE TYPE provenance_kind AS ENUM (
    'official_text',
    'llm_extracted',
    'human_annotated',
    'inferred'
);

CREATE TYPE relation_type AS ENUM (
    'HAS_ARTICLE',
    'HAS_PARAGRAPH',
    'REFERENCES',
    'AMENDED_BY',
    'REPEALED_BY',
    'INTERPRETED_BY',
    'CITES',
    'ISSUED_BY',
    'DISCUSSES',
    'BASED_ON',
    'HAS_REMEDY',
    'HAS_DEADLINE'
);

CREATE TYPE duration_unit AS ENUM ('day', 'week', 'month', 'year');

CREATE TYPE calendar_type AS ENUM ('civil', 'administrative', 'criminal');

CREATE TYPE ingestion_status AS ENUM ('success', 'partial', 'failed');

-- ---------------------------------------------------------------------------
-- Tenancy / identity (security from day one)
-- ---------------------------------------------------------------------------

CREATE TABLE tenants (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            citext NOT NULL UNIQUE,
    name            text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    email           citext NOT NULL,
    display_name    text NOT NULL,
    role            text NOT NULL DEFAULT 'researcher' CHECK (role IN ('admin', 'researcher', 'reviewer', 'readonly')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email)
);

-- ---------------------------------------------------------------------------
-- Sources and raw provenance
-- ---------------------------------------------------------------------------

CREATE TABLE sources (
    id              text PRIMARY KEY,
    provider        text NOT NULL,
    official        boolean NOT NULL,
    authority       authority_level NOT NULL,
    base_url        text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK ((official AND authority = 'official') OR (NOT official AND authority <> 'official'))
);

CREATE TABLE ingestion_runs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id           text NOT NULL REFERENCES sources (id),
    document_id         text,
    status              ingestion_status NOT NULL,
    articles_found      integer NOT NULL DEFAULT 0 CHECK (articles_found >= 0),
    warnings            jsonb NOT NULL DEFAULT '[]'::jsonb,
    content_changed     boolean NOT NULL DEFAULT false,
    parser_version      text,
    raw_snapshot_uri    text,
    started_at          timestamptz NOT NULL DEFAULT now(),
    finished_at         timestamptz
);

-- ---------------------------------------------------------------------------
-- Legal documents (identity) and versions (temporal)
-- ---------------------------------------------------------------------------

CREATE TABLE legal_documents (
    id              text PRIMARY KEY,
    document_type   document_type NOT NULL,
    number          text,
    title           text NOT NULL,
    source_id       text NOT NULL REFERENCES sources (id),
    publication_date date,
    gazette_number  text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX legal_documents_number_idx ON legal_documents (document_type, number);

CREATE TABLE document_versions (
    id                  text PRIMARY KEY,
    document_id         text NOT NULL REFERENCES legal_documents (id) ON DELETE CASCADE,
    version             integer NOT NULL CHECK (version >= 1),
    valid_from          timestamptz NOT NULL,
    valid_until         timestamptz,
    content_hash        text NOT NULL,
    raw_snapshot_uri    text,
    UNIQUE (document_id, version),
    CHECK (valid_until IS NULL OR valid_until > valid_from),
    EXCLUDE USING gist (
        document_id WITH =,
        tstzrange(valid_from, valid_until, '[)') WITH &&
    )
);

-- ---------------------------------------------------------------------------
-- Articles and article versions
-- ---------------------------------------------------------------------------

CREATE TABLE articles (
    id              text PRIMARY KEY,
    document_id     text NOT NULL REFERENCES legal_documents (id) ON DELETE CASCADE,
    article_no      text NOT NULL,
    UNIQUE (document_id, article_no)
);

CREATE TABLE article_versions (
    id                      text PRIMARY KEY,
    article_id              text NOT NULL REFERENCES articles (id) ON DELETE CASCADE,
    document_version_id     text REFERENCES document_versions (id) ON DELETE SET NULL,
    version                 integer NOT NULL CHECK (version >= 1),
    title                   text,
    body                    text NOT NULL,
    valid_from              timestamptz NOT NULL,
    valid_until             timestamptz,
    UNIQUE (article_id, version),
    CHECK (valid_until IS NULL OR valid_until > valid_from),
    EXCLUDE USING gist (
        article_id WITH =,
        tstzrange(valid_from, valid_until, '[)') WITH &&
    )
);

CREATE INDEX article_versions_body_trgm_idx ON article_versions USING gin (body gin_trgm_ops);
CREATE INDEX article_versions_valid_from_idx ON article_versions (article_id, valid_from);

CREATE TABLE paragraphs (
    id                  text PRIMARY KEY,
    article_version_id  text NOT NULL REFERENCES article_versions (id) ON DELETE CASCADE,
    paragraph_no        text NOT NULL,
    body                text NOT NULL,
    order_index         integer NOT NULL CHECK (order_index >= 0),
    UNIQUE (article_version_id, paragraph_no)
);

-- ---------------------------------------------------------------------------
-- Courts, decisions, concepts, procedure engine inputs
-- ---------------------------------------------------------------------------

CREATE TABLE courts (
    id          text PRIMARY KEY,
    slug        text NOT NULL UNIQUE,
    name        text NOT NULL,
    parent_id   text REFERENCES courts (id)
);

CREATE TABLE court_decisions (
    id              text PRIMARY KEY,
    court_id        text NOT NULL REFERENCES courts (id),
    year            integer NOT NULL,
    docket_no       text NOT NULL,
    decision_no     text NOT NULL,
    decision_date   date,
    title           text NOT NULL,
    body            text,
    source_id       text NOT NULL REFERENCES sources (id),
    content_hash    text,
    UNIQUE (court_id, year, docket_no, decision_no)
);

CREATE TABLE institutions (
    id      text PRIMARY KEY,
    name    text NOT NULL,
    kind    text
);

CREATE TABLE legal_concepts (
    id      text PRIMARY KEY,
    label   text NOT NULL,
    domain  text
);

CREATE TABLE procedures (
    id      text PRIMARY KEY,
    name    text NOT NULL,
    domain  text
);

CREATE TABLE remedies (
    id              text PRIMARY KEY,
    name            text NOT NULL,
    procedure_id    text REFERENCES procedures (id)
);

CREATE TABLE deadline_rules (
    id              text PRIMARY KEY,
    procedure       text NOT NULL,
    trigger         text NOT NULL,
    duration        integer NOT NULL CHECK (duration > 0),
    unit            duration_unit NOT NULL,
    calendar_type   calendar_type NOT NULL,
    legal_basis     text[] NOT NULL,
    provenance      provenance_kind NOT NULL DEFAULT 'official_text'
);

-- ---------------------------------------------------------------------------
-- Graph edges live here first; Neo4j is a projection
-- ---------------------------------------------------------------------------

CREATE TABLE legal_relations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_id         text NOT NULL,
    from_type       text NOT NULL,
    to_id           text NOT NULL,
    to_type         text NOT NULL,
    relation_type   relation_type NOT NULL,
    provenance      provenance_kind NOT NULL,
    confidence      numeric(4, 3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (provenance = 'official_text' AND confidence = 1)
        OR (provenance = 'llm_extracted' AND confidence < 1)
        OR (provenance IN ('human_annotated', 'inferred'))
    ),
    UNIQUE (from_id, to_id, relation_type, provenance)
);

CREATE INDEX legal_relations_from_idx ON legal_relations (from_id, relation_type);
CREATE INDEX legal_relations_to_idx ON legal_relations (to_id, relation_type);

-- ---------------------------------------------------------------------------
-- Tenant work product (Evrak / cases)
-- ---------------------------------------------------------------------------

CREATE TABLE cases (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    title       text NOT NULL,
    status      text NOT NULL DEFAULT 'open',
    created_by  uuid REFERENCES users (id),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_documents (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    owner_user_id   uuid NOT NULL REFERENCES users (id),
    case_id         uuid REFERENCES cases (id) ON DELETE SET NULL,
    filename        text NOT NULL,
    content_type    text NOT NULL,
    storage_uri     text NOT NULL,
    sha256          text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX user_documents_tenant_idx ON user_documents (tenant_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Audit (do not store document body / PII payload)
-- ---------------------------------------------------------------------------

CREATE TABLE audit_logs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid REFERENCES tenants (id) ON DELETE SET NULL,
    actor_user_id   uuid REFERENCES users (id) ON DELETE SET NULL,
    action          text NOT NULL,
    entity_type     text NOT NULL,
    entity_id       text NOT NULL,
    metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX audit_logs_tenant_idx ON audit_logs (tenant_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Temporal lookup helpers
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION article_version_at(p_article_id text, p_at timestamptz)
RETURNS article_versions
LANGUAGE sql
STABLE
AS $$
    SELECT *
    FROM article_versions
    WHERE article_id = p_article_id
      AND valid_from <= p_at
      AND (valid_until IS NULL OR p_at < valid_until)
    LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION document_version_at(p_document_id text, p_at timestamptz)
RETURNS document_versions
LANGUAGE sql
STABLE
AS $$
    SELECT *
    FROM document_versions
    WHERE document_id = p_document_id
      AND valid_from <= p_at
      AND (valid_until IS NULL OR p_at < valid_until)
    LIMIT 1;
$$;

-- ---------------------------------------------------------------------------
-- Seed official sources and courts used by Alpha
-- ---------------------------------------------------------------------------

INSERT INTO sources (id, provider, official, authority, base_url) VALUES
    ('source:mevzuat.gov.tr', 'mevzuat.gov.tr', true, 'official', 'https://www.mevzuat.gov.tr'),
    ('source:yargitay.gov.tr', 'yargitay.gov.tr', true, 'official', 'https://karararama.yargitay.gov.tr'),
    ('source:danistay.gov.tr', 'danistay.gov.tr', true, 'official', 'https://karararama.danistay.gov.tr'),
    ('source:anayasa.gov.tr', 'anayasa.gov.tr', true, 'official', 'https://kararlarbilgibankasi.anayasa.gov.tr');

INSERT INTO courts (id, slug, name) VALUES
    ('court:yargitay', 'yargitay', 'Yargıtay'),
    ('court:danistay', 'danistay', 'Danıştay'),
    ('court:aym', 'aym', 'Anayasa Mahkemesi');

ALTER DATABASE hakim SET search_path TO hakim, public;

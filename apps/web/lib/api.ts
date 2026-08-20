export type Evidence = {
  n: number;
  chunk_id: string;
  document_id?: string | null;
  law_no?: string | null;
  article_no?: string | null;
  title?: string | null;
  content: string;
  authority?: string | null;
  bm25_rank?: number | null;
  semantic_rank?: number | null;
  rrf_rank: number;
  rrf_score: number;
  retrievers: string[];
  graph_neighbors: Array<{
    id?: string;
    article_no?: string;
    title?: string | null;
    direction?: string;
    kind?: string;
  }>;
  used_in_answer: boolean;
};

export type TraceNode = {
  id: string;
  label: string;
  kind: string;
  meta: Record<string, unknown>;
};

export type TraceEdge = {
  source: string;
  target: string;
  label: string;
};

export type ResearchResponse = {
  query: string;
  answer: string;
  route: string;
  evidence: Evidence[];
  trace_nodes: TraceNode[];
  trace_edges: TraceEdge[];
  writer?: string;
  writer_error?: string | null;
  reasoning?: ReasoningTrace;
};

export type SystemStatus = {
  status: string;
  service: string;
  ready: boolean;
  checks: {
    api: string;
    elasticsearch: string;
    neo4j: string;
    postgres: string;
    yazim?: string;
    ollama?: string;
    langfuse?: string;
    langgraph?: string;
  };
  etiketler?: Record<string, string>;
};

export function writerLabel(writer?: string | null): string {
  if (writer === "api") return "API";
  if (writer === "ollama") return "Ollama";
  if (writer === "refuse") return "Cevap yok";
  return "Kaynaklı gerekçe";
}

export function writerIsLlm(writer?: string | null): boolean {
  return writer === "api" || writer === "ollama";
}

const API_BASE =
  process.env.NEXT_PUBLIC_HAKIM_API_URL ??
  (typeof window !== "undefined" ? "http://127.0.0.1:8000" : "/api-hakim");

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, { ...init, cache: init?.cache ?? "no-store" });
}

export async function getSystemStatus(): Promise<SystemStatus> {
  const response = await apiFetch("/v1/durum", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Sistem durumu alınamadı");
  }
  return response.json();
}

export type GraphDump = {
  nodes: Array<{
    id: string;
    label: string;
    kind: string;
    title?: string | null;
    article_no?: string | null;
  }>;
  edges: Array<{ source: string; target: string; label: string }>;
  counts: Record<string, number>;
  detail?: string;
};

export async function getGraph(): Promise<GraphDump> {
  const response = await apiFetch("/v1/graf", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Graf alınamadı");
  }
  return response.json();
}

export type LegalSource = {
  id?: string;
  name?: string;
  url?: string;
  repo?: string;
  status?: string;
  ingest?: string;
  documents?: number;
  authority?: string;
  note?: string;
};

export type SourceCatalog = {
  official: LegalSource[];
  mcp: LegalSource[];
  huggingface: LegalSource[];
  counts: Record<string, number>;
};

export async function getLegalSources(): Promise<SourceCatalog> {
  const response = await apiFetch("/v1/kaynaklar", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Kaynak listesi alınamadı");
  }
  return response.json();
}

export async function runResearch(query: string, lawNo = "5237"): Promise<ResearchResponse> {
  const response = await apiFetch("/v1/arastirma", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, law_no: lawNo }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Araştırma isteği başarısız");
  }
  return response.json();
}

export type Finding = {
  label: string;
  value: string;
  confidence: number;
  evidence: string;
  source?: string | null;
};

export type DeadlineOut = {
  rule_id: string;
  name: string;
  trigger: string | null;
  duration: number;
  unit: string;
  calendar: string;
  last_day: string | null;
  legal_basis: string[];
  missing: string | null;
};

export type ReasoningHop = {
  n: number;
  id: string;
  title?: string;
  question?: string;
  answer?: string;
  why?: string | null;
  state: string;
  depends_on?: string | null;
};

export type ReasoningTrace = {
  status: string;
  hops: ReasoningHop[];
  conclusion?: string;
};

export type PetitionSection = {
  id: string;
  label: string;
  text: string;
  kind?: string;
};

export type PetitionMeta = {
  label: string;
  value: string;
};

export type PetitionView = {
  id?: string;
  title?: string;
  family?: string;
  layout?: string;
  makam?: string;
  hitap?: string;
  via?: string;
  subtitle?: string;
  konu?: string;
  meta?: PetitionMeta[];
  sections?: PetitionSection[];
  closing?: string;
  signature?: { role?: string; name?: string } | null;
  onay_notu?: string;
};

export type DocumentAnalysis = {
  classification: {
    document_type: string;
    legal_nature: string;
    unit: string;
    stage: string;
    remedies: string[];
    confidence: number;
    evidence_span: string;
    label: string;
  };
  dates: Record<string, string>;
  fields: Record<string, string>;
  missing: string[];
  findings: Finding[];
  deadlines: DeadlineOut[];
  stages: Array<{ id: string; title: string; state: string }>;
  related: Array<{
    n: number;
    title?: string | null;
    article_no?: string | null;
    document_id?: string | null;
    law_no?: string | null;
    content?: string;
  }>;
  draft: string;
  official_targets: Array<{ name: string; url: string }>;
  action?: string;
  belge?: string | null;
  writer?: string;
  writer_error?: string | null;
  uyap_note?: string;
  source_filename?: string;
  source_kind?: string;
  extract_note?: string;
  text?: string;
  verdict?: string;
  route_reason?: string;
  route_evidence?: string;
  route_confidence?: number;
  suggested_action?: string;
  senaryo?: boolean;
  agents?: AgentStep[];
  chain_status?: string;
  reasoning?: ReasoningTrace;
  petition?: PetitionView;
  gaps?: Array<{ id: string; label: string; hint: string }>;
  havale?: { unit: string; note?: string };
  observability?: {
    engine?: string;
    graph_nodes?: string[];
    graph_edges?: Array<{ source: string; target: string }>;
    langfuse_enabled?: boolean;
    langfuse_trace_id?: string | null;
    langfuse_url?: string | null;
  };
};

export type AgentStep = {
  id: string;
  title: string;
  state: string;
  ms: number;
  summary: string;
  answer?: string | null;
  confidence?: number | null;
  depends_on?: string | null;
  note?: string | null;
};

export type BelgeKalip = {
  id: string;
  title: string;
  when: string;
  makam: string;
  family?: string;
  legal_basis: string[];
  sections: string[];
};

export type KamuSablonBlock = {
  sira?: number;
  ornek?: string;
  kurallar?: string;
};

export type KamuSablonVariant = {
  belge_id?: string;
  ornek?: string;
  blok_sirasi?: string[];
  kapanis?: string;
};

export type KamuKaynak = {
  id?: string;
  name: string;
  kind?: string;
  url: string;
  note?: string;
};

export type KamuSablon = {
  id?: string;
  title?: string;
  source?: string;
  ornek_pdf?: string;
  kaynaklar?: KamuKaynak[];
  bloklar?: Record<string, KamuSablonBlock>;
  varyantlar?: Record<string, KamuSablonVariant>;
  ornekler?: Record<string, string>;
};

export async function getKamuSablon(): Promise<KamuSablon> {
  const response = await apiFetch("/v1/kamu/sablon", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Kamu şablonu alınamadı");
  }
  return response.json();
}

export async function getBelgeler(): Promise<BelgeKalip[]> {
  const response = await apiFetch("/v1/belgeler", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Belge kalıpları alınamadı");
  }
  const body = (await response.json()) as { documents?: BelgeKalip[] };
  return body.documents ?? [];
}

export async function analyzeWorkspace(
  path: "/v1/evrak" | "/v1/surec" | "/v1/islem" | "/v1/senaryo",
  text: string,
  action?: string,
): Promise<DocumentAnalysis> {
  const response = await apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, action }),
  });
  if (!response.ok) {
    const raw = await response.text();
    let detail = raw || "Analiz isteği başarısız";
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      /* keep raw body */
    }
    if (response.status === 404) {
      detail = "API bu uç noktayı tanımıyor. HÂKİM API sunucusunu yeniden başlatın.";
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function analyzeEvrakFile(file: File): Promise<DocumentAnalysis> {
  const body = new FormData();
  body.append("file", file);
  const response = await apiFetch("/v1/evrak/dosya", { method: "POST", body });
  if (!response.ok) {
    const raw = await response.text();
    let detail = raw || "Dosya okunamadı";
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      /* keep raw */
    }
    throw new Error(detail);
  }
  return response.json();
}

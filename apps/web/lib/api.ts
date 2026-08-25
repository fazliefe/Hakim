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
  mulga_warning?: string | null;
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

export type TraceHop = {
  id: string;
  title: string;
  ms: number;
  state: string;
  summary?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  cost_usd?: number;
};

export type Observability = {
  engine?: string;
  graph_nodes?: string[];
  graph_edges?: Array<{ source: string; target: string }>;
  langfuse_enabled?: boolean;
  langfuse_trace_id?: string | null;
  langfuse_url?: string | null;
  hops?: TraceHop[];
  totals?: {
    ms?: number;
    prompt_tokens?: number;
    completion_tokens?: number;
    cost_usd?: number;
    provider?: string;
    model?: string;
    model_label?: string;
  };
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
  observability?: Observability;
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
    takvim?: string;
  };
  etiketler?: Record<string, string>;
};

export function writerLabel(writer?: string | null): string {
  if (writer === "refuse") return "Cevap Yok";
  if (writer === "api" || writer === "ollama") return "Kaynaklı Gerekçe";
  return "Kaynaklı Gerekçe";
}

export function writerIsLlm(writer?: string | null): boolean {
  return writer === "api" || writer === "ollama";
}

// Varsayılan HER ZAMAN göreli `/api-hakim` — next.config.js'deki rewrite bunu
// sunucu tarafında (dev/prod, tünel arkasında fark etmez) gerçek backend'e
// (HAKIM_API_ORIGIN ?? 127.0.0.1:8000) proxy'ler. Tarayıcı hiçbir zaman
// backend'e DOĞRUDAN, mutlak bir localhost adresiyle gitmez — böylece jüri
// public URL'i açtığında kendi makinesindeki 127.0.0.1:8000'e değil, sunucu
// tarafındaki gerçek backend'e istek gider. NEXT_PUBLIC_HAKIM_API_URL yalnızca
// bilinçli bir override için var (ör. backend'i başka bir origin'den doğrudan
// çağırmak); production için hardcoded bir origin BURAYA yazılmaz.
//
// apiBase() ayrıca tarayıcıda çalışırken loopback/tünel uyuşmazlığını
// (ör. NEXT_PUBLIC_HAKIM_API_URL yanlışlıkla 127.0.0.1'e işaret ediyorsa ama
// sayfa tünel üzerinden public bir origin'den açıldıysa) tespit edip yine
// göreli `/api-hakim`'e düşer.
const CONFIGURED_API_BASE = (process.env.NEXT_PUBLIC_HAKIM_API_URL ?? "/api-hakim").replace(/\/$/, "");

function apiBase(): string {
  const configured = CONFIGURED_API_BASE;
  if (typeof window === "undefined") return configured;
  try {
    const target = new URL(configured, window.location.origin);
    const loopback = target.hostname === "127.0.0.1" || target.hostname === "localhost";
    const pageLoopback =
      window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost";
    if (loopback && !pageLoopback) return "/api-hakim";
    if (window.location.protocol === "https:" && target.protocol === "http:" && loopback) {
      return "/api-hakim";
    }
  } catch {
    return "/api-hakim";
  }
  return configured;
}

const TOKEN_KEY = "hakim-token";
const USER_KEY = "hakim-user";

export type AuthUser = {
  id: string;
  username?: string;
  email: string;
  display_name: string;
  role: string;
  created_at?: string;
  last_login_at?: string | null;
  email_verified?: boolean;
  locked?: boolean;
  pending_email?: string | null;
  session_count?: number;
  is_admin?: boolean;
  recent?: AuthActivity[];
};

export type AuthActivity = {
  id: string;
  user_id: string;
  username?: string;
  email: string;
  display_name: string;
  role: string;
  kind: string;
  summary: string;
  detail: Record<string, unknown> | string;
  created_at: string;
};

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setAuthSession(token: string, user: AuthUser): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  persistUser(user);
  window.sessionStorage.setItem("hakim-auth", user.role);
}

function persistUser(user: AuthUser): void {
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  window.dispatchEvent(new Event("hakim-auth-updated"));
}

export function clearAuthSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  window.sessionStorage.removeItem("hakim-auth");
  window.sessionStorage.removeItem("hakim-scale-bias");
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  const token = getAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  try {
    return await fetch(`${apiBase()}${path}`, { ...init, headers, cache: init?.cache ?? "no-store" });
  } catch (err) {
    const raw = err instanceof Error ? err.message : "";
    if (/load failed|failed to fetch|networkerror|network request failed/i.test(raw)) {
      throw new Error("Sunucuya bağlanılamadı.");
    }
    throw err;
  }
}

async function readError(response: Response, fallback: string): Promise<string> {
  const raw = await response.text();
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    /* keep raw */
  }
  return raw || fallback;
}

export async function loginAccount(identifier: string, password: string): Promise<{ token: string; user: AuthUser }> {
  const response = await apiFetch("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ identifier, password }),
  });
  if (!response.ok) throw new Error(await readError(response, "Giriş başarısız"));
  const body = (await response.json()) as { token: string; user: AuthUser };
  setAuthSession(body.token, body.user);
  return body;
}

export type RegisterPending = {
  status: string;
  mailed: boolean;
  smtp: boolean;
  message: string;
  preview_code?: string;
  user: AuthUser;
};

export async function registerAccount(
  username: string,
  email: string,
  password: string,
  displayName: string,
): Promise<RegisterPending> {
  const response = await apiFetch("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, email, password, display_name: displayName }),
  });
  if (!response.ok) throw new Error(await readError(response, "Kayıt başarısız"));
  return response.json() as Promise<RegisterPending>;
}

export async function verifyAccount(identifier: string, code: string): Promise<{ token: string; user: AuthUser }> {
  const response = await apiFetch("/v1/auth/verify", {
    method: "POST",
    body: JSON.stringify({ identifier, code }),
  });
  if (!response.ok) throw new Error(await readError(response, "Doğrulama başarısız"));
  const body = (await response.json()) as { token: string; user: AuthUser };
  setAuthSession(body.token, body.user);
  return body;
}

export async function resendVerification(identifier: string): Promise<{ mailed: boolean; preview_code?: string }> {
  const response = await apiFetch("/v1/auth/resend", {
    method: "POST",
    body: JSON.stringify({ identifier }),
  });
  if (!response.ok) throw new Error(await readError(response, "Kod gönderilemedi"));
  return response.json() as Promise<{ mailed: boolean; preview_code?: string }>;
}

export type CodeMailResult = {
  mailed: boolean;
  smtp?: boolean;
  message?: string;
  preview_code?: string;
};

export async function requestPasswordReset(identifier: string): Promise<CodeMailResult> {
  const response = await apiFetch("/v1/auth/forgot", {
    method: "POST",
    body: JSON.stringify({ identifier }),
  });
  if (!response.ok) throw new Error(await readError(response, "Kod gönderilemedi"));
  return response.json() as Promise<CodeMailResult>;
}

export async function resetPassword(identifier: string, code: string, password: string): Promise<void> {
  const response = await apiFetch("/v1/auth/reset", {
    method: "POST",
    body: JSON.stringify({ identifier, code, password }),
  });
  if (!response.ok) throw new Error(await readError(response, "Şifre güncellenemedi"));
}

export async function logoutAccount(): Promise<void> {
  try {
    await apiFetch("/v1/auth/logout", { method: "POST" });
  } finally {
    clearAuthSession();
  }
}

export async function getCurrentUser(): Promise<AuthUser> {
  const response = await apiFetch("/v1/auth/me");
  if (!response.ok) throw new Error(await readError(response, "Oturum yok"));
  const body = (await response.json()) as { user: AuthUser };
  persistUser(body.user);
  return body.user;
}

export async function listAuthUsers(): Promise<AuthUser[]> {
  const response = await apiFetch("/v1/auth/users");
  if (!response.ok) throw new Error(await readError(response, "Kullanıcı listesi alınamadı"));
  const body = (await response.json()) as { users?: AuthUser[] };
  return body.users ?? [];
}

export async function updateAccountProfile(displayName: string): Promise<AuthUser> {
  const response = await apiFetch("/v1/auth/me", {
    method: "PATCH",
    body: JSON.stringify({ display_name: displayName }),
  });
  if (!response.ok) throw new Error(await readError(response, "Profil güncellenemedi"));
  const body = (await response.json()) as { user: AuthUser };
  persistUser(body.user);
  return body.user;
}

export async function revokeOwnSessions(): Promise<{ revoked: number; user: AuthUser }> {
  const response = await apiFetch("/v1/auth/sessions/revoke", { method: "POST" });
  if (!response.ok) throw new Error(await readError(response, "Oturumlar kapatılamadı"));
  const body = (await response.json()) as { revoked?: number; user: AuthUser };
  persistUser(body.user);
  return { revoked: body.revoked ?? 0, user: body.user };
}

export async function changeAccountPassword(currentPassword: string, newPassword: string): Promise<AuthUser> {
  const response = await apiFetch("/v1/auth/password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (!response.ok) throw new Error(await readError(response, "Parola güncellenemedi"));
  const body = (await response.json()) as { user: AuthUser };
  persistUser(body.user);
  return body.user;
}

export async function requestEmailChange(password: string, email: string): Promise<CodeMailResult> {
  const response = await apiFetch("/v1/auth/email", {
    method: "POST",
    body: JSON.stringify({ password, email }),
  });
  if (!response.ok) throw new Error(await readError(response, "E-posta güncellenemedi"));
  return response.json() as Promise<CodeMailResult>;
}

export async function confirmEmailChange(code: string): Promise<AuthUser> {
  const response = await apiFetch("/v1/auth/email/confirm", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
  if (!response.ok) throw new Error(await readError(response, "E-posta doğrulanamadı"));
  const body = (await response.json()) as { user: AuthUser };
  persistUser(body.user);
  return body.user;
}

export async function createAuthUser(payload: {
  username: string;
  email: string;
  password: string;
  display_name: string;
  role: "admin" | "user";
}): Promise<{ user: AuthUser; mailed: boolean; preview_code?: string; message?: string }> {
  const response = await apiFetch("/v1/auth/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await readError(response, "Kullanıcı eklenemedi"));
  return response.json() as Promise<{ user: AuthUser; mailed: boolean; preview_code?: string; message?: string }>;
}

export async function patchAuthUser(
  userId: string,
  payload: { role?: "admin" | "user"; locked?: boolean },
): Promise<AuthUser> {
  const response = await apiFetch(`/v1/auth/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await readError(response, "Kullanıcı güncellenemedi"));
  const body = (await response.json()) as { user: AuthUser };
  return body.user;
}

export async function deleteAuthUser(userId: string): Promise<void> {
  const response = await apiFetch(`/v1/auth/users/${encodeURIComponent(userId)}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await readError(response, "Kullanıcı silinemedi"));
}

export async function sendAuthPassword(userId: string): Promise<{
  mailed: boolean;
  smtp?: boolean;
  message?: string;
  preview_password?: string;
  preview_code?: string;
}> {
  const response = await apiFetch(`/v1/auth/users/${encodeURIComponent(userId)}/send-password`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(await readError(response, "Parola gönderilemedi"));
  return response.json() as Promise<{
    mailed: boolean;
    smtp?: boolean;
    message?: string;
    preview_password?: string;
    preview_code?: string;
  }>;
}

export async function revokeAuthSessions(userId: string): Promise<number> {
  const response = await apiFetch(`/v1/auth/users/${encodeURIComponent(userId)}/revoke-sessions`, { method: "POST" });
  if (!response.ok) throw new Error(await readError(response, "Oturumlar kapatılamadı"));
  const body = (await response.json()) as { revoked?: number };
  return body.revoked ?? 0;
}

export async function listAuthActivity(userId?: string): Promise<AuthActivity[]> {
  const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  const response = await apiFetch(`/v1/auth/activity${query}`);
  if (!response.ok) throw new Error(await readError(response, "Kayıtlar alınamadı"));
  const body = (await response.json()) as { activity?: AuthActivity[] };
  return body.activity ?? [];
}

export function isLiveCheck(value?: string): boolean {
  return value === "ok";
}

export async function getSystemStatus(signal?: AbortSignal): Promise<SystemStatus> {
  const response = await apiFetch("/v1/durum", { cache: "no-store", signal });
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

export async function runResearch(query: string, lawNo: string | null = null): Promise<ResearchResponse> {
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
  form?: string;
  makam?: string;
  hitap?: string;
  via?: string;
  subtitle?: string;
  konu?: string;
  tarih?: string;
  sehir?: string;
  adres?: string;
  ekler?: string[];
  paragraphs?: string[];
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
  related: Evidence[];
  trace_nodes?: TraceNode[];
  trace_edges?: TraceEdge[];
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
  legal_caveat?: string | null;
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
  observability?: Observability;
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

export type IslemGuess = {
  action: string;
  title: string;
  reason: string;
  evidence?: string;
  confidence: number;
};

export async function guessIslem(text: string): Promise<IslemGuess> {
  const response = await apiFetch("/v1/islem/anla", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    throw new Error("Anlatı anlaşılamadı");
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

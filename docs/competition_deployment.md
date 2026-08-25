# HÂKİM — Yarışma / Jüri Deployment Runbook

Amaç: HÂKİM'i jüri önünde, `localhost` yerine sabit bir HTTPS URL üzerinden
göstermek. Mimari: **tek public port** (Next.js, 3000) + Cloudflare named
Tunnel; backend, veritabanları ve diğer internal servisler internete hiç
açılmaz.

```text
Jüri / Kullanıcı
      |
      v
https://<HAKIM_PUBLIC_HOSTNAME>          (Cloudflare, sabit hostname)
      |
      v
localhost:3000                            (Next.js, production build)
      |
      v  /api-hakim/* rewrite (apps/web/next.config.js)
      v
127.0.0.1:8000                            (FastAPI backend — hiç dışa açılmaz)
      |
      v
Evren LLM profili (config/models.yaml: active: evren)
```

Local LLM / GPU **yok**. LLM tarafı tamamen Evren API'sine (`config/models.yaml`
`active: evren`) gidiyor; bu deployment yalnızca frontend/backend/tunnel'ı
düzenler, RAG/agent/prompt mantığına dokunmaz.

---

## İlk kurulum (bir kez yapılır)

### 1. cloudflared kurulumu (Windows)

```powershell
winget install --id Cloudflare.cloudflared
```

Kurulumu doğrulayın:

```powershell
cloudflared --version
```

### 2. Cloudflare hesabına login

```powershell
cloudflared tunnel login
```

Açılan tarayıcı sekmesinde tünelin bağlanacağı **zone**'u (domain'i) seçin.
Bu komut `%USERPROFILE%\.cloudflared\cert.pem` dosyasını oluşturur — bu dosya
makineye özeldir, **commit edilmez** (repo'nun içinde de değildir).

### 3. Named tunnel oluşturma

```powershell
cloudflared tunnel create hakim-competition
```

Çıktıda bir **Tunnel ID** ve bir credentials JSON dosyasının yolu
(`%USERPROFILE%\.cloudflared\<TUNNEL_ID>.json`) verilir. Bu ikisini not edin.

### 4. DNS hostname bağlama

```powershell
cloudflared tunnel route dns hakim-competition <hostname>.<sizin-domaininiz>
```

Örnek: `cloudflared tunnel route dns hakim-competition hakim.sizin-domaininiz.com`

### 5. Repo içi config dosyası

```powershell
copy infra\cloudflared\config.yml.example infra\cloudflared\config.yml
```

`infra\cloudflared\config.yml` içindeki iki placeholder'ı doldurun:

```yaml
tunnel: <TUNNEL_ID>                          # adım 3'ten
credentials-file: <TUNNEL_CREDENTIALS_JSON_PATH>  # adım 3'ten (…\.cloudflared\<ID>.json)

ingress:
  - hostname: <HAKIM_PUBLIC_HOSTNAME>        # adım 4'te bağladığınız hostname
    service: http://localhost:3000
  - service: http_status:404
```

Bu dosya `.gitignore`'da (`infra/cloudflared/config.yml`) — tunnel ID/hostname
makineye özel olduğu için commit edilmez, yalnızca `.example` şablonu
tracked'tir.

### 6. Gerekli environment variable'lar

`.env` dosyanızda (`copy .env.example .env` ile oluşturduysanız) şunlar dolu
olmalı:

| Değişken | Değer | Not |
|---|---|---|
| `HAKIM_PROFILE` | `evren` | `config/models.yaml`'daki `active: evren` zaten varsayılan; bu satır sadece açık teyit |
| `HAKIM_LLM_API_KEY` | (takım anahtarı) | e-posta ile iletilen `sk-evren-teamNN-...` |
| `HAKIM_ADMIN_PASSWORD` | (güçlü bir parola) | **Bkz. aşağıdaki "Admin parolasını değiştirin" bölümü — zorunlu** |

`NEXT_PUBLIC_HAKIM_API_URL` ve `HAKIM_API_ORIGIN` — standart kurulumda
(backend her zaman `127.0.0.1:8000`) **set etmenize gerek yok**, kod
varsayılanı zaten doğru. Yalnızca backend'i farklı bir portta çalıştırırsanız
`HAKIM_API_ORIGIN`'i **build'den önce** set etmeniz gerekir (bkz. aşağıdaki
"Bilinen davranış: build-time env" notu).

### 7. Admin parolasını değiştirin (zorunlu, bir kez)

Kaynak kodda artık sabit bir admin parolası yok
(`services/auth/store.py::_bootstrap_admin_password`) — ama **bu makinede
`data/accounts.sqlite` zaten var ve admin hesabı önceden `admin1234` ile
oluşturulmuş**. `HAKIM_ADMIN_PASSWORD` set etmek bunu GERİYE DÖNÜK değiştirmez
(yalnızca hesap ilk kez oluşturulurken kullanılır). Yarışmadan önce:

```powershell
# .env içine HAKIM_ADMIN_PASSWORD=<güçlü-parola> ekleyin, sonra:
del data\accounts.sqlite
```

Backend bir sonraki başlatılışında admin hesabını `HAKIM_ADMIN_PASSWORD` ile
yeniden oluşturur. **Uyarı**: bu, o dosyadaki tüm kayıtlı kullanıcıları/
aktivite geçmişini siler — yarışma öncesi temiz bir başlangıç için zaten
istenen şey budur.

Alternatif (mevcut kullanıcıları kaybetmeden): admin panelinden
("Yönetim" → kullanıcı satırı → "Geçici parola gönder",
`/v1/auth/users/{id}/send-password`) admin hesabının parolasını döndürün.

### 8. (Opsiyonel) Cloudflare tarafında basit rate limiting

`/v1/arastirma`, `/v1/evrak`, `/v1/islem` gibi uçlar giriş yapmadan da
çalışıyor (`Depends(optional_user)` — bilinçli bir demo tasarımı, bkz. README)
ve backend'de kod seviyesinde bir rate limit yok. Public URL'in linki yalnızca
jüriyle paylaşılacağı için pratik risk düşük, ama ekstra bir kod değişikliği
gerektirmeden Cloudflare panelinden (Security → WAF → Rate limiting rules)
`/api-hakim/*` path'i için dakikada istek sınırı tanımlanabilir. Bu tamamen
opsiyoneldir ve kod tarafında hiçbir değişiklik gerektirmez — panelden
yapılır.

---

## Yarışma günü

### Tek komutla başlatma

```powershell
.\scripts\start_competition.ps1
```

Bu script sırayla: Docker infra → backend (8000) → frontend (production
build + start, 3000) → Cloudflare Tunnel açar; her biri ayrı bir pencerede
çalışır, port zaten doluysa o adımı atlar (duplicate process açmaz), tunnel
adımı başarısız olursa diğerlerini durdurmaz.

Yardımcı bayraklar:

```powershell
.\scripts\start_competition.ps1 -SkipInfra      # Docker zaten ayaktaysa
.\scripts\start_competition.ps1 -SkipTunnel     # yalnızca localhost testi
.\scripts\start_competition.ps1 -SkipBuild      # değişmeyen bir build'i yeniden kullan
```

### Manuel adımlar (script yerine, veya script'i anlamak için)

```powershell
# 1) Infra
cd infra
docker compose up -d
cd ..

# 2) Backend (ayrı pencere/terminal)
uv run uvicorn hakim_api.main:app --app-dir apps/api/src --port 8000 --host 127.0.0.1

# 3) Frontend — production (ayrı pencere/terminal, apps\web içinde)
cd apps\web
npm run build
npm run start
cd ..\..

# 4) Cloudflare Tunnel (ayrı pencere/terminal)
cloudflared tunnel --config infra\cloudflared\config.yml run hakim-competition
```

### Health check

Ayrı ayrı kontrol:

| Bileşen | Komut | Beklenen |
|---|---|---|
| Backend + Evren + Database + Retriever | `curl http://127.0.0.1:8000/health` | `"status":"ok"`, `checks.yazim`=Evren, `checks.postgres`=Database, `checks.elasticsearch`/`checks.neo4j`=Retriever/Graf, hepsi `"ok"` |
| Frontend (local) | `curl -I http://localhost:3000` | `200` veya `307` (login'e yönlendirme — ikisi de "ayakta" demek) |
| Cloudflare + tam zincir | `curl https://<HAKIM_PUBLIC_HOSTNAME>/api-hakim/v1/durum` | Backend'dekiyle aynı `checks` nesnesi — bu TEK istek frontend+tunnel+proxy+backend'in **hepsinin** çalıştığını kanıtlar |

Not: `/health` bare path'i (`https://<hostname>/health`) **tünel üzerinden
çalışmaz** — Next.js rewrite'ı yalnızca `/api-hakim/*`'ü proxy'ler. Tünel
üzerinden backend'i kontrol etmek için her zaman `/api-hakim/v1/durum`
kullanın.

### Public URL testi

Tarayıcıda `https://<HAKIM_PUBLIC_HOSTNAME>` açın, `/arastirma` sayfasında bir
sorgu deneyin. `evren` profili tek bir LLM çağrısı için genelde birkaç
saniye, en ağır akışlarda (bkz. "Ölçülen gerçek süreler") ~7 saniyeye kadar
sürüyor — bu normaldir, timeout değildir.

---

## İnternet kesilirse

Hiçbir şey yapmanıza gerek yok: `http://localhost:3000` backend/frontend
süreçleri tünelden tamamen bağımsız çalışır. cloudflared'in kapanması veya
hiç açılmamış olması backend/frontend'i etkilemez — script bunu zaten bu
şekilde tasarlar (tunnel adımı en son ve en izole adımdır).

Jüri bilgisayarınıza fiziksel erişebiliyorsa: `http://localhost:3000`'i
doğrudan gösterin, hiçbir ek adım gerekmez.

---

## Tunnel çalışmazsa (troubleshooting)

| Belirti | Olası sebep | Çözüm |
|---|---|---|
| `cloudflared: command not found` | Kurulu değil | "İlk kurulum" adım 1 |
| `cloudflared tunnel run` hemen çıkıyor, "tunnel not found" | Yanlış tunnel adı / login farklı hesapta | `cloudflared tunnel list` ile mevcut tünelleri görün |
| Public URL 502/503 veriyor | Frontend (3000) ayakta değil | `curl http://localhost:3000` ile local'i önce doğrulayın |
| Public URL DNS hatası veriyor | `route dns` adımı yapılmadı/yanlış hostname | "İlk kurulum" adım 4'ü tekrarlayın, `config.yml`'deki hostname ile birebir eşleştiğinden emin olun |
| Sayfa açılıyor ama API çağrıları başarısız | `next build`, `HAKIM_API_ORIGIN` değiştirildikten SONRA çalıştırılmadı (bkz. aşağıki not) | Backend'i varsayılan 8000'de tutuyorsanız bu sorun oluşmaz; portu değiştirdiyseniz `HAKIM_API_ORIGIN`'i set edip **yeniden build alın** |
| Her şey local'de çalışıyor, sadece tünel sorunlu | — | `-SkipTunnel` ile devam edin, jüriye `localhost:3000`'i gösterin |

---

## Yarışma bitince

Her bileşenin kendi penceresinde `Ctrl+C` yeterli. Yalnızca tüneli kapatmak
için o pencerede `Ctrl+C` (backend/frontend etkilenmez). Tüneli tamamen
silmek isterseniz (yarışma sonrası, opsiyonel):

```powershell
cloudflared tunnel cleanup hakim-competition
cloudflared tunnel delete hakim-competition
```

---

## Bilinen davranış: build-time environment variable'lar

Next.js'te hem `NEXT_PUBLIC_*` (tarayıcı bundle'ına gömülür) hem de
`next.config.js` içindeki `rewrites()`'in okuduğu değişkenler (`HAKIM_API_ORIGIN`)
**`npm run build` anında** çözülüp `.next/` içine sabitlenir — `npm run start`
zamanında set etmenin hiçbir etkisi olmaz (bu, deployment hazırlığı sırasında
canlı doğrulandı: `HAKIM_API_ORIGIN`'i yalnızca `start`'tan önce set etmek
proxy hedefini DEĞİŞTİRMEDİ; build'den önce set etmek değiştirdi). Standart
kurulumda (backend hep `127.0.0.1:8000`) bu hiç sorun yaratmaz çünkü kod
varsayılanı zaten doğru adres. Yalnızca backend portunu değiştirirseniz:
`HAKIM_API_ORIGIN`'i set edip **`npm run build`'i yeniden çalıştırın**, sadece
`npm run start`'ı değil.

## Ölçülen gerçek süreler (Evren, bu makinede canlı ölçüldü)

| Endpoint | Toplam süre | writer | Not |
|---|---|---|---|
| `POST /v1/arastirma` (RAG soru) | ~6.9 s | `api` (Evren) | rerank (cross-encoder) ~1.5s, LLM ~5.2s |
| `POST /v1/evrak` (evrak analizi) | ~7.0 s | `api` (Evren) | |
| `POST /v1/islem` (dilekçe taslağı) | ~1.9 s | `api` (Evren) | tek LLM çağrısı ilk seferde başarılı oldu |

Hepsi Cloudflare Tunnel'ın tipik ~100 saniyelik boşta-bağlantı zaman aşımının
çok altında. `services/llm/writer.py`'deki self-correction retry (şema
hatasında bir kez daha dener) tetiklenirse teorik en kötü durum bu sürelerin
~2 katına çıkabilir (ör. evrak analizi ~14s) — yine de güvenli bir marj var.
Retry'ı zorlayan bir senaryo bu ölçümde canlı gözlemlenmedi (ilk denemede
hepsi başarılı oldu); demodan önce birkaç gerçek istekle prova yapmanız
önerilir.

## MANUEL DOĞRULAMA GEREKİYOR

Aşağıdakiler bu ortamda (Cloudflare hesabına/domain'e erişim olmadığı için)
**yapılamadı** — yarışma öncesi sizin doğrulamanız gerekiyor:

- `cloudflared tunnel login` / `create` / `route dns` adımlarının gerçek
  Cloudflare hesabınızda çalıştığı.
- `infra\cloudflared\config.yml` gerçek değerlerle dolduktan sonra
  `cloudflared tunnel run` ile tünelin gerçekten açıldığı.
- Public hostname'in tarayıcıdan gerçekten erişilebilir olduğu ve
  `/api-hakim/v1/durum`'un tünel üzerinden 200 döndürdüğü.
- `scripts\start_competition.ps1`'in cloudflared adımının (4. adım) gerçek bir
  `config.yml` ile uçtan uca çalıştığı (script'in syntax'ı doğrulandı, infra/
  backend/frontend adımları ayrı ayrı elle test edildi; tunnel adımı gerçek
  bir Cloudflare hesabı gerektirdiği için bu ortamda çalıştırılamadı).

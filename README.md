# FP Support Portal

React/TypeScript arayüzü, Python/Django API, PostgreSQL, Celery ve ClamAV kullanan destek portalı. Görsel dil `fpfinansman/ui-next` projesinden uyarlanmıştır.

## Özellikler

- Tenant ve proje seçimi; kapsamlı üyelikler ve roller.
- Ticket, kategori, etiket, atama, öncelik, filtreleme ve sayfalama.
- Müşteri yanıtı, özel iç not ve gerekçeli durum değişikliği.
- Ticket ve yorum eki, sürükle bırak, panodan resim yapıştırma ve yerel önizleme.
- Boyut/kota/tür kontrolü, özel karantina, gerçek ClamAV ve metadata temizliği.
- Yeniden yetkilendirilen indirme; yerel özel depolama veya S3 adaptörü.
- MFA, CSRF, sunucu oturumu, giriş deneme sınırı ve üyelik iptali.
- Proje kapsamlı API anahtarları: MFA ile oluşturma/iptal, tek seferlik gösterim, süre ve salt okunur/okuma-yazma izni.
- İş takvimi/tatiller, ilk yanıt ve çözüm SLA'sı, eskalasyon, otomatik kapanış.
- Outbox, uygulama içi ve yapılandırılabilir içeriksiz e-posta bildirimleri.
- Tek kullanımlık davet, proje/kuruluş yönetimi ve denetim kayıtları.
- Model API’siyle müşteri agentı, PO değerlendirme/yönlendirme/onay kuyruğu ve dış çözüm agentları için MCP.
- İlgili kişi başvurusu, doğrulanmış export, iki yöneticili imha ve hukuki muhafaza.

## Cloudflare üzerinden Docker yayını

`python3 scripts/configure_local.py` ile Git tarafından dışlanan `.env` dosyasını
oluşturun. `.env` içine gerçek alan adınızla `ALLOWED_HOSTS=localhost,127.0.0.1,api,web,destek.example.com`
ve `CSRF_TRUSTED_ORIGINS=https://destek.example.com` ekleyin.

```sh
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.production.yaml up -d --build --wait --wait-timeout 900
```

API, worker ve zamanlayıcı production modunda çalışır; HTTPS ve güvenli çerezler
etkindir. İlk kurulumdaki ayrı seed işi sentetik demo hesapları ve örnek talepler
oluşturur; bu hesapların parolası `.env` içindeki rastgele `DEMO_PASSWORD` değeridir.
Bu kurulum demo verisiyle başlar. ClamAV taraması aktiftir. Apple Silicon üzerinde
ClamAV stable imajı amd64 emülasyonu ile çalışır.

Cloudflare panelinde projeye özel bir Tunnel oluşturun. Published application
hostname alanına kendi alan adınızı, service alanına **HTTP / web:80** girin.
Kurulum tokenını paylaşmadan `.runtime/cloudflare-tunnel-token` dosyasına kaydedin
ve dosyayı yalnızca kendi kullanıcınızın okuyabilmesini sağlayın.

```sh
chmod 600 .env .runtime/cloudflare-tunnel-token
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.production.yaml -f infra/compose.cloudflare.yaml up -d --wait --wait-timeout 900
```

Cloudflare Tunnel DNS kaydı ilgili hostname için Cloudflare tarafından oluşturulur.
`https://destek.example.com/` ve `https://destek.example.com/api/v1/health`
adreslerini doğrulayın. Gateway `127.0.0.1:1000`, API `127.0.0.1:1001` üzerinde dinler; router'da
port açılması gerekmez. Docker Desktop ve bu bilgisayar açık kalmalıdır.
Cloudflare katmanı olmadan yerel geliştirme için aşağıdaki temel Compose komutunu kullanın.

## Docker Compose ile çalıştırma

Docker Desktop açıkken proje kökünde `.env` dosyasını oluşturun. Bu bilgisayarda `scripts/configure_local.py` ile üretilen yerel dosya zaten vardır. Yeni kurulumda Python 3 ile `python scripts/configure_local.py` çalıştırın; `.env.example` sadece alanların örneğidir.

```powershell
docker compose --env-file .env -f infra/compose.yaml up -d --build --wait --wait-timeout 600
docker compose --env-file .env -f infra/compose.yaml ps
```

Portal: http://127.0.0.1:1000 · API: http://127.0.0.1:1001 · Sağlık: http://127.0.0.1:1000/api/v1/health

Compose PostgreSQL, Redis, ClamAV, migration, sentetik demo yükleme, API, Celery worker/beat ve React arayüzünü başlatır. Dosyalar `support_files` adlı özel Docker hacminde saklanır; migration veritabanı sahibiyle, çalışan API ve worker kısıtlı `support_app` rolüyle bağlanır. İlk ClamAV açılışı imza indirme nedeniyle uzun sürebilir. Kayıtları görmek için `docker compose --env-file .env -f infra/compose.yaml logs -f api worker web`; verileri silmeden durdurmak için `docker compose --env-file .env -f infra/compose.yaml stop` kullanın. Hacimleri silen `down -v` komutunu veri korumak istediğinizde kullanmayın.

Bu Compose yapılandırması yalnız yerel sentetik demo içindir. HTTP kapısı sadece `127.0.0.1:1000` üzerinde açılır. Gerçek kullanıcı/veriyle kullanım için TLS, üretim ayarları ve [işletim rehberindeki](docs/isletim.md) dış servis kontrolleri gerekir.

Demo kullanıcıları: `admin`, `agent`, `customer`, `other`, `customer-bot`, `solution-bot`. Ortak sentetik parola `.env` içindeki `DEMO_PASSWORD` değeridir; uygulama veya test loglarına yazılmaz. Bot hesapları ayrı destek kimlikleridir; model yanıtı proje ayarında açılana kadar kapalıdır.

## API anahtarı kullanımı

Bir projeyi açıp sol menüde **API anahtarları** bölümüne gidin. MFA kurulumunu ve güncel doğrulamasını Ayarlar'dan yapın. Anahtara ad, izin ve 30-365 günlük süre seçin. Gizli değer yalnız oluşturma yanıtında ve ekrandaki tek seferlik pencerede görünür; sonradan yalnız ön eki, son kullanımı ve durumu listelenir. İptal edilen anahtar hemen geçersiz olur. Etkin proje üyeliği veya kullanıcı hesabı kaldırıldığında da kullanılamaz.

```powershell
curl.exe -H "Authorization: Bearer <API_KEY>" "http://127.0.0.1:1000/api/v1/tenants/<TENANT_ID>/projects/<PROJECT_ID>/tickets"
```

Anahtar yalnız kendi projesinin ticket, taslak/ek, capability ve bildirim uç noktalarında kullanılabilir. Salt okunur anahtar değiştirme yapamaz. Yazma işlemleri hâlâ kullanıcının güncel RBAC iznine ve ilgili `Idempotency-Key` / `If-Match` kurallarına uyar. Anahtar yönetimi, kuruluş yönetimi, gizlilik ve hesap işlemleri için oturum ve gerektiğinde MFA gerekir. Üretimde anahtarı yalnız TLS üzerinden kullanın ve güvenilir sunucu gizli deposunda saklayın.

## Kaynak koddan yerelde çalıştırma

Python 3.12, Node.js 24, PowerShell 7 ve çalışan Docker Desktop gerekir. Python bulunmazsa bootstrap, bu makinedeki Codex Python çalışma zamanını kullanır.

```powershell
./scripts/bootstrap.ps1
./scripts/init.ps1
./scripts/start-all.ps1
```

Portal: http://127.0.0.1:5173 · API: http://127.0.0.1:8000/api/v1/health

Bootstrap bağımlılıkları kurar ve bulunmuyorsa rastgele sırlarla Git tarafından dışlanan `.env` oluşturur. Init, izole Docker servislerini başlatır, migration ve sentetik demo verisini yükler. Start-all servisleri görünmeyen pencerelerde başlatır; loglar `.runtime/` altındadır. Aynı portlarda açık eski oturumları önce kapatın.

İki tenant ve dört proje bulunur. Proje içerik erişimi tenant yöneticiliğinden ayrı atanır. Yönetim, davet ve gizlilik işlemleri için Ayarlar'da MFA kurup güncel kodla doğrulayın.

Servisler ayrı terminallerde de başlatılabilir:

```powershell
./scripts/start-api.ps1
./scripts/start-worker.ps1
./scripts/start-beat.ps1
./scripts/start-web.ps1
```

ClamAV ilk açılışta imzaları indirir; hazır değilken ekler erişime açılmaz. `DEV_SCAN_BYPASS=0` varsayılandır. Yerel e-posta backend'i yalnız içeriksiz bildirim örneklerini konsola yazar; SMTP `.env` ile yapılandırılır. Launcher süreçlerini `./scripts/stop-all.ps1` kapatır; ayrı terminal süreçleri Ctrl+C ile kapatılır. Docker verilerini koruyarak durdurmak için `docker compose --env-file .env -f infra/compose.yaml stop` kullanın.

## Kontroller

```powershell
./scripts/test-api.ps1
. ./scripts/env.ps1
./.venv/Scripts/python.exe scripts/check-scanner.py
./.venv/Scripts/python.exe scripts/smoke-api.py
./.venv/Scripts/python.exe scripts/smoke-api-key.py
cd apps/web
npm run build
npm test
npm audit
```

Backend testleri ayrı `test_support` DB oluşturur. Fixture kurulumu owner rolüyle, izolasyon kontrolleri gerçek `support_app` rolüyle yapılır. SQLite bu kontrollerin yerine geçmez. HTTP smoke testi çalışan API ve worker üzerinde sentetik ticket/PNG oluşturur. Antivirüs testi EICAR test imzasını yalnız bellekte ClamAV'a gönderir.

Python bağımlılıkları `apps/api/requirements.lock`, frontend bağımlılıkları `apps/web/package-lock.json` ile sabitlenir. GitHub Actions kontrolleri tanımlanmıştır; uzaktaki workflow bu oturumda tetiklenmemiştir.

## Kaynaklar ve üretim

Agent kurulumu, model ayarları ve dış agent MCP bağlantısı için [agent iş akışı rehberi](docs/agent-workflow.md).
Oto Teklif, FPHR ve FPFinansman sunucu bağlantıları için [ürün entegrasyon sözleşmesi](docs/product-integrations.md).

Backend kodu `apps/api/portal`, oturum/kabuk `apps/web/src/app`, ekranlar `pages`, ek/clipboard akışı `features`, tipli API `shared` altındadır. Altyapı `infra`, kurulum ve test komutları `scripts` içindedir.

Üretim için `APP_ENV=production`, güçlü `DJANGO_SECRET_KEY`, Fernet `FIELD_ENCRYPTION_KEY`, açık `PRIVATE_STORAGE_ROOT`, güvenilir host/origin ve ayrı runtime DB rolü gerekir. WSGI ve Celery owner/superuser/RLS bypass veya değiştirilebilir audit izinlerini reddeder. MFA'sız ilk giriş yalnız MFA kurulumuna erişir.

Yerel klasör OneDrive altında olduğundan demo yalnız sentetik veriyle kullanılır. Üretim verisi ve scratch alanı senkronize kaynak klasöründen ayrı tutulmalıdır. Hukuki metinler, veri yerleşimi, saklama, yedek, SMTP/S3 sağlayıcıları kuruluş tarafından belirlenir. Kod kontrolleri KVKK uygunluğu veya BGYS sertifikasyonu iddiası oluşturmaz.

[Ürün planı](docs/urun-ve-mimari-plani.md) · [Uygulama kapsamı](docs/uygulama-durumu.md) · [İşletim rehberi](docs/isletim.md)

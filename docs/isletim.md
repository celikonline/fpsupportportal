# Destek portalı işletim rehberi

## Yerel ortam ve kimlikler

Docker Compose adı `fpsupportportal` olarak sabittir. Tam Docker yığınında portal/API tek HTTP kapısından `127.0.0.1:8080` üzerinde açılır. PostgreSQL 56432, Redis 56379, ClamAV 53310 portlarından yalnız loopback'e açılır. Kaynak kod süreçleriyle çalıştırma seçeneğinde API 8000, frontend 5173 portundadır. Servisler aynı isimli farklı projelerin konteynerlerine dokunmaz.

`start-all.ps1` kendi launcher PID'lerini `.runtime/processes.json` içinde tutar. `stop-all.ps1` script yolunu doğruladıktan sonra bu süreç ağacını kapatır. Tam Docker yığını `docker compose --env-file .env -f infra/compose.yaml up -d --build --wait --wait-timeout 600` ile başlar. Docker `stop` verileri korur; `down -v` normal durdurma işlemi değildir, verileri siler.

Yeni tenant `python apps/api/manage.py provision_tenant --name "Kuruluş" --admin existing_username` komutuyla mevcut aktif kullanıcıya atanabilir. Bu, proje içeriği erişimi vermez. Yönetici MFA sonrasında proje ve davet oluşturur, rol atar. Üretimde demo hesaplar kullanılmaz; ilk yönetici kontrollü kurulumla yaratılır. MFA kaybı ve parola kurtarma, kimlik doğrulaması ve kayıtlı operatör süreci gerektirir. Otomatik parola sıfırlama e-postası ve OIDC bu sürümde yoktur.

## Veritabanı ve TLS

`support_owner` yalnız migration sahibidir. `support_app` runtime rolü superuser, tablo sahibi veya `BYPASSRLS` olamaz. Migration 0002 RLS, `FORCE ROW LEVEL SECURITY`, bileşik ilişkiler ve audit update/delete kısıtlarını kurar. Owner parolası API ve worker ortamlarına verilmez. WSGI ve görev tabanı runtime rolünü denetler.

API anahtarı tablosu da RLS ve tenant/proje bileşik ilişki kullanır. Anahtarlar yalnız proje uç noktalarında Bearer başlığıyla geçerlidir; tam değer saklanmaz, yalnız HMAC özeti kalır. Oluşturma/iptal için güncel MFA, kullanım için hâlâ aktif kullanıcı/tenant/proje üyeliği gerekir. Salt okunur anahtar değişiklik isteği yapamaz; son kullanım zamanı en fazla beş dakikada bir güncellenir. İlgili kişi imhası ilgili tenant anahtarlarını siler.

`APP_ENV` eksikse üretim kuralları uygulanır. Güçlü sırlar ve açık özel dosya/scratch yolu gerekir. Runtime API yalnız güvenilir TLS proxy'den erişilebilir; forwarded-proto başlığını proxy yazar. `infra/nginx.conf` TLS ve CSP örneğidir; gerçek sertifika/alan adıyla kuruluş ortamında doğrulanmalıdır.

## Dosyalar ve S3

Yerel dosya alanı statik olarak yayımlanmaz. Üretimde `PRIVATE_STORAGE_ROOT` senkronize kaynak klasörünün dışında, yalnız servis kimliğinin eriştiği şifreli hacim/scratch alanıdır. OneDrive altındaki demo ortamında yalnız sentetik veri kullanılır.

S3 için `STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_REGION`, gerekirse `S3_ENDPOINT_URL` tanımlanır. Boto3 standart servis kimliği zincirini kullanır. Public access kapalı, IAM yalnız ilgili bucket/prefixlerle sınırlı olmalıdır. `quarantine/` ve `clean/` alanlarında sunucu şifrelemesi istenir. Sağlayıcı, bölge, IAM, anahtar ve aktarım değerlendirmesi kuruluşça doğrulanır.

Karantina nesnesi, temiz durumun DB commit'inden sonra kaldırılır. Tarama başarısızsa dosya erişime kapalı kalır ve bakım işi yeniden dener. Orijinal/türev ayrı saklanmaz; temiz resim metadata'sız yeniden kodlanır. İmha karantina, temiz nesne ve yerel geçici dosyayı kapsar. S3 versioning açık ise geçmiş sürümler için ayrıca lifecycle ve sürüm silme prosedürü gerekir; current object silmek eski sürümleri imha etmez.

## İşçiler ve SLA

Bir beat ve ayrı worker çalıştırılır. Linux üretim worker'larında kaynak sınırları, Windows geliştirmede solo pool kullanılır. İlk yanıt yalnız açık destek yanıtıyla tamamlanır; müşteri beklenirken çözüm saati durur. Politika snapshot'ı eski talebi sonradan sessizce değiştirmez. SLA ihlali tekilleştirilmiş olayla bildirilir; çözülmüş ticket 7 gün sonra kapanır.

Outbox iş değişikliğiyle aynı transaction'da kaydedilir. Uygulama içi bildirimler olay/kullanıcı unique constraint ile tekilleştirilir. E-posta öncesi üyelik yeniden kontrol edilir; başlık, ticket metni ve ek adları e-postada yer almaz. SMTP kabulünden sonra süreç çökerse aynı içeriksiz e-posta yeniden gönderilebilir; tam bir kez teslim garantisi yoktur.

## Gizlilik işlemleri

Başvuru kimlik doğrulaması ve gerekçeyle incelemeye alınır. Export yalnız doğrulanan erişim başvurusunda ve iç notlar hariç yapılır. İndirilen export'un güvenli teslimi ve imhası kuruluş prosedürüne tabidir.

İmha farklı iki yönetici ve güncel MFA ister. İlişkili hukuki muhafaza kaydı varsa durur. İşçi ticket/yorum içeriğini redakte eder, ekleri siler, kişinin ilgili tenant üyeliğini iptal eder ve görünen kimliğini anonimleştirir. Başka tenant değişmez. Asgari aktör ve işlem metaverisi denetim amacı ve ayrı saklama süresi kapsamında korunur.

Saklama süresini kaydetmek otomatik toplu imha başlatmaz. Periyodik toplu imha, onaylı listeler ve hukuki yükümlülüklerle işletim sürecinde yürütülür; bu sürümde otomatik toplu saklama süresi imhası açık değildir. Yedek, audit arşivi ve export'lar envantere alınır.

## Yedek ve yayına alma

DB snapshot/PITR, dosyalar ve tamamlanan imha kararlarının bağımsız kaydı birlikte şifreli saklanır. Restore sırasında dış erişim kapatılır, DB ve dosyalar tutarlı noktaya alınır, son yedekten sonraki imha kararları yeniden uygulanır. Outbox tekrar teslimi, dosya referansları, iptal edilen üyelikler ve RLS doğrulanmadan erişim açılmaz. Yalnız DB restore'u yeterli değildir.

RPO 15 dakika ve RTO 4 saat plan hedefidir; üretim tatbikatı yapılmadan sağlandıkları iddia edilmez. Yayına geçmeden hukuki metinler, veri envanteri, alt işleyen/aktarım değerlendirmesi, saklama/ihlal prosedürü, SMTP/S3/IAM/lifecycle, TLS, restore, erişilebilirlik, tarayıcı uyumluluğu, yük testi ve bağımsız güvenlik incelemesi tamamlanır. Yerel API ve ClamAV doğrulanmıştır; tarayıcı erişim izni reddedildiğinden görsel tarayıcı QA yapılmamıştır.

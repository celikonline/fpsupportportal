# Destek portalı ilk sürüm kapsamı

14 Ekim 2026

React ve Python/Django uygulaması bu depoda çalıştırılabilir ilk sürüm olarak geliştirilmiştir. İstenen çok tenant, çok proje, RBAC, ticket/yorum dosyaları ve panodan resim yapıştırma akışları gerçek API ve veritabanına bağlanır. Arayüz `ui-next` tasarım dilini kullanır; referans projede değişiklik yapılmamıştır.

## Gerçekleşen kapsam

| Alan | Uygulama |
| --- | --- |
| Tenant ve proje | Tenant provisioning komutu, seçici, proje oluşturma/arşivleme, üyelik ve proje rolü |
| RBAC | Yönetici/lider/uzman/talep sahibi/gözlemci rolleri; tenant admin ve auditor kapsamları |
| İzolasyon | Her istekte üyelik ve kaynak kontrolü; PostgreSQL RLS ve bileşik ilişkiler; role bağlı liste/sayım |
| Ticket | Oluşturma, kategori, etiket, öncelik, atama, arama, filtre, sunucu sayfalaması |
| Agentlar ve PO | Model müşteri agentı, kalıcı yeniden deneme, PO yönlendirme/onay ve dış agent için süreli MCP iş sahipliği |
| Ürün köprüsü | Sunucu ürün anahtarı, müşteri subject kapsamı, idempotent oluşturma/yanıt/iptal ve açık mesaj/durum takibi |
| İletişim | Açık yanıt, iç not, görünürlüğü filtrelenmiş tarihçe ve geçiş gerekçeleri |
| Ekler | Ticket ve yorum eki, draft sahipliği, dosya seçme/drop/paste, yerel resim önizlemesi |
| Güvenli dosya | MIME/içerik, boyut, kota, SHA-256, ClamAV, metadata temizliği, yeniden boyut/kota kontrolü |
| Depolama | Özel yerel dizin ve S3 karantina/temiz nesne adaptörü; kontrollü stream indirme |
| Oturum | CSRF, HttpOnly çerez, idle/absolute süre, parola değişimi, MFA ve deneme sınırı |
| API anahtarları | Proje kapsamlı Bearer anahtarı, salt okunur/okuma-yazma, 1-365 gün süre, tek seferlik gösterim, hash saklama, iptal ve güncel RBAC kontrolü |
| MFA onboarding | Üretimde MFA kurulana kadar çalışma alanlarına erişmeyen sınırlı oturum |
| Davet | Süreli, tek kullanımlık token; URL fragment; aynı e-posta hesabı kontrolü |
| SLA | Takvim/tatil/saat dilimi, politika snapshot, bekleme, ihlal olayı ve 7 günlük kapanış |
| Bildirim | Transaction outbox, alıcı erişim kontrolü, uygulama içi liste, SMTP adaptörü |
| Denetim | Tenant filtreli metadata, runtime rolünde update/delete engeli |
| Gizlilik | Başvuru, kimlik doğrulamalı export, farklı iki admin onayı, hukuki muhafaza ve tenant sınırında redaksiyon/imha |
| Teslim | Migrationlar, kilit dosyaları, kurulum/başlatma scriptleri, tam yerel Docker Compose yığını, TLS proxy örneği, CI tanımı |

## Doğrulama sonuçları

- PostgreSQL üzerinde **47 backend testi** geçti. Gerçek restricted role ile RLS, kapsam, dosya/iç not gizliliği, rol değişiminde replay, audit kısıtı, imha sınırı, API anahtarı ve agent/PO/ürün köprüsü izolasyonu doğrulandı.
- **6 frontend testi** geçti. CSRF/idempotency, scoped clipboard, gizli anahtar cache sınırı, PO çözüm onayı ve eski çözüm sürümünün reddi kontrol edilir.
- **7 MCP/çalışan testi** geçti. Gerçek stdio oturumunda araç keşfi, atanmış temiz ek erişimi ve kontrollü alt süreçle iş teslimi/başarısızlıkta PO'ya dönüş kontrol edildi.
- TypeScript kontrolü ve Vite üretim derlemesi geçti; `npm audit` bildirilen **0 açık** döndürdü.
- Django sistem kontrolü, migration farkı ve Python paket bütünlük kontrolü geçti.
- Gerçek ClamAV temiz içeriği kabul etti, bellekteki EICAR test imzasını reddetti.
- Çalışan API üzerinde gerçek oturum/CSRF, tenant/proje seçimi, PNG yükleme/tarama, ticket, iç not gizliliği, dosya indirme ve açık yanıt HTTP akışı geçti.
- Docker Compose ile PostgreSQL, Redis, ClamAV, migration, demo seed, API, worker, beat ve statik React sunucusu sağlıklı açıldı. `127.0.0.1:8080` kapısından aynı HTTP akışı ve gerçek ClamAV taraması geçti. Runtime API işlemi UID 10001 ile çalışıyor; owner veritabanı sırrı ortamında yok.
- Aynı Docker kapısında sentetik kullanıcıyla MFA doğrulaması, API anahtarı oluşturma, gizli değerin listede gösterilmemesi, Bearer okuma, yazma/yönetim reddi ve iptal sonrası 401 yanıtı doğrulandı; sentetik kullanıcı temizlendi.
- S3 namespace/şifreleme adaptörü mock testle doğrulandı; gerçek kuruluş bucket/IAM ve SMTP hesabına bağlantı yapılmadı.

Tarayıcı önizlemesine erişim izni reddedildiği için görsel QA, gerçek tarayıcı paste/drop ve erişilebilirlik incelemesi çalıştırılmadı. Başka tarayıcı yüzeyleri veya otomasyon yöntemleriyle bu izin aşılmadı. GitHub Actions tanımı kaydedildi; uzak CI bu oturumda çalıştırılmadı.

## Üretim kapsamının sınırları

Bu sürümün SLA hedefleri proje bazındadır; öncelik bazlı farklı SLA matrisi yoktur. Katılımcı/watchers, özel rol editörü, bilgi bankası, OIDC, otomatik parola sıfırlama, e-postadan ticket açma ve OCR sonraki kapsamdır. Model müşteri agentı ve dış çözüm agentı/PO/MCP akışı vardır; gerçek model yanıtı için sağlayıcı URL/anahtar/model ayarı gerekir. Ana veritabanı modeli Django modüllerinde, frontend tipleri tipli istemcide tutulur; OpenAPI'den istemci üretimi bu sürümde eklenmemiştir.

Saklama politikası ve iki yöneticili ilgili kişi imhası vardır; otomatik toplu saklama süresi imhası açık değildir. Üretim yedeği/PITR, imha kararlarının restore sonrası yeniden uygulanması, harici değiştirilemez audit arşivi ve S3 geçmiş sürüm lifecycle'ı işletim ortamında kurulmalıdır. Yük, restore, pentest, TLS proxy ve gerçek bucket/SMTP entegrasyonu bu yerel doğrulamanın kapsamında değildir.

KVKK aydınlatma/işleme şartları, veri envanteri, alt işleyen ve yurt dışı aktarım değerlendirmesi, saklama gerekçeleri ve BGYS risk/denetim süreçleri kurum tarafından tamamlanır. Kod tek başına hukuki uygunluk veya sertifikasyon sağlamaz. Yayına alma şartları [işletim rehberinde](isletim.md), çalıştırma adımları [README](../README.md) içindedir.

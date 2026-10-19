# Destek portalı — İK ve muhasebe bakışıyla test raporu

**Tarih:** 15 Ekim 2026
**Ortam:** Yerel geliştirme, `http://127.0.0.1:8080`, sentetik demo verisi
**Sonuç:** İncelenen portal ve müşteri destek akışlarında yüksek öncelikli erişim veya veri sızıntısı hatası görülmedi. Üretim kullanımı ve gerçek AI yanıtı bu koşumda doğrulanmadı.

## Kapsam ve yöntem

İK tarafından çalışan/başvuran verilerinin erişim sınırları, ajanların rolü ve insan onayı; muhasebe tarafından tenant/proje ayrımı, kayıt izlenebilirliği ve destek akışının mali kayıtlara etkisi incelendi. Yerel portal sayfası ve giriş ekranı açıldı. Yetkili bir İK veya muhasebe personeli hesabıyla görsel oturum açma yapılmadığından giriş sonrası ekranların görsel kabulü bu raporun kapsamına dahil değildir; işlevsel kontroller sentetik API akışı ve otomatik testlerle yapıldı.

| Kontrol | Sonuç |
| --- | --- |
| Django API testleri, PostgreSQL test veritabanı | **47/47 geçti**; gerçek yerel PostgreSQL/RLS kontrolleri dahil |
| Portal web testleri | **6/6 geçti** |
| MCP ve dış çalışan testleri | **7/7 geçti** |
| Ürün müşteri köprüsü, çalışan HTTP servisi | **Geçti:** talep oluşturma ve tekrarında tek kayıt, açık yorumlar, müşteri yanıtı, iptal, başka müşteri için 404 |
| Sistem ve şema kontrolü | **Geçti:** Django system check temiz, yeni migration gerekmiyor |
| Yerel web | Giriş ekranı HTTP 200 ile açıldı; TypeScript kontrolü ve üretim derlemesi geçti |

HTTP akışında geçici sentetik API anahtarı test sonunda iptal edildi. Kontrol, iptal edilmiş bir sentetik talep kaydı bırakır; müşteri kaydı kullanılmadı.

## İK değerlendirmesi

- Talepler, ürün sunucusunun doğruladığı kullanıcı kimliğinden türetilen müşteri kapsamına bağlanıyor. Başka müşteri veya tenant kapsamından talep okuma denemesi 404 ile reddedildi.
- İç notlar ve iç olaylar müşteri yanıtında görünmüyor. Otomatik müşteri agentına da iç notlar gönderilmiyor. Dış agent sadece kendisine atanmış işi alabiliyor; çözüm PO incelemesinden geçmeden müşteriye yayınlanmıyor.
- Model yanıtı ve dış agent yorumlarının kaynağı ayırt ediliyor. Yeni talep PO kuyruğuna giriyor; ajan kendi çözümünü onaylayıp talebi kapatamıyor.
- İK kullanımı öncesinde çalışan sicil numarası, sağlık/izin eki, disiplin belgesi ve ücret bilgisi gibi özel nitelikli veya hassas içeriğin hangi projelerde tutulacağı; erişim grupları ve saklama süresi belirlenmeli. Portalın veri silme/anonimleştirme akışı iki yönetici onayı istiyor; şirketin imha ve hukuki saklama politikası yine ayrıca tanımlanmalı.

## Muhasebe değerlendirmesi

- Destek köprüsü talep oluşturma, okuma, yorum ve iptal uçlarıyla sınırlı. Bu entegrasyon muhasebe fişi, fatura, ödeme, bordro veya yevmiye kaydı yazmıyor.
- Ürün/tenant/proje/müşteri kapsamı sunucu tarafında kuruluyor; istemci gövdesinden tenant veya müşteri seçilemiyor. Idempotency anahtarı tekrarlanan talebin çoğalmasını önlüyor.
- Talep numarası, durum, yorum kaynağı ve olay geçmişi sorun takibine yardımcı oluyor. Bu kayıtlar muhasebe defteri veya mali mutabakat kanıtı yerine geçmez; finansal işlem için ayrıca kaynak belge ve onay süreci gerekir.
- Oto Teklif, FPHR ve FPFinansman için ayrı proje ve sunucu anahtarı yapısı var. Yerel sentetik köprü testi geçti; gerçek ürün ortamı anahtarlarının kurulumu ve devreye alınması doğrulanmadı.

## Bulgular ve önerilen takip

**Yüksek öncelikli kusur:** Bu testte doğrulanmadı.

**Kurulum engeli — gerçek AI yanıtı kapalı:** Yerel ortamda `AI_API_URL`, `AI_API_KEY` ve `AI_MODEL` ayarları yok. Portal içi AI müşteri agentı bu nedenle gerçek bir sağlayıcıdan yanıt üretemez; API ve MCP testlerinin geçmesi çalışan bir model sağlayıcısını kanıtlamaz. Üretim öncesi sağlayıcı URL/modeli, sır yönetimi, veri işleme/retention şartları ve başarısızlıkta insana yönlendirme birlikte yapılandırılmalı.

**Üretim öncesi kontrol:** Her ürün için HTTPS uç noktası ve ayrı, süreli sunucu köprü anahtarı verilmeli; anahtarlar tarayıcıya veya istemci loguna taşınmamalı. İK ve muhasebe temsilcileriyle oturum açma sonrası rol matrisi, eklerin görünürlüğü, durum değişimi bildirimi ve kapatılmış talep davranışı gerçek hesaplarla kabul edilmeli.

## Tekrar çalıştırma

Depo kökündeki `scripts/test-api.ps1`, `apps/web` altındaki `npm test -- --run` ve `npm run build`, `apps/mcp` altındaki `.runtime/mcp-venv/Scripts/python.exe -m unittest discover -s . -p 'test_*.py' -v` komutları bu test kapsamını tekrarlar. Ürün köprüsü için `scripts/smoke-product-api.py` yalnız `APP_ENV=development` yerel ortamında sentetik veri kullanır.

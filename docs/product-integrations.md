# Ürünlerden merkezi destek

Oto Teklif, FPHR ve FPFinansman sunucuları ayrı destek projeleri ve sunucu hesaplarıyla bağlanır. Anahtar **Ürün müşteri destek köprüsü** türünde, proje yöneticisi tarafından MFA ile oluşturulur; yalnız `customer-tickets` uçlarında çalışır.

Sunucu ortamı:

```dotenv
FP_SUPPORT_PORTAL_URL=https://support.example.com
FP_SUPPORT_TENANT_ID=SUPPORT-TENANT-UUID
FP_SUPPORT_PROJECT_ID=PRODUCT-SUPPORT-PROJECT-UUID
FP_SUPPORT_API_KEY=PRODUCT-CUSTOMER-BRIDGE-SECRET
```

URL bir origin olmalıdır. Yerelde `http://127.0.0.1:8080` kullanılabilir; üretimde HTTPS gerekir. Anahtar tarayıcıya, `VITE_` alanına, kaynak koda veya loglara verilmez. Anahtar yenilemede aynı sunucu hesabı/proje korunur; müşteri kapsamı anahtar önekinden bağımsızdır.

## Müşteri API sözleşmesi

Kök: `/api/v1/tenants/{supportTenant}/projects/{supportProject}/customer-tickets`.

Her istekte `Authorization: Bearer ...` ve `X-Support-Subject` gerekir. Subject ürünün doğruladığı kullanıcı/tenant/acente bağlamından **sunucuda** oluşturulur. Müşteri body/header/query ile subject seçemez. Portal subject’i sunucu hesabıyla birlikte HMAC’ler; tenant/proje/talep sahibi/subject birlikte aranır. Başka müşterinin talep kimliğini bilmek erişim vermez.

| Yol / yöntem | İşlem |
| --- | --- |
| `GET /?page=1&status=new` | Müşterinin talepleri; `results,total,page,pageSize=20` |
| `GET /?page=1&includeComments=1` | Listeyle her talebin son 5 açık mesajı; daha eski mesaj varsa `commentsTruncated:true` |
| `POST /` | Talep oluştur; `Idempotency-Key` zorunlu |
| `GET /{ticketId}` | Talep, açık yorumlar ve açık olaylar; iç notlar verilmez |
| `POST /{ticketId}/comments` | Takip yanıtı; `{body}` ve idempotency anahtarı |
| `POST /{ticketId}/cancel` | Çalışılmamış talebi iptal et; `{}` ve idempotency anahtarı |

Create gövdesi: `title` (200 karakter), `description` (20.000), `sourceProduct` (`ototeklif`, `fphr`, `fpfinansman`), `externalReference` (üründeki sabit talep kimliği, 128), `priority` (`low`,`normal`,`high`,`critical`). Opsiyonel `images:[{mimeType,base64}]`: en fazla 6 PNG/JPEG, her biri 3 MiB. Portal içerik/kota kontrolü ve ClamAV karantinasını uygular. Remote görüntü URL’leri takip edilmez.

İlk create/comment 201, aynı müşteri/işlem/anahtar/gövde tekrarında 200 döner. Aynı anahtar farklı gövdeyle 409 verir. Ağ hatasında **aynı anahtar ve aynı gövde** tekrar gönderilmelidir. Farklı müşteriler aynı idempotency string’ini kullansa da kayıtları ayrıdır. İptal yalnız `new` veya `triaged` durumunda mümkündür; çalışılmaya başlanmışsa 409.

Durumlar: `new`, `triaged`, `in_progress`, `waiting_requester`, `waiting_internal`, `resolved`, `closed`, `cancelled`. İç durumun adı görünür olabilir; iç gerekçe ve iç not müşteriye verilmez. Açık yorum `source` değerleri: `human`, `customer_agent` (model yanıtı), `external_agent` (PO onaylı çözüm).

Ürün talebi normal PO/agent kuyruğuna girer. Müşteri model agentı yalnız proje ayarında etkinse yanıt üretir. Dış agentın çözümü PO onayından sonra müşteriye açılır.

## Yerel sentetik kurulum

Development-only `provision_demo_bridge`, mevcut tenant admini için ayrı ürün destek projesi ve parolasız sunucu hesabı oluşturur. Gizli değer yalnız Git tarafından dışlanan `.runtime` dosyasına yazılır:

```powershell
. ./scripts/env.ps1
./.venv/Scripts/python.exe apps/api/manage.py provision_demo_bridge --product ototeklif --tenant SUPPORT-TENANT-UUID --output C:/path/fpsupportportal/.runtime/integrations/ototeklif.env
```

Ürün değerleri sırayla `ototeklif`, `fphr`, `fpfinansman` olabilir. Dosya ürün sunucusunun ortamına işletim aracıyla aktarılır. Sentetik anahtar 90 gün geçerlidir; tekrar çalıştırmak yeni anahtar oluşturur. Yenilemede `--rotate` bu komutun aynı ürün/sunucu hesabı için oluşturduğu eski demo anahtarlarını iptal eder. Demo sunucu hesabı etkileşimli giriş yapamaz; üretim anahtarları kuruluşun işletim kimlikleriyle yönetilir. Bu komut üretim sır yönetiminin yerine geçmez.

Oto Teklif ayrıntıları ilgili checkout’taki `oto_teklif_web/SUPPORT_PORTAL.md`; FPHR ve FPFinansman’ın belgeleri kendi checkout’larında tutulur.

Kontroller: `scripts/test-api.ps1` gerçek PostgreSQL/RLS müşteri izolasyonunu; `scripts/test-product-bridge.py` geçici DB’de Oto aktarım çalışanını; `scripts/smoke-product-api.py` çalışan yerel HTTP kapısında gerçek anahtar/kapsam/idempotency/görünürlük akışını doğrular. HTTP smoke sentetik kayıt oluşturup kendi geçici anahtarını iptal eder.

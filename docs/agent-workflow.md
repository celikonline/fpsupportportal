# Agentlar, PO ve MCP

İki ayrı agent türü vardır. Portal müşteri agentı, Celery üzerinden model API’sine bağlanır ve yeni taleplere/müşteri mesajlarına açık yanıt yazar. Dış çözüm agentı MCP üzerinden yalnız kendisine atanmış işleri alır. PO rolünü proje yöneticisi (`manager`) veya destek lideri (`lead`) yürütür; müşteri agentı, dış agent ve PO ayrı hesaplardır.

Akış: **Talep → PO incelemesi → Dış agent veya insan → Çözüm incelemesi → PO onayı → Müşteriye yayın / çözüldü**. PO bir işi tekrar yönlendirebilir; önceki iş sahipliği iptal olur. İnsan desteği mevcut talep ekranını kullanır. Yeniden açılan talepler PO değerlendirmesine döner.

## Portal müşteri agentı

Sunucu ortamında şu değerleri tanımlayın (anahtarı kaynak koda veya tarayıcıya koymayın):

```dotenv
AI_API_URL=https://YOUR-PROVIDER/v1/chat/completions
AI_API_KEY=YOUR-SERVER-SECRET
AI_MODEL=YOUR-MODEL
```

Sağlayıcı OpenAI uyumlu Chat Completions mesajları ve `response_format: {"type":"json_object"}` desteklemelidir. Tam endpoint URL kullanılır; HTTPS zorunludur, yalnız yerel model için loopback HTTP kabul edilir. Yönlendirmeler izlenmez. Model çıktısı `{"reply":"...", "needsHuman":false}` olarak doğrulanır. Model ismi sağlayıcınıza göre seçilir. Docker Compose bu üç değeri API/worker/beat’e aktarır; değişiklikten sonra bu servisleri yeniden oluşturun.

Projede ayrı müşteri ve dış agent hesaplarını destek uzmanı olarak davet edin. **Agentlar ve PO** ekranında hesapları seçin, yönergeleri yazın, güncel MFA doğrulamasından sonra otomatik yanıtı açın. Varsayılan kapalıdır. API anahtarı ve gerçek model bağlantısı olmadan kendiliğinden yanıt üretilmez.

Modele talep başlığı/açıklaması ve son 12 açık mesaj gönderilir; iç notlar gönderilmez. Müşteri metni güvenilmeyen veri olarak belirtilir. Agent işlemler gerçekleştirdiğini varsayamaz, talep kapatamaz ve çözüm onaylayamaz. Yanıtlar **AI müşteri agentı** etiketiyle görünür. `needsHuman=true` iç PO inceleme olayı oluşturur; bütün yeni işler zaten PO kuyruğundadır.

İşler veritabanında kalıcıdır. Beat 30 saniyede bir kuyruk hatalarını/süresi dolmuş model işlerini geri alır. Model hatası en fazla 5 kez artan aralıkla denenir; PO ekranında hata ve yeniden deneme bulunur. Model çağrısı sırasında DB kilidi tutulmaz. İnsan talebi değiştirirse veya agent erişimi kaldırılırsa eski model yanıtı yayınlanmaz. PO yönlendirmesi de talep sürümünü değiştirdiğinden bekleyen ilk yanıtı geçersiz kılabilir.

## Dış agent MCP bağlantısı

[Resmî MCP Python SDK](https://py.sdk.modelcontextprotocol.io/) 2.3.0 kullanılır. MCP bağımlılıkları backend’den ayrı ortamda tutulur:

```powershell
./scripts/bootstrap-mcp.ps1
```

Dış agent hesabıyla giriş yapıp projenin **API anahtarları** ekranından okuma/yazma anahtarı oluşturun. Kişisel anahtar aynı proje ve güncel üyelikle sınırlıdır; iptal/süre dolumu/üyelik kaybı yeni istekleri engeller. Dış agent olarak tanımlanan hesabın Bearer anahtarları doğrudan müşteri yorumu veya durum değişikliği yapamaz; yalnız atanan işlere ve yetenek bilgisine erişebilir.

Agentın MCP istemcisine, yolları kendi makinenize uyarlayarak şu yapılandırmayı ekleyin:

```json
{
  "mcpServers": {
    "fp-support": {
      "command": "C:/path/fpsupportportal/.runtime/mcp-venv/Scripts/python.exe",
      "args": ["C:/path/fpsupportportal/apps/mcp/server.py"],
      "env": {
        "PORTAL_URL": "http://127.0.0.1:8080",
        "PORTAL_TENANT_ID": "YOUR-TENANT-UUID",
        "PORTAL_PROJECT_ID": "YOUR-PROJECT-UUID",
        "PORTAL_API_KEY": "YOUR-EXTERNAL-AGENT-SECRET"
      }
    }
  }
}
```

Linux’ta sanal ortam Python yolu `.../bin/python` olur. Linux’a kurulum için Python 3.11+ ile venv oluşturup `pip install -r apps/mcp/requirements.lock` çalıştırın. Tenant/proje UUID’leri portal URL’sindeki `/t/.../p/...` alanlarıdır. Başka makineden çalışan agent için `PORTAL_URL` erişilebilir HTTPS adresi olmalıdır; yerel Compose loopback kapısı başka makineye açık değildir. Her agent/proje ayrı MCP süreci ve anahtar kullanır. MCP stdio üzerinden çalışır; model barındırmaz ve dış agentın kendi çalışma döngüsünü başlatmaz.

Araçlar:

| Araç | İşlem |
| --- | --- |
| `list_my_work(state, page)` | Yalnız bu hesaba atanmış işleri sayfalı listeler |
| `get_my_work(ticket_id)` | Talep, tartışma, PO yönergeleri ve güncel sürümler |
| `claim_work(work_id, version)` | Kuyruktaki işi veya süresi dolmuş sahipliği 15 dakikalığına alır |
| `heartbeat(work_id, claim_token)` | Sahipliği 15 dakika uzatır |
| `submit_solution(work_id, claim_token, solution)` | Kanıtlarıyla çözümü PO incelemesine sunar |
| `release_work(work_id, claim_token, reason)` | Engellenen işi PO incelemesine iade eder |
| `read_attachment(work_id, attachment_id)` | Atanmış işin taraması tamamlanmış ekini okur; görüntüler native MCP image döner |

Agent döngüsü 30–60 saniye aralıkla `queued` işlerini ve `claimed` durumunda süresi geçmiş sahiplikleri taramalı; `pageSize=20` olduğu için bütün sayfaları gezmeli. İşi almadan önce PO yönergelerini ve kabul koşullarını okumalı; başarılı claim sonucundaki `claimToken` değerini saklamalı. Çalışırken 5 dakikada bir heartbeat gönderip çözüm/test kanıtını sunmalı. Sürüm uyuşmazlığında eski girdilerle devam etmek yerine PO’ya yeniden değerlendirme gereksinimini bildirmeli. Portal bu döngüyü dış makinede kendiliğinden çalıştırmaz; MCP istemcisinin agent runtime’ı yönetir.

Aynı sahiplikle aynı çözümün PO incelemesi aşamasında tekrar gönderimi yeni çözüm yaratmaz. Farklı içerik ve eski sahiplik reddedilir. Süresi dolmuş heartbeat/sonuç reddedilir; aynı işe iki aktif sahiplik verilmez. Gönderilen çözüm müşteriye hemen görünmez. PO güncel talep sürümüne karşı onayladığında tek açık yorum olarak yayınlanır, SLA alanları güncellenir ve talep çözülür. MCP araçları dosya/kod yürütmez; dış agent kendi yetkili çalışma ortamında çözümü üretir.

## Opsiyonel dış çalışan

MCP istemcisiyle kendi agent döngünüzü kullanabilir veya `apps/mcp/worker.py` supervisor’ını çalıştırabilirsiniz. Supervisor atanmış işleri alır, iki dakikada bir sahipliği yeniler, güvenilir bir agent sürecini başlatır ve doğrulanan çözümü PO incelemesine teslim eder. Engellenen/başarısız işler gerekçeyle PO’ya döner. Aktif sahipliği başka oturumdan alınmış işler tüketilmez.

`PORTAL_*` bağlantı ayarlarına ek olarak `FP_WORKER_COMMAND` shell komutu değil, JSON argv dizisidir; `FP_WORKER_CWD` mevcut mutlak çalışma dizinidir. Örnek:

```powershell
$env:FP_WORKER_COMMAND = '["C:/Tools/your-agent-wrapper.exe"]'
$env:FP_WORKER_CWD = 'C:/work/authorized-product-checkout'
./.runtime/mcp-venv/Scripts/python.exe apps/mcp/worker.py
```

Adapter stdin’den tek JSON iş bağlamı okur; stdout’a yalnız `{"solution":"doğrulanan çözüm ve test kanıtı"}` yazar. İlerleme stderr’e yazılabilir. Talep metni komut olarak çalıştırılmaz; executable/work directory işletmecinin seçtiği değerlerdir. Portal anahtarı alt sürece verilmez. Temiz ekler özel geçici dizine indirilir; `localAttachments` dizisi yerel dosya yollarını taşır. Tarama bekleyen ekler metadata’da görünür; erişime açılmaz. Model/agent sağlayıcısını adapter yönetir. Varsayılan çalışma süresi bir saat, `FP_WORKER_TIMEOUT_SECONDS` ile 60–86400 saniye seçilebilir. Supervisor kendi başına model veya kodlama agentı sağlayıcısı kurmaz.

## Doğrulama komutları

```powershell
./scripts/test-api.ps1
./.runtime/mcp-venv/Scripts/python.exe -m unittest discover -s apps/mcp -p test_*.py -v
cd apps/web
npm test
npm run build
```

Gerçek model sağlayıcısıyla yanıt üretimi, ortam anahtarı/model URL’si tanımlandıktan sonra yapılmalıdır. Otomatik testlerde sağlayıcı yanıtı mock edilir; müşteri mesajının görünürlüğü, iç notların modele gitmemesi, sürüm/iş sahipliği, PO onayı, idempotent çözüm gönderimi ve gerçek PostgreSQL RLS sınırları doğrulanır.

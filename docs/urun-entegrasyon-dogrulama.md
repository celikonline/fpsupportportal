# Ürün bağlantıları — 14 Ekim 2026

MCP ve portal içi model yanıtı, PO yönlendirmesi, dış agent sahiplik/çözüm inceleme akışı uygulandı. Ürün müşteri köprüsü yalnız sunucu hesabı ve doğrulanmış müşteri kapsamıyla çalışır. Üç ürünün kod bağlantısı Oto Teklif, FPHR, FPFinansman sırasıyla eklendi; üretim ortamına dağıtım yapılmadı.

| Alan | Doğrulama |
| --- | --- |
| Portal | Gerçek PostgreSQL/RLS üzerinde 47 backend, 6 web, 7 MCP/çalışan testi; build ve çalışan HTTP müşteri köprüsü geçti. |
| Oto Teklif | Broker build, geçici PostgreSQL aktarım testi, web build/typecheck ve son 228 web testi geçti. |
| FPHR | Son destek kaynaklarında geliştirici ve bağımsız Announcements 112/112; web geniş kapı 1467/1467, build/lint/typecheck başarılı. Tam depo kapısı KIRMIZI/RET: destek dışında 14 görünür test hatası ve koşu sırasında başka çalışma tarafından commit nedeniyle geçersiz kanıt. Bu hataların önceki baseline'da bulunduğu ayrıca kanıtlanmadı. |
| FPFinansman | Ayrı worktree'de destek UI testleri, typecheck/lint/build/isolation, tüm .NET çözümü, SupportChecks ve 495 SecurityChecks geçti. Son kod bağımsız incelemede ONAY aldı ve mevcut ürün ağacına çakışmadan aktarıldı. Mevcut ağacın Support modülü derlemesi ve son 12/12 destek UI testi de geçti. Geniş UI koşusunun sonucu elde edilemedi; PASS sayılmadı. |

FPFinansman gerçek Host → çalışan portal HTTP testi son kaynaklarla geçti: oluşturma, liste, ayrıntı, müşteri yanıtı, aynı işlem anahtarıyla çoğaltmama, aynı tenant farklı kullanıcı ve farklı tenant için 404. Ürünün mevcut ortak çalışma ağacında genel TypeScript kontrolü `declarations/api/payeeApi.test.ts` dosyasının eksik `payeeApi` modülü ve `RevisionBody.withholdingPayees` alanıyla ilgili hatalar verdi; bu dosyalar destek yamasında değiştirilmedi.

Yerel demo üç ayrı ürün projesi ve parolasız servis hesabı içerir. Sentetik bağlantı değerleri yalnız Git dışlanan `.runtime/integrations` içinde saklanır. Gerçek ürün sunucularına `FP_SUPPORT_*` değerleri işletim ortamından verilmelidir. Gerçek otomatik model yanıtları için portalın `AI_API_URL`, `AI_API_KEY`, `AI_MODEL` ayarları gereklidir; bu oturumda sağlayıcı anahtarı verilmediği için botlar etkinleştirilmedi. Dış agent MCP istemcisi veya yapılandırılmış `apps/mcp/worker.py` adapter'ıyla atanmış işi tüketir, çözümü PO onayına sunar.

# CV Project Text

## English

### 1-Line Version

Built a production-oriented Python market monitoring platform for BIST IPO ceiling-break detection
with Clean Architecture, SQLite persistence, Telegram alerts, Docker, CI, and a FastAPI dashboard.

### 2-Bullet Version

- Designed and implemented a modular Python monitoring platform for BIST IPO ceiling-break
  detection, using Clean Architecture, typed domain models, Decimal-based financial calculations,
  SQLite persistence, adaptive scheduling, and provider/notification adapters.
- Delivered production-readiness assets including Docker Compose, GitHub Actions CI, 136 automated
  tests, a FastAPI dashboard, release documentation, security notes, and professional architecture
  docs.

### Detailed Project Section

**BIST Market Monitor - Python, FastAPI, SQLite, Docker, GitHub Actions**

- Built a production-oriented monitoring and alerting platform for selected Borsa Istanbul IPO
  symbols, focused on detecting potential daily ceiling-break events.
- Modeled the core domain with market quotes, IPO tracking configuration, ceiling calculations,
  tracking state, lifecycle state, monitoring modes, and structured break signals.
- Applied Clean Architecture so business rules remain independent from yfinance, SQLite, Telegram,
  FastAPI, Docker, and CLI concerns.
- Implemented SQLite persistence with schema versioning, migrations, state recovery, alert
  deduplication, and temporary-database test coverage.
- Added optional Telegram notifications with retry/error handling and no real HTTP calls in tests.
- Built a long-running production runner that reuses the scheduler policy and monitoring
  orchestrator, handles graceful shutdown, and persists runner status.
- Added a FastAPI/Jinja2/HTMX dashboard with persisted symbol state, recent alerts, system status,
  runner status, and Chart.js visualization.
- Shipped Docker Compose support, GitHub Actions CI, professional documentation, release notes,
  security guidance, and 136 passing automated tests.

## Türkçe

### 1 Satırlık Versiyon

BIST halka arz tavan bozulma takibi için Clean Architecture, SQLite, Telegram bildirimleri, Docker,
CI ve FastAPI dashboard içeren üretim odaklı bir Python izleme platformu geliştirdim.

### 2 Maddelik Versiyon

- BIST halka arz tavan bozulma tespiti için Clean Architecture, tipli domain modelleri,
  Decimal tabanlı finansal hesaplamalar, SQLite kalıcılık, adaptif zamanlama ve adapter yapısı
  kullanan modüler bir Python izleme platformu tasarladım ve geliştirdim.
- Docker Compose, GitHub Actions CI, 136 otomatik test, FastAPI dashboard, release dokümantasyonu,
  güvenlik notları ve profesyonel mimari dokümantasyon ile projeyi portfolyo seviyesine taşıdım.

### Detaylı Proje Bölümü

**BIST Market Monitor - Python, FastAPI, SQLite, Docker, GitHub Actions**

- Seçili Borsa İstanbul halka arz hisselerinde olası tavan bozulma sinyallerini izlemek için
  üretim odaklı bir takip ve alarm platformu geliştirdim.
- Market quote, halka arz takip konfigürasyonu, tavan fiyat hesaplama, takip durumu, yaşam döngüsü,
  izleme modu ve yapılandırılmış sinyal modelleri ile domain katmanını modelledim.
- Clean Architecture uygulayarak iş kurallarını yfinance, SQLite, Telegram, FastAPI, Docker ve CLI
  detaylarından bağımsız tuttum.
- SQLite kalıcılık katmanında schema versioning, migration, state recovery ve alert deduplication
  mekanizmalarını uyguladım.
- Telegram bildirimlerini retry/error handling ile opsiyonel adapter olarak ekledim ve testlerde
  gerçek HTTP çağrısını engelledim.
- Scheduler policy ve monitoring orchestrator'u yeniden kullanan, graceful shutdown destekleyen ve
  runner durumunu saklayan uzun süre çalışan production runner geliştirdim.
- Persisted sembol durumları, son alarmlar, sistem durumu, runner durumu ve Chart.js grafiklerini
  gösteren FastAPI/Jinja2/HTMX dashboard ekledim.
- Docker Compose, GitHub Actions CI, profesyonel dokümantasyon, release notları, güvenlik rehberi ve
  136 başarılı otomatik test ile projeyi yayınlanabilir seviyeye getirdim.

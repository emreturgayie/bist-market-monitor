# BIST Tavan Bozulma Takip Sistemi

Borsa İstanbul'da halka arz olan hisseleri takip eden ve tavan bozulma sinyalini bildiren izleme/alarm sistemi.

> ⚠️ Bu proje yatırım tavsiyesi değildir. Eğitim ve portföy amacıyla geliştirilmiştir. Otomatik emir göndermez.

## Durum

🚧 Faz 11: Docker ve Docker Compose ile çalıştırma desteği hazır.

## Kapsam v1

- Demo/gecikmeli veri kaynağı
- Telegram bildirimi
- Manuel sembol takibi
- Otomatik alım-satım yok

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

```

## Docker

```bash
cp .env.example .env
# .env içindeki TAVAN_TAKIP_TRACKED_SYMBOLS değerini doldurun
docker compose up --build
```

SQLite verisi Docker volume üzerinde `/data/tavan_takip.sqlite3` yolunda saklanır.

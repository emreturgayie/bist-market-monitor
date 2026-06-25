# BIST Tavan Bozulma Takip Sistemi

Borsa İstanbul'da halka arz olan hisseleri takip eden ve tavan bozulma sinyalini bildiren izleme/alarm sistemi.

> ⚠️ Bu proje yatırım tavsiyesi değildir. Eğitim ve portföy amacıyla geliştirilmiştir. Otomatik emir göndermez.

## Durum

🚧 Faz 10: Adaptif izleme zamanlama politikası hazır.

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

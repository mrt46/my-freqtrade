# Binance + VisualPriceAction Kurulum

## 1) Config oluştur
Örnek dosyayı kopyala:

```bash
cp config_examples/config_binance_visualpriceaction.example.json config_binance_visualpriceaction.json
```

Sonra bu dosyada Binance API `key` ve `secret` alanlarını doldur.

## 2) 1 yıllık 15m veri indir

```bash
python -m freqtrade download-data \
  --exchange binance \
  --config config_binance_visualpriceaction.json \
  --pairs BTC/USDT \
  --timeframe 15m \
  --timerange 20250101-20260101 \
  --data-dir user_data/data
```

## 3) Backtest

```bash
python -m freqtrade backtesting \
  --strategy VisualPriceAction \
  --strategy-path user_data/strategies \
  --config config_binance_visualpriceaction.json \
  --timeframe 15m \
  --timerange 20250101-20260101 \
  --data-dir user_data/data
```

## 4) Dry-run trade

```bash
python -m freqtrade trade \
  --strategy VisualPriceAction \
  --strategy-path user_data/strategies \
  --config config_binance_visualpriceaction.json
```

> Canlıya geçmeden önce mutlaka dry-run ve küçük stake ile başlayın.

# Autonomous Trading Bot - Kurulum Rehberi

## Hizli Baslangic

### 1. API Anahtarlarini Ayarla

`config_full.json` dosyasinda su alanlari guncelle:

```json
"exchange": {
    "key": "BINANCE_API_KEY_BURAYA",
    "secret": "BINANCE_SECRET_KEY_BURAYA"
}
```

### 2. Telegram Bot Ayarla

```json
"telegram": {
    "token": "TELEGRAM_BOT_TOKEN_BURAYA",
    "chat_id": "TELEGRAM_CHAT_ID_BURAYA"
}
```

#### Telegram Bot Nasil Olusturulur:
1. Telegram'da @BotFather'a git
2. `/newbot` yaz
3. Bot adini gir
4. Token'i kopyala

#### Chat ID Nasil Bulunur:
1. @userinfobot'a mesaj at
2. Chat ID'ni kopyala

### 3. API Server Sifrelerini Degistir

```json
"api_server": {
    "jwt_secret_key": "RASTGELE_UZUN_BIR_STRING",
    "ws_token": "BASKA_RASTGELE_STRING",
    "password": "GUCLU_BIR_SIFRE"
}
```

---

## Calistirma

### Dry Run (Simulasyon - Oneri)
```bash
python -m freqtrade trade --config user_data/config/config_full.json --strategy AdaptiveMultiStrategy --dry-run
```

### Live Trading (Gercek Para)
```bash
python -m freqtrade trade --config user_data/config/config_full.json --strategy AdaptiveMultiStrategy
```

### Backtest
```bash
python -m freqtrade backtesting --config user_data/config/config_full.json --strategy AdaptiveMultiStrategy --timerange 20240101-20240201
```

### Veri Indirme
```bash
python -m freqtrade download-data --config user_data/config/config_full.json --days 30 --timeframes 5m 15m 1h
```

---

## Strateji Parametreleri

### Market Regime Detection
Sistem su piyasa kosullarini otomatik tespit eder:
- **Trend**: strong_uptrend, uptrend, sideways, downtrend, strong_downtrend
- **Volatilite**: low, normal, high, extreme
- **Hacim**: low, normal, high, spike

### Alt Stratejiler
1. **TrendFollowing**: Trend piyasalari icin (ADX > 25)
2. **Grid**: Sideways piyasalar icin (ADX < 20)
3. **MeanReversion**: RSI ekstrem bolgelerinde

### Risk Yonetimi
- Max Drawdown: %15
- Gunluk Kayip Limiti: %5
- Trade Basina Risk: %2
- Dinamik Stoploss: 2x ATR

---

## Onemli Notlar

1. **ILK ONCE DRY RUN KULLANIN** - En az 1 hafta simulasyonda test edin
2. **Kucuk Baslatin** - Gercek parayla baslarken minimum sermaye ile baslayin
3. **Izleyin** - Telegram bildirimlerini takip edin
4. **Sabir** - Sistem ogrenmeye devam eder, hemen sonuc beklemeyin

---

## Dosya Yapisi

```
user_data/
├── config/
│   ├── config_full.json       # Ana config (BUNU KULLANIN)
│   └── config_binance_spot.json  # Basit config
├── strategies/
│   └── adaptive/
│       ├── adaptive_multi_strategy.py  # Ana strateji
│       ├── market_regime.py            # Piyasa analizi
│       ├── strategy_base.py            # Alt stratejiler
│       └── risk_manager.py             # Risk yonetimi
├── models/                    # ML modelleri (otomatik)
└── logs/                      # Log dosyalari
```

---

## Sorun Giderme

### "Insufficient balance" hatasi
- `dry_run_wallet` degerini kontrol edin
- Binance hesabinizda yeterli USDT oldugundan emin olun

### Telegram bildirimi gelmiyor
- Token ve chat_id'yi kontrol edin
- Bot'un `/start` komutu ile baslatildigindan emin olun

### Strateji bulunamadi hatasi
- `strategy_path` dogru mu kontrol edin
- `__init__.py` dosyasinin var oldugundan emin olun

---

## Destek

Sorulariniz icin:
1. Freqtrade Discord: https://discord.gg/freqtrade
2. Freqtrade Docs: https://www.freqtrade.io/

---

*Son guncelleme: 2026-02-01*

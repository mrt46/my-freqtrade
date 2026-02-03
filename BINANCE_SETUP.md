# Binance Bot Otomasyonu - Kurulum Rehberi

Bu rehber, Binance için optimize edilmiş trading botunuzu otomatik çalıştırmak için gereken tüm adımları içerir.

## 📊 Strateji Performansı

Backtest sonuçlarına göre en başarılı stratejiler:

| Strateji | Kar | Trade Sayısı | Başarı Oranı |
|----------|-----|--------------|--------------|
| FixedRiskRewardLoss | %407 | 4 | %100 |
| CustomStoplossWithPSAR | %72 | 10 | %60 |
| MultiMa | %51 | 81 | %41 |
| Supertrend | %44 | 284 | %58 |

**BinanceOptimized** stratejisi, bu 3 başarılı stratejiyi birleştirir:
- FixedRiskRewardLoss'tan 3.5:1 Risk/Reward yönetimi
- Supertrend'den trend takibi
- MultiMa'dan konfirmasyon

## 🚀 Hızlı Başlangıç

### 1. Binance API Anahtarlarını Ayarlayın

```bash
# Config dosyasını düzenleyin
nano user_data/config/config_full.json
```

Aşağıdaki alanları doldurun:
```json
{
  "exchange": {
    "key": "BURAYA_API_KEY",
    "secret": "BURAYA_API_SECRET"
  },
  "dry_run": true,  // İlk testler için true bırakın
  "telegram": {
    "enabled": true,  // Bildirimler için
    "token": "TELEGRAM_BOT_TOKEN",
    "chat_id": "TELEGRAM_CHAT_ID"
  }
}
```

**Önemli:**
- Binance API anahtarı oluştururken **SPOT Trading** iznini verin
- **Withdraw** iznini VERMEYİN (güvenlik için)
- IP kısıtlaması ekleyin (önerilir)

### 2. Backtesting ile Test Edin

Canlıya almadan önce stratejiyi test edin:

```bash
# Hızlı backtest
./scripts/quick_backtest.sh
```

veya manuel:

```bash
# 1. Veri indirin
freqtrade download-data \
  --exchange binance \
  --timeframe 4h \
  --timerange 20240101- \
  --config user_data/config/config_backtest.json

# 2. Backtest çalıştırın
freqtrade backtesting \
  --config user_data/config/config_backtest.json \
  --strategy BinanceOptimized \
  --timeframe 4h
```

### 3. Dry-Run ile Canlı Test

Gerçek para kullanmadan canlı piyasada test edin:

```bash
freqtrade trade \
  --config user_data/config/config_full.json \
  --strategy BinanceOptimized
```

**24 saat boyunca** dry-run'da çalıştırın ve performansı izleyin.

### 4. Otomatik Çalışma İçin Systemd Servisi

Bot'u arka planda sürekli çalıştırmak için:

```bash
# Servisi yükleyin
sudo ./scripts/install_service.sh

# Bot'u başlatın
sudo systemctl start freqtrade-bot

# Durumu kontrol edin
sudo systemctl status freqtrade-bot

# Log'ları izleyin
sudo journalctl -u freqtrade-bot -f
```

### 5. Canlı Trading'e Geçiş

Dry-run'da her şey iyi çalıştıysa:

1. Config dosyasını düzenleyin:
```bash
nano user_data/config/config_full.json
```

2. `dry_run`'ı `false` yapın:
```json
{
  "dry_run": false,
  "dry_run_wallet": 1000  // Bu artık kullanılmayacak
}
```

3. Bot'u yeniden başlatın:
```bash
sudo systemctl restart freqtrade-bot
```

## 📈 Monitoring (İzleme)

### Bot Durumunu Kontrol Etme

```bash
# Hızlı durum özeti
./scripts/monitor_bot.sh

# Canlı log takibi
sudo journalctl -u freqtrade-bot -f

# Son 100 log
sudo journalctl -u freqtrade-bot -n 100
```

### Telegram Bildirimleri

Config'de Telegram'ı aktif ederseniz, bot şu bildirimleri gönderir:
- Yeni trade açılışı
- Trade kapanışı (kar/zarar)
- Stoploss tetiklenmeleri
- Hata mesajları

### Freqtrade UI (Web Arayüzü)

Config'de API server'ı aktif edin:

```json
{
  "api_server": {
    "enabled": true,
    "listen_ip_address": "127.0.0.1",
    "listen_port": 8080,
    "username": "admin",
    "password": "GÜÇLÜBİRŞİFRE"
  }
}
```

Ardından tarayıcıda: http://localhost:8080

## ⚙️ Strateji Ayarları

### BinanceOptimized Özellikleri

**Zaman Dilimi:** 4 saat (4h)

**Risk Yönetimi:**
- 3.5:1 Risk/Reward oranı
- 2x ATR dinamik stoploss
- Break-even: 1x risk karlılıkta
- Take-profit: 3.5x risk karlılıkta

**Entry Koşulları:**
1. Supertrend UP (yükseliş trendi)
2. MultiMa hizalanması (kısa MA'lar yukarıda)
3. Volume konfirmasyonu (>%80 ortalama)
4. RSI < 70 (aşırı alım değil)
5. ADX > 20 (trend gücü)

**Exit Koşulları:**
1. Supertrend DOWN'a döner
2. RSI > 80 (aşırı alım)
3. Custom exit: %15+ kar (ekstrem kar al)
4. 5 gün+ açık ve -%3 zarar (eski trade temizleme)

### Özelleştirme

Stratejiyi optimize etmek için hyperopt kullanın:

```bash
freqtrade hyperopt \
  --config user_data/config/config_backtest.json \
  --strategy BinanceOptimized \
  --hyperopt-loss SharpeHyperOptLoss \
  --epochs 100 \
  --spaces buy sell
```

## 🛡️ Güvenlik ve Risk Yönetimi

### Önerilen Ayarlar

1. **Başlangıç Sermayesi:** Minimum $500-1000
2. **Max Açık Trade:** 3-5 arası
3. **Trade Başına Risk:** Portfolio'nun %1-2'si
4. **Stoploss:** Otomatik (strateji yönetir)

### Güvenlik Kontrol Listesi

- [ ] API anahtarında withdraw izni YOK
- [ ] IP kısıtlaması aktif
- [ ] 2FA (Two-Factor Auth) aktif Binance'de
- [ ] Dry-run ile 24 saat test edildi
- [ ] Telegram bildirimleri aktif
- [ ] Düzenli log kontrolü yapılıyor
- [ ] Backtest sonuçları tatmin edici

### Risk Uyarıları

⚠️ **UYARI:** Cryptocurrency trading yüksek risklidir!

- Kaybedebileceğiniz paradan fazlasını yatırmayın
- Bot otomatik çalışır ama düzenli kontrol gereklidir
- Piyasa koşulları her zaman değişir
- Geçmiş performans gelecek garantisi değildir
- Kendi araştırmanızı yapın (DYOR)

## 🔧 Sorun Giderme

### Bot Çalışmıyor

```bash
# Servis durumunu kontrol edin
sudo systemctl status freqtrade-bot

# Log'lara bakın
sudo journalctl -u freqtrade-bot -n 50

# Manuel çalıştırıp hata mesajlarını görün
cd /home/user/my-freqtrade
freqtrade trade --config user_data/config/config_full.json --strategy BinanceOptimized
```

### Trade Açılmıyor

Muhtemel sebepler:
1. Entry koşulları sağlanmıyor (normal, seçici strateji)
2. Volume yetersiz
3. Maksimum trade limitine ulaşıldı
4. Bakiye yetersiz

Log'larda "Entry blocked" mesajlarına bakın.

### API Hataları

- Binance API anahtarlarını kontrol edin
- IP kısıtlaması varsa, IP'nizi ekleyin
- API rate limitine takılmış olabilirsiniz (bekleyin)

## 📚 Ek Kaynaklar

- [Freqtrade Dokümantasyonu](https://www.freqtrade.io/en/stable/)
- [Binance API Dokümantasyonu](https://binance-docs.github.io/apidocs/spot/en/)
- [Trading Stratejileri](https://github.com/freqtrade/freqtrade-strategies)

## 🎯 Sonraki Adımlar

1. ✅ Config dosyasını ayarladınız
2. ✅ Backtest ile test ettiniz (>%40 kar hedefi)
3. ✅ Dry-run'da 24 saat çalıştırdınız
4. ✅ Telegram bildirimleri aktif
5. ⏳ Canlıya geçiş (küçük sermaye ile başlayın)
6. ⏳ 1 hafta performans izleme
7. ⏳ Gerekirse hyperopt ile optimizasyon

## 📞 Destek

Sorun yaşarsanız:
1. Log'ları kontrol edin
2. Freqtrade dokümantasyonunu okuyun
3. GitHub Issues'a bakın

**Başarılar! 🚀📈**

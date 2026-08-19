# Institutional Flow Ribbon PRO

TradingView / Pine Script **v6** stratejisi. Yedi EMA'yı ekranda ayrı ayrı çizmek
yerine tek bir "hizalanma skoru"na indirger ve yalnızca **tek bir çizginin renk
değişimiyle** sinyal üretir: yeşil = long, kırmızı = short, gri = işlem yok.

**Dosya:** [`ifr_master_pro.pine`](ifr_master_pro.pine)

![IFR PRO önizleme](ifr_preview.svg)

> Yukarıdaki görsel dekoratif değil: stratejinin gerçek skor algoritması sentetik
> fiyat verisi üzerinde çalıştırılıp çizildi. Şeridin renk geçişleri, sıkışma
> bölgesindeki sessizlik ve sinyal noktaları hesaplanmış sonuçlardır.

---

## Bu sürümde ne değişti

Önceki dosya TradingView'de derleme hatası veriyordu. Elimde Pine derleyicisi
olmadığı için hangi satırın patladığını göremedim; bu yüzden hata avlamak yerine
**riskli yapıların tamamını eledim.** Çıkarılanlar ve yerlerine konanlar:

| Çıkarılan | Neden | Yerine |
|---|---|---|
| `array` + `for` döngüsü | `request.security()` içinde çağrılan fonksiyonda dizi/döngü en kırılgan kombinasyon; ayrıca `for i = 0 to n-1` ifadesi `n = 0` iken Pine'da **geriye doğru** sayar | Yedi EMA açık açık işlenir, döngü yok |
| Fonksiyon içinde `s[1]` | Yerel değişken geçmişi, fonksiyon her barda tam bir kez çağrılmazsa tutarsız seri üretir | PineCoders'ın standart `f_sec()` sarmalayıcısı: `_src[1]` parametre üzerinden |
| `input.source()` | `request.security()` bağlamında kaynak çözümlemesi belirsizleşebiliyor | Doğrudan `close` |
| `ta.percentile_nearest_rank()` | Nadir kullanılan fonksiyon, argüman nitelikleri (simple/series) katı | `ta.lowest()` ile darlık karşılaştırması |
| Çok satıra yayılmış `strategy()` | Satır devamı kuralı (girinti 4'ün katı olmamalı) sessiz hata kaynağı | Tek satır |

Ayrıca `ta.dmi()` tuple'ının kullanılmayan `diPlus`/`diMinus` değerleri artık
panelde trend yönü olarak gösteriliyor — hem uyarı kalktı hem bilgi kazanıldı.

### Düzeltilen gerçek hata: `syminfo.exchange`

`f_json()` içinde `syminfo.exchange` kullanılmıştı — **Pine'da böyle bir yerleşik
değişken yok.** Doğrusu `syminfo.prefix` (borsa öneki, örn. "BINANCE"). Bu satır
hem ilk sürümde hem yeniden yazımda aynen bulunduğu için, en baştaki derleme
hatasının kaynağı büyük olasılıkla buydu.

Bunun üzerine dosyadaki **tüm** yerleşik referanslar (`ta.*`, `strategy.*`,
`syminfo.*`, `str.*`, `format.*`, `plot.*`, `shape.*`, `position.*` …) tek tek
tarandı; `syminfo.exchange` dışında geçersiz tanımlayıcı bulunmadı.

Yapı ayrıca parantez dengesi, girinti tutarlılığı ve satır sonu operatörü
açısından denetlendi. **Yine de dosya TradingView'de derlenerek doğrulanmadı**,
bu ortamda Pine derleyicisi yok. Başka hata çıkarsa mesajın tam metnini
gönderin.

---

## Nasıl çalışır

**1. Hizalanma skoru (-100 … +100)**

| Bileşen | Hesap | Ne ölçer |
|---|---|---|
| Fiyat konumu | Her aktif EMA için `fiyat > EMA ? +1 : -1`, ortalaması ×100 | Fiyat kümenin neresinde |
| Dizilim (fan) | Ardışık aktif EMA çiftleri için `hızlı > yavaş ? +1 : -1`, ortalaması ×100 | Trend yapısı bozulmuş mu |

Skor `Yeşil Eşiği`ni geçerse şerit yeşil, `Kırmızı Eşiği`nin altına inerse
kırmızı, arada kalırsa gri. **Gri bölgede hiçbir işlem açılmaz** — sinyal
kirliliğini engelleyen asıl mekanizma bu. Kaç EMA açık olursa olsun skor daima
-100/+100 aralığında kalır, yani eşikleriniz anlamını korur.

**2. Kurumsal para akışı** — beş bağımsız filtre, "en az N onay" mantığı: CVD,
OBV eğimi, relative volume, MFI(14), seans VWAP. Üçü (`ta.obv`, `ta.vwap`,
`ta.mfi`) hacim verisi olmayan sembollerde scripti runtime hatasıyla durdurduğu
için aynı formüllerle `nz(volume)` üzerinden elle yazıldı.

**3. Multi-timeframe** — aynı skor fonksiyonu iki üst zaman diliminde çalıştırılır.
Sıkı mod: iki HTF de aynı renk. Gevşek mod: ters renk olmasın.

**Repaint yok:** skor `request.security()` çağrısının *içinde* bir bar geri
kaydırılır, yani daima kapanmış HTF barı okunur; üstüne `barmerge.lookahead_off`.
`request.security(...)[1]` yazmak chart barını kaydırırdı — bu yanlış olurdu.

**4. Giriş / çıkış** — sinyal yalnız durum değişiminde (edge trigger), `pyramiding = 0`,
stop ve hedef pozisyon açılırken sabitlenir, opsiyonel trailing ve reverse.

**5. Sıkışma filtresi** — ADX eşik altı ve/veya Bollinger bant genişliğinin son
120 barın en darına yakın olması. Tespit edilince **skor ne olursa olsun şerit
gri kabul edilir.** Bunun güzel yan etkisi: sıkışma çözüldüğünde gri → renkli
geçişi doğal bir dönüş ürettiği için kırılım barı ayrı bir breakout kodu
yazmadan yakalanır.

---

## Parametreler

### 1. Şerit (MA)
| Parametre | Varsayılan | İşlevi |
|---|---|---|
| Fiyat Konumu Ağırlığı (%) | 50 | Skorun konum/dizilim dengesi |
| Yeşil / Kırmızı Eşiği | 40 / -40 | Renk değişim sınırları; yükseltmek sinyali azaltır, kaliteyi artırır |
| Şerit Ağırlık Modu | Hızlıya Ağırlıklı | Baseline harmanı; "Eşit" daha yavaş ve sakin |
| EMA 1–7 | 8, 13, 21, 34, 55, 89, 200 | Her biri tek tek kapatılabilir |

### 2. Kurumsal Para Akışı
| Parametre | Varsayılan | İşlevi |
|---|---|---|
| Gereken Minimum Onay | 3 | Aktif 5 filtreden kaçı yönü desteklemeli |
| CVD / OBV EMA | 21 / 21 | Sinyal çizgisi periyotları |
| Relative Volume SMA / Çarpan | 20 / 1.5 | Hacim ortalaması ve eşiği |
| MFI Uzunluk | 14 | Para akışı endeksi periyodu |
| Session VWAP | açık | Fiyatın günlük VWAP'a göre konumu |

### 3. Multi-Timeframe
| Parametre | Varsayılan | İşlevi |
|---|---|---|
| HTF 1 / HTF 2 | 60 / 240 | Üst zaman dilimleri |
| Sıkı Mod | açık | Kapalı = gevşek (nötr kabul edilir) |
| Sadece Kapanmış HTF Barı | açık | **Açık bırakın**, kapatmak repaint demek |

### 4. Risk Yönetimi
| Parametre | Varsayılan | İşlevi |
|---|---|---|
| Sadece Renk Dönüş Barında Gir | açık | Kapalı = onaylar tamamlanınca da girer, daha çok işlem |
| Stop Loss (ATR ×) | 1.5 | Stop mesafesi |
| Risk / Reward | 2.0 | Hedef = risk × bu oran |
| Trailing Stop | kapalı | Aktivasyon 1.0 ATR, mesafe 0.7 ATR |
| Reverse | açık | Ters sinyalde pozisyonu döndürür |
| Şerit Nötre Dönünce Kapat | kapalı | Açıksa sıkışmaya girmek de pozisyonu kapatır |

### 5. Sıkışma Filtresi
| Parametre | Varsayılan | İşlevi |
|---|---|---|
| Tespit Yöntemi | Herhangi biri (OR) | OR = en sıkı eleme. Tek başına "ADX" daha az bloke eder |
| ADX Eşiği | 20 | Altı trendsiz sayılır |
| BBW Geriye Bakış / Darlık Çarpanı | 120 / 1.2 | Bant genişliği son N barın en darının bu katı içindeyse sıkışma |

### 6. Görsel
| Parametre | Varsayılan | İşlevi |
|---|---|---|
| Şerit Kalınlığı | 3 | Ana çizgi kalınlığı |
| Gradient Fill | açık | Şeridin altında iki katmanlı gölge |
| Mumları Şerit Rengiyle Boya | kapalı | Tüm mumlar rejim rengini alır |
| Stop / Hedef Çizgileri | açık | Pozisyondayken seviyeler grafikte |
| Sıkışma Arka Planı | açık | Turuncu tarama |
| Panel Konumu | Sağ Üst | Dört köşeden biri |

---

## Piyasa / zaman dilimi önerileri

| Piyasa | TF | HTF1 / HTF2 | Eşikler | Min. onay | ATR × | R/R | Sıkışma |
|---|---|---|---|---|---|---|---|
| Kripto (BTC, ETH) | 15m | 60 / 240 | ±40 | 3 | 1.5 | 2.0 | OR |
| Kripto (altcoin) | 1h | 240 / D | ±50 | 3 | 2.0 | 2.0 | OR |
| Kripto swing | 4h | D / W | ±40 | 2–3 | 2.0 | 2.5 | ADX |
| BIST / hisse gün içi | 15m | 60 / D | ±45 | 3 | 1.5 | 1.5–2.0 | OR |
| BIST / hisse pozisyon | D | W / M | ±35 | 2 | 2.5 | 3.0 | ADX |
| Forex | 1h | 240 / D | ±45 | 2 | 1.5 | 2.0 | ADX |
| Endeks (hacimsiz) | 1h | 240 / D | ±40 | 1–2 | 1.5 | 2.0 | OR |
| Scalp | 1–5m | 15 / 60 | ±55 | 4 | 1.0 | 1.5 | OR |

Genel kural: **TF küçüldükçe eşikleri ve minimum onayı yükseltin.** Hacimsiz
sembollerde (endeksler) para akışı filtrelerini kapatın; ADX ve BBW hacme bağlı
olmadığı için sıkışma filtresi ana koruma katmanınız olarak çalışmaya devam eder.

---

## Bilinen zayıf noktalar

**1. Yatay piyasa hâlâ en zor senaryo.** Sıkışma filtresi bölgelerin büyük kısmını
eler ama sıfırlamaz: ADX 21–25 bandında gezerken piyasa yönsüz olabilir ve filtre
devreye girmez. Eşikleri ±50/±60'a çekin veya ADX eşiğini 25 yapın.

**2. MTF onayı geç kalır.** 4 saatlik onayı beklerken hareketin ilk üçte biri kaçar.
Trendin gövdesini yakalar, dip/tepe yakalamaz — bu bilinçli bir tercih.

**3. Sadece renk dönüş barında giriş fırsat kaçırır.** Renk döndüğü barda para
akışı onayı tamamlanmamışsa o sinyal tamamen kaybedilir, renk yeşil kalsa bile
tekrar tetiklenmez.

**4. CVD gerçek order flow değil.** TradingView'de bar içi alım/satım ayrımı yok;
kapanışın bar aralığındaki konumundan türetilen bir yaklaşım. Uzun fitilli
barlarda yanıltır.

**5. Kümülatif CVD ve OBV başlangıç noktasına bağlı.** Grafikte yüklü bar sayısı
değişince mutlak değerleri değişir; farklı hesaplarda birebir aynı işlem listesini
beklemeyin.

**6. Gap'ler stop mesafesini aşabilir.** Stop pozisyon açılırken sabitlenir; seans
arası boşluklarda gerçek zarar hesaplanandan büyük olur. Backtest bu yüzden iyimser.

**7. Emirler sonraki barın açılışında dolar.** Sinyal bar kapanışında üretilir.
Hızlı piyasada gerçek kayma modellenen 2 tick'ten büyük olabilir.

**8. Komisyon varsayılanı geneldir.** %0.05 ve %10 equity tipik kripto spot
senaryosu. Kendi borsanızın oranlarıyla değiştirmeden alınan sonuç anlamsızdır.

**9. Sıkışma filtresinin kendi bedeli var.** ADX gecikmelidir, sert trendin ilk
barlarında hâlâ eşiğin altında olup girişi bloke edebilir. OR modu işlem sayısını
belirgin düşürür; uzun düşük volatilite rejimlerinde strateji haftalarca sessiz
kalabilir.

**10. Etiketlerdeki Türkçe karakterler sadeleştirildi.** Kopyala-yapıştır
zincirinde bozulma riskini sıfırlamak için arayüz metinleri ASCII yazıldı
("Ayarlari"). Derlemeyi etkilemez; diakritikli sürüm isterseniz geri koyarım.

---

## Alarmlar

`alertcondition()` strateji scriptinde **derlenir, hata vermez** — ancak
oluşturduğu koşul "Alarm Oluştur" penceresinde listelenmez, seçilemez. Bu yüzden
işlevsel alarmlar `alert()` ve emirlerdeki `alert_message` ile verilir.

TradingView'de: **Alarm Oluştur → Koşul: IFR PRO → "Any alert() function call"**,
veya emir bazlı alarmda mesaj alanına `{{strategy.order.alert_message}}`.

```json
{"action":"buy","ticker":"BTCUSDT","exchange":"BINANCE","tf":"15","price":64250.5,"sl":63800.0,"tp":65150.5,"score":78.57}
```

`action`: `buy`, `sell`, `close_long`, `close_short`.

---

## Kurulum

1. TradingView → Pine Editor → yeni boş script
2. `ifr_master_pro.pine` içeriğini yapıştırın
3. **Save** → **Add to chart**
4. Komisyon ve slippage'i kendi borsanıza göre güncelleyin
5. Strategy Tester'da 100+ işlem gören bir dönemde test edin

> Eğitim ve araştırma amaçlıdır, yatırım tavsiyesi değildir. Gerçek parayla
> kullanmadan önce ileri testten geçirin.

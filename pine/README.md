# Institutional Flow Ribbon (IFR)

Pine Script **v6** stratejisi. 7 EMA'yı ekranda ayrı ayrı çizmek yerine tek bir
"hizalanma skoru"na indirger ve sadece **tek bir çizginin renk değişimiyle**
sinyal üretir: yeşil = long, kırmızı = short, gri = işlem yok.

Dosya: [`institutional_flow_ribbon.pine`](institutional_flow_ribbon.pine)

---

## Nasıl çalışır

**1. Hizalanma skoru (-100 … +100)**

İki bileşenin ağırlıklı toplamıdır:

| Bileşen | Hesap | Ne ölçer |
|---|---|---|
| Fiyat konumu | Her aktif EMA için `fiyat > EMA ? +1 : -1`, ortalaması ×100 | Fiyat kümenin neresinde |
| Dizilim (fan) | Ardışık EMA çiftleri için `hızlı > yavaş ? +1 : -1`, ortalaması ×100 | Trend yapısı bozulmuş mu |

Skor `Yeşil Eşiği`ni geçerse şerit yeşil, `Kırmızı Eşiği`nin altına inerse kırmızı,
arada kalırsa gri olur. Gri bölgede hiçbir işlem açılmaz — sinyal kirliliğini
engelleyen asıl mekanizma budur.

Ekrana çizilen tek çizgi (`baseline`) aktif EMA'ların ağırlıklı ortalamasıdır;
"Hızlıya Ağırlıklı" modda ağırlık `1/periyot` olduğu için çizgi daha tepkiseldir.

**2. Kurumsal para akışı onayı**

Beş bağımsız filtre, "en az N tanesi" mantığıyla çalışır:

- **CVD** — bar içi alıcı/satıcı hacmi kapanışın bar aralığındaki konumuyla ayrıştırılır, kümülatif delta kendi EMA'sının üstünde/altında mı
- **OBV eğimi** — OBV kendi EMA'sının üstünde/altında mı
- **Relative Volume** — `hacim > SMA(hacim, 20) × 1.5` (yönden bağımsız: kurumsal ilgi var mı)
- **MFI(14)** — long için > 50, short için < 50
- **Session VWAP** — fiyat günlük VWAP'ın üstünde/altında mı

OBV, VWAP ve MFI hacimsiz sembollerde çalışmayı durduran runtime hatası
vermemeleri için `ta.obv` / `ta.vwap` / `ta.mfi` yerine aynı formülle elle
hesaplanmıştır.

**3. Multi-timeframe onayı**

Aynı skor fonksiyonu `request.security()` ile HTF1 ve HTF2'de çalıştırılır.

- **Sıkı (Strict):** her iki HTF de aynı renkte olmalı
- **Gevşek (Loose):** HTF'ler ters renkte olmasın (nötr kabul edilir)

**Repaint yok:** skor, `request.security` çağrısının *içinde* bir bar geri
kaydırılır (`s[1]`), yani daima **kapanmış** HTF barı kullanılır; ayrıca
`barmerge.lookahead_off` zorunlu tutulmuştur. `request.security(...)[1]` yazmak
chart barını kaydırırdı — bu koddaki yaklaşım HTF barını kaydırır, doğru olan
budur.

**4. Giriş / çıkış**

Sinyal yalnızca durum **değişiminde** üretilir (edge trigger), her barda değil.
`pyramiding = 0` ile aynı yönde ikinci giriş engellenir. Stop `ATR × çarpan`,
hedef `risk × R/R` olarak pozisyon açıldığı anda sabitlenir; sonradan ATR
değişse bile seviyeler kaymaz.

---

## Parametre tablosu

### ① MA Ayarları

| Parametre | Varsayılan | Ne işe yarar |
|---|---|---|
| Kaynak | `close` | EMA'ların besleneceği fiyat serisi |
| Fiyat Konumu Ağırlığı (%) | 50 | Skorun yüzde kaçı "fiyat EMA'nın üstünde mi"den gelsin; kalanı dizilim bileşeni. Yükseltmek → daha hızlı tepki, düşürmek → daha çok yapı odaklı |
| Yeşil Eşiği | 40 | Şeridin yeşile dönmesi için gereken minimum skor. Yükseltmek sinyal sayısını azaltır, kalitesini artırır |
| Kırmızı Eşiği | -40 | Short için ayna eşik |
| Şerit Ağırlık Modu | Hızlıya Ağırlıklı | Baseline çizgisinin harmanı. "Eşit" seçilirse çizgi yavaşlar, daha az gürültülü olur |
| Şerit Altına Fill | açık | Çizginin altına ATR ölçekli hafif gölge (transparency 85) |
| Fill Kalınlığı (ATR ×) | 0.35 | Gölgenin dikey kalınlığı |
| EMA 1–7 + uzunlukları | 8, 13, 21, 34, 55, 89, 200 | Her biri tek tek kapatılabilir; skor kalan EMA sayısına göre otomatik normalize edilir |

### ② Kurumsal Para Akışı

| Parametre | Varsayılan | Ne işe yarar |
|---|---|---|
| Gereken Minimum Onay | 3 | Aktif 5 filtreden kaçı sinyal yönünü desteklemeli. 4–5 → çok az ama çok seçici sinyal |
| CVD Yönü + EMA | açık, 21 | Kümülatif delta sinyal çizgisi periyodu |
| OBV Eğimi + EMA | açık, 21 | OBV'nin karşılaştırılacağı EMA periyodu |
| Relative Volume + SMA | açık, 20 | Ortalama hacim penceresi |
| Hacim Çarpanı | 1.5 | Barın "kurumsal ilgi" sayılması için ortalamanın kaç katı olmalı |
| MFI + Uzunluk | açık, 14 | Para akışı endeksi periyodu |
| Session VWAP | açık | Fiyatın günlük VWAP'a göre konumu |

### ③ Multi-Timeframe

| Parametre | Varsayılan | Ne işe yarar |
|---|---|---|
| MTF Onayını Kullan | açık | Kapatılırsa yalnız mevcut TF ile çalışır |
| HTF 1 / HTF 2 | 60 / 240 | Üst zaman dilimleri |
| MTF Modu | Sıkı | Sıkı: iki HTF de aynı renk. Gevşek: ters renk olmasın |
| Sadece Kapanmış HTF Barı | açık | **Açık bırakın.** Kapatmak repaint'e yol açar |
| MTF Panelini Göster | açık | Sağ üstteki durum tablosu |

### ④ Risk Yönetimi

| Parametre | Varsayılan | Ne işe yarar |
|---|---|---|
| Long / Short İşlemler | açık / açık | Tek yön test etmek için |
| Sadece Renk Dönüş Barında Gir | açık | Açık: sinyal yalnız rengin döndüğü barda. Kapalı: renk zaten doğruyken onaylar tamamlanınca da girer (daha çok işlem) |
| ATR Uzunluğu | 14 | Volatilite ölçüm penceresi |
| Stop Loss (ATR ×) | 1.5 | Stop mesafesi |
| Take Profit Kullan | açık | Kapatılırsa çıkış yalnız stop / trailing / renk kaybı ile olur |
| Risk / Reward | 2.0 | Hedef = risk mesafesi × bu oran |
| Trailing Stop | kapalı | Açılırsa aşağıdaki iki çarpanla çalışır |
| Trailing Aktivasyon (ATR ×) | 1.0 | Trailing'in devreye gireceği kâr mesafesi |
| Trailing Mesafe (ATR ×) | 0.7 | Zirveden ne kadar geride sürünsün |
| Ters Sinyalde Döndür | açık | Kapalıysa yalnız pozisyonsuzken girilir |
| Şerit Nötre Dönünce Kapat | kapalı | Açıksa SL/TP beklenmeden renk kaybında çıkılır |

---

## Piyasa / zaman dilimi önerileri

| Piyasa | TF | HTF1 / HTF2 | Eşikler | Min. onay | ATR × | R/R | Not |
|---|---|---|---|---|---|---|---|
| Kripto (BTC, ETH) | 15m | 60 / 240 | ±40 | 3 | 1.5 | 2.0 | Varsayılanlar bu senaryo için ayarlandı |
| Kripto (altcoin) | 1h | 240 / D | ±50 | 3 | 2.0 | 2.0 | Volatilite yüksek, stop'u genişletin |
| Kripto swing | 4h | D / W | ±40 | 2–3 | 2.0 | 2.5 | Gevşek MTF modu daha çok fırsat verir |
| BIST / hisse (gün içi) | 15m | 60 / D | ±45 | 3 | 1.5 | 1.5–2.0 | VWAP filtresi burada en değerli; seans açılış gürültüsüne dikkat |
| BIST / hisse (pozisyon) | D | W / M | ±35 | 2 | 2.5 | 3.0 | Sıkı MTF modu D+W+M ile çok az ama güçlü sinyal üretir |
| Forex | 1h | 240 / D | ±45 | 2 | 1.5 | 2.0 | Tick hacmi kullanılır; RVOL ve CVD zayıflar, min. onayı 2'ye çekin |
| Endeks / vadeli (hacimsiz semboller) | 1h | 240 / D | ±40 | 1–2 | 1.5 | 2.0 | Hacme dayalı filtreleri (CVD/OBV/RVOL/MFI) kapatın |
| Scalp | 1–5m | 15 / 60 | ±55 | 4 | 1.0 | 1.5 | Komisyon oranını gerçek borsanıza göre güncelleyin, aksi halde sonuçlar yanıltıcı olur |

Genel kural: **TF küçüldükçe eşikleri ve minimum onay sayısını yükseltin.**
Küçük zaman dilimlerinde skor sık sık eşik civarında salınır; eşiği yükseltmek
bu salınımların sinyale dönüşmesini engeller.

---

## Bilinen zayıf noktalar

**1. Yatay piyasa en büyük düşman.** Sıkışma bölgelerinde EMA'lar iç içe geçer,
dizilim bileşeni sıfıra yakınsar ve skor eşiklerin etrafında gidip gelir. Şerit
çoğunlukla gri kalır (iyi), ama eşiğe yakın salınımlarda arka arkaya küçük
zararlı işlemler (whipsaw) üretebilir. Çözüm: eşikleri ±50/±60'a çekin, minimum
onayı 4 yapın, ya da ADX/BBW gibi bir sıkışma filtresi ekleyip skoru orada
zorla nötre çevirin.

**2. MTF onayı geç kalır.** 4 saatlik onay beklerken hareketin ilk üçte biri
kaçar. Sıkı mod bunu daha da belirginleştirir. Trendlerin gövdesini yakalar,
dip/tepe yakalamaz — bu bilinçli bir tasarım tercihidir.

**3. Sadece renk dönüş barında giriş, fırsat kaçırır.** `flipOnly` açıkken renk
yeşile döndüğü barda para akışı onayı henüz tamamlanmamışsa o sinyal tamamen
kaybedilir; renk yeşil kalmaya devam etse bile tekrar tetiklenmez. Daha çok
işlem isteyenler bu ayarı kapatmalı.

**4. CVD gerçek order flow değil.** TradingView'de bar içi alım/satım ayrımı
yoktur; kapanışın bar aralığındaki konumundan türetilen bir yaklaşımdır. Uzun
fitilli barlarda yanıltabilir. Gerçek delta için borsa bazlı footprint verisi
gerekir.

**5. Kümülatif CVD ve OBV başlangıç noktasına bağlıdır.** Grafikte yüklü bar
sayısı değişince (farklı abonelik seviyeleri, farklı zoom geçmişi) bu iki
serinin mutlak değeri değişir. Kendi EMA'larıyla karşılaştırıldıkları için etki
sınırlıdır ama sıfır değildir — farklı hesaplarda birebir aynı işlem listesini
beklemeyin.

**6. Gap'ler stop mesafesini aşabilir.** Stop, pozisyon açılırken sabitlenir;
hafta sonu / seans arası boşluklarda gerçekleşen zarar hesaplanandan büyük
olabilir. Backtest sonuçları bu yüzden gerçeğe göre iyimserdir.

**7. Emirler bir sonraki barın açılışında dolar.** `calc_on_every_tick = false`
olduğu için sinyal bar kapanışında üretilir, emir sonraki barın açılışında
gerçekleşir. Hızlı piyasalarda bu kayma (slippage 2 tick olarak modellendi)
gerçekte daha büyük olabilir.

**8. Komisyon ve kaldıraç varsayılanları genel.** `%0.05` komisyon ve
`%10 equity` pozisyon büyüklüğü tipik bir kripto spot senaryosudur. Kendi
borsanızın oranlarıyla değiştirmeden alınan backtest sonucu anlamlı değildir.

---

## Alarm kurulumu

`alertcondition()` bir strateji scriptinde **derlenir, hata vermez** — ancak
oluşturduğu koşul strateji scriptlerinde "Alarm Oluştur" penceresinde hiç
listelenmez, dolayısıyla seçilip etkinleştirilemez. Çalışıyormuş gibi görünen
ölü kod bırakmamak için bu satırlar dosyanın sonunda yorum halindedir; scripti
indicator'a çevirirseniz aynen açabilirsiniz.

İşlevsel alarmlar dinamik JSON üreten `alert()` çağrıları ve emirlerdeki
`alert_message` parametresi ile sağlanır.

TradingView'de alarm oluştururken:

- **Koşul:** IFR stratejisi → **"Any alert() function call"** seçin, mesaj alanını boş bırakın (JSON otomatik gelir), veya
- Emir bazlı alarmlarda mesaj alanına `{{strategy.order.alert_message}}` yazın.

Gönderilen format:

```json
{"action":"buy","ticker":"BTCUSDT","exchange":"BINANCE","tf":"15","price":64250.5,"sl":63800.0,"tp":65150.5,"score":78.57,"time":1723600000000}
```

`action` alanı `buy`, `sell`, `close_long`, `close_short` veya bilgi amaçlı
`info` (şerit renk değişimi) değerlerini alır.

---

## Kurulum

1. TradingView → Pine Editor → yeni boş script
2. `institutional_flow_ribbon.pine` içeriğini yapıştırın
3. **Save** → **Add to chart**
4. Strateji ayarlarından komisyon/slippage değerlerini kendi borsanıza göre güncelleyin
5. Strategy Tester'da en az 100+ işlem gören bir dönemde test edin

> Bu kod eğitim ve araştırma amaçlıdır, yatırım tavsiyesi değildir. Gerçek
> parayla kullanmadan önce kendi verilerinizle ileri testten (forward test)
> geçirin.

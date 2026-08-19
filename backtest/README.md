# IFR Trader Pro — Backtest ve Optimizasyon

`ifr_master_pro.pine` stratejisinin birebir Python karşılığı. Üç oyun kitabını da (RANGE / BREAKOUT / TREND) destekler; grid'deki `mode` parametresi hangisinin açık olduğunu belirler (`auto` = üçü birden). BTC/USD verisini
indirir, parametre taraması yapar, sonucu **walk-forward** doğrulamadan geçirir
ve kazanan ayarları doğrudan `.pine` dosyasına yazar.

## Kurulum ve çalıştırma

```bash
pip install numpy pandas requests

# BTCUSDT 4 saatlik, son 4 yıl — tam tarama (~5 dk)
python3 ifr_backtest.py --interval 4h --years 4

# Kazanan ayarları doğrudan Pine dosyasına yaz
python3 ifr_backtest.py --interval 4h --years 4 --apply ../pine/ifr_master_pro.pine

# Hızlı deneme (64 kombinasyon, saniyeler)
python3 ifr_backtest.py --quick

# Kendi verinizle (TradingView'den CSV export dahil)
python3 ifr_backtest.py --csv veri.csv
```

CSV formatı: `time,open,high,low,close,volume` — `time` ISO tarih veya epoch.

## Önemli seçenekler

| Bayrak | Varsayılan | Ne yapar |
|---|---|---|
| `--interval` | `4h` | `15m`, `1h`, `4h`, `1d` |
| `--years` | `4` | Kaç yıllık geçmiş inilecek |
| `--htf1` / `--htf2` | otomatik merdiven | Üst zaman dilimlerini elle seçin |
| `--folds` | `4` | Walk-forward dilim sayısı |
| `--quick` | kapalı | 64 kombinasyonluk küçük grid |
| `--apply` | — | Kazananı bu `.pine` dosyasına yazar |
| `--apply-which` | `walkforward` | `best` derseniz tüm geçmişin en iyisini yazar |

## Çıktı iki ayrı sonuç verir

1. **Tüm geçmişte en iyi getiri** — vitrin rakamı. Binlerce kombinasyon
   denendiği için en iyisi kaçınılmaz olarak gürültüye de uymuştur. Buna
   güvenmeyin.
2. **Walk-forward şampiyonu** — her dilimde yalnızca geçmiş veriyle seçilip
   *görülmemiş* sonraki dilimde test edilmiştir. Gerçekte kullanılacak ayar budur.
   `--apply` varsayılan olarak bunu yazar.

Ayrıca **al-ve-tut** referansı basılır. BTC gibi güçlü boğa geçmişi olan bir
varlıkta trend stratejilerinin al-tut'u geçmesi zordur; bu satırı görmezden
gelmeyin.

## Motorun sadakati

Pine dosyasıyla eşleşen noktalar: aynı EMA seti ve hizalanma skoru, aynı
`ta.rma` (Wilder) yumuşatması, CVD/OBV/RVOL/MFI/VWAP onay sayacı, ADX+BBW
sıkışma filtresi, HTF skorunun **bir bar kaydırılması** (repaint yok), kenar
tetiklemeli sinyal, ATR stop ve R/R hedef, `pyramiding = 0`, %10 equity
pozisyon, %0.05 komisyon.

Bilinçli farklar:

- **Emirler bir sonraki barın açılışında dolar** (Pine varsayılanı ile aynı).
- **Aynı bar içinde hem stop hem hedef görülürse stop varsayılır.** Kötümser ve
  bilerek: bar içi sırayı bilmiyoruz, iyimser varsayım sonucu şişirir.
- Kayma (slippage) tick yerine baz puan cinsinden modellendi (varsayılan 1 bp).
- HTF hizalaması yeniden örnekleme ile yapılır; TradingView'in gerçek HTF
  barlarıyla uç barlarda küçük farklar olabilir.

Bu yüzden sonuçlar TradingView Strategy Tester ile **birebir aynı olmayacaktır.**
Nihai doğrulamayı orada yapın; bu araç doğru bölgeyi bulmak içindir.

## Uyarı

Parametre optimizasyonu doğası gereği geçmişe uydurmadır. Walk-forward bu riski
azaltır, yok etmez. Çıkan ayarları gerçek parayla kullanmadan önce ileri testten
(forward test) geçirin. Bu bir yatırım tavsiyesi değildir.

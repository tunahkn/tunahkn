#!/usr/bin/env python3
"""
Pine Script yerel denetimi
==========================
Bu ortamda Pine derleyicisi yok. Bu betik derleme garantisi VERMEZ; yalnizca bu
projede gercekten yasanmis hata siniflarini yakalar:

  1. Parantez / koseli parantez dengesi
  2. Girinti 4'un kati mi (Pine'da satir devami kurali buna bagli)
  3. Satir sonunda sarkan operator
  4. Yerlesik referans beyaz listesi   -> syminfo.exchange'i bu yakaladi
  5. Koseli parantez baglami           -> TFOPT = [...] (CE10156) bunu kacirmisti

Kullanim:
    python3 tools/pine_lint.py pine/ifr_master_pro.pine
Cikis kodu 0 = temiz, 1 = bulgu var.
"""
import re
import sys

# Dogrulanmis Pine v6 yerlesikleri (yalnizca bu projede kullanilanlar)
BUILTINS = {
    "alert": {"freq_once_per_bar_close", "freq_once_per_bar", "freq_all"},
    "barmerge": {"lookahead_off", "lookahead_on", "gaps_off", "gaps_on"},
    "barstate": {"islast", "isfirst", "isconfirmed", "isrealtime", "ishistory", "isnew"},
    "color": {"new", "black", "white", "gray", "red", "green", "blue", "orange",
              "yellow", "purple", "teal", "silver", "maroon", "navy", "olive",
              "lime", "aqua", "fuchsia", "rgb"},
    "format": {"mintick", "percent", "volume", "price", "inherit"},
    "input": {"bool", "float", "int", "string", "color", "source", "timeframe",
              "symbol", "session", "time", "price", "text_area", "enum"},
    "label": {"new", "delete", "set_text", "set_xy", "style_label_left",
              "style_label_right", "style_label_up", "style_label_down",
              "style_none", "style_label_center"},
    "line": {"new", "delete", "set_xy1", "set_xy2", "style_solid", "style_dashed",
             "style_dotted"},
    "location": {"abovebar", "belowbar", "top", "bottom", "absolute"},
    "math": {"abs", "max", "min", "round", "floor", "ceil", "sqrt", "pow", "log",
             "sign", "avg", "sum", "random"},
    "plot": {"style_line", "style_linebr", "style_stepline", "style_histogram",
             "style_cross", "style_area", "style_areabr", "style_columns",
             "style_circles"},
    "position": {"top_right", "top_left", "top_center", "bottom_right",
                 "bottom_left", "bottom_center", "middle_right", "middle_left",
                 "middle_center"},
    "request": {"security", "security_lower_tf", "financial", "dividends"},
    "shape": {"labelup", "labeldown", "triangleup", "triangledown", "arrowup",
              "arrowdown", "circle", "cross", "xcross", "flag", "square",
              "diamond"},
    "size": {"auto", "tiny", "small", "normal", "large", "huge"},
    "str": {"tostring", "tonumber", "format", "length", "contains", "replace",
            "replace_all", "split", "substring", "upper", "lower"},
    "strategy": {"entry", "exit", "close", "close_all", "cancel", "cancel_all",
                 "order", "long", "short", "commission", "percent_of_equity",
                 "fixed", "cash", "position_size", "position_avg_price",
                 "openprofit", "netprofit", "equity", "opentrades", "closedtrades",
                 "risk", "direction"},
    "syminfo": {"ticker", "tickerid", "prefix", "root", "currency", "basecurrency",
                "description", "mintick", "pointvalue", "session", "timezone",
                "type", "volumetype", "country"},
    "ta": {"ema", "sma", "rma", "wma", "vwma", "hma", "atr", "tr", "rsi", "macd",
           "stoch", "cci", "mfi", "obv", "vwap", "bb", "bbw", "kc", "dmi", "adx",
           "sar", "cum", "change", "highest", "lowest", "highestbars",
           "lowestbars", "crossover", "crossunder", "cross", "barssince",
           "valuewhen", "stdev", "variance", "correlation", "median", "mode",
           "percentile_nearest_rank", "percentile_linear_interpolation",
           "pivothigh", "pivotlow", "linreg", "roc", "mom", "falling", "rising"},
    "table": {"new", "cell", "set_bgcolor", "clear", "delete", "merge_cells",
              "cell_set_text", "cell_set_bgcolor"},
    "timeframe": {"period", "multiplier", "change", "isseconds", "isminutes",
                  "isintraday", "isdaily", "isweekly", "ismonthly", "isdwm",
                  "in_seconds", "from_seconds"},
}


def strip_noise(line: str) -> str:
    """Yorumlari ve metin sabitlerini temizler.
    NOT: iki tirnak turu TEK geciste islenmeli — once tek tirnaklari temizlemek,
    cift tirnak icindeki bir kesme isaretinde dosyanin yarisini yutuyor."""
    s = re.sub(r"//.*", "", line)
    return re.sub(r'"[^"\n]*"|\'[^\'\n]*\'', " STR ", s)


def lint(path: str):
    src = open(path, encoding="utf-8").read()
    lines = src.split("\n")
    issues = []

    for n, raw in enumerate(lines, 1):
        s = strip_noise(raw)

        # 1) Denge
        if s.count("(") != s.count(")"):
            issues.append((n, "PARANTEZ", raw.strip()[:70]))
        if s.count("[") != s.count("]"):
            issues.append((n, "KOSELI PARANTEZ", raw.strip()[:70]))

        # 2) Girinti
        ind = len(raw) - len(raw.lstrip(" "))
        if raw.strip() and ind % 4:
            issues.append((n, f"GIRINTI ({ind} bosluk, 4'un kati degil)", raw.strip()[:70]))

        # 3) Sarkan operator
        if s.rstrip().endswith(("+", "-", "*", "/", ",", " and", " or")):
            issues.append((n, "SATIR SONU OPERATOR", raw.strip()[:70]))

        # 5) Koseli parantez baglami — CE10156'nin sebebi
        # Pine'da [...] yalnizca su uc yerde gecerli:
        #   options = [...]  |  [a, b] = f()  |  x[1] (gecmis referansi)
        # Bir degiskene atanan liste literali gecersizdir.
        for m in re.finditer(r"\[", s):
            before = s[:m.start()].rstrip()
            if re.search(r"options\s*=\s*$", before):
                continue                                  # options literali
            if re.search(r"(?<![=!<>])=\s*$", before):     # '=' veya ':=' ama '==' degil
                issues.append((n, "LISTE ATAMASI (CE10156) — Pine'da [...] degiskene atanamaz",
                               raw.strip()[:70]))

    # 4) Yerlesik referans taramasi
    body = strip_noise(src)
    unknown = set()
    for ns, member in re.findall(r"\b([a-z][a-zA-Z_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)", body):
        if ns in BUILTINS and member not in BUILTINS[ns]:
            unknown.add(f"{ns}.{member}")
    for u in sorted(unknown):
        issues.append((0, "TANIMSIZ YERLESIK", u))

    return issues


def main():
    if len(sys.argv) < 2:
        sys.exit("kullanim: pine_lint.py <dosya.pine> [...]")
    total = 0
    for path in sys.argv[1:]:
        issues = lint(path)
        total += len(issues)
        name = path.split("/")[-1]
        if not issues:
            print(f"  TEMIZ  {name}")
        else:
            print(f"  {len(issues)} BULGU  {name}")
            for n, kind, txt in issues:
                loc = f"satir {n}" if n else "dosya"
                print(f"    {loc:>10}  {kind}\n                {txt}")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()

"""Lấy dữ liệu vĩ mô từ các nguồn miễn phí (không cần API key) -> docs/data/macro.json

Nguồn:
  BIS       – lãi suất điều hành (WS_CBPOL), lạm phát CPI y/y (WS_LONG_CPI), theo tháng
  FRED      – lợi suất trái phiếu 10 năm (OECD), theo tháng
  OECD      – tỷ lệ thất nghiệp, theo tháng
  Eurostat  – thất nghiệp khu vực đồng euro
  World Bank– tăng trưởng GDP, lạm phát theo năm (dùng cho Việt Nam và để bổ sung)
Mỗi chuỗi lỗi riêng sẽ bị bỏ qua, không làm hỏng cả file.
"""
import csv, io, json, datetime, urllib.request
from pathlib import Path

START = "2000-01"
OUT = Path(__file__).parent / "docs" / "data" / "macro.json"

# id: tên, vùng, mã BIS lãi suất (None = không có/dùng chung ECB), mã FRED 10Y, mã OECD thất nghiệp, mã World Bank, mục tiêu lạm phát
COUNTRIES = {
    # Mỹ lấy toàn bộ từ FRED (xem us_series), các trường bis/y10/une bên dưới không dùng
    "US": dict(name="Mỹ", region="Bắc Mỹ", bis=None, y10=None, une=None, wb="USA", target=2.0, bank="Fed"),
    "AU": dict(name="Úc", region="Châu Úc", bis="AU", y10="IRLTLT01AUM156N", une="AUS", wb="AUS", target=2.5, bank="RBA"),
    "NZ": dict(name="New Zealand", region="Châu Úc", bis="NZ", y10="IRLTLT01NZM156N", une="NZL", wb="NZL", target=2.0, bank="RBNZ"),
    "XM": dict(name="Khu vực Euro", region="Châu Âu", bis="XM", y10="IRLTLT01EZM156N", une="EUROSTAT", wb="EMU", target=2.0, bank="ECB"),
    "DE": dict(name="Đức", region="Châu Âu", bis=None, y10="IRLTLT01DEM156N", une="DEU", wb="DEU", target=2.0, bank="ECB"),
    "GB": dict(name="Anh", region="Châu Âu", bis="GB", y10="IRLTLT01GBM156N", une="GBR", wb="GBR", target=2.0, bank="BoE"),
    "CH": dict(name="Thụy Sĩ", region="Châu Âu", bis="CH", y10="IRLTLT01CHM156N", une=None, wb="CHE", target=1.0, bank="SNB"),
    "JP": dict(name="Nhật Bản", region="Châu Á", bis="JP", y10="IRLTLT01JPM156N", une="JPN", wb="JPN", target=2.0, bank="BoJ"),
    "CN": dict(name="Trung Quốc", region="Châu Á", bis="CN", y10=None, une=None, wb="CHN", target=3.0, bank="PBoC"),
    "KR": dict(name="Hàn Quốc", region="Châu Á", bis="KR", y10="IRLTLT01KRM156N", une="KOR", wb="KOR", target=2.0, bank="BoK"),
    "IN": dict(name="Ấn Độ", region="Châu Á", bis="IN", y10="INDIRLTLT01STM", une=None, wb="IND", target=4.0, bank="RBI"),
    "ID": dict(name="Indonesia", region="Châu Á", bis="ID", y10=None, une=None, wb="IDN", target=2.5, bank="BI"),
    "TH": dict(name="Thái Lan", region="Châu Á", bis="TH", y10=None, une=None, wb="THA", target=2.0, bank="BoT"),
    "SG": dict(name="Singapore", region="Châu Á", bis=None, y10=None, une=None, wb="SGP", target=2.0, bank="MAS"),
    "VN": dict(name="Việt Nam", region="Châu Á", bis=None, y10=None, une=None, wb="VNM", target=4.5, bank="SBV"),
}


def get(url):
    # FRED treo nếu User-Agent không quen, nên giả dạng curl
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.7.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def bis(flow, key):
    """Trả về {mã nước: [[yyyy-mm, value], ...]}"""
    text = get(f"https://stats.bis.org/api/v2/data/dataflow/BIS/{flow}/1.0/{key}?startPeriod={START}&format=csv")
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        if row["OBS_VALUE"] not in ("", "NaN"):
            out.setdefault(row["REF_AREA"], []).append([row["TIME_PERIOD"], round(float(row["OBS_VALUE"]), 2)])
    return {k: sorted(v) for k, v in out.items()}


def fred(series):
    text = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}")
    rows = list(csv.reader(io.StringIO(text)))[1:]
    return [[d[:7], round(float(v), 2)] for d, v in rows if v not in ("", ".")]


def fred_raw(series):
    text = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}")
    return [(d, float(v)) for d, v in list(csv.reader(io.StringIO(text)))[1:] if v not in ("", ".")]


def yoy(series, digits=2):
    """Chuỗi chỉ số theo tháng -> % thay đổi so với cùng kỳ năm trước"""
    m = dict(series)
    out = []
    for d, v in series:
        y, mo = d.split("-")
        prev = m.get(f"{int(y) - 1}-{mo}")
        if prev:
            out.append([d, round((v / prev - 1) * 100, digits)])
    return out


def fed_moves():
    """Mọi lần Fed đổi lãi suất mục tiêu từ 1982 (DFEDTAR) và biên độ từ 12/2008 (DFEDTARL/U)."""
    single = fred_raw("DFEDTAR")
    lower = dict(fred_raw("DFEDTARL"))
    upper = fred_raw("DFEDTARU")
    daily = [(d, v, v) for d, v in single] + [(d, lower[d], v) for d, v in upper if d in lower]
    moves, prev = [], None
    for d, lo, up in daily:
        if prev is not None and up != prev:
            moves.append({"date": d, "lower": lo, "upper": up, "bps": round((up - prev) * 100)})
        prev = up
    now = {"date": daily[-1][0], "lower": daily[-1][1], "upper": daily[-1][2]}
    # Mức lãi suất cuối mỗi tháng (cận trên) để vẽ biểu đồ bậc thang
    monthly = {}
    for d, _, up in daily:
        monthly[d[:7]] = up
    return moves, now, sorted([k, v] for k, v in monthly.items() if k >= "1983-01")


def fed_cycles(moves, since="1988-01-01"):
    """Gom các lần điều chỉnh liên tiếp cùng chiều thành một chu kỳ tăng/giảm."""
    cycles = []
    for m in (x for x in moves if x["date"] >= since):
        direction = "up" if m["bps"] > 0 else "down"
        if cycles and cycles[-1]["dir"] == direction:
            c = cycles[-1]
            c.update(end=m["date"], to=m["upper"], moves=c["moves"] + 1, bps=c["bps"] + m["bps"])
        else:
            cycles.append({"dir": direction, "start": m["date"], "end": m["date"], "from": round(m["upper"] - m["bps"] / 100, 4),
                           "to": m["upper"], "moves": 1, "bps": m["bps"]})
    return cycles


def us_data():
    s = {}
    s["rate"] = safe("US fedfunds", fred, "FEDFUNDS")
    cpi = safe("US cpi", fred_raw, "CPIAUCSL")
    s["cpi"] = yoy([[d[:7], v] for d, v in cpi]) if cpi else None
    core = safe("US core pce", fred_raw, "PCEPILFE")
    s["core_pce"] = yoy([[d[:7], v] for d, v in core]) if core else None
    s["y10"] = safe("US y10", fred, "GS10")
    s["y2"] = safe("US y2", fred, "GS2")
    s["une"] = safe("US une", fred, "UNRATE")
    m2 = safe("US m2", fred_raw, "M2SL")
    if m2:
        m2 = [[d[:7], v] for d, v in m2]
        s["m2"] = [[d, round(v / 1000, 3)] for d, v in m2]   # nghìn tỷ USD
        s["m2_yoy"] = yoy(m2)
    for k in s:  # giới hạn từ START cho gọn; M2 và CPI giữ từ 1960 để so sánh dài hạn
        if s[k]:
            since = "1960-01" if k in ("m2", "m2_yoy", "cpi") else START
            s[k] = [x for x in s[k] if x[0] >= since]
    fed = None
    r = safe("US fed moves", fed_moves)
    if r:
        moves, now, monthly = r
        fed = {"now": now, "moves": moves[-40:], "cycles": fed_cycles(moves), "target_monthly": monthly}
    return s, fed


def oecd_unemployment(codes):
    text = get("https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0/"
               f"{'+'.join(codes)}..._Z.Y._T.Y_GE15..M?startPeriod={START}&format=csv")
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        if row["OBS_VALUE"]:
            out.setdefault(row["REF_AREA"], []).append([row["TIME_PERIOD"], round(float(row["OBS_VALUE"]), 2)])
    return {k: sorted(v) for k, v in out.items()}


def eurostat_unemployment():
    d = json.loads(get("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m"
                       f"?geo=EA21&s_adj=SA&age=TOTAL&sex=T&unit=PC_ACT&sinceTimePeriod={START}"))
    times = {i: t for t, i in d["dimension"]["time"]["category"]["index"].items()}
    return sorted([times[int(i)], v] for i, v in d["value"].items())


def worldbank(country, indicator):
    d = json.loads(get(f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page=100&date=2000:2030"))
    return sorted([x["date"], round(x["value"], 2)] for x in (d[1] or []) if x["value"] is not None)


def safe(label, fn, *args):
    try:
        return fn(*args)
    except Exception as e:  # một nguồn lỗi không làm hỏng cả bộ dữ liệu
        print(f"  ! {label}: {e}")
        return None


def main():
    # BIS: gọi từng nước một (gộp nhiều nước trong một truy vấn hay bị treo)
    print("BIS…")
    rates, cpi = {}, {}
    for cid, c in COUNTRIES.items():
        if c["bis"]:
            rates.update(safe(f"BIS rate {cid}", bis, "WS_CBPOL", f"M.{c['bis']}") or {})
        if cid not in ("VN", "US"):  # VN: BIS không có CPI tháng; US: lấy từ FRED
            cpi.update(safe(f"BIS CPI {cid}", bis, "WS_LONG_CPI", f"M.{c['bis'] or cid}.771") or {})
    print("OECD…")
    une = safe("OECD une", oecd_unemployment, [c["une"] for c in COUNTRIES.values() if c["une"] not in (None, "EUROSTAT")]) or {}

    data, fed = {}, None
    for cid, c in COUNTRIES.items():
        print(cid, c["name"])
        s = {}
        if cid == "US":
            s, fed = us_data()
        else:
            s["rate"] = rates.get(c["bis"]) if c["bis"] else (rates.get("XM") if c["bank"] == "ECB" else None)
            s["cpi"] = cpi.get(c["bis"] or cid)
            s["y10"] = safe(f"{cid} y10", fred, c["y10"]) if c["y10"] else None
            s["une"] = safe(f"{cid} une", eurostat_unemployment) if c["une"] == "EUROSTAT" else une.get(c["une"])
        s["gdp_y"] = safe(f"{cid} gdp", worldbank, c["wb"], "NY.GDP.MKTP.KD.ZG")
        s["cpi_y"] = safe(f"{cid} cpi_y", worldbank, c["wb"], "FP.CPI.TOTL.ZG")
        data[cid] = {**{k: c[k] for k in ("name", "region", "target", "bank")},
                     "series": {k: v for k, v in s.items() if v}}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"),
                               "countries": data, "fed": fed}, ensure_ascii=False, separators=(",", ":")))
    print("OK ->", OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()

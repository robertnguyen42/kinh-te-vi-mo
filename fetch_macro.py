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
        if cid != "VN":  # BIS không có CPI tháng của Việt Nam
            cpi.update(safe(f"BIS CPI {cid}", bis, "WS_LONG_CPI", f"M.{c['bis'] or cid}.771") or {})
    print("OECD…")
    une = safe("OECD une", oecd_unemployment, [c["une"] for c in COUNTRIES.values() if c["une"] not in (None, "EUROSTAT")]) or {}

    data = {}
    for cid, c in COUNTRIES.items():
        print(cid, c["name"])
        s = {}
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
                               "countries": data}, ensure_ascii=False, separators=(",", ":")))
    print("OK ->", OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()

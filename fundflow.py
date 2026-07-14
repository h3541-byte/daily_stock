"""
紫金矿业 (601899) 资金流向监控
每天定时跑 → 推送到 PushPlus → 微信
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional

# ---------- 配置 ----------
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")
STOCK_CODE = "601899"
# 上交所股票 secid=1.xxxxx, 深交所 secid=0.xxxxx
SECID = f"1.{STOCK_CODE}"


# ---------- API 请求 ----------
def fetch_json(url: str) -> Optional[dict]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://data.eastmoney.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[ERROR] 请求失败: {e}")
        return None


def get_quote() -> Optional[dict]:
    """获取实时行情 + 当日资金流"""
    url = (
        "https://push2.eastmoney.com/api/qt/stock/get"
        f"?secid={SECID}"
        "&fields=f43,f44,f45,f46,f47,f48,f50,f52,f57,f58,"
        "f60,f116,f117,f162,f167,f168,f169,f170,f171"
    )
    data = fetch_json(url)
    if data and data.get("data"):
        return data["data"]
    return None


def get_fundflow_history(days: int = 5) -> Optional[list]:
    """获取近 N 日资金流历史"""
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
        f"?secid={SECID}"
        "&fields1=f1,f2,f3,f7"
        "&fields2=f51,f52,f53,f54,f55,f56,f57"
    )
    data = fetch_json(url)
    if data and data.get("data") and data["data"].get("klines"):
        klines = data["data"]["klines"]
        result = []
        for line in klines[-days:]:
            parts = line.split(",")
            if len(parts) >= 7:
                result.append({
                    "date": parts[0],
                    "主力净流入": float(parts[1]),
                    "超大单净流入": float(parts[2]),
                    "大单净流入": float(parts[3]),
                    "中单净流入": float(parts[4]),
                    "小单净流入": float(parts[5]),
                })
        return result
    return None


# ---------- 格式化推送消息 ----------
def format_wan(v: float) -> str:
    """以「万元」为单位显示"""
    if abs(v) >= 10000:
        return f"{v / 10000:.2f}亿"
    return f"{v:.0f}万"


def build_message(quote: dict, history: Optional[list]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    name = quote.get("f58", "紫金矿业")
    code = quote.get("f57", STOCK_CODE)
    price = quote.get("f43", 0)
    change_pct = quote.get("f48", 0)
    change_amt = quote.get("f47", 0)
    turnover_rate = quote.get("f52", 0)
    volume_ratio = quote.get("f50", 0)
    high = quote.get("f44", 0)
    low = quote.get("f45", 0)
    open_p = quote.get("f46", 0)
    pre_close = quote.get("f60", 0)

    # 主力资金
    main_flow = quote.get("f162", 0) or 0       # 主力净流入(万元)
    super_large = quote.get("f167", 0) or 0      # 超大单(万元)
    large = quote.get("f168", 0) or 0            # 大单(万元)
    medium = quote.get("f169", 0) or 0           # 中单(万元)
    small = quote.get("f170", 0) or 0            # 小单(万元)
    main_ratio = quote.get("f171", 0) or 0       # 主力净流入占比%

    # 涨跌符号
    symbol = "🔴" if change_pct < 0 else "🟢" if change_pct > 0 else "⚪"

    # 主力资金方向
    flow_symbol = "🟢" if main_flow > 0 else "🔴" if main_flow < 0 else "⚪"
    flow_label = "净流入" if main_flow > 0 else "净流出" if main_flow < 0 else "持平"

    lines = []
    lines.append(f"# ⛏️ {name} ({code}) 资金监控")
    lines.append(f"")
    lines.append(f"> 📅 {now} | 实时")
    lines.append(f"")
    lines.append(f"## 📊 行情")
    lines.append(f"")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|:----|:-----|")
    lines.append(f"| 最新价 | **{price:.2f}** |")
    lines.append(f"| 涨跌幅 | {symbol} **{change_pct:+.2f}%** ({change_amt:+.2f}) |")
    lines.append(f"| 昨收 | {pre_close:.2f} |")
    lines.append(f"| 今开 | {open_p:.2f} |")
    lines.append(f"| 最高 | {high:.2f} |")
    lines.append(f"| 最低 | {low:.2f} |")
    lines.append(f"| 换手率 | {turnover_rate:.2f}% |")
    lines.append(f"| 量比 | {volume_ratio:.2f} |")
    lines.append(f"")
    lines.append(f"## 💰 当日资金流向")
    lines.append(f"")
    lines.append(f"| 类型 | 净流入(万元) |")
    lines.append(f"|:----|:------------|")
    lines.append(f"| {flow_symbol} **主力资金** | **{format_wan(main_flow)}** ({flow_label}, 占比 {main_ratio:.2f}%) |")
    lines.append(f"| 🏆 超大单 | {format_wan(super_large)} |")
    lines.append(f"| 🏅 大单 | {format_wan(large)} |")
    lines.append(f"| 🥈 中单 | {format_wan(medium)} |")
    lines.append(f"| 🥉 小单 | {format_wan(small)} |")
    lines.append(f"")

    if history:
        lines.append(f"## 📈 近{len(history)}日资金趋势")
        lines.append(f"")
        lines.append(f"| 日期 | 主力净流入 | 超大单 | 大单 | 中单 | 小单 |")
        lines.append(f"|:----|:---------|:------|:----|:----|:----|")
        for day in history:
            d = day["date"][5:]  # 去掉年份
            m = day["主力净流入"]
            s = day["超大单净流入"]
            l = day["大单净流入"]
            md = day["中单净流入"]
            sm = day["小单净流入"]
            sym = "🔴" if m < 0 else "🟢" if m > 0 else "⚪"
            lines.append(f"| {d} | {sym} {format_wan(m)} | {format_wan(s)} | {format_wan(l)} | {format_wan(md)} | {format_wan(sm)} |")
        lines.append(f"")

    lines.append(f"---")
    lines.append(f"")
    lines.append(f"> 🤖 自动推送 · 仅供参考，不作投资建议 ⚠️")

    return "\n".join(lines)


# ---------- 推送 PushPlus ----------
def push_to_wechat(title: str, content: str):
    url = "https://www.pushplus.plus/send"
    payload = json.dumps({
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown",
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 200:
                print(f"[OK] 推送成功 ✅")
            else:
                print(f"[WARN] 推送返回: {result}")
    except Exception as e:
        print(f"[ERROR] 推送失败: {e}")


# ---------- 主流程 ----------
def main():
    if not PUSHPLUS_TOKEN:
        print("[ERROR] 未设置 PUSHPLUS_TOKEN 环境变量")
        return

    print(f"[INFO] 获取 {STOCK_CODE} 行情数据...")
    quote = get_quote()
    if not quote:
        print("[ERROR] 获取行情失败")
        push_to_wechat("⚠️ 紫金矿业数据获取失败", "行情接口异常，请检查网络或稍后重试。")
        return

    history = get_fundflow_history(5)

    title = f"⛏️ 紫金矿业资金监控 | {datetime.now().strftime('%m/%d %H:%M')}"
    content = build_message(quote, history)

    push_to_wechat(title, content)
    print("[INFO] 完成 ✅")


if __name__ == "__main__":
    main()

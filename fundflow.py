"""
紫金矿业 (601899) 资金流向监控
数据源: 腾讯财经(主力) → 新浪财经(备用)
"""

import json
import os
import urllib.request
import re
from datetime import datetime
from typing import Optional

# ---------- 配置 ----------
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")
STOCK_CODE = "601899"


# ---------- HTTP 请求 ----------
def get_text(url: str, encoding: str = "gbk") -> Optional[str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode(encoding)
    except Exception as e:
        print(f"  [WARN] 请求失败: {e}")
        return None


# ---------- 数据源 1: 腾讯财经 ----------
def get_tencent() -> Optional[dict]:
    """腾讯财经 - 稳定可靠"""
    raw = get_text(f"https://qt.gtimg.cn/q=sh{STOCK_CODE}")
    if not raw:
        return None
    m = re.search(r'"(.*?)"', raw)
    if not m:
        return None
    p = m.group(1).split("~")
    # 腾讯字段说明(~分隔):
    # 0:market, 1:name, 2:code, 3:price, 4:prev_close, 5:open,
    # 6:volume(手), 7:amount(元),
    # 8~17:5档买卖(弃用)
    # 18:bid1, 19:ask1
    # 20~29:更多买卖(弃用)
    # 30:date, 31:time, 32:status,
    # 33:high, 34:low
    try:
        name = p[1]
        code = p[2]
        price = float(p[3]) if p[3] else 0
        prev_close = float(p[4]) if p[4] else 0
        open_p = float(p[5]) if p[5] else 0
        volume = int(p[6]) if p[6] else 0       # 手
        amount = float(p[7]) if p[7] else 0      # 元
        high = float(p[33]) if len(p) > 33 and p[33] else 0
        low = float(p[34]) if len(p) > 34 and p[34] else 0
        change_amt = round(price - prev_close, 2)
        change_pct = round((change_amt / prev_close * 100), 2) if prev_close else 0

        return {
            "name": name,
            "code": code,
            "price": price,
            "prev_close": prev_close,
            "open": open_p,
            "high": high,
            "low": low,
            "change_amt": change_amt,
            "change_pct": change_pct,
            "volume_shares": volume,         # 手
            "amount_yuan": amount,           # 元
            "source": "tencent",
        }
    except (IndexError, ValueError) as e:
        print(f"  [WARN] 解析腾讯数据失败: {e}")
        return None


# ---------- 数据源 2: 新浪财经 ----------
def get_sina() -> Optional[dict]:
    """新浪财经 - 备用"""
    raw = get_text(f"https://hq.sinajs.cn/list=sh{STOCK_CODE}")
    if not raw:
        return None
    m = re.search(r'"(.*?)"', raw)
    if not m:
        return None
    p = m.group(1).split(",")
    # 新浪字段:
    # 0:name, 1:open, 2:prev_close, 3:price, 4:high, 5:low,
    # 6:buy, 7:sell, 8:volume(手), 9:amount(元)
    try:
        name = p[0]
        prev_close = float(p[2]) if p[2] else 0
        price = float(p[3]) if p[3] else 0
        high = float(p[4]) if p[4] else 0
        low = float(p[5]) if p[5] else 0
        open_p = float(p[1]) if p[1] else 0
        volume = float(p[8]) if p[8] else 0
        amount = float(p[9]) if p[9] else 0
        change_amt = round(price - prev_close, 2)
        change_pct = round((change_amt / prev_close * 100), 2) if prev_close else 0

        return {
            "name": name,
            "code": STOCK_CODE,
            "price": price,
            "prev_close": prev_close,
            "open": open_p,
            "high": high,
            "low": low,
            "change_amt": change_amt,
            "change_pct": change_pct,
            "volume_shares": volume,
            "amount_yuan": amount,
            "source": "sina",
        }
    except (IndexError, ValueError) as e:
        print(f"  [WARN] 解析新浪数据失败: {e}")
        return None


# ---------- 格式化 ----------
def build_message(q: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    src = {"tencent": "腾讯", "sina": "新浪"}.get(q["source"], q["source"])
    symbol = "🔴" if q["change_pct"] < 0 else "🟢" if q["change_pct"] > 0 else "⚪"

    # 成交额单位
    amount = q["amount_yuan"]
    if amount >= 1e8:
        amount_str = f"{amount/1e8:.2f}亿"
    elif amount >= 1e4:
        amount_str = f"{amount/1e4:.0f}万"
    else:
        amount_str = f"{amount:.0f}"

    # 成交量单位
    vol = q["volume_shares"]
    if vol >= 1e8:
        vol_str = f"{vol/1e8:.2f}亿手"
    elif vol >= 1e4:
        vol_str = f"{vol/1e4:.0f}万手"
    else:
        vol_str = f"{vol:.0f}手"

    lines = [
        f"# ⛏️ {q['name']} ({q['code']}) 实时行情",
        "",
        f"> 📅 {now} | 数据源: {src}",
        "",
        "| 指标 | 数值 |",
        "|:----|:-----|",
        f"| 最新价 | **{q['price']:.2f}** |",
        f"| 涨跌幅 | {symbol} **{q['change_pct']:+.2f}%** ({q['change_amt']:+.2f}) |",
        f"| 昨收 | {q['prev_close']:.2f} |",
        f"| 今开 | {q['open']:.2f} |",
        f"| 最高 | {q['high']:.2f} |",
        f"| 最低 | {q['low']:.2f} |",
        f"| 成交量 | {vol_str} |",
        f"| 成交额 | {amount_str} |",
        "",
        "---",
        "",
        "> 🤖 自动推送 · 仅供参考，不作投资建议 ⚠️",
    ]
    return "\n".join(lines)


# ---------- 推送 ----------
def push(title: str, content: str):
    payload = json.dumps({
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://www.pushplus.plus/send",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read().decode("utf-8"))
            print(f"[OK] 推送成功 ✅" if result.get("code") == 200 else f"[WARN] {result}")
    except Exception as e:
        print(f"[ERROR] 推送失败: {e}")


# ---------- 主流程 ----------
def main():
    if not PUSHPLUS_TOKEN:
        print("[ERROR] 未设置 PUSHPLUS_TOKEN")
        return

    print(f"[INFO] 获取 {STOCK_CODE} 数据...")

    q = get_tencent()
    if q:
        print(f"  ✅ 腾讯财经: {q['price']}")
    else:
        q = get_sina()
        if q:
            print(f"  ✅ 新浪财经: {q['price']}")
        else:
            print("[ERROR] 所有数据源失败")
            push("⚠️ 紫金矿业数据获取失败", "所有行情接口均异常，请稍后重试。")
            return

    title = f"⛏️ {q['name']} | {q['price']:.2f} ({q['change_pct']:+.2f}%)"
    content = build_message(q)
    push(title, content)
    print("[INFO] 完成 ✅")


if __name__ == "__main__":
    main()

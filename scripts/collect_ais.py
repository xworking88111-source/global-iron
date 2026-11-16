"""收集鐵礦港口與咽喉要道附近貨船位置的快照。

免費資料：AISStream.io（用 GitHub 登入、建立 API key，不需要信用卡）。

    export AISSTREAM_API_KEY=你的key
    python scripts/collect_ais.py --seconds 300

運作方式
--------
1. 連上 AISStream 的 WebSocket，訂閱 data/static/geo_layers.json 中每個港口與
   咽喉要道的範圍框（以及 fleet.json 裡的 MMSI）。
2. 收聽 N 秒。船舶每幾秒到幾分鐘廣播一次位置，靜態資料（船名、船型、目的地）
   約每 6 分鐘一次，所以收 5–10 分鐘就能得到合理的快照。
3. 每艘船只保留最新位置；已知船型且不是貨船的剔除；統計各區域船數；
   寫入 data/cache/ais_snapshot.json。

限制：只有岸基 AIS（沿岸涵蓋）；AIS 無法得知船上載什麼貨。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config, data  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("ais")

WS_URL = "wss://stream.aisstream.io/v0/stream"
PORT_BOX_DEG = 0.6  # 港口範圍框的半寬（約 65 公里）

# AIS 船型代碼：70–79 = 貨船，80–89 = 油輪。散裝船回報的是 70–79。
CARGO_TYPES = range(70, 80)


def build_zones() -> list[dict]:
    """區域 = 每個港口周圍的方框 + JSON 裡咽喉要道的範圍框。

    港口放前面：港口框比較小，而 zone_of() 回傳第一個符合的區域，
    所以停在高雄港的船會算成「高雄」，而不是「台灣海峽」。
    """
    geo = data.geo_layers()
    zones = []
    for p in geo.get("ports", []):
        d = PORT_BOX_DEG
        zones.append({"id": p["id"], "name": p["en"],
                      "box": [[p["lat"] - d, p["lon"] - d], [p["lat"] + d, p["lon"] + d]]})
    for c in geo.get("chokepoints", []):
        (lat1, lon1), (lat2, lon2) = c["box"]
        zones.append({"id": c["id"], "name": c["en"], "box": [[lat1, lon1], [lat2, lon2]]})
    return zones


def zone_of(lat: float, lon: float, zones: list[dict]) -> str | None:
    """經緯度落在哪個區域（都不在則回傳 None）。"""
    for z in zones:
        (a, b), (c, d) = z["box"]
        if min(a, c) <= lat <= max(a, c) and min(b, d) <= lon <= max(b, d):
            return z["name"]
    return None


async def collect(api_key: str, seconds: int) -> dict:
    """連線收聽 `seconds` 秒，回傳快照內容。"""
    import websockets  # pip install websockets

    zones = build_zones()
    fleet = {int(v["mmsi"]): v for v in data.fleet() if v.get("mmsi")}
    sub = {
        "APIKey": api_key,
        "BoundingBoxes": [z["box"] for z in zones],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }
    ships: dict[int, dict] = {}     # 每艘船（MMSI）的最新位置
    static: dict[int, dict] = {}    # 每艘船的船名／船型／目的地
    deadline = time.monotonic() + seconds
    n_msgs = 0

    async with websockets.connect(WS_URL, open_timeout=30) as ws:
        await ws.send(json.dumps(sub))
        log.info("subscribed to %d zones, listening %ds", len(zones), seconds)
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(1, deadline - time.monotonic()))
            except asyncio.TimeoutError:
                break
            msg = json.loads(raw)
            if "error" in msg:
                raise RuntimeError(msg["error"])
            n_msgs += 1
            meta = msg.get("MetaData", {})
            mmsi = meta.get("MMSI")
            if not mmsi:
                continue
            body = msg.get("Message", {})
            if msg.get("MessageType") == "ShipStaticData":
                sd = body.get("ShipStaticData", {})
                static[mmsi] = {"type": sd.get("Type"), "destination": (sd.get("Destination") or "").strip(),
                                "name": (sd.get("Name") or "").strip()}
                continue
            pr = body.get("PositionReport", {})
            lat, lon = meta.get("latitude"), meta.get("longitude")
            if lat is None or lon is None:
                continue
            ships[mmsi] = {"mmsi": mmsi, "name": (meta.get("ShipName") or "").strip(), "lat": round(lat, 4),
                           "lon": round(lon, 4), "sog": pr.get("Sog"), "cog": pr.get("Cog"),
                           "nav_status": pr.get("NavigationalStatus"), "time": meta.get("time_utc", "")}
    log.info("received %d messages, %d ships", n_msgs, len(ships))

    out = []
    for mmsi, s in ships.items():
        st = static.get(mmsi, {})
        typ = st.get("type")
        tracked = mmsi in fleet
        # 保留：追蹤名單的船、已知是貨船的、以及還沒收到船型資料的
        if not tracked and typ is not None and typ not in CARGO_TYPES:
            continue
        s.update({"type": typ, "destination": st.get("destination"), "zone": zone_of(s["lat"], s["lon"], zones),
                  "tracked": tracked})
        if st.get("name") and not s["name"]:
            s["name"] = st["name"]
        if tracked:
            s["operator"] = fleet[mmsi].get("operator_en")
        out.append(s)

    counts: dict[str, int] = {}
    for s in out:
        if s["zone"]:
            counts[s["zone"]] = counts.get(s["zone"], 0) + 1
    return {"collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "listen_seconds": seconds, "messages": n_msgs, "zone_counts": counts, "vessels": out}


def main():
    """命令列入口：讀取 API key、收集、寫檔。"""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=int, default=300, help="how long to listen (default 300)")
    args = ap.parse_args()
    key = os.environ.get("AISSTREAM_API_KEY")
    if not key:
        sys.exit("Set AISSTREAM_API_KEY first (free key at https://aisstream.io).")
    snap = asyncio.run(collect(key, args.seconds))
    config.AIS_FILE.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    log.info("wrote %s (%d vessels, %d zones)", config.AIS_FILE, len(snap["vessels"]), len(snap["zone_counts"]))


if __name__ == "__main__":
    main()

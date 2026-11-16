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

追蹤特定船隊（例如中鋼運通）：
    python scripts/collect_ais.py --discover-fleet --seconds 600
會用船名找出 fleet.json 裡各船的 MMSI 並寫回；之後一般收集就會全球追蹤這些船。

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


WORLD_BOX = [[-90, -180], [90, 180]]


def normalize_name(name: str | None) -> str:
    """AIS 船名正規化：轉大寫、去頭尾空白、多個空格合成一個，方便比對。"""
    return " ".join((name or "").upper().split())


async def _listen(api_key: str, sub: dict, seconds: int, handle) -> int:
    """收聽 `seconds` 秒，每則訊息交給 handle(msg)。回傳收到的訊息數。

    伺服器偶爾會斷線：只要時間還沒到就自動重連（最多 5 次）。
    若一連上就被斷線、一則訊息都沒收到，幾乎都是金鑰無效，直接報錯說明。
    """
    import websockets  # pip install websockets

    deadline = time.monotonic() + seconds
    n = 0
    for attempt in range(1, 6):
        try:
            async with websockets.connect(WS_URL, open_timeout=30, max_size=None, ping_interval=20) as ws:
                await ws.send(json.dumps({"APIKey": api_key, **sub}))
                while time.monotonic() < deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=max(1, deadline - time.monotonic()))
                    except asyncio.TimeoutError:
                        return n
                    msg = json.loads(raw)
                    if "error" in msg:
                        raise RuntimeError(f"AISStream error: {msg['error']}")
                    n += 1
                    handle(msg)
            return n
        except websockets.ConnectionClosed as e:
            code = e.rcvd.code if e.rcvd else None
            reason = e.rcvd.reason if e.rcvd else ""
            log.warning("connection closed (attempt %d, code=%s, reason=%r, messages so far=%d)",
                        attempt, code, reason, n)
            if n == 0:
                raise RuntimeError(
                    "AISStream closed the connection before sending any data. "
                    "This almost always means the API key is invalid: check the key at "
                    "https://aisstream.io/account and re-save the AISSTREAM_API_KEY secret."
                ) from e
            if time.monotonic() >= deadline:
                return n
            await asyncio.sleep(2 * attempt)  # 稍等再重連
    return n


async def collect(api_key: str, seconds: int) -> dict:
    """同時開兩條連線收聽 `seconds` 秒：
    1. 區域連線：港口與咽喉要道範圍內的所有船（看壅塞與活動）
    2. 船隊連線：fleet.json 裡已知 MMSI 的船，全球範圍追蹤（MMSI 未知的船靠船名比對）
    """
    zones = build_zones()
    fleet_list = data.fleet()
    fleet_by_mmsi = {int(v["mmsi"]): v for v in fleet_list if v.get("mmsi")}
    fleet_by_name = {normalize_name(v["name"]): v for v in fleet_list}

    ships: dict[int, dict] = {}     # 每艘船（MMSI）的最新位置
    static: dict[int, dict] = {}    # 每艘船的船名／船型／目的地

    def handle(msg: dict) -> None:
        meta = msg.get("MetaData", {})
        mmsi = meta.get("MMSI")
        if not mmsi:
            return
        body = msg.get("Message", {})
        if msg.get("MessageType") == "ShipStaticData":
            sd = body.get("ShipStaticData", {})
            static[mmsi] = {"type": sd.get("Type"), "destination": (sd.get("Destination") or "").strip(),
                            "name": (sd.get("Name") or "").strip()}
            return
        pr = body.get("PositionReport", {})
        lat, lon = meta.get("latitude"), meta.get("longitude")
        if lat is None or lon is None:
            return
        ships[mmsi] = {"mmsi": mmsi, "name": (meta.get("ShipName") or "").strip(), "lat": round(lat, 4),
                       "lon": round(lon, 4), "sog": pr.get("Sog"), "cog": pr.get("Cog"),
                       "nav_status": pr.get("NavigationalStatus"), "time": meta.get("time_utc", "")}

    msg_types = ["PositionReport", "ShipStaticData"]
    tasks = [_listen(api_key, {"BoundingBoxes": [z["box"] for z in zones], "FilterMessageTypes": msg_types},
                     seconds, handle)]
    if fleet_by_mmsi:
        # AISStream 一條連線最多可過濾 50 個 MMSI
        mmsis = [str(m) for m in list(fleet_by_mmsi)[:50]]
        tasks.append(_listen(api_key, {"BoundingBoxes": [WORLD_BOX], "FiltersShipMMSI": mmsis,
                                       "FilterMessageTypes": msg_types}, seconds, handle))
    log.info("listening %ds: %d zones, %d fleet MMSIs tracked worldwide", seconds, len(zones), len(fleet_by_mmsi))
    counts_msgs = await asyncio.gather(*tasks)
    n_msgs = sum(counts_msgs)
    log.info("received %d messages, %d ships", n_msgs, len(ships))

    out = []
    for mmsi, s in ships.items():
        st = static.get(mmsi, {})
        if st.get("name") and not s["name"]:
            s["name"] = st["name"]
        f = fleet_by_mmsi.get(mmsi) or fleet_by_name.get(normalize_name(s["name"]))
        typ = st.get("type")
        # 保留：追蹤名單的船、已知是貨船的、以及還沒收到船型資料的
        if not f and typ is not None and typ not in CARGO_TYPES:
            continue
        s.update({"type": typ, "destination": st.get("destination"), "zone": zone_of(s["lat"], s["lon"], zones),
                  "tracked": bool(f)})
        if f:
            s.update({"operator_en": f.get("operator_en"), "operator_zh": f.get("operator_zh"),
                      "name_zh": f.get("name_zh"), "linked_company": f.get("linked_company")})
        out.append(s)

    # 各區域船數：zone_counts = 全部（含尚未回報船型的船），cargo_counts = 已確認是貨船的
    # 船型資料約 6 分鐘才廣播一次，收聽時間內很多船還沒回報，所以兩個數字都保留
    counts: dict[str, int] = {}
    cargo: dict[str, int] = {}
    for s in out:
        if s["zone"]:
            counts[s["zone"]] = counts.get(s["zone"], 0) + 1
            if s.get("type") in CARGO_TYPES:
                cargo[s["zone"]] = cargo.get(s["zone"], 0) + 1
    return {"collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "listen_seconds": seconds, "messages": n_msgs, "zone_counts": counts, "cargo_counts": cargo,
            "vessels": out}


def save_fleet_mmsis(vessels: list[dict]) -> int:
    """快照中靠「船名」比對到的船隊船舶，把 MMSI 寫回 fleet.json，下次就能全球追蹤。"""
    path = config.STATIC_DIR / "fleet.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    by_name = {normalize_name(v["name"]): v for v in doc["vessels"] if not v.get("mmsi")}
    added = 0
    for s in vessels:
        f = by_name.get(normalize_name(s.get("name"))) if s.get("tracked") else None
        if f and not f.get("mmsi"):
            f["mmsi"] = int(s["mmsi"])
            added += 1
            log.info("fleet: %s -> MMSI %s (matched by name)", f["name"], f["mmsi"])
    if added:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


async def discover_fleet(api_key: str, seconds: int) -> int:
    """找出 fleet.json 中還沒有 MMSI 的船，並把找到的 MMSI 寫回 fleet.json。

    做法：訂閱「全球」的船舶靜態資料（船名、船型），用船名比對。
    船舶約每 6 分鐘廣播一次靜態資料，且只有船在岸基接收站範圍內才收得到，
    所以一次不一定找齊；多跑幾次（例如每天排程順便跑）就會陸續補上。
    """
    path = config.STATIC_DIR / "fleet.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    wanted = {normalize_name(v["name"]): v for v in doc["vessels"] if not v.get("mmsi")}
    if not wanted:
        log.info("all fleet vessels already have an MMSI")
        return 0
    found: dict[str, int] = {}

    def handle(msg: dict) -> None:
        sd = msg.get("Message", {}).get("ShipStaticData", {})
        name = normalize_name(sd.get("Name") or msg.get("MetaData", {}).get("ShipName"))
        if name in wanted and name not in found:
            found[name] = int(msg["MetaData"]["MMSI"])
            log.info("found %s -> MMSI %s", name, found[name])

    log.info("discovering %d vessels for %ds (global static data)", len(wanted), seconds)
    await _listen(api_key, {"BoundingBoxes": [WORLD_BOX], "FilterMessageTypes": ["ShipStaticData"]}, seconds, handle)
    for name, mmsi in found.items():
        wanted[name]["mmsi"] = mmsi
    if found:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log.info("discovered %d / %d vessels", len(found), len(wanted))
    return len(found)


def main():
    """命令列入口：讀取 API key，執行收集（或船隊探索），寫檔。"""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=int, default=300, help="how long to listen (default 300)")
    ap.add_argument("--discover-fleet", action="store_true",
                    help="find MMSIs for fleet.json vessels by name, then exit")
    args = ap.parse_args()
    key = os.environ.get("AISSTREAM_API_KEY")
    if not key:
        sys.exit("Set AISSTREAM_API_KEY first (free key at https://aisstream.io).")
    if args.discover_fleet:
        asyncio.run(discover_fleet(key, args.seconds))
        return
    snap = asyncio.run(collect(key, args.seconds))
    config.AIS_FILE.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    log.info("wrote %s (%d vessels, %d zones)", config.AIS_FILE, len(snap["vessels"]), len(snap["zone_counts"]))
    save_fleet_mmsis(snap["vessels"])


if __name__ == "__main__":
    main()

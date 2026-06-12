"""JPN Government states actor primitives.

This module moves the `did:web:jpn-state.etzhayyim.com` app actor off its
dedicated Cloudflare Worker path. The public edge keeps only XRPC/MCP
facade duties; these functions run as Zeebe jobs in Kubernetes and write
the same graph-visible state the Worker previously wrote via host-sdk.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import time
import urllib.error as _u_err
import urllib.request as _u_req
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


PRIMARY_DID = "did:web:jpn-state.etzhayyim.com"
DOMAIN_CODE = "jpn"
SITE_NANOID = "w3bpg001"
SITE_GOV_TOPIC_DID = "did:web:site.etzhayyim.com:topic:government"
PDS_BASE = os.environ.get("PDS_URL", "https://atproto.etzhayyim.com")
PDS_SERVICE_AUTH_TOKEN = os.environ.get("PDS_SERVICE_AUTH_TOKEN", "").strip()
PDS_SERVICE_AUTH_MINT_URL = os.environ.get(
    "PDS_SERVICE_AUTH_MINT_URL",
    f"{PDS_BASE}/_internal/mint-pds-bearer",
).strip()
PDS_SERVICE_AUTH_MINT_SECRET = os.environ.get("PDS_SERVICE_AUTH_MINT_SECRET", "").strip()
PDS_LEGACY_INTERNAL_TRUST = os.environ.get("PDS_LEGACY_INTERNAL_TRUST", "0") == "1"
try:
    PDS_SERVICE_AUTH_TTL_SEC = int(os.environ.get("PDS_SERVICE_AUTH_TTL_SEC", "600"))
except ValueError:
    PDS_SERVICE_AUTH_TTL_SEC = 600
PDS_SERVICE_AUTH_TTL_SEC = max(30, min(600, PDS_SERVICE_AUTH_TTL_SEC))
_PDS_SERVICE_AUTH_CACHE: dict[str, dict[str, Any]] = {}

_MINISTRY_NDJSON = """\
{"path":"cao","name":"内閣府","nameEn":"Cabinet Office","website":"https://www.cao.go.jp/","contract":"内閣府設置法","tags":["cofog:01","executive","ai-strategy","digital-policy"],"orgTier":"ministry"}
{"path":"cao:digital","name":"デジタル庁","nameEn":"Digital Agency","website":"https://www.digital.go.jp/","contract":"デジタル庁設置法","tags":["cofog:01","digital-transformation","mynumber"],"orgTier":"agency"}
{"path":"cao:ai-strategy-council","name":"AI戦略会議","nameEn":"AI Strategy Council","website":"https://www.cao.go.jp/","contract":"内閣府設置法","tags":["cofog:01","ai-strategy","digital-policy"],"orgTier":"executive"}
{"path":"cao:cybersecurity-strategy-hq","name":"サイバーセキュリティ戦略本部","nameEn":"Cybersecurity Strategy Headquarters","website":"https://www.nisc.go.jp/","contract":"サイバーセキュリティ基本法","tags":["cofog:01","cybersecurity"],"orgTier":"executive"}
{"path":"cao:aisi","name":"AI安全研究所","nameEn":"AI Safety Institute","website":"https://aisi.go.jp/","contract":"内閣府設置法","tags":["cofog:01","ai-safety"],"orgTier":"agency"}
{"path":"cao:digital:next-mynumber-card-taskforce","name":"次世代マイナンバーカードタスクフォース","nameEn":"Next-Gen My Number Card Task Force","website":"https://www.digital.go.jp/","contract":"デジタル庁設置法","tags":["cofog:01","digital-transformation","mynumber"],"orgTier":"executive"}
{"path":"mic","name":"総務省","nameEn":"Ministry of Internal Affairs and Communications","website":"https://www.soumu.go.jp/","contract":"総務省設置法","tags":["cofog:01","telecommunications","local-government","statistics"],"orgTier":"ministry"}
{"path":"mic:joho:cybersecurity-taskforce","name":"サイバーセキュリティタスクフォース (総務省)","nameEn":"MIC Cybersecurity Task Force","website":"https://www.soumu.go.jp/","contract":"総務省設置法","tags":["cofog:01","cybersecurity","telecommunications"],"orgTier":"executive"}
{"path":"moj","name":"法務省","nameEn":"Ministry of Justice","website":"https://www.moj.go.jp/","contract":"法務省設置法","tags":["cofog:03","justice","immigration","human-rights"],"orgTier":"ministry"}
{"path":"mofa","name":"外務省","nameEn":"Ministry of Foreign Affairs","website":"https://www.mofa.go.jp/","contract":"外務省設置法","tags":["cofog:01.2","diplomacy","international-relations"],"orgTier":"ministry"}
{"path":"mof","name":"財務省","nameEn":"Ministry of Finance","website":"https://www.mof.go.jp/","contract":"財務省設置法","tags":["cofog:01.1","finance","taxation","budget"],"orgTier":"ministry"}
{"path":"mof:nta","name":"国税庁","nameEn":"National Tax Agency","website":"https://www.nta.go.jp/","contract":"国税庁設置法","tags":["cofog:01.1","taxation"],"orgTier":"agency"}
{"path":"mof:nta:choushuu","name":"国税庁徴収部","nameEn":"NTA Collection Bureau","website":"https://www.nta.go.jp/","contract":"国税徴収法","tags":["cofog:01.1","taxation","choushuu","taino-shobun"],"orgTier":"bureau"}
{"path":"mof:nta:choushuu:sashiosae","name":"差押管理室","nameEn":"NTA Seizure Administration","website":"https://www.nta.go.jp/","contract":"国税徴収法","tags":["cofog:01.1","taxation","sashiosae"],"orgTier":"division"}
{"path":"mof:nta:choushuu:kanka","name":"換価・公売室","nameEn":"NTA Public Auction Division","website":"https://www.koubai.nta.go.jp/","contract":"国税徴収法","tags":["cofog:01.1","taxation","kanka","public-auction"],"orgTier":"division"}
{"path":"mof:nta:choushuu:haitou","name":"配当・充当室","nameEn":"NTA Allocation Division","website":"https://www.nta.go.jp/","contract":"国税徴収法","tags":["cofog:01.1","taxation","haitou"],"orgTier":"division"}
{"path":"sashiosae","name":"差押 Aggregator","nameEn":"Seizure Intelligence Aggregator","website":"https://jpn-state.etzhayyim.com/sashiosae","contract":"国税徴収法・地方税法・民事執行法・刑事訴訟法","tags":["cofog:01.1","cofog:03","sashiosae","aggregator","cross-regime"],"orgTier":"executive"}
{"path":"mext","name":"文部科学省","nameEn":"Ministry of Education, Culture, Sports, Science and Technology","website":"https://www.mext.go.jp/","contract":"文部科学省設置法","tags":["cofog:09","education","science","culture","sports"],"orgTier":"ministry"}
{"path":"mhlw","name":"厚生労働省","nameEn":"Ministry of Health, Labour and Welfare","website":"https://www.mhlw.go.jp/","contract":"厚生労働省設置法","tags":["cofog:07","health","labour","social-welfare"],"orgTier":"ministry"}
{"path":"maff","name":"農林水産省","nameEn":"Ministry of Agriculture, Forestry and Fisheries","website":"https://www.maff.go.jp/","contract":"農林水産省設置法","tags":["cofog:04.2","agriculture","forestry","fisheries"],"orgTier":"ministry"}
{"path":"meti","name":"経済産業省","nameEn":"Ministry of Economy, Trade and Industry","website":"https://www.meti.go.jp/","contract":"経済産業省設置法","tags":["cofog:04","economy","trade","industry","semiconductor"],"orgTier":"ministry"}
{"path":"meti:jpo","name":"特許庁","nameEn":"Japan Patent Office","website":"https://www.jpo.go.jp/","contract":"特許庁設置法","tags":["cofog:04","intellectual-property","patents"],"orgTier":"agency"}
{"path":"meti:semiconductor-digital-strategy","name":"半導体・デジタル産業戦略","nameEn":"Semiconductor and Digital Industry Strategy","website":"https://www.meti.go.jp/","contract":"経済産業省設置法","tags":["cofog:04","semiconductor","digital-industry"],"orgTier":"executive"}
{"path":"mlit","name":"国土交通省","nameEn":"Ministry of Land, Infrastructure, Transport and Tourism","website":"https://www.mlit.go.jp/","contract":"国土交通省設置法","tags":["cofog:04.5","infrastructure","transport","tourism","urban-planning"],"orgTier":"ministry"}
{"path":"mlit:jma","name":"気象庁","nameEn":"Japan Meteorological Agency","website":"https://www.jma.go.jp/","contract":"気象業務法","tags":["cofog:04","meteorology","disaster-prevention"],"orgTier":"agency"}
{"path":"moe","name":"環境省","nameEn":"Ministry of the Environment","website":"https://www.env.go.jp/","contract":"環境省設置法","tags":["cofog:05","environment","climate","biodiversity"],"orgTier":"ministry"}
{"path":"mod","name":"防衛省","nameEn":"Ministry of Defense","website":"https://www.mod.go.jp/","contract":"防衛省設置法","tags":["cofog:02","defense","self-defense-forces"],"orgTier":"ministry"}
{"path":"npa","name":"警察庁","nameEn":"National Police Agency","website":"https://www.npa.go.jp/","contract":"警察法","tags":["cofog:03.1","police","public-safety","cybersecurity"],"orgTier":"agency"}
"""

_STATE_NDJSON = """\
{"path":"prefecture:hokkaido","name":"北海道","nameEn":"Hokkaido","adminCode":"01","population":5224614,"headquarters":"札幌市","website":"https://www.pref.hokkaido.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:aomori","name":"青森県","nameEn":"Aomori","adminCode":"02","population":1237984,"headquarters":"青森市","website":"https://www.pref.aomori.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:iwate","name":"岩手県","nameEn":"Iwate","adminCode":"03","population":1210534,"headquarters":"盛岡市","website":"https://www.pref.iwate.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:miyagi","name":"宮城県","nameEn":"Miyagi","adminCode":"04","population":2301996,"headquarters":"仙台市","website":"https://www.pref.miyagi.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:akita","name":"秋田県","nameEn":"Akita","adminCode":"05","population":959502,"headquarters":"秋田市","website":"https://www.pref.akita.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:yamagata","name":"山形県","nameEn":"Yamagata","adminCode":"06","population":1068027,"headquarters":"山形市","website":"https://www.pref.yamagata.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:fukushima","name":"福島県","nameEn":"Fukushima","adminCode":"07","population":1833152,"headquarters":"福島市","website":"https://www.pref.fukushima.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:ibaraki","name":"茨城県","nameEn":"Ibaraki","adminCode":"08","population":2867009,"headquarters":"水戸市","website":"https://www.pref.ibaraki.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:tochigi","name":"栃木県","nameEn":"Tochigi","adminCode":"09","population":1933146,"headquarters":"宇都宮市","website":"https://www.pref.tochigi.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:gunma","name":"群馬県","nameEn":"Gunma","adminCode":"10","population":1939110,"headquarters":"前橋市","website":"https://www.pref.gunma.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:saitama","name":"埼玉県","nameEn":"Saitama","adminCode":"11","population":7344765,"headquarters":"さいたま市","website":"https://www.pref.saitama.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:chiba","name":"千葉県","nameEn":"Chiba","adminCode":"12","population":6284480,"headquarters":"千葉市","website":"https://www.pref.chiba.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:tokyo","name":"東京都","nameEn":"Tokyo","adminCode":"13","population":14047594,"headquarters":"新宿区","website":"https://www.metro.tokyo.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5","metropolis"],"orgTier":"prefecture"}
{"path":"prefecture:kanagawa","name":"神奈川県","nameEn":"Kanagawa","adminCode":"14","population":9237337,"headquarters":"横浜市","website":"https://www.pref.kanagawa.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:niigata","name":"新潟県","nameEn":"Niigata","adminCode":"15","population":2201272,"headquarters":"新潟市","website":"https://www.pref.niigata.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:toyama","name":"富山県","nameEn":"Toyama","adminCode":"16","population":1034814,"headquarters":"富山市","website":"https://www.pref.toyama.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:ishikawa","name":"石川県","nameEn":"Ishikawa","adminCode":"17","population":1132526,"headquarters":"金沢市","website":"https://www.pref.ishikawa.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:fukui","name":"福井県","nameEn":"Fukui","adminCode":"18","population":766863,"headquarters":"福井市","website":"https://www.pref.fukui.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:yamanashi","name":"山梨県","nameEn":"Yamanashi","adminCode":"19","population":809974,"headquarters":"甲府市","website":"https://www.pref.yamanashi.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:nagano","name":"長野県","nameEn":"Nagano","adminCode":"20","population":2048011,"headquarters":"長野市","website":"https://www.pref.nagano.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:gifu","name":"岐阜県","nameEn":"Gifu","adminCode":"21","population":1978742,"headquarters":"岐阜市","website":"https://www.pref.gifu.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:shizuoka","name":"静岡県","nameEn":"Shizuoka","adminCode":"22","population":3633202,"headquarters":"静岡市","website":"https://www.pref.shizuoka.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:aichi","name":"愛知県","nameEn":"Aichi","adminCode":"23","population":7542415,"headquarters":"名古屋市","website":"https://www.pref.aichi.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:mie","name":"三重県","nameEn":"Mie","adminCode":"24","population":1770254,"headquarters":"津市","website":"https://www.pref.mie.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:shiga","name":"滋賀県","nameEn":"Shiga","adminCode":"25","population":1413610,"headquarters":"大津市","website":"https://www.pref.shiga.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:kyoto","name":"京都府","nameEn":"Kyoto","adminCode":"26","population":2578087,"headquarters":"京都市","website":"https://www.pref.kyoto.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:osaka","name":"大阪府","nameEn":"Osaka","adminCode":"27","population":8837685,"headquarters":"大阪市","website":"https://www.pref.osaka.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:hyogo","name":"兵庫県","nameEn":"Hyogo","adminCode":"28","population":5465002,"headquarters":"神戸市","website":"https://web.pref.hyogo.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:nara","name":"奈良県","nameEn":"Nara","adminCode":"29","population":1324473,"headquarters":"奈良市","website":"https://www.pref.nara.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:wakayama","name":"和歌山県","nameEn":"Wakayama","adminCode":"30","population":922584,"headquarters":"和歌山市","website":"https://www.pref.wakayama.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:tottori","name":"鳥取県","nameEn":"Tottori","adminCode":"31","population":553407,"headquarters":"鳥取市","website":"https://www.pref.tottori.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:shimane","name":"島根県","nameEn":"Shimane","adminCode":"32","population":671126,"headquarters":"松江市","website":"https://www.pref.shimane.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:okayama","name":"岡山県","nameEn":"Okayama","adminCode":"33","population":1888432,"headquarters":"岡山市","website":"https://www.pref.okayama.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:hiroshima","name":"広島県","nameEn":"Hiroshima","adminCode":"34","population":2799702,"headquarters":"広島市","website":"https://www.pref.hiroshima.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:yamaguchi","name":"山口県","nameEn":"Yamaguchi","adminCode":"35","population":1342059,"headquarters":"山口市","website":"https://www.pref.yamaguchi.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:tokushima","name":"徳島県","nameEn":"Tokushima","adminCode":"36","population":719559,"headquarters":"徳島市","website":"https://www.pref.tokushima.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:kagawa","name":"香川県","nameEn":"Kagawa","adminCode":"37","population":950244,"headquarters":"高松市","website":"https://www.pref.kagawa.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:ehime","name":"愛媛県","nameEn":"Ehime","adminCode":"38","population":1334841,"headquarters":"松山市","website":"https://www.pref.ehime.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:kochi","name":"高知県","nameEn":"Kochi","adminCode":"39","population":691527,"headquarters":"高知市","website":"https://www.pref.kochi.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:fukuoka","name":"福岡県","nameEn":"Fukuoka","adminCode":"40","population":5135214,"headquarters":"福岡市","website":"https://www.pref.fukuoka.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:saga","name":"佐賀県","nameEn":"Saga","adminCode":"41","population":811442,"headquarters":"佐賀市","website":"https://www.pref.saga.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:nagasaki","name":"長崎県","nameEn":"Nagasaki","adminCode":"42","population":1312317,"headquarters":"長崎市","website":"https://www.pref.nagasaki.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:kumamoto","name":"熊本県","nameEn":"Kumamoto","adminCode":"43","population":1738301,"headquarters":"熊本市","website":"https://www.pref.kumamoto.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:oita","name":"大分県","nameEn":"Oita","adminCode":"44","population":1123852,"headquarters":"大分市","website":"https://www.pref.oita.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:miyazaki","name":"宮崎県","nameEn":"Miyazaki","adminCode":"45","population":1069576,"headquarters":"宮崎市","website":"https://www.pref.miyazaki.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:kagoshima","name":"鹿児島県","nameEn":"Kagoshima","adminCode":"46","population":1588256,"headquarters":"鹿児島市","website":"https://www.pref.kagoshima.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
{"path":"prefecture:okinawa","name":"沖縄県","nameEn":"Okinawa","adminCode":"47","population":1467480,"headquarters":"那覇市","website":"https://www.pref.okinawa.lg.jp/","contract":"地方自治法","tags":["cofog:01","prefecture","l5"],"orgTier":"prefecture"}
"""


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _url_to_domain_slug(url: str) -> str:
    try:
        host = re.sub(r"^https?://", "", url).split("/", 1)[0]
        host = re.sub(r"^(www|web)\.", "", host)
        return host.replace(".", "-")
    except Exception:
        return ""


def _load_seed_orgs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for blob in (_MINISTRY_NDJSON, _STATE_NDJSON):
        for line in blob.splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _vertex_id(path: str) -> str:
    return f"at://{PRIMARY_DID}/com.etzhayyim.apps.states.govOrg/{path}"


def _repo_rkey(prefix: str, key: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S%f")
    safe = re.sub(r"[^a-zA-Z0-9._~-]+", "-", key).strip("-")[:80] or "record"
    return f"{prefix}-{safe}-{stamp}"


def _http_post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    merged_headers = {
        "User-Agent": "etzhayyim-kotodama-gov-afg/0.1",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    merged_headers.update(headers)
    req = _u_req.Request(url, data=body, headers=merged_headers, method="POST")
    try:
        with _u_req.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = int(resp.status)
    except _u_err.HTTPError as e:
        raw = e.read()
        status = int(e.code)
    except Exception as e:  # noqa: BLE001
        return {"status": -1, "body": {"error": f"transport: {e}"}}
    try:
        parsed: Any = json.loads(raw.decode("utf-8"))
    except Exception:
        parsed = {"raw": raw.decode("utf-8", errors="replace")[:500]}
    return {"status": status, "body": parsed}


def _mint_pds_service_auth(lxm: str) -> str:
    cached = _PDS_SERVICE_AUTH_CACHE.get(lxm)
    now = int(time.time())
    if cached and int(cached.get("expiresAt", 0)) > now + 30:
        token = str(cached.get("token") or "")
        if token:
            return token
    if not PDS_SERVICE_AUTH_MINT_URL or not PDS_SERVICE_AUTH_MINT_SECRET:
        return ""
    payload = {"lxm": lxm, "ttlSeconds": PDS_SERVICE_AUTH_TTL_SEC}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(PDS_SERVICE_AUTH_MINT_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    req = _u_req.Request(
        PDS_SERVICE_AUTH_MINT_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-bpmn-auth": sig,
        },
        method="POST",
    )
    try:
        with _u_req.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return ""
    token = str(data.get("token") or "")
    expires_at = int(data.get("expiresAt") or (now + PDS_SERVICE_AUTH_TTL_SEC))
    if token:
        _PDS_SERVICE_AUTH_CACHE[lxm] = {"token": token, "expiresAt": expires_at}
    return token


async def _pds_xrpc(lxm: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = await asyncio.to_thread(_mint_pds_service_auth, lxm)
    bearer = token or PDS_SERVICE_AUTH_TOKEN
    headers: dict[str, str] = {}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    elif PDS_LEGACY_INTERNAL_TRUST:
        headers["x-kotoba-kotodama-verified"] = "true"
    else:
        return {"status": 401, "body": {"error": "PDS service auth unavailable"}}
    return await asyncio.to_thread(_http_post_json, f"{PDS_BASE}/xrpc/{lxm}", payload, headers)


def _insert_repo_record(repo: str, collection: str, rkey: str, record: dict[str, Any]) -> str:
    created_at = str(record.get("createdAt") or _utc_now_iso())
    uri = f"at://{repo}/{collection}/{rkey}"
    if collection != "app.bsky.feed.post":
        value_json = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
        if collection == "actorManifest":
            path = str(record.get("path") or rkey)
            params = {
                "vertex_id": uri,
                "record_key": rkey,
                "record_kind": collection,
                "path": path,
                "country": str(record.get("country") or DOMAIN_CODE),
                "display_name": str(record.get("displayName") or ""),
                "description": str(record.get("description") or ""),
                "performer_type": str(record.get("performerType") or ""),
                "agent_type": str(record.get("agentType") or ""),
                "is_bot": bool(record.get("isBot") or False),
                "value_json": value_json,
                "indexed_at": created_at,
                "created_at": created_at,
                "updated_at": str(record.get("updated_at") or created_at),
                "actor_did": repo,
                "org_did": repo,
                "owner_did": PRIMARY_DID,
                "sensitivity_ord": 2,
            }
            get_kotoba_client().insert_row("vertex_gov_actor_manifest", params)
            return uri
        if collection == "com.etzhayyim.apps.states.govOrgSiteDep":
            path = str(record.get("path") or "")
            site_did = str(record.get("siteDid") or "")
            params = {
                "edge_id": uri,
                "record_key": rkey,
                "from_vertex_id": _vertex_id(path) if path else repo,
                "to_vertex_id": site_did,
                "path": path,
                "site_nanoid": str(record.get("siteNanoid") or ""),
                "site_topic_did": str(record.get("siteTopicDid") or ""),
                "site_did": site_did,
                "value_json": value_json,
                "indexed_at": created_at,
                "created_at": created_at,
                "updated_at": str(record.get("updated_at") or created_at),
                "actor_did": repo,
                "org_did": str(record.get("orgId") or "anon"),
                "owner_did": repo,
                "sensitivity_ord": 2,
            }
            get_kotoba_client().insert_row("edge_gov_org_site_dependency", params)
            return uri
        raise ValueError(f"unsupported gov collection: {collection!r}")
    params = {
        "vertex_id": uri,
        "record_kind": collection,
        "record_key": rkey,
        "label": "GovRecord",
        "status": "active",
        "value_json": json.dumps(record, separators=(",", ":"), ensure_ascii=False),
        "indexed_at": created_at,
        "created_at": created_at,
        "updated_at": str(record.get("updated_at") or record.get("updatedAt") or created_at),
        "org_id": str(record.get("orgId") or "anon"),
        "user_id": str(record.get("userId") or "anon"),
        "actor_id": str(record.get("actorId") or repo),
        "actor_did": repo,
        "org_did": str(record.get("orgDid") or "anon"),
        "owner_did": repo,
        "sensitivity_ord": 2,
    }
    get_kotoba_client().insert_row("vertex_gov_record", params)
    return uri


def _upsert_gov_org(row: dict[str, Any]) -> None:
    now = _utc_now_iso()
    path = str(row["path"])
    params = {
        "vertex_id": _vertex_id(path),
        "sensitivity_ord": 1,
        "owner_did": PRIMARY_DID,
        "path": path,
        "name": str(row.get("name") or ""),
        "name_en": str(row.get("nameEn") or row.get("name_en") or ""),
        "website": str(row.get("website") or ""),
        "contract": str(row.get("contract") or ""),
        "tags": json.dumps(row.get("tags") or [], separators=(",", ":"), ensure_ascii=False),
        "domain_code": DOMAIN_CODE,
        "org_tier": str(row.get("orgTier") or row.get("org_tier") or ""),
        "site_domain_slug": str(row.get("site_domain_slug") or _url_to_domain_slug(str(row.get("website") or ""))),
        "site_followed": str(row.get("site_followed") or "false"),
        "did_registered": str(row.get("did_registered") or "false"),
        "last_ingested_at": str(row.get("last_ingested_at") or ""),
        "last_content_hash": str(row.get("last_content_hash") or ""),
        "last_kyumei_at": str(row.get("last_kyumei_at") or ""),
        "last_shinka_at": str(row.get("last_shinka_at") or ""),
        "created_at": str(row.get("created_at") or now),
        "props": json.dumps(row.get("props") or {}, separators=(",", ":"), ensure_ascii=False),
    }
    get_kotoba_client().insert_row("vertex_gov_org", params)


def _direct_fetch_hash(url: str, timeout: int = 10) -> tuple[str, str]:
    """Fetch url and return (md5_content_hash, text_snippet). Returns ('', '') on failure."""
    if not url or not url.startswith("http"):
        return "", ""
    try:
        req = _u_req.Request(url, headers={"User-Agent": "GovBot/1.0"})
        with _u_req.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536)
        content_hash = hashlib.md5(body).hexdigest()
        text = re.sub(r"<[^>]+>", " ", body.decode("utf-8", errors="replace"))
        text = re.sub(r"\s+", " ", text).strip()[:300]
        return content_hash, text
    except Exception:
        return "", ""


def _update_gov_org_fields(path: str, fields: dict[str, str]) -> None:
    allowed = {
        "site_followed",
        "did_registered",
        "last_ingested_at",
        "last_content_hash",
        "last_kyumei_at",
        "last_shinka_at",
    }
    updates = {k: str(v) for k, v in fields.items() if k in allowed}
    if not path or not updates:
        return
    # R0: fetch single row by path, check domain/owner, and insert modified row
    row = get_kotoba_client().select_first_where("vertex_gov_org", "path", path)
    if not row or row.get("domain_code") != DOMAIN_CODE or row.get("owner_did") != PRIMARY_DID:
        return
    for k, v in updates.items():
        row[k] = v
    get_kotoba_client().insert_row("vertex_gov_org", row)


def _get_org(path: str) -> dict[str, Any] | None:
    # R0: fetch single row by path, check domain_code and owner_did
    row = get_kotoba_client().select_first_where("vertex_gov_org", "path", path)
    if not row or row.get("domain_code") != DOMAIN_CODE or row.get("owner_did") != PRIMARY_DID:
        return None
    keys = [
        "path", "name", "name_en", "website", "contract", "tags", "org_tier",
        "site_domain_slug", "site_followed", "did_registered",
        "last_ingested_at", "last_content_hash", "last_kyumei_at",
        "last_shinka_at", "created_at",
    ]
    return {k: row.get(k) for k in keys}


def task_gov_jpn_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    # R0: fetchall by owner_did, in-python filter for domain_code and name_en
    rows = get_kotoba_client().select_where("vertex_gov_org", "owner_did", PRIMARY_DID, limit=10000)
    existing = {
        str(r.get("path")) for r in rows
        if r.get("domain_code") == DOMAIN_CODE and r.get("name_en")
    }
    pending = [row for row in _load_seed_orgs() if row["path"] not in existing]
    written = 0
    for row in pending[:limit]:
        _upsert_gov_org(row)
        written += 1
    return {"ok": True, "seeded": written, "remaining": max(0, len(pending) - written)}


def task_gov_jpn_resolve_org_path(path: str = "") -> dict[str, Any]:
    path = str(path or "").strip()
    if not path:
        return {"error": "missing path"}
    row = _get_org(path)
    if not row:
        return {"error": f"not found: {path}"}
    return {
        "did": f"{PRIMARY_DID}:{path}",
        "name": str(row.get("name") or ""),
        "nameEn": str(row.get("name_en") or ""),
        "website": str(row.get("website") or ""),
    }


def task_gov_jpn_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))
    # R0: fetchall by owner_did, in-python filter, sort, and slice
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "owner_did", PRIMARY_DID, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("domain_code") == DOMAIN_CODE and r.get("name_en")
        and (not org_tier or r.get("org_tier") == org_tier)
    ]
    total = len(filtered)
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    rows = filtered[offset : offset + limit]
    return {
        "orgs": [
            {
                "path": str(r.get("path") or ""),
                "did": f"{PRIMARY_DID}:{str(r.get('path') or '')}",
                "name": str(r.get("name") or ""),
                "nameEn": str(r.get("name_en") or ""),
                "website": str(r.get("website") or ""),
                "didRegistered": str(r.get("did_registered") or "") == "true",
            }
            for r in rows
        ],
        "total": total,
    }


async def task_gov_jpn_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    # R0: fetchall by owner_did, in-python filter, sort, and slice
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "owner_did", PRIMARY_DID, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("domain_code") == DOMAIN_CODE
        and r.get("name_en")
        and r.get("did_registered") != "true"
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    rows = filtered[:limit]
    registered: list[str] = []
    pds_results: list[dict[str, Any]] = []
    for r in rows:
        row = {
            "path": str(r.get("path") or ""),
            "name": str(r.get("name") or ""),
            "name_en": str(r.get("name_en") or ""),
            "website": str(r.get("website") or ""),
            "contract": str(r.get("contract") or ""),
            "tags": json.loads(str(r.get("tags") or "[]")),
            "org_tier": str(r.get("org_tier") or ""),
            "site_domain_slug": str(r.get("site_domain_slug") or ""),
            "site_followed": str(r.get("site_followed") or "false"),
            "last_ingested_at": str(r.get("last_ingested_at") or ""),
            "last_content_hash": str(r.get("last_content_hash") or ""),
            "last_kyumei_at": str(r.get("last_kyumei_at") or ""),
            "last_shinka_at": str(r.get("last_shinka_at") or ""),
            "created_at": str(r.get("created_at") or _utc_now_iso()),
            "did_registered": "true",
        }
        path = row["path"]
        org_did = f"{PRIMARY_DID}:{path}"
        display_name = f"{row['name']} ({row['name_en']})"
        description = (
            "[AI Agent - unofficial, not affiliated with the real organization] "
            f"{row['name_en']}"
        )
        pds_results.append(
            {
                "path": path,
                "identity": await _pds_xrpc(
                    "com.atproto.identity.create",
                    {
                        "path": path,
                        "documentJson": json.dumps(
                            {
                                "displayName": display_name,
                                "description": f"{description} - {row['website']}",
                            },
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ),
                    },
                ),
            }
        )
        _insert_repo_record(
            org_did,
            "actorManifest",
            _repo_rkey("actor", path),
            {
                "$type": "actorManifest",
                "displayName": display_name,
                "description": description,
                "performerType": "service",
                "isBot": True,
                "agentType": "autonomous",
                "country": DOMAIN_CODE,
                "path": path,
                "createdAt": _utc_now_iso(),
            },
        )
        pds_results[-1]["post"] = await _pds_xrpc(
            "app.bsky.feed.post",
            {"did": org_did, "text": f"{row['name_en']} registered.\n{org_did}"},
        )
        _insert_repo_record(
            org_did,
            "app.bsky.feed.post",
            _repo_rkey("registered", path),
            {
                "$type": "app.bsky.feed.post",
                "text": f"{row['name_en']} registered.\n{org_did}",
                "createdAt": _utc_now_iso(),
            },
        )
        _upsert_gov_org(row)
        registered.append(org_did)
    pds_ok = sum(
        1
        for result in pds_results
        if int(result.get("identity", {}).get("status") or 0) in range(200, 300)
    )
    return {"ok": True, "registered": len(registered), "dids": registered, "pdsIdentityOk": pds_ok}


async def task_gov_jpn_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0
    # R0: fetchall by owner_did, in-python filter, sort, and slice
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "owner_did", PRIMARY_DID, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("domain_code") == DOMAIN_CODE
        and r.get("site_followed") != "true"
        and r.get("site_domain_slug")
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    rows = filtered[:limit]
    for r in rows:
        path = str(r.get("path") or "")
        slug = str(r.get("site_domain_slug") or "")
        await _pds_xrpc("app.bsky.graph.follow", {"did": f"did:web:site.etzhayyim.com:{slug}"})
        row = {
            "path": path,
            "name": str(r.get("name") or ""),
            "name_en": str(r.get("name_en") or ""),
            "website": str(r.get("website") or ""),
            "contract": str(r.get("contract") or ""),
            "tags": json.loads(str(r.get("tags") or "[]")),
            "org_tier": str(r.get("org_tier") or ""),
            "site_domain_slug": slug,
            "site_followed": "true",
            "did_registered": str(r.get("did_registered") or "false"),
            "last_ingested_at": str(r.get("last_ingested_at") or ""),
            "last_content_hash": str(r.get("last_content_hash") or ""),
            "last_kyumei_at": str(r.get("last_kyumei_at") or ""),
            "last_shinka_at": str(r.get("last_shinka_at") or ""),
            "created_at": str(r.get("created_at") or _utc_now_iso()),
        }
        _insert_repo_record(
            f"{PRIMARY_DID}:{path}",
            "com.etzhayyim.apps.states.govOrgSiteDep",
            _repo_rkey("site-dep", path),
            {
                "$type": "com.etzhayyim.apps.states.govOrgSiteDep",
                "path": path,
                "siteNanoid": SITE_NANOID,
                "siteTopicDid": SITE_GOV_TOPIC_DID,
                "siteDid": f"did:web:site.etzhayyim.com:{slug}",
                "updated_at": _utc_now_iso(),
            },
        )
        _upsert_gov_org(row)
        followed += 1
    return {"ok": True, "followed": followed}


async def task_gov_jpn_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    # R0: fetchall by owner_did, in-python filter, sort by last_ingested_at, and slice
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "owner_did", PRIMARY_DID, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("domain_code") == DOMAIN_CODE
        and r.get("site_domain_slug")
        and (not r.get("last_ingested_at") or r.get("last_ingested_at") < cutoff_iso)
    ]
    filtered.sort(key=lambda x: str(x.get("last_ingested_at") or ""))
    rows = filtered[:limit]
    checked = 0
    updated = 0
    posted = 0
    now = _utc_now_iso()
    for r in rows:
        path = str(r.get("path") or "")
        name_en = str(r.get("name_en") or "")
        website = str(r.get("website") or "")
        slug = str(r.get("site_domain_slug") or "")
        last_hash = str(r.get("last_content_hash") or "")
        if not path or not slug:
            continue
        checked += 1
        # R0: fetch single row by domain and limit (crawled_at order implied or fetch all and sort)
        wet_rows = get_kotoba_client().select_where("vertex_wet_chunk", "domain", slug, limit=50)
        wet = None
        if wet_rows:
            wet_rows.sort(key=lambda x: str(x.get("crawled_at") or ""), reverse=True)
            wet = wet_rows[0]
        if not wet:
            fetch_hash, fetch_text = _direct_fetch_hash(website)
            if fetch_hash:
                fields: dict[str, str] = {"last_ingested_at": now, "last_content_hash": fetch_hash}
                _update_gov_org_fields(path, fields)
                if fetch_hash != last_hash:
                    updated += 1
                    text = f"{name_en} - official site updated\n{fetch_text[:200]}..."
                    org_did = f"{PRIMARY_DID}:{path}"
                    if postUpdates:
                        result = await _pds_xrpc("app.bsky.feed.post", {"did": org_did, "text": text})
                        if int(result.get("status") or 0) in range(200, 300):
                            posted += 1
                    _insert_repo_record(
                        org_did,
                        "app.bsky.feed.post",
                        _repo_rkey("wet-update", path),
                        {"$type": "app.bsky.feed.post", "text": text, "createdAt": now},
                    )
            else:
                _update_gov_org_fields(path, {"last_ingested_at": now})
            continue
        markdown = str(wet.get("markdown") or "")
        content_hash = str(wet.get("content_hash") or "")
        fields = {"last_ingested_at": now}
        if content_hash:
            fields["last_content_hash"] = content_hash
        _update_gov_org_fields(path, fields)
        if content_hash and content_hash != last_hash:
            updated += 1
            summary = re.sub(r"\s+", " ", markdown)[:200]
            text = f"{name_en} - official site updated\n{summary}..."
            org_did = f"{PRIMARY_DID}:{path}"
            if postUpdates:
                result = await _pds_xrpc("app.bsky.feed.post", {"did": org_did, "text": text})
                if int(result.get("status") or 0) in range(200, 300):
                    posted += 1
            _insert_repo_record(
                org_did,
                "app.bsky.feed.post",
                _repo_rkey("wet-update", path),
                {
                    "$type": "app.bsky.feed.post",
                    "text": text,
                    "createdAt": now,
                },
            )
    return {"ok": True, "checked": checked, "updated": updated, "posted": posted}


async def task_gov_jpn_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))
    # R0: fetchall by owner_did, in-python filter, sort, and slice
    all_rows = get_kotoba_client().select_where("vertex_gov_org", "owner_did", PRIMARY_DID, limit=2000)
    filtered = [
        r for r in all_rows
        if r.get("domain_code") == DOMAIN_CODE
        and r.get("did_registered") == "true"
    ]
    filtered.sort(key=lambda x: str(x.get("last_shinka_at") or ""))
    rows = filtered[:limit]
    posted = 0
    now = _utc_now_iso()
    for r in rows:
        path = str(r.get("path") or "")
        name_en = str(r.get("name_en") or "")
        if not path:
            continue
        org_did = f"{PRIMARY_DID}:{path}"
        text = f"{name_en} - government organization update"
        if postUpdates:
            result = await _pds_xrpc("app.bsky.feed.post", {"did": org_did, "text": text})
            if int(result.get("status") or 0) in range(200, 300):
                posted += 1
        _insert_repo_record(
            org_did,
            "app.bsky.feed.post",
            _repo_rkey("shinka", path),
            {
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": now,
            },
        )
        _update_gov_org_fields(path, {"last_shinka_at": now})
    return {"ok": True, "posted": posted, "touched": len(rows)}


async def task_gov_jpn_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_jpn_seed_orgs, seedLimit)
    register = await task_gov_jpn_register_dids(registerLimit)
    follow = await task_gov_jpn_follow_site_deps(followLimit)
    ingest = await task_gov_jpn_sync_wet_updates(ingestLimit)
    shinka = await task_gov_jpn_shinka(shinkaLimit)
    return {
        "ok": True,
        "seeded": seed.get("seeded", 0),
        "registered": register.get("registered", 0),
        "followed": follow.get("followed", 0),
        "wetUpdated": ingest.get("updated", 0),
        "shinkaPosted": shinka.get("posted", 0),
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="xrpc.com.etzhayyim.govJpn.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_jpn_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govJpn.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_jpn_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govJpn.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_jpn_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govJpn.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_jpn_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govJpn.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_jpn_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govJpn.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_jpn_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govJpn.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_jpn_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govJpn.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_jpn_heartbeat_tick)

"""TUR Government states actor primitives.

This module moves the `did:web:tur-state.etzhayyim.com` app actor off its
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


PRIMARY_DID = "did:web:tur-state.etzhayyim.com"
DOMAIN_CODE = "tur"
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
{"path":"cumhurbaskanligi","name":"Cumhurbaşkanlığı","nameEn":"Presidency of the Republic","website":"https://www.tccb.gov.tr/","contract":"Anayasa Madde 104","tags":["cofog:01","executive","president"],"orgTier":"ministry"}
{"path":"disisleri","name":"Dışişleri Bakanlığı","nameEn":"Ministry of Foreign Affairs","website":"https://www.mfa.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:01.2","foreign-affairs"],"orgTier":"ministry"}
{"path":"millisavunma","name":"Millî Savunma Bakanlığı","nameEn":"Ministry of National Defence","website":"https://www.msb.gov.tr/","contract":"Anayasa Madde 118","tags":["cofog:02","defence"],"orgTier":"ministry"}
{"path":"icisleri","name":"İçişleri Bakanlığı","nameEn":"Ministry of Interior","website":"https://www.icisleri.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:01","interior","police"],"orgTier":"ministry"}
{"path":"hazine","name":"Hazine ve Maliye Bakanlığı","nameEn":"Ministry of Treasury and Finance","website":"https://www.hmb.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:01.1","finance","treasury","budget"],"orgTier":"ministry"}
{"path":"adalet","name":"Adalet Bakanlığı","nameEn":"Ministry of Justice","website":"https://www.adalet.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:03","justice"],"orgTier":"ministry"}
{"path":"saglik","name":"Sağlık Bakanlığı","nameEn":"Ministry of Health","website":"https://www.saglik.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:07","health"],"orgTier":"ministry"}
{"path":"milliegitim","name":"Millî Eğitim Bakanlığı","nameEn":"Ministry of National Education","website":"https://www.meb.gov.tr/","contract":"Anayasa Madde 42","tags":["cofog:09","education"],"orgTier":"ministry"}
{"path":"ulasim","name":"Ulaştırma ve Altyapı Bakanlığı","nameEn":"Ministry of Transport and Infrastructure","website":"https://www.uab.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:04.5","transport","infrastructure"],"orgTier":"ministry"}
{"path":"ticaret","name":"Ticaret Bakanlığı","nameEn":"Ministry of Trade","website":"https://www.ticaret.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:04","trade","commerce"],"orgTier":"ministry"}
{"path":"sanayi","name":"Sanayi ve Teknoloji Bakanlığı","nameEn":"Ministry of Industry and Technology","website":"https://www.sanayi.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:04","industry","technology"],"orgTier":"ministry"}
{"path":"enerji","name":"Enerji ve Tabiî Kaynaklar Bakanlığı","nameEn":"Ministry of Energy and Natural Resources","website":"https://www.enerji.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:04","energy","natural-resources"],"orgTier":"ministry"}
{"path":"tarim","name":"Tarım ve Orman Bakanlığı","nameEn":"Ministry of Agriculture and Forestry","website":"https://www.tarimorman.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:04.2","agriculture","forestry"],"orgTier":"ministry"}
{"path":"cevre","name":"Çevre, Şehircilik ve İklim Değişikliği Bakanlığı","nameEn":"Ministry of Environment, Urbanisation and Climate Change","website":"https://www.csb.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:05","environment","urban","climate"],"orgTier":"ministry"}
{"path":"kultur","name":"Kültür ve Turizm Bakanlığı","nameEn":"Ministry of Culture and Tourism","website":"https://www.ktb.gov.tr/","contract":"Anayasa Madde 8","tags":["cofog:08","culture","tourism"],"orgTier":"ministry"}
{"path":"yargitay","name":"Yargıtay","nameEn":"Court of Cassation","website":"https://www.yargitay.gov.tr/","contract":"Anayasa Madde 154","tags":["cofog:03","judiciary"],"orgTier":"agency"}
{"path":"tbmm","name":"Türkiye Büyük Millet Meclisi","nameEn":"Grand National Assembly of Türkiye","website":"https://www.tbmm.gov.tr/","contract":"Anayasa Madde 75","tags":["cofog:01","legislature"],"orgTier":"agency"}
"""

_STATE_NDJSON = """\
{"path":"il:01","name":"Adana","nameEn":"Adana","website":"https://www.adana.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:02","name":"Adıyaman","nameEn":"Adıyaman","website":"https://www.adiyaman.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:03","name":"Afyonkarahisar","nameEn":"Afyonkarahisar","website":"https://www.afyonkarahisar.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:04","name":"Ağrı","nameEn":"Ağrı","website":"https://www.agri.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:05","name":"Amasya","nameEn":"Amasya","website":"https://www.amasya.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:06","name":"Ankara","nameEn":"Ankara","website":"https://www.ankara.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il","capital"],"orgTier":"state"}
{"path":"il:07","name":"Antalya","nameEn":"Antalya","website":"https://www.antalya.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:08","name":"Artvin","nameEn":"Artvin","website":"https://www.artvin.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:09","name":"Aydın","nameEn":"Aydın","website":"https://www.aydin.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:10","name":"Balıkesir","nameEn":"Balıkesir","website":"https://www.balikesir.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:11","name":"Bilecik","nameEn":"Bilecik","website":"https://www.bilecik.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:12","name":"Bingöl","nameEn":"Bingöl","website":"https://www.bingol.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:13","name":"Bitlis","nameEn":"Bitlis","website":"https://www.bitlis.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:14","name":"Bolu","nameEn":"Bolu","website":"https://www.bolu.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:15","name":"Burdur","nameEn":"Burdur","website":"https://www.burdur.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:16","name":"Bursa","nameEn":"Bursa","website":"https://www.bursa.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:17","name":"Çanakkale","nameEn":"Çanakkale","website":"https://www.canakkale.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:18","name":"Çankırı","nameEn":"Çankırı","website":"https://www.cankiri.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:19","name":"Çorum","nameEn":"Çorum","website":"https://www.corum.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:20","name":"Denizli","nameEn":"Denizli","website":"https://www.denizli.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:21","name":"Diyarbakır","nameEn":"Diyarbakır","website":"https://www.diyarbakir.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:22","name":"Edirne","nameEn":"Edirne","website":"https://www.edirne.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:23","name":"Elazığ","nameEn":"Elazığ","website":"https://www.elazig.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:24","name":"Erzincan","nameEn":"Erzincan","website":"https://www.erzincan.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:25","name":"Erzurum","nameEn":"Erzurum","website":"https://www.erzurum.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:26","name":"Eskişehir","nameEn":"Eskişehir","website":"https://www.eskisehir.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:27","name":"Gaziantep","nameEn":"Gaziantep","website":"https://www.gaziantep.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:28","name":"Giresun","nameEn":"Giresun","website":"https://www.giresun.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:29","name":"Gümüşhane","nameEn":"Gümüşhane","website":"https://www.gumushane.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:30","name":"Hakkari","nameEn":"Hakkari","website":"https://www.hakkari.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:31","name":"Hatay","nameEn":"Hatay","website":"https://www.hatay.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:32","name":"Isparta","nameEn":"Isparta","website":"https://www.isparta.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:33","name":"Mersin","nameEn":"Mersin","website":"https://www.mersin.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:34","name":"İstanbul","nameEn":"Istanbul","website":"https://www.istanbul.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il","largest-city"],"orgTier":"state"}
{"path":"il:35","name":"İzmir","nameEn":"İzmir","website":"https://www.izmir.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:36","name":"Kars","nameEn":"Kars","website":"https://www.kars.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:37","name":"Kastamonu","nameEn":"Kastamonu","website":"https://www.kastamonu.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:38","name":"Kayseri","nameEn":"Kayseri","website":"https://www.kayseri.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:39","name":"Kırklareli","nameEn":"Kırklareli","website":"https://www.kirklareli.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:40","name":"Kırşehir","nameEn":"Kırşehir","website":"https://www.kirsehir.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:41","name":"Kocaeli","nameEn":"Kocaeli","website":"https://www.kocaeli.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:42","name":"Konya","nameEn":"Konya","website":"https://www.konya.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:43","name":"Kütahya","nameEn":"Kütahya","website":"https://www.kutahya.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:44","name":"Malatya","nameEn":"Malatya","website":"https://www.malatya.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:45","name":"Manisa","nameEn":"Manisa","website":"https://www.manisa.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:46","name":"Kahramanmaraş","nameEn":"Kahramanmaraş","website":"https://www.kahramanmaras.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:47","name":"Mardin","nameEn":"Mardin","website":"https://www.mardin.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:48","name":"Muğla","nameEn":"Muğla","website":"https://www.mugla.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:49","name":"Muş","nameEn":"Muş","website":"https://www.mus.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:50","name":"Nevşehir","nameEn":"Nevşehir","website":"https://www.nevsehir.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:51","name":"Niğde","nameEn":"Niğde","website":"https://www.nigde.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:52","name":"Ordu","nameEn":"Ordu","website":"https://www.ordu.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:53","name":"Rize","nameEn":"Rize","website":"https://www.rize.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:54","name":"Sakarya","nameEn":"Sakarya","website":"https://www.sakarya.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:55","name":"Samsun","nameEn":"Samsun","website":"https://www.samsun.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:56","name":"Siirt","nameEn":"Siirt","website":"https://www.siirt.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:57","name":"Sinop","nameEn":"Sinop","website":"https://www.sinop.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:58","name":"Sivas","nameEn":"Sivas","website":"https://www.sivas.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:59","name":"Tekirdağ","nameEn":"Tekirdağ","website":"https://www.tekirdag.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:60","name":"Tokat","nameEn":"Tokat","website":"https://www.tokat.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:61","name":"Trabzon","nameEn":"Trabzon","website":"https://www.trabzon.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:62","name":"Tunceli","nameEn":"Tunceli","website":"https://www.tunceli.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:63","name":"Şanlıurfa","nameEn":"Şanlıurfa","website":"https://www.sanliurfa.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:64","name":"Uşak","nameEn":"Uşak","website":"https://www.usak.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:65","name":"Van","nameEn":"Van","website":"https://www.van.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:66","name":"Yozgat","nameEn":"Yozgat","website":"https://www.yozgat.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:67","name":"Zonguldak","nameEn":"Zonguldak","website":"https://www.zonguldak.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:68","name":"Aksaray","nameEn":"Aksaray","website":"https://www.aksaray.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:69","name":"Bayburt","nameEn":"Bayburt","website":"https://www.bayburt.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:70","name":"Karaman","nameEn":"Karaman","website":"https://www.karaman.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:71","name":"Kırıkkale","nameEn":"Kırıkkale","website":"https://www.kirikkale.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:72","name":"Batman","nameEn":"Batman","website":"https://www.batman.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:73","name":"Şırnak","nameEn":"Şırnak","website":"https://www.sirnak.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:74","name":"Bartın","nameEn":"Bartın","website":"https://www.bartin.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:75","name":"Ardahan","nameEn":"Ardahan","website":"https://www.ardahan.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:76","name":"Iğdır","nameEn":"Iğdır","website":"https://www.igdir.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:77","name":"Yalova","nameEn":"Yalova","website":"https://www.yalova.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:78","name":"Karabük","nameEn":"Karabük","website":"https://www.karabuk.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:79","name":"Kilis","nameEn":"Kilis","website":"https://www.kilis.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:80","name":"Osmaniye","nameEn":"Osmaniye","website":"https://www.osmaniye.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
{"path":"il:81","name":"Düzce","nameEn":"Düzce","website":"https://www.duzce.gov.tr/","contract":"5442 Sayılı İl İdaresi Kanunu","tags":["cofog:01","il"],"orgTier":"state"}
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
    params: dict[str, Any] = {
        "vertex_id": _vertex_id(path),
        **updates,
    }
    get_kotoba_client().insert_row("vertex_gov_org", params)


def _get_org(path: str) -> dict[str, Any] | None:
    return get_kotoba_client().select_first_where(
        "vertex_gov_org",
        "vertex_id",
        _vertex_id(path),
        columns=[
            "path", "name", "name_en", "website", "contract", "tags", "org_tier",
            "site_domain_slug", "site_followed", "did_registered",
            "last_ingested_at", "last_content_hash", "last_kyumei_at",
            "last_shinka_at", "created_at",
        ]
    )


def task_gov_tur_seed_orgs(limit: int = 30) -> dict[str, Any]:
    limit = max(1, min(int(limit or 30), 100))
    # R0: in-python filter for owner_did and name_en
    rows = get_kotoba_client().select_where("vertex_gov_org", "domain_code", DOMAIN_CODE, columns=["path", "name_en", "owner_did"], limit=10000)
    existing = {str(r["path"]) for r in rows if r.get("owner_did") == PRIMARY_DID and r.get("name_en")}
    pending = [row for row in _load_seed_orgs() if row["path"] not in existing]
    written = 0
    for row in pending[:limit]:
        _upsert_gov_org(row)
        written += 1
    return {"ok": True, "seeded": written, "remaining": max(0, len(pending) - written)}


def task_gov_tur_resolve_org_path(path: str = "") -> dict[str, Any]:
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


def task_gov_tur_list_orgs(orgTier: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    org_tier = str(orgTier or "").strip()
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 50), 100))
    # R0: in-python filtering, sorting, pagination, and counting
    raw_rows = get_kotoba_client().select_where(
        "vertex_gov_org",
        "domain_code",
        DOMAIN_CODE,
        columns=["path", "name", "name_en", "website", "did_registered", "owner_did", "org_tier"],
        limit=2000
    )
    filtered = [
        r for r in raw_rows
        if r.get("owner_did") == PRIMARY_DID
        and r.get("name_en")
        and (not org_tier or r.get("org_tier") == org_tier)
    ]
    filtered.sort(key=lambda x: str(x.get("path") or ""))
    total = len(filtered)
    page = filtered[offset : offset + limit]
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
            for r in page
        ],
        "total": total,
    }


async def task_gov_tur_register_dids(limit: int = 10) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    # R0: in-python filtering and sorting for un-registered dids
    raw_rows = get_kotoba_client().select_where(
        "vertex_gov_org",
        "domain_code",
        DOMAIN_CODE,
        columns=[
            "path", "name", "name_en", "website", "contract", "tags", "org_tier",
            "site_domain_slug", "site_followed", "last_ingested_at",
            "last_content_hash", "last_kyumei_at", "last_shinka_at", "created_at",
            "did_registered", "owner_did"
        ],
        limit=2000
    )
    filtered = [
        r for r in raw_rows
        if r.get("owner_did") == PRIMARY_DID
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


async def task_gov_tur_follow_site_deps(limit: int = 15) -> dict[str, Any]:
    limit = max(1, min(int(limit or 15), 50))
    followed = 0
    # R0: in-python filtering and sorting for site dependencies to follow
    raw_rows = get_kotoba_client().select_where(
        "vertex_gov_org",
        "domain_code",
        DOMAIN_CODE,
        columns=[
            "path", "name", "name_en", "website", "contract", "tags", "org_tier",
            "site_domain_slug", "did_registered", "last_ingested_at",
            "last_content_hash", "last_kyumei_at", "last_shinka_at", "created_at",
            "site_followed", "owner_did"
        ],
        limit=2000
    )
    filtered = [
        r for r in raw_rows
        if r.get("owner_did") == PRIMARY_DID
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


async def task_gov_tur_sync_wet_updates(limit: int = 10, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    cutoff = (_dt.datetime.now(tz=_dt.UTC) - _dt.timedelta(days=7)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat().replace("+00:00", "Z")
    # R0: in-python filtering for last_ingested_at cutoff
    raw_rows = get_kotoba_client().select_where(
        "vertex_gov_org",
        "domain_code",
        DOMAIN_CODE,
        columns=["path", "name_en", "website", "site_domain_slug", "last_content_hash", "last_ingested_at", "owner_did"],
        limit=2000
    )
    filtered = [
        r for r in raw_rows
        if r.get("owner_did") == PRIMARY_DID
        and r.get("site_domain_slug")
        and (not r.get("last_ingested_at") or str(r.get("last_ingested_at")) < cutoff_iso)
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
        # R0: fetch limit=10 and sort in python to get latest crawled_at
        wet_rows = get_kotoba_client().select_where(
            "vertex_wet_chunk",
            "domain",
            slug,
            columns=["markdown", "content_hash", "crawled_at"],
            limit=10
        )
        wet_rows.sort(key=lambda x: str(x.get("crawled_at") or ""), reverse=True)
        wet = wet_rows[0] if wet_rows else None
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


async def task_gov_tur_shinka(limit: int = 1, postUpdates: bool = True) -> dict[str, Any]:
    limit = max(1, min(int(limit or 1), 5))
    # R0: in-python filtering and sorting by last_shinka_at
    raw_rows = get_kotoba_client().select_where(
        "vertex_gov_org",
        "domain_code",
        DOMAIN_CODE,
        columns=["path", "name_en", "did_registered", "last_shinka_at", "owner_did"],
        limit=2000
    )
    filtered = [
        r for r in raw_rows
        if r.get("owner_did") == PRIMARY_DID
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


async def task_gov_tur_heartbeat_tick(
    seedLimit: int = 30,
    registerLimit: int = 10,
    followLimit: int = 15,
    ingestLimit: int = 5,
    shinkaLimit: int = 1,
) -> dict[str, Any]:
    seed = await asyncio.to_thread(task_gov_tur_seed_orgs, seedLimit)
    register = await task_gov_tur_register_dids(registerLimit)
    follow = await task_gov_tur_follow_site_deps(followLimit)
    ingest = await task_gov_tur_sync_wet_updates(ingestLimit)
    shinka = await task_gov_tur_shinka(shinkaLimit)
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
        task_type="xrpc.com.etzhayyim.govTur.seedOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_tur_seed_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govTur.registerDIDs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_tur_register_dids)
    worker.task(
        task_type="xrpc.com.etzhayyim.govTur.followSiteDeps",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_tur_follow_site_deps)
    worker.task(
        task_type="xrpc.com.etzhayyim.govTur.resolveOrgPath",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_tur_resolve_org_path)
    worker.task(
        task_type="xrpc.com.etzhayyim.govTur.listOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_tur_list_orgs)
    worker.task(
        task_type="xrpc.com.etzhayyim.govTur.syncWetUpdates",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_tur_sync_wet_updates)
    worker.task(
        task_type="xrpc.com.etzhayyim.govTur.shinka",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_tur_shinka)
    worker.task(
        task_type="xrpc.com.etzhayyim.govTur.heartbeatTick",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_gov_tur_heartbeat_tick)

"""Zero-dependency HTTP client for the Kotobase unified query envelope."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

Json = Any
GremlinBytecode = Sequence[Sequence[Json]]
Transport = Callable[[str, Mapping[str, str], bytes, Optional[float]], tuple]
QUERY_PATH = "/xrpc/ai.gftd.apps.kotobase.query.execute"


@dataclass(frozen=True)
class QueryResult:
    language: str
    data: Json
    meta: Mapping[str, Json]
    warnings: Sequence[str] = field(default_factory=tuple)


class KotobaseError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "query_failed",
        status: int = 0,
        retryable: bool = False,
        request_id: Optional[str] = None,
        details: Json = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable
        self.request_id = request_id
        self.details = details


class KotobaseClient:
    def __init__(
        self,
        endpoint: str = "https://kotobase.net",
        *,
        token: Optional[str] = None,
        transport: Optional[Transport] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.transport = transport or _urllib_transport
        self.headers = dict(headers or {})
        self.timeout = timeout

    def query(
        self,
        language: str,
        query: Union[str, GremlinBytecode],
        *,
        parameters: Optional[Mapping[str, Json]] = None,
        database: Optional[str] = None,
        collections: Optional[Sequence[str]] = None,
        options: Optional[Mapping[str, Json]] = None,
        request_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> QueryResult:
        _validate_query(language, query)
        payload: Dict[str, Json] = {"language": language, "query": query}
        if parameters is not None:
            payload["parameters"] = dict(parameters)
        if database is not None:
            payload["database"] = database
        if collections is not None:
            payload["collections"] = list(collections)
        if options is not None:
            payload["options"] = dict(options)

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            **self.headers,
        }
        if self.token:
            headers["authorization"] = "Bearer " + self.token
        if request_id:
            headers["x-request-id"] = request_id

        try:
            status, body = self.transport(
                self.endpoint + QUERY_PATH,
                headers,
                json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                self.timeout if timeout is None else timeout,
            )
        except KotobaseError:
            raise
        except (OSError, URLError) as exc:
            raise KotobaseError(str(exc), code="transport_error", retryable=True) from exc

        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KotobaseError(
                "Kotobase returned a non-JSON response",
                code="invalid_response",
                status=status,
                retryable=status >= 500,
            ) from exc

        if not 200 <= status < 300:
            raise _response_error(status, decoded)
        if not _is_result(decoded):
            raise KotobaseError(
                "Kotobase returned an invalid query result",
                code="invalid_response",
                status=status,
            )
        return QueryResult(
            language=decoded["language"],
            data=decoded["data"],
            meta=decoded["meta"],
            warnings=tuple(decoded.get("warnings", ())),
        )

    def datalog(self, query: str, **kwargs: Json) -> QueryResult:
        return self.query("datalog", query, **kwargs)

    def cypher(self, query: str, **kwargs: Json) -> QueryResult:
        return self.query("cypher", query, **kwargs)

    def graphql(self, query: str, **kwargs: Json) -> QueryResult:
        return self.query("graphql", query, **kwargs)

    def graphdb(self, query: str, **kwargs: Json) -> QueryResult:
        return self.query("graphdb", query, **kwargs)

    def sparql(self, query: str, **kwargs: Json) -> QueryResult:
        return self.query("sparql", query, **kwargs)

    def gremlin(self, bytecode: GremlinBytecode, **kwargs: Json) -> QueryResult:
        return self.query("gremlin", bytecode, **kwargs)


def _validate_query(language: str, query: Union[str, GremlinBytecode]) -> None:
    languages = {"datalog", "cypher", "gremlin", "graphdb", "graphql", "sparql"}
    if language not in languages:
        raise ValueError("unsupported query language: " + language)
    if language == "gremlin":
        if isinstance(query, (str, bytes)) or not query:
            raise ValueError("Gremlin query must be non-empty bytecode")
    elif not isinstance(query, str) or not query.strip():
        raise ValueError(language + " query must be a non-empty string")


def _is_result(value: Json) -> bool:
    return (
        isinstance(value, dict)
        and value.get("ok") is True
        and isinstance(value.get("language"), str)
        and "data" in value
        and isinstance(value.get("meta"), dict)
        and isinstance(value["meta"].get("requestId"), str)
        and isinstance(value["meta"].get("elapsedMs"), int)
    )


def _response_error(status: int, value: Json) -> KotobaseError:
    error = value.get("error", {}) if isinstance(value, dict) else {}
    if not isinstance(error, dict):
        error = {}
    return KotobaseError(
        error.get("message", "Kotobase query failed with HTTP %d" % status),
        code=error.get("code", "query_failed"),
        status=status,
        retryable=error.get("retryable", status >= 500),
        request_id=error.get("requestId"),
        details=error.get("details"),
    )


def _urllib_transport(
    url: str, headers: Mapping[str, str], body: bytes, timeout: Optional[float]
) -> tuple:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()

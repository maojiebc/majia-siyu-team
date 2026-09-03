"""飞书多维表格连接器：tenant token、拉记录、回写字段。

只用标准库 urllib。密钥来自环境变量，并可回退到 keychain 指针。
测试通过注入 transport，不访问网络。
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .base import ConnectorNotConfigured, resolve_secret


POINTER = "keychain:siyu-team/lark"
TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
BITABLE_BASE = "https://open.feishu.cn/open-apis/bitable/v1/apps"
MAX_RETRIES = 3
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class LarkAPIError(RuntimeError):
    """飞书接口返回业务错误或不可恢复的 HTTP 错误。"""


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
        query: Mapping[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        ...


class UrllibTransport:
    """真实 HTTP 传输；生产默认使用。"""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
        query: Mapping[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        if query:
            url = f"{url}?{urlencode(query)}"
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request_headers = {"Content-Type": "application/json; charset=utf-8"}
        if headers:
            request_headers.update(headers)
        req = Request(url, data=payload, headers=request_headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw) if raw else {}
                if not isinstance(parsed, dict):
                    raise LarkAPIError("飞书响应顶层必须是对象")
                return int(response.status), parsed
        except HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"error": raw}
            if not isinstance(parsed, dict):
                parsed = {"error": raw}
            return int(exc.code), parsed
        except URLError as exc:
            raise LarkAPIError(f"飞书网络错误：{exc}") from exc
        except json.JSONDecodeError as exc:
            raise LarkAPIError(f"飞书响应不是 JSON：{exc.msg}") from exc


def _sleep_seconds(attempt: int) -> float:
    return float(2 ** (attempt - 1))


def _safe_api_error(status: int, url: str, payload: Mapping[str, Any]) -> str:
    path = urlparse(url).path
    code = payload.get("code", "")
    msg = payload.get("msg") or payload.get("message") or ""
    return f"HTTP {status} path={path} code={code} msg={msg}"


@dataclass(frozen=True)
class LarkConfig:
    app_id: str
    app_secret: str
    app_token: str
    table_submissions: str
    table_confirmations: str


def load_lark_config(environ: Mapping[str, str] | None = None) -> LarkConfig:
    env = os.environ if environ is None else environ
    app_id = (env.get("LARK_APP_ID") or "").strip()
    app_secret = (env.get("LARK_APP_SECRET") or "").strip()
    if not app_secret:
        app_secret = (resolve_secret(POINTER) or "").strip()
    app_token = (env.get("LARK_BASE_APP_TOKEN") or "").strip()
    table_submissions = (env.get("LARK_TABLE_SUBMISSIONS") or "").strip()
    table_confirmations = (env.get("LARK_TABLE_CONFIRMATIONS") or "").strip()
    missing = [
        name
        for name, value in (
            ("LARK_APP_ID", app_id),
            ("LARK_APP_SECRET", app_secret),
            ("LARK_BASE_APP_TOKEN", app_token),
            ("LARK_TABLE_SUBMISSIONS", table_submissions),
            ("LARK_TABLE_CONFIRMATIONS", table_confirmations),
        )
        if not value
    ]
    if missing:
        raise ConnectorNotConfigured(
            "飞书未配置：" + "、".join(missing)
        )
    return LarkConfig(
        app_id=app_id,
        app_secret=app_secret,
        app_token=app_token,
        table_submissions=table_submissions,
        table_confirmations=table_confirmations,
    )


class LarkBitable:
    """飞书 Bitable：取 token、分页列记录、回写字段。"""

    def __init__(
        self,
        config: LarkConfig,
        *,
        transport: Transport | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self.config = config
        self.transport = transport or UrllibTransport()
        self._sleeper = sleeper
        self._token: str | None = None

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        transport: Transport | None = None,
    ) -> "LarkBitable":
        return cls(load_lark_config(environ), transport=transport)

    def tenant_access_token(self, *, force: bool = False) -> str:
        if self._token and not force:
            return self._token
        status, payload = self._request_with_retry(
            "POST",
            TOKEN_URL,
            body={"app_id": self.config.app_id, "app_secret": self.config.app_secret},
            authed=False,
        )
        token = str(payload.get("tenant_access_token") or "").strip()
        if status != 200 or int(payload.get("code", 1)) != 0 or not token:
            raise LarkAPIError(
                "获取 tenant_access_token 失败："
                + _safe_api_error(status, TOKEN_URL, payload)
            )
        self._token = token
        return token

    def list_records(
        self,
        table_id: str,
        *,
        filter_expr: str | None = None,
        page_size: int = 500,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_token = ""
        while True:
            query: dict[str, str] = {"page_size": str(page_size)}
            if page_token:
                query["page_token"] = page_token
            if filter_expr:
                query["filter"] = filter_expr
            payload = self._bitable(
                "GET",
                f"{BITABLE_BASE}/{self.config.app_token}/tables/{table_id}/records",
                query=query,
            )
            data = payload.get("data")
            if not isinstance(data, Mapping):
                raise LarkAPIError("list records 缺少 data")
            items = data.get("items") or ()
            if isinstance(items, Sequence) and not isinstance(items, (str, bytes)):
                for item in items:
                    if isinstance(item, Mapping):
                        records.append(dict(item))
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token") or "")
            if not page_token:
                break
        return records

    def update_record(
        self,
        table_id: str,
        record_id: str,
        fields: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._bitable(
            "PUT",
            (
                f"{BITABLE_BASE}/{self.config.app_token}/tables/{table_id}"
                f"/records/{record_id}"
            ),
            body={"fields": dict(fields)},
        )

    def create_record(
        self,
        table_id: str,
        fields: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._bitable(
            "POST",
            f"{BITABLE_BASE}/{self.config.app_token}/tables/{table_id}/records",
            body={"fields": dict(fields)},
        )

    def delete_record(self, table_id: str, record_id: str) -> dict[str, Any]:
        return self._bitable(
            "DELETE",
            (
                f"{BITABLE_BASE}/{self.config.app_token}/tables/{table_id}"
                f"/records/{record_id}"
            ),
        )

    def batch_create_records(
        self,
        table_id: str,
        records: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        if not records:
            return {"code": 0, "data": {"records": []}}
        return self._bitable(
            "POST",
            (
                f"{BITABLE_BASE}/{self.config.app_token}/tables/{table_id}"
                "/records/batch_create"
            ),
            body={"records": [dict(item) for item in records]},
        )

    def batch_update_records(
        self,
        table_id: str,
        records: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        if not records:
            return {"code": 0, "data": {"records": []}}
        return self._bitable(
            "POST",
            (
                f"{BITABLE_BASE}/{self.config.app_token}/tables/{table_id}"
                "/records/batch_update"
            ),
            body={"records": [dict(item) for item in records]},
        )

    def batch_delete_records(
        self,
        table_id: str,
        record_ids: Sequence[str],
    ) -> dict[str, Any]:
        if not record_ids:
            return {"code": 0, "data": {"records": []}}
        return self._bitable(
            "POST",
            (
                f"{BITABLE_BASE}/{self.config.app_token}/tables/{table_id}"
                "/records/batch_delete"
            ),
            body={"records": list(record_ids)},
        )

    def list_submissions(self, *, filter_expr: str | None = None) -> list[dict[str, Any]]:
        return self.list_records(
            self.config.table_submissions, filter_expr=filter_expr
        )

    def list_confirmations(self, *, filter_expr: str | None = None) -> list[dict[str, Any]]:
        return self.list_records(
            self.config.table_confirmations, filter_expr=filter_expr
        )

    def _bitable(
        self,
        method: str,
        url: str,
        *,
        body: Mapping[str, Any] | None = None,
        query: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        status, payload = self._request_with_retry(
            method, url, body=body, query=query, authed=True
        )
        if status == 401:
            self.tenant_access_token(force=True)
            status, payload = self._request_with_retry(
                method, url, body=body, query=query, authed=True
            )
        if status != 200 or int(payload.get("code", 1)) != 0:
            raise LarkAPIError(
                "飞书 Bitable 失败：" + _safe_api_error(status, url, payload)
            )
        return payload

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        body: Mapping[str, Any] | None = None,
        query: Mapping[str, str] | None = None,
        authed: bool,
    ) -> tuple[int, dict[str, Any]]:
        last_error: tuple[int, dict[str, Any]] | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            headers: dict[str, str] = {}
            if authed:
                headers["Authorization"] = f"Bearer {self.tenant_access_token()}"
            status, payload = self.transport.request(
                method, url, headers=headers, body=body, query=query
            )
            if status not in RETRY_STATUSES:
                return status, payload
            last_error = (status, payload)
            if attempt < MAX_RETRIES:
                self._sleeper(_sleep_seconds(attempt))
        assert last_error is not None
        return last_error


def call(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    """兼容旧入口：配置齐全时列出案例提交表。"""
    del args, kwargs
    return LarkBitable.from_env().list_submissions()

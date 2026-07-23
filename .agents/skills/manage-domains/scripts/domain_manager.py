#!/usr/bin/env python3
"""Least-privilege DNS helper for Cloudflare and GoDaddy."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DEFAULT_ALLOWLIST = {"myusa.us", "ho-tel.co"}
RECORD_TYPES = {"A", "AAAA", "CAA", "CNAME", "MX", "NS", "SRV", "TXT"}


class DomainManagerError(RuntimeError):
    pass


def emit(value: Any) -> None:
    json.dump(value, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def allowed_domains() -> set[str]:
    raw = os.environ.get("DOMAIN_MANAGER_ALLOWLIST")
    if raw is None:
        return set(DEFAULT_ALLOWLIST)
    return {part.strip().lower().rstrip(".") for part in raw.split(",") if part.strip()}


def require_allowed(domain: str) -> str:
    normalized = domain.strip().lower().rstrip(".")
    if normalized not in allowed_domains():
        raise DomainManagerError(
            f"{normalized} is not in DOMAIN_MANAGER_ALLOWLIST."
        )
    return normalized


def require_token(name: str) -> str:
    token = os.environ.get(name)
    if not token:
        raise DomainManagerError(
            f"{name} is not configured. Read references/provider-setup.md."
        )
    return token


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    encoded = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if encoded is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(
        url,
        data=encoded,
        headers=request_headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except HTTPError as error:
        payload = error.read().decode("utf-8", errors="replace")
        try:
            detail: Any = json.loads(payload)
        except json.JSONDecodeError:
            detail = payload[:500]
        raise DomainManagerError(
            f"Provider request failed with HTTP {error.code}: {detail}"
        ) from error
    except URLError as error:
        raise DomainManagerError(f"Provider request failed: {error.reason}") from error


def cloudflare_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {require_token('CLOUDFLARE_API_TOKEN')}"}


def cloudflare_call(
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> Any:
    _, payload = request_json(
        f"https://api.cloudflare.com/client/v4{path}",
        method=method,
        headers=cloudflare_headers(),
        body=body,
    )
    if not isinstance(payload, dict) or not payload.get("success"):
        errors = payload.get("errors") if isinstance(payload, dict) else payload
        raise DomainManagerError(f"Cloudflare rejected the request: {errors}")
    return payload.get("result")


def cloudflare_zone_id(domain: str) -> str:
    query = urlencode({"name": domain, "status": "active", "per_page": 50})
    result = cloudflare_call(f"/zones?{query}")
    if not isinstance(result, list) or len(result) != 1:
        raise DomainManagerError(
            f"Expected one active Cloudflare zone for {domain}; found {len(result or [])}."
        )
    return str(result[0]["id"])


def cloudflare_name(domain: str, name: str) -> str:
    normalized = name.strip().lower().rstrip(".")
    if normalized in {"", "@"}:
        return domain
    if normalized == domain or normalized.endswith(f".{domain}"):
        return normalized
    return f"{normalized}.{domain}"


def cloudflare_list(
    domain: str,
    record_type: str | None,
    name: str | None,
) -> list[dict[str, Any]]:
    zone_id = cloudflare_zone_id(domain)
    params: dict[str, Any] = {"per_page": 100}
    if record_type:
        params["type"] = record_type
    if name:
        params["name"] = cloudflare_name(domain, name)
    result = cloudflare_call(
        f"/zones/{quote(zone_id)}/dns_records?{urlencode(params)}"
    )
    return [
        {
            "record_id": record.get("id"),
            "type": record.get("type"),
            "name": record.get("name"),
            "data": record.get("content"),
            "ttl": record.get("ttl"),
            "proxied": record.get("proxied"),
        }
        for record in (result or [])
    ]


def godaddy_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {require_token('GODADDY_PAT')}"}


def godaddy_list(
    domain: str,
    record_type: str | None,
    name: str | None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"pageSize": 100, "totalRequired": "true"}
    if record_type:
        params["type"] = record_type
    if name:
        params["name"] = name
    _, payload = request_json(
        f"https://api.godaddy.com/v3/domains/zones/{quote(domain)}/dns-records?"
        f"{urlencode(params)}",
        headers=godaddy_headers(),
    )
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return [
        {
            "record_id": record.get("recordId"),
            "type": record.get("type"),
            "name": record.get("name"),
            "data": record.get("data"),
            "ttl": record.get("ttl"),
            "priority": record.get("priority"),
        }
        for record in items
    ]


def require_record_type(value: str) -> str:
    record_type = value.upper()
    if record_type not in RECORD_TYPES:
        raise DomainManagerError(
            f"Unsupported record type {record_type}. Allowed: {sorted(RECORD_TYPES)}"
        )
    return record_type


def parse_proxied(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() == "true"


def confirmation_for(action: str, domain: str, record_id: str | None) -> str:
    if action == "delete":
        return f"DELETE DNS RECORD {record_id} FROM {domain}"
    return f"APPLY DNS CHANGE {domain}"


def build_record(args: argparse.Namespace, domain: str) -> dict[str, Any]:
    record_type = require_record_type(args.type)
    if args.provider == "cloudflare":
        body: dict[str, Any] = {
            "type": record_type,
            "name": cloudflare_name(domain, args.name),
            "content": args.data,
            "ttl": args.ttl,
        }
        proxied = parse_proxied(args.proxied)
        if proxied is not None:
            body["proxied"] = proxied
        if args.priority is not None:
            body["priority"] = args.priority
        return body
    body = {
        "type": record_type,
        "name": args.name,
        "data": args.data,
        "ttl": max(args.ttl, 600),
    }
    if args.priority is not None:
        body["priority"] = args.priority
    return body


def plan_or_require_confirmation(
    args: argparse.Namespace,
    domain: str,
    change: dict[str, Any],
) -> bool:
    phrase = confirmation_for(args.command, domain, getattr(args, "record_id", None))
    if not args.apply:
        emit(
            {
                "status": "planned",
                "provider": args.provider,
                "domain": domain,
                "change": change,
                "required_confirmation": phrase,
            }
        )
        return False
    if args.confirm != phrase:
        raise DomainManagerError(
            f"Confirmation mismatch. Required exact phrase: {phrase}"
        )
    return True


def create_record(args: argparse.Namespace, domain: str) -> Any:
    record = build_record(args, domain)
    if not plan_or_require_confirmation(
        args, domain, {"action": "create", "record": record}
    ):
        return None
    if args.provider == "cloudflare":
        zone_id = cloudflare_zone_id(domain)
        return cloudflare_call(
            f"/zones/{quote(zone_id)}/dns_records",
            method="POST",
            body=record,
        )
    _, payload = request_json(
        f"https://api.godaddy.com/v3/domains/zones/{quote(domain)}/dns-records",
        method="POST",
        headers=godaddy_headers(),
        body=record,
    )
    return payload


def update_record(args: argparse.Namespace, domain: str) -> Any:
    if args.provider != "cloudflare":
        raise DomainManagerError(
            "GoDaddy updates require a separately confirmed delete and create."
        )
    record = build_record(args, domain)
    if not plan_or_require_confirmation(
        args,
        domain,
        {"action": "update", "record_id": args.record_id, "record": record},
    ):
        return None
    zone_id = cloudflare_zone_id(domain)
    return cloudflare_call(
        f"/zones/{quote(zone_id)}/dns_records/{quote(args.record_id)}",
        method="PUT",
        body=record,
    )


def delete_record(args: argparse.Namespace, domain: str) -> Any:
    change = {"action": "delete", "record_id": args.record_id}
    if not plan_or_require_confirmation(args, domain, change):
        return None
    if args.provider == "cloudflare":
        zone_id = cloudflare_zone_id(domain)
        return cloudflare_call(
            f"/zones/{quote(zone_id)}/dns_records/{quote(args.record_id)}",
            method="DELETE",
        )
    request_json(
        f"https://api.godaddy.com/v3/domains/zones/{quote(domain)}/dns-records/"
        f"{quote(args.record_id)}",
        method="DELETE",
        headers=godaddy_headers(),
    )
    return {"record_id": args.record_id, "deleted": True}


def add_common_record_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--type", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--ttl", type=int, default=600)
    parser.add_argument("--priority", type=int)
    parser.add_argument("--proxied", choices=["true", "false"])


def add_write_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor")

    listing = subparsers.add_parser("list")
    listing.add_argument("--provider", choices=["cloudflare", "godaddy"], required=True)
    listing.add_argument("--domain", required=True)
    listing.add_argument("--type")
    listing.add_argument("--name")

    creating = subparsers.add_parser("create")
    creating.add_argument("--provider", choices=["cloudflare", "godaddy"], required=True)
    creating.add_argument("--domain", required=True)
    add_common_record_arguments(creating)
    add_write_arguments(creating)

    updating = subparsers.add_parser("update")
    updating.add_argument("--provider", choices=["cloudflare", "godaddy"], required=True)
    updating.add_argument("--domain", required=True)
    updating.add_argument("--record-id", required=True)
    add_common_record_arguments(updating)
    add_write_arguments(updating)

    deleting = subparsers.add_parser("delete")
    deleting.add_argument("--provider", choices=["cloudflare", "godaddy"], required=True)
    deleting.add_argument("--domain", required=True)
    deleting.add_argument("--record-id", required=True)
    add_write_arguments(deleting)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "doctor":
            emit(
                {
                    "allowlist": sorted(allowed_domains()),
                    "cloudflare_configured": bool(
                        os.environ.get("CLOUDFLARE_API_TOKEN")
                    ),
                    "godaddy_configured": bool(os.environ.get("GODADDY_PAT")),
                }
            )
            return 0

        domain = require_allowed(args.domain)
        if args.command == "list":
            record_type = require_record_type(args.type) if args.type else None
            records = (
                cloudflare_list(domain, record_type, args.name)
                if args.provider == "cloudflare"
                else godaddy_list(domain, record_type, args.name)
            )
            emit(
                {
                    "provider": args.provider,
                    "domain": domain,
                    "records": records,
                }
            )
            return 0

        result = (
            create_record(args, domain)
            if args.command == "create"
            else update_record(args, domain)
            if args.command == "update"
            else delete_record(args, domain)
        )
        if result is not None:
            emit(
                {
                    "status": "applied",
                    "provider": args.provider,
                    "domain": domain,
                    "result": result,
                }
            )
        return 0
    except DomainManagerError as error:
        emit({"status": "error", "message": str(error)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

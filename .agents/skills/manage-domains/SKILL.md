---
name: manage-domains
description: Safely diagnose and manage DNS records for the user's GoDaddy and Cloudflare domains. Use for domain routing problems, DNS audits, record lookups, ChatGPT Sites custom-domain setup, and carefully confirmed A, AAAA, CNAME, TXT, MX, CAA, or SRV record changes. Default to myusa.us and ho-tel.co, use least-privilege API credentials, and never handle purchases, transfers, billing, ownership, contacts, forwarding, or nameserver changes.
---

# Manage Domains

Manage DNS through the bundled `scripts/domain_manager.py` helper. Keep credentials outside chat and source code.

## Safety rules

- Limit operations to the allowlist. It defaults to `myusa.us,ho-tel.co`; override only at the user's request with `DOMAIN_MANAGER_ALLOWLIST`.
- Start with `doctor`, then list the exact live records before proposing a change.
- Prefer the authoritative DNS provider. A GoDaddy registration does not mean GoDaddy hosts the DNS.
- Show the provider, domain, record type, name, old value, new value, TTL, and proxy status before every write.
- Obtain the user's explicit confirmation after showing that plan. Do not treat an earlier generic request as confirmation for a newly resolved DNS target.
- Run a write only with `--apply` and the exact confirmation phrase returned by the dry run.
- Re-list the affected record after a write and verify public resolution separately.
- Never print, echo, log, request in chat, or store API tokens in the skill.
- Do not change nameservers, buy or transfer domains, change contacts, configure billing, or change account access.

## Setup

Read `references/provider-setup.md` when a credential is missing or the user asks how to connect an account.

Required runtime secrets:

- `CLOUDFLARE_API_TOKEN`
- `GODADDY_PAT`

Use only the credential needed for the selected provider.

For repository-backed Codex cloud tasks, keep this skill in
`.agents/skills/manage-domains` so the bundled helper is available in the
task container. Configure the provider credential as a Codex environment
variable and allow only the provider API hostname needed by the task:
`api.cloudflare.com` or `api.godaddy.com`.

## Commands

Set the helper path:

```bash
helper="<skill-directory>/scripts/domain_manager.py"
```

Always use the bundled helper for provider API calls. For GoDaddy, the helper
uses the current v3 DNS API. Never improvise a legacy
`/v1/domains/{domain}/records` request.

Check configuration without revealing secrets:

```bash
python3 "$helper" doctor
```

List records:

```bash
python3 "$helper" list --provider cloudflare --domain myusa.us
python3 "$helper" list --provider godaddy --domain example.com
```

Filter a list:

```bash
python3 "$helper" list --provider cloudflare --domain myusa.us --type A --name @
```

Create a dry-run plan:

```bash
python3 "$helper" create --provider cloudflare --domain myusa.us \
  --type A --name @ --data 162.159.143.30 --ttl 1 --proxied false
```

Apply only after the user repeats the returned confirmation:

```bash
python3 "$helper" create --provider cloudflare --domain myusa.us \
  --type A --name @ --data 162.159.143.30 --ttl 1 --proxied false \
  --apply --confirm "APPLY DNS CHANGE myusa.us"
```

Update a Cloudflare record by its listed record ID:

```bash
python3 "$helper" update --provider cloudflare --domain myusa.us \
  --record-id RECORD_ID --type A --name @ --data 162.159.143.30 \
  --ttl 1 --proxied false
```

Delete by its listed record ID:

```bash
python3 "$helper" delete --provider cloudflare --domain myusa.us \
  --record-id RECORD_ID
```

GoDaddy DNS supports list, create, and delete in this helper. Plan a replacement as a separately confirmed delete followed by create; never silently combine them.

## Routing diagnosis

For ChatGPT Sites custom domains:

1. Inspect the Site custom-domain status and exact provider records.
2. List authoritative DNS records from Cloudflare or GoDaddy.
3. Identify conflicts at the same hostname before adding anything.
4. Use DNS-only status when the service provider requires it.
5. Preserve unrelated mail and verification records.
6. Verify both the apex and `www` hostname after propagation.

If provider access is unavailable, give the user one clear manual change at a time.

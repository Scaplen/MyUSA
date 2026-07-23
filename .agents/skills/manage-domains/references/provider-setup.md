# Provider setup

## Cloudflare

Create a custom token at:

`https://dash.cloudflare.com/profile/api-tokens`

Use these permissions:

- Zone / Zone / Read
- Zone / DNS / Edit

Restrict Zone Resources to only `myusa.us` and `ho-tel.co`. Set an expiration date when practical. Store the resulting secret in a password manager or the host's secret store and inject it at runtime as `CLOUDFLARE_API_TOKEN`.

Cloudflare shows the token once. Never paste it into chat, a source file, a command committed to source control, or an ordinary log.

## GoDaddy

Create a Personal Access Token at:

`https://developer.godaddy.com/personal-access-token`

Grant only:

- `domains.domain:read`
- `domains.dns:update`

Do not grant domain creation, deletion, nameserver, contacts, transfer, forwarding, or billing scopes. Store the token in a password manager or the host's secret store and inject it at runtime as `GODADDY_PAT`.

GoDaddy shows the PAT once. Never paste it into chat or source code.

## Runtime check

Run:

```bash
python3 scripts/domain_manager.py doctor
```

The output reports whether each credential is configured without revealing its value.

## Troubleshooting

- A domain registered at GoDaddy may use Cloudflare nameservers. Change DNS only at the authoritative provider.
- A `401` usually means a missing, expired, or invalid token.
- A `403` usually means the token lacks the required scope or the account is ineligible for that operation.
- A Cloudflare token should be zone-restricted and include both Zone Read and DNS Edit.
- Revoke a lost or exposed token immediately and generate a replacement.

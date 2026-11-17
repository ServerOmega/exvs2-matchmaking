# Security: what the patched card server / matchmaker protects, and what it doesn't

> Applies to `online-matchmaking.patch` commits 27–28 (2026-11-15) and the v0.4.0-pre package.
> Confirmed in the real game on 2026-11-15 7:33 AM Pacific Time (4 cabinets, two online-tag pairs, several 2v2
> games; see [TESTING.md](../TESTING.md#security-hardening-and-4-cabinet-online-tag-2026-11-15)).

This is a hobby server for an arcade game. It speaks **plain HTTP** to cabinets (the game can't do TLS here), so
everything below is about limiting *who can reach what* and *what ends up in logs*, not about encrypting traffic.

## 1. Two kinds of server, two access modes

`CardServerConfig.Security.AccessMode` in `Configurations/server.json`:

| Mode | Use it for | Who may reach what |
|---|---|---|
| `LanOnly` (default) | a card server whose cabinets are in the same home / shop (or on your VPN) | every path answers only loopback and private sources: `127/8`, `10/8`, `172.16/12`, `192.168/16`, `169.254/16`, `::1`, `fc00::/7`, `fe80::/10`, plus `ExtraAllowedCidrs` |
| `PublicMatchmaker` | a shared matchmaker on a VPS or a port-forwarded PC | internet sources may reach **only** `/match`, `/mms` (matchmaking), `/tag` (partner codes), the read-only `/leaderboard` page (`Leaderboard.PublicPage`) and exactly `/status` (totals only, `Status.PublicStatus`, `status-endpoint` branch). The card website, card APIs (`/ui`, `/game`, …) and static files answer loopback/LAN only (403 from the internet) |
| `Open` | upstream behaviour, nothing filtered | not recommended: card data, access codes and the card website become reachable from the internet over plain HTTP |

STUN (UDP 3478/3479, built-in) is not HTTP and is always open on a matchmaker; it only reflects addresses.

**VPN players:** Tailscale / CGNAT (`100.64.0.0/10`), Radmin (`26.0.0.0/8`), Hamachi (`25.0.0.0/8`) and ZeroTier
addresses are not "private" — add the range to `Security.ExtraAllowedCidrs` (space or comma separated).
`2-Configure.bat` / `linux/configure.sh` pick the mode from the address you give them (private or known VPN range →
`LanOnly`, public → `PublicMatchmaker`) and add the VPN range for you.

Ports a public matchmaker needs: **TCP 28090 and UDP 3478–3479**. Nothing else. Each player's own card server (and its web page at `http://<card-server>:28080/`) stays on **TCP 28080** and is not opened to the internet.

## 2. `/tag` shared secret (cross-server online tag)

Partner codes live on the matchmaker's `/tag` API. Every `/tag` request must carry the header
`X-Tag-Secret: <OnlineTag.TagSecret>`; without it the matchmaker answers **401**. Every card server that uses the
matchmaker for online tag sets the **same** value:

```json
"CardServerConfig": { "OnlineTag": { "TagSecret": "<long random string>" } }
```

* Generate it once, e.g. `python3 -c "import secrets;print(secrets.token_urlsafe(32))"`. The package's configure
  script generates one for a Host and asks a Player for the host's value. Step-by-step (where hosts find it later,
  where players paste it, how to rotate): [SETUP.md A8](SETUP.md#a8-online-tag-shared-secret-tagsecret).
* **Windows / Linux package:** it is `CardServerConfig.OnlineTag.TagSecret` in `server\Configurations\server.json`
  or `server-linux/Configurations/server.json`. Read it later with:
  `(Get-Content -Raw .\server\Configurations\server.json | ConvertFrom-Json).CardServerConfig.OnlineTag.TagSecret`
  or
  `python3 -c "import json;print(json.load(open('server-linux/Configurations/server.json'))['CardServerConfig']['OnlineTag']['TagSecret'])"`.
* **Linux VPS** (typical install `/opt/exvs2-mm`): it lives only in `/opt/exvs2-mm/Configurations/server.json`
  (mode `0640`, owner `root`, group the service user). There is no separate secret file. Read:
  `jq -r '.CardServerConfig.OnlineTag.TagSecret' /opt/exvs2-mm/Configurations/server.json`
  or the same python one-liner over `ssh root@<VPS_IP>`. To set or rotate it, write the new value into that key
  (or `deploy.sh --host <VPS_IP> --tag-secret-file FILE`, which sends the first line over SSH stdin and never
  prints it), then put the same value on every card server and restart the matchmaker and all card servers.
* Share it **only privately, and only with operators of card servers you trust**. **Never commit it, never paste
  it in a public chat, never share `server.json`.** On Windows restrict the file to your user
  (`icacls server.json /inheritance:r /grant:r "%USERNAME%:F"`).
* No secret configured on the matchmaker = `/tag` answers LAN sources only (internet card servers get 401).
* A card server with a missing / wrong secret logs: `The matchmaker refused this card server: OnlineTag.TagSecret
  in server.json is missing or does not match the matchmaker's.` The matchmaker logs
  `SEC-REFUSE 401 … /tag … /tag without a valid shared secret`.

A pilot can only register codes it created or joined (`/tag/register` keeps the others out), so knowing someone's
code is not enough to steal their pairing from a third cabinet.

**Code expiry:** a code nobody joined expires after **7 days** (`OnlineTag.OpenCodeExpiryDays`); a joined code after
**90 days** without use (`JoinedCodeExpiryDays`). Showing / using a code refreshes it.

## 3. `/match` hardening

* **Source-IP binding** (`Security.BindMatchNodesToSourceIp`, default on): `CheckMatching` / `CancelMatching` for a
  node are honoured only from the IP that sent that node's `EntryMatching`. A stranger guessing node ids can't
  cancel other cabinets' searches or read their room roster. Refusals log `SRC-WARN … from a different source than
  its entry: refused`. Cabinets behind one NAT share the IP, so LAN setups are unaffected.
* **Rate limits** per source IP (token bucket, 429 when exceeded):
  `/match` + `/mms` **1200/min, burst 300** (`MatchRequestsPerMinute` / `MatchBurst`; a cabinet polls about every
  3 s, so this covers 16+ cabinets behind one NAT); `/tag` **240/min, burst 60** (`TagRequestsPerMinute` /
  `TagBurst`). Loopback is exempt. `X-Forwarded-For` is never trusted.

## 4. Logs

* Public IPv4 addresses are written as `a.b.x.x` and partner codes as `AB******` (`Security.MaskNetworkInLog`,
  default on). Private / LAN addresses are kept (needed to debug a LAN).
* Card access codes, chip ids, session ids and tokens are written as `<masked:N>` everywhere: the protobuf request
  dump, structured log fields, **and WebUI request paths** such as `/ui/team/getTeams/<masked:20>/<masked:32>`
  (`MaskCardSecretsInLog`, default on). Older logs from before this change may still contain them in clear text —
  delete or scrub them, and don't share old `Logs/` folders.
* `SEC-REFUSE` lines show refused requests (403 source, 401 `/tag` secret, 429 rate limit) with a masked IP.

### Reading `TAG-WAIT` (why an online-tag pair didn't form)

When an Online Tag search (world 5) has waited **20 s** without its partner, the matchmaker logs **one** line per
search (logging only; matching is unchanged):

```
TAG-WAIT node=1032 am=2000003 waiting for partner 2000004: partner not searching (20s tag=RU******)
```
The partner's cabinet hasn't started an Online Tag search — it is still in menus, picked another mode, or picked
Online Tag more than ~90 s later (each search times out after 90 s). Have both players pick オンラインタッグ at about
the same time.

```
TAG-WAIT node=1032 am=2000003 waiting for partner 2000004: partner is in the queue as node=1030 class-team key=… but cannot pair (21s …)
```
The partner *is* searching, but in a different mode (here Team mode with a CPU partner, which `NoCpuPartner` never
places) or with a different code / pair key / game version.

`waiting for partner (unknown: code not joined yet)` means the code was created but the partner never joined it in
the Teams tab. `am=` / partner numbers are wire pilot ids (`ServerId × 1,000,000 + card id`), not card secrets.

## 5. Card website (WebUI)

* The Cards list no longer returns chip ids; it shows a hint like `****1234`. The full chip id is returned only by
  `ui/card/authorize` after the access code matched (no partial chip-id search oracle).
* **Single-card login:** the browser keeps one saved login (chip id + access code together). Logging in to another
  card replaces it; a tab left open for a different card asks for the access code again instead of sending one
  card's access code with another card's chip id (the old 500 "Card Profile is invalid").
* The WebUI is meant for the LAN. Keep it behind `LanOnly` / `PublicMatchmaker`.

## 6. Known remaining risks

* **Plain HTTP.** Cabinet ↔ card server ↔ matchmaker traffic (including `X-Tag-Secret` between card servers and
  the matchmaker) is unencrypted. Use a VPN or keep card servers on the LAN; the VPS sees only matchmaking.
* **P2P exposes public IPs.** Matched cabinets connect to each other directly, so every player in a room learns
  the others' public IP:port. That is how the game works; use a VPN if that matters.
* **The VPS IP is in old git history** of this repository (redacted from current files on 2026-11-15; history was
  not rewritten). Treat the matchmaker's address as public anyway — that is what the allowlist is for.
* **Access codes are the only card login.** Anyone on your LAN with a card's access code can edit it in the WebUI.
* The matchmaker trusts what cabinets report about themselves (am id, mode). Source binding and rate limits stop
  casual abuse, not a determined attacker.
* Upstream card-server code is unaudited; keep `LanOnly` on card servers and update the OS of a VPS
  (unattended-upgrades is enabled by `deploy.sh --bootstrap`).

Report security problems privately to the repository owner (GitHub: ServerOmega) rather than in a public issue.

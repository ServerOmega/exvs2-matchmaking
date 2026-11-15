# Release package (Windows + Linux)

Sources of the downloadable server package published on the
[Releases page](https://github.com/ServerOmega/exvs2-matchmaking/releases). Start with
[`package/START-HERE.txt`](package/START-HERE.txt).

The card server this builds on ([Chiang-17/EXVS2-IB-Server](https://github.com/Chiang-17/EXVS2-IB-Server)) has
**no license**, so the package contains **only our files**: scripts, instructions and
[`online-matchmaking.patch`](package/files/online-matchmaking.patch). The build script downloads upstream at the
pinned commit `7f4b280` (v1.2.0) from GitHub on the user's own PC, applies the patch and builds it there.
No upstream source and no compiled server is uploaded anywhere.

Our scripts and instructions in the package are GPL-3.0 (`package/LICENSE.txt`). The card server and
`online-matchmaking.patch` (and the follow-on `results-gap-and-rolling-fill/` series, already included in that combined patch) are **not** covered; see the License section of the main README.

| File | What it does |
|---|---|
| `1-Build-Server.bat` → `scripts/build-server.ps1` | portable git (MinGit, SHA-256 checked) and .NET 9 SDK (`dotnet-install.ps1`, local folder) if missing, download upstream @ 7f4b280, `git apply` the patch, `dotnet publish -r win-x64` (self-contained single exe), lay out `server/` keeping existing `Configurations/*.json` and `ServerInfinite.db`; optional copy of WebUI pictures / DB from an official v1.2.0 folder |
| `2-Configure.bat` → `scripts/configure.ps1` | Host (StunHost = LAN / VPN / public IP, BuiltinStun, FillAfterSeconds 3, NoCpuPartner) or Player (local card server, MatchUrl + StunHost → remote matchmaker); `Security.AccessMode` from the address (LanOnly / PublicMatchmaker, VPN ranges added), `OnlineTag.TagSecret` generated (Host) or asked (Player) — [docs/SECURITY.md](../docs/SECURITY.md); writes `server.json` + `kestrel.json`; optional firewall rules (`scripts/firewall.ps1`, elevated) |
| `3-Start-Server.bat` | runs `server/Server-Infinite.exe` from its folder |
| `linux/build-server.sh`, `configure.sh`, `start-server.sh`, `exvs2-matchmaking.service` | same for a Linux PC / VPS (self-contained linux-x64, `-p:LinuxHost=true`), systemd example |
| `START-HERE.txt`, `Connect-Your-Game.txt`, `Public-Server.txt`, `Troubleshooting.txt` | plain-language instructions |

Build the zip: `release/make-release.sh v0.4.1-pre` → `release/dist/` (not committed).

## Changelog

* **v0.4.1-pre (2026-11-15)** — docs only, same `online-matchmaking.patch` as v0.4.0-pre (rebuild not needed).
  `testmode_pcb.json` is in `<game folder>\29\`; how to set `battleMode` to 0 by hand in Notepad (only `value`,
  leave `type`, every `group` of the active `settingFile`, game closed, back up first). Every cabinet needs its
  **own random 4-character serial** in both `SnowLauncher.ini` and `config.ini` — two cabinets with the same
  serial behind the same public IP knock each other out of the queue (`same cabinet entered again`). SnowLauncher
  always starts the stock card server: start the patched one first (or swap the `server` folder). `MatchUrl`
  examples use the default port 28080 (`2-Configure` "2 = PLAY" assumes the host listens on 28080). Found in a
  friend's from-scratch build test 2026-11-15; that build then paired through the VPS matchmaker in Online Tag
  and filled a 4-player 2v2 game (9:52 AM PT).
* **v0.4.0-pre (2026-11-15)** — security hardening (patch commits 27–28): `PublicMatchmaker` / `LanOnly` access
  modes, `/tag` shared secret (`X-Tag-Secret`), `/match` source-IP binding, rate limits (1200 / 240 per minute),
  partner-code expiry (7 / 90 days), public IPs / codes / card secrets masked in logs (including WebUI request
  paths), masked chip ids in the card list, WebUI single-card login, `TAG-WAIT` diagnostics for online tag.
  Configure scripts set the access mode and the tag secret; `OnlineTag.TagStatus` default 1. Real-game test
  2026-11-15 7:33 AM PT: 4 cabinets, two online-tag pairs (cross-server + same-server) → 2v2 games completed.
  See [docs/SECURITY.md](../docs/SECURITY.md).
* **v0.3.0-pre (2026-11-15)** — cross-server online tag (shared partner codes on the matchmaker, settings sync),
  `TagStatus` 1.

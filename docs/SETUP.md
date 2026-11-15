# Setup guide: host a matchmaking server, connect a cabinet

> ⚠️ Experimental. Verified in the real game on 2026-11-13 with **two cabinets on one PC** only
> ([test report](../analysis/real-game-test-2026-11-13.md)). Matching between separate machines / over the internet
> is not yet tested. You must already have your own copy of the game; nothing here includes game files.

The matchmaking server is the **patched EXVS2-IB-Server** (card server + matchmaker + optional STUN in one exe),
built from [`server-sketch/ib-server/online-matchmaking.patch`](../server-sketch/ib-server/online-matchmaking.patch).
All config keys below are under `CardServerConfig` → `OnlineMatching` in `Configurations/server.json`
(full reference: [`server-sketch/ib-server/README.md`](../server-sketch/ib-server/README.md#configure)).

---

## Part A — Hosting the matchmaking server

### A1. Build
**Easiest:** download the [pre-release package](https://github.com/ServerOmega/exvs2-matchmaking/releases) and run
`1-Build-Server.bat` → `2-Configure.bat` → `3-Start-Server.bat` (Linux: `linux/*.sh`); it does the steps below for you.
Public server / VPN / VPS guide: [`release/package/Public-Server.txt`](../release/package/Public-Server.txt).

Manual build:
Needs the **.NET 9 SDK** and git (Windows or Linux can build the Windows exe).
```bash
git clone https://github.com/Chiang-17/EXVS2-IB-Server && cd EXVS2-IB-Server
git checkout 7f4b280
git am /path/to/exvs2-matchmaking/server-sketch/ib-server/online-matchmaking.patch

# Windows server: self-contained single-file exe (~220 MB), runs without any .NET installed
dotnet publish Server-Infinite -c Release -r win-x64 -o out-win
#   (building on Linux: add -p:EnableWindowsTargeting=true)

# or a Linux server (needs the .NET 9 runtime to run):
dotnet build Server-Infinite -c Release -p:LinuxHost=true -o out-linux

dotnet test Tests/Matchmaking.Tests      # optional: matchmaker unit tests
```
No pre-built server exe is published (upstream has no license); the package above builds it on your PC. If you already run an IB card server, copy its
`ServerInfinite.db` next to the new exe to keep your cards (**back it up first**; a migration adds one column).

The card website (`http://<host>:28080/`) also needs mobile-suit / pilot pictures. Those are **not in the source**
(and not in our package). Matchmaking works without them; only the website looks empty. Download
[Server-Infinite-v1.2.0.zip](https://github.com/Chiang-17/EXVS2-IB-Server/releases/tag/v1.2.0), then import only
`wwwroot/images` into your built server's `wwwroot/images` — step-by-step for Windows and Linux, including helper
scripts: [`release/package/Import-Pictures.txt`](../release/package/Import-Pictures.txt). The build scripts can also
copy them if you pass the official folder (`1-Build-Server.bat` asks; Linux: `OFFICIAL_SERVER_FOLDER=... ./linux/build-server.sh`).

### A2. Configure `Configurations/server.json` → `CardServerConfig.OnlineMatching`
Minimum for a matchmaker with built-in STUN:
```json
"OnlineMatching": {
  "Enabled": true,
  "MatchUrl": "",
  "StunHost": "203.0.113.10",
  "StunPort": 3478,
  "BuiltinStun": true,
  "FillAfterSeconds": 3,
  "MaxFillWaitSeconds": 3,
  "InStoreFillAfterSeconds": 3,
  "InStoreMaxFillWaitSeconds": 3,
  "AllowPartialRooms": true,
  "NoCpuPartner": true,
  "CpuStandInSeats": false
}
```
| Key | What to set |
|---|---|
| `Enabled` | `true`, otherwise RegisterPcb behaves like upstream (no online matching). |
| `MatchUrl` | `""` = cabinets are sent `http://<the address they used to reach this server>/match` (this server's built-in matchmaker). Set a full URL only to forward matchmaking elsewhere (split setup, A6). |
| `StunHost` | **This host's IP as the players reach it** (IP literal): your public IP for internet play, the overlay IP (Radmin/Tailscale/ZeroTier) for VPN play, the LAN IP on a LAN. Not `127.0.0.1` for remote players. When it is one of this PC's own addresses, the built-in STUN binds to it (needed on PCs with several adapters). |
| `StunPort` | `3478` (default). Built-in STUN also uses `StunPort + 1` (`BuiltinStunAltPort`, 0 = port+1). |
| `BuiltinStun` | `true` = STUN runs inside this server (no coturn). `false` = use an external STUN server at `StunHost:StunPort` (e.g. [coturn](../server-sketch/coturn/turnserver.conf)). |
| `FillAfterSeconds` | Seconds to wait for a full 2v2 before a short-handed room may form. Shipped default **3**. With `NoCpuPartner` on (the default), this no longer starts short-handed 2v2 rooms. In the default `Rolling` mode this wait restarts when a new compatible cabinet joins. |
| `FillTimerMode` / `MaxFillWaitSeconds` | `Rolling` (default) or `FromFirst`. `MaxFillWaitSeconds` (shipped default 3, `0` = no cap) is a hard cap from the first searcher. |
| `InStoreFillAfterSeconds` / `InStoreMaxFillWaitSeconds` | In-store worlds (15/16) only: shipped default 3 / 3. `0` = use the shared FillAfter / MaxFillWait. |
| `OneOnOneWorlds` | Default `"20"` (Fes 1on1): two solos pair immediately into a 2-client 1v1 with no CPU seats. `""` = off. To offer Fes 1on1, also set that day's `FesConfigurations.*Type` to a `OneOnOne*` value and restart the cabinets. |
| `AllowPartialRooms` | `true` = allow short-handed rooms when `NoCpuPartner` is off; `false` = only full 4-player rooms. |
| `NoCpuPartner` | **Default `true`.** 2v2 modes only form a match when at least 4 human players are searching (no CPU partners). Fes 1on1 (world 20) still needs only 2 players. |
| `CpuStandInSeats` | **Experimental**, leave `false`. Lists a CPU client for each empty seat; it did not fix the results-screen hang. |
| `PollingIntervalSeconds`, `StaleAfterSeconds`, `NetworkRealms`, `InStoreScope`, `ShopKeys`, `VerboseLog` | Optional; see the [config reference](../server-sketch/ib-server/README.md#configure). |

Online tag (players inviting a chosen partner, B5) is on by default and has its own section, `CardServerConfig` →
`OnlineTag`: `SendTagTeams` (true), `TagStatus` (1; 0 leaves the in-game online-tag list greyed out), `MaxTeams` (20),
`OneTimeInviteCode` (true = a partner's invitation code changes after it was used). The player-facing part is the
card server's web page (WebUI, same address and port as the card server, e.g. `http://<host>:28080/`). Since the
2026-11-15 security update the WebUI answers **LAN / VPN sources only** (`Security.AccessMode`, see A7), so remote
players run their own card server (A6) or join over a VPN whose range is in `Security.ExtraAllowedCidrs`.

Any key can also be set with an environment variable, which wins over the file, e.g.
`CardServerConfig__OnlineMatching__FillAfterSeconds=10`.

The listen address/port is in `Configurations/kestrel.json` (`"Url": "http://0.0.0.0:28080"` by default).

### A3. Ports
| Where | Port | Why |
|---|---|---|
| Server | **TCP 28080** (or whatever `kestrel.json` says) | card server + matchmaker `/match` (HTTP) |
| Server | **UDP 3478 and 3479** (`StunPort`, `StunPort+1`) | built-in STUN (NAT test) — only with `BuiltinStun: true` |
| Each player's PC | **UDP 48000** (+ terminal offset) | the game's own P2P battle socket; the game has no UPnP, so behind a strict NAT forward it, or use an overlay VPN |
| LM stores only | UDP 49000 | LM broadcast, local network only — never forward it |

Forward the server ports on your router to the server PC if players come from the internet. With an overlay
VPN (Radmin / Tailscale / ZeroTier) no forwarding is needed; use the overlay IP as `StunHost`.
More: [analysis/networking-issues.md](../analysis/networking-issues.md).

### A4. Firewall
* **Windows Firewall:** the first start of `Server.exe` may show an "allow access" prompt — allow it on the profile
  the players come in on (Private/Public), or add inbound rules for TCP 28080 and UDP 3478–3479. Check `wf.msc` for
  leftover **Block** rules on the exe.
* **TinyWall** (or another allow-list firewall): add `Server.exe` (and on player PCs every copy of the game exe /
  launcher) to the allowed applications; each copied folder is a different exe path and needs its own entry.

### A5. Run it and read the log
Start `Server.exe` (Linux: `dotnet Server-Infinite.dll` in the output folder). Logs go to `Logs/log-<date>.txt`.
Lines to watch, in the order a match happens:
| Log line | Meaning |
|---|---|
| `STUN built-in server on UDP 3478 (+alt 3479)...` | built-in STUN is up (at start) |
| `NET register-pcb src=<ip> -> match=<url> stun=<host>:<port>` | a cabinet booted and was told where the matchmaker and STUN are. `NET-WARN register-pcb` = a remote cabinet got a loopback address → fix `StunHost` / `MatchUrl` |
| `MMS IssueNodeId x2 -> [..]` | the cabinet started online matching |
| `NET entry node=N ... global=<ip:port> ... class=<c>` | a player queued. `class=stun-missing` = STUN failed (firewall / wrong `StunHost`) |
| `entry <mode> nodes=[..] slots=.. queue=..` | the player is waiting in that mode's queue |
| `MATCH room=R <mode> S[..] vs S[..] (humans=x/4)` + `MATCH-NET room=R ...` | a room formed; MATCH-NET shows which address each pair will dial |
| `drop nodes=[..] reason=...` | a player left the queue (cancel, timeout, stopped polling) |
| `check node=N -> ...` | one line per poll; only with `VerboseLog: true` |
| `MMS-POST <method> ... room=R +Ts` / `STUN-POST ...` | that cabinet called the matchmaker / STUN T seconds after its room was made (e.g. a re-queue). Nothing here between battle end and the end of a hung results screen = the matchmaker isn't involved |
| `MMS-UNHANDLED method=...` | a matchmaking method this server doesn't know (please report it) |
Details: [networking-issues.md §6](../analysis/networking-issues.md#6-reading-the-network-log).

### A6. Split setup: own card server, shared matchmaker
Players can keep their own card server (cards stay local) and only match on the shared server. On the
**player's** card server (the same patched build):
```json
"OnlineMatching": {
  "Enabled": true,
  "MatchUrl": "http://<matchmaker-ip>:28080/match",
  "StunHost": "<matchmaker-ip>",
  "StunPort": 3478,
  "BuiltinStun": false
}
```
The cabinet then registers on its own card server, but queues on (and gets STUN from) the shared matchmaker.
The card server only hands the cabinet the `MatchUrl` at boot; it never talks to the matchmaker itself, and nothing
goes between the two servers before, during or after a match (the cabinet calls `MatchUrl` directly).
Results are still saved to the player's own card server. This was tested on 2026-11-13 (one cabinet on a second
card-server instance, one directly on the matchmaker; they matched and played).

### A7. Security (access mode, `/tag` secret, logs)
Full reference: [`docs/SECURITY.md`](SECURITY.md). In short, in `CardServerConfig`:
```json
"Security": { "AccessMode": "PublicMatchmaker", "ExtraAllowedCidrs": "" },
"OnlineTag": { "TagSecret": "<long random string, same on the matchmaker and every card server>" }
```
* **Matchmaker on a VPS / port-forwarded PC:** `PublicMatchmaker` — the internet reaches only `/match`, `/mms`,
  `/tag` (and STUN on UDP); the card website and card APIs answer 403.
* **Card server for your own cabinets:** `LanOnly` (default) — loopback / private networks only; add VPN ranges
  (Tailscale `100.64.0.0/10`, Radmin `26.0.0.0/8`, Hamachi `25.0.0.0/8`) to `ExtraAllowedCidrs`.
* **Cross-server online tag** needs the same `OnlineTag.TagSecret` on the matchmaker and on every card server
  (`/tag` answers 401 without it). VPS: `tools/vps/deploy.sh --host <VPS_IP> --tag-secret-file FILE`.
  Never commit it or share `server.json`.
* `2-Configure.bat` / `linux/configure.sh` (release package) set both for you.

---

## Part B — Players: connecting a cabinet to a matchmaking server

### B1. Requirements
* EXVS2 **Infinite Boost** with the POC client (the build this project analysed), working locally.
* A card server: either the matchmaker itself, or your own patched card server in the split setup (A6).
* UDP reachability to the other players (public IP / forwarded UDP 48000, or the same overlay VPN as everyone).

### B2. Switch the cabinet to online matching (`battleMode: 0`)
1. Close the game. **Back up `testmode_pcb.json`.**
2. In the **active** setting entry of `testmode_pcb.json`, set `battleMode` to `0` using a testmode editor
   (this project used its `svd1.py` tool on the test PC; it is not in this repo). Any other value keeps the
   LM / in-store path.
3. Never use **EXIT & SAVE** in the in-game test menu, and don't edit the file while the game runs (the game
   rewrites it).

### B3. Point the cabinet at the server
* **Card server = the matchmaker:** set your POC client's card-server address to the matchmaker host and port
  (28080). Nothing else is needed: RegisterPcb tells the cabinet the matchmaker URL and the STUN server.
* **SnowLauncher users:** SnowLauncher ignores its `Server=` key — the client always talks to `127.0.0.1:28080`.
  So run a **local** patched card server on port 28080 and use the split setup (A6): `MatchUrl` and `StunHost`
  point at the remote matchmaker. (SnowLauncher once wiped the `AccessCode` in its ini during testing — keep a
  backup of your launcher/card config.)

### B4. Queue
1. Start the game, insert your card, pick an online mode. **Everyone must pick the same mode** to meet
   (each mode is its own queue; e.g. Mix Match and Class Match solo never mix).
2. Wait. **2v2 matches only form when at least 4 human players are searching** (`NoCpuPartner`,
   default on; no CPU partners). With fewer than 4, each cabinet times out after about 150 s,
   returns to practice mode, and can search again. Fes 1on1 (world 20) needs only 2 players.
3. Cancelling in the game's search screen works and leaves the queue.
4. After the match, results (class-match rate, badge) are saved to **your own** card server.

### B5. Invite a partner (online tag)
Online tag (オンラインタッグ) lets two players in different shops / homes play as a fixed team. There is no
code to type in the game: the team is made on the card server's web page first. Confirmed in the real game
on 2026-11-15 at 5:57 AM Pacific Time (two cabinets, two card servers, one shared matchmaker).

**Same card server:** use Friend's User ID + Invitation Code as before.

1. **Your partner** opens the card server's web page (`http://<card server>:28080/` or the port that server
   uses), logs in with their card's access code (keep that one private), opens **Customize → Teams**, and
   sends you the two values under *Your Information*: **Your User ID** and **Your Invitation Code**.
   (Share them privately; the code works once and then changes.)
2. **You** open your own card's **Customize → Teams**, enter them under *Add Team* as **Friend's User ID**
   and **Friend's Invitation Code**, and press **ADD**.

**Different card servers** (each player keeps their own cards; both servers point `OnlineMatching.MatchUrl`
and `StunHost` at the same matchmaker, for example `http://<VPS_IP>:28090/match`). Give each card server a
distinct `OnlineTag.ServerId` (for example 1 and 2) and the matchmaker's `OnlineTag.TagSecret` (A7). Leave
`OnlineTag.InviteUrl` empty so it is derived as `/tag` on that matchmaker. Two cards on the **same** card server
can also use a partner code (tested 2026-11-15 with four cabinets: one cross-server and one same-server pair).

1. Each player opens **their own** card server's web page → Customize → **Teams**.
2. One partner taps **Create a code** (under *Partner on another card server*) and sends the 8-character
   code to the other (chat, voice, etc.).
3. The other partner types that code under **Partner's code** and taps **Join**.
4. The creator reopens the Teams tab so the team appears on their side too.
5. Saving the team name, BGM, effect, background, emblem or name color on either card server's Teams tab
   updates the copy on the matchmaker; reload the other side's Teams tab (or reinsert the card) to pick
   it up.

**In the game (both setups):**

1. Insert both cards (re-insert if you were already playing, so the game reloads the team list).
2. On **TEAM SELECT**, choose **オンラインタッグ (Online Tag)** — not Mix Match, Class Match, or Fes —
   and pick the shared team. Do not pick 店内チーム (in-store team) unless you actually want a same-shop
   LAN team.
3. Start searching at about the same time (each cabinet waits up to 90 s for the other).
4. The matchmaker pairs the two cabinets as a duo (world 5). **A 2v2 still needs two more human players**
   (`NoCpuPartner`). The duo forming and waiting is expected when only two cabinets are present.

`OnlineTag.TagStatus` defaults to 1 (required for the in-game list to show). If the Online Tag panel is
empty or greyed out, confirm the card server log has `LoadCard online tag: … tag_teams=1 tag_status=1`
and that you reinserted the card after creating the team.

Partner recruit (パートナー急募, random partner) also pairs two players, but is less tested.

### B6. Troubleshooting
| Symptom | Likely cause / fix |
|---|---|
| No `NET register-pcb` line for your cabinet | the cabinet isn't talking to this card server: check the address/port (SnowLauncher: local server on 28080), firewall |
| `register-pcb` but no `MMS IssueNodeId` / no `NET entry` | `battleMode` isn't 0 in the active entry, or `Enabled` is false on the card server the cabinet uses |
| Stuck searching; `NET entry ... class=stun-missing` or a `NET-WARN ... no STUN global address` | STUN not reachable: UDP 3478/3479 blocked or forwarded wrong, or `StunHost` isn't the host's reachable IP (on a multi-adapter host it must be one of its own IPs) |
| `entry ...` lines but never `MATCH` | players are in different modes, or in different network realms (e.g. one on Radmin, one on the internet — they can never reach each other), or only one player queued |
| `MATCH` but the battle never starts | P2P UDP between players is blocked: firewall on the game exe, strict/CGNAT NAT without UDP 48000 forwarded → use an overlay VPN |
| Online tag: no team to pick / panel greyed out | team not created in the WebUI (B5), card read before the team was made (re-insert the card), or `OnlineTag.TagStatus` is still 0 (default is now 1). Log: `LoadCard online tag: … tag_teams=N tag_status=1` |
| Online tag: `entry online-tag` for both but no `online-tag pair` | they searched a different mode (e.g. Mix Match world 23 instead of Online Tag world 5), or the two cabinets sent different pair keys / codes, or they didn't search at the same time (90 s each) |
| Online tag: one cabinet searches alone, matchmaker log `TAG-WAIT … waiting for partner N: partner not searching` | the partner's cabinet never started an Online Tag search (still in menus, picked another mode, or started more than ~90 s later). `… partner is in the queue as node=… but cannot pair` = the partner searched another mode (e.g. Team mode with a CPU partner) — see [SECURITY.md](SECURITY.md#reading-tag-wait-why-an-online-tag-pair-didnt-form) |
| Card server log: `The matchmaker refused this card server: OnlineTag.TagSecret …` / matchmaker `SEC-REFUSE 401 … /tag` | `OnlineTag.TagSecret` missing or different from the matchmaker's (A7) |
| Card website or cabinet gets HTTP 403, log `SEC-REFUSE 403` | the source isn't allowed by `Security.AccessMode`: a VPN range missing from `ExtraAllowedCidrs`, or a cabinet on the internet using a `PublicMatchmaker` server as its card server (use your own card server, A6) |
| `SEC-REFUSE 429` | rate limit (`/match` 1200/min, `/tag` 240/min per source IP) — normally only a misbehaving script |
| Results screen hangs for minutes after a versus match | **known issue with two cabinets on one PC** (also happens in local LM mode without any matchmaker); the games recover by themselves. Not seen with a solo match; separate-machine test pending ([report](../analysis/real-game-test-2026-11-13.md#4-results-screen-hang-open)) |

Running two cabinets on one PC for testing: see the recipe in
[real-game-test-2026-11-13.md §5](../analysis/real-game-test-2026-11-13.md#5-recipe-two-cabinets-on-one-pc).

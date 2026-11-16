# Step 3 — card server with online matchmaking (EXVS2-IB-Server patch)

> ⚠️ **Experimental.** First real-game test 2026-11-13: two cabinets on one Windows PC queued online, matched and
> played full matches through this server (built-in STUN); results saved. Not yet tried between separate machines.
> See [the test report](../../analysis/real-game-test-2026-11-13.md). You must already have a copy of the game.

> **2v2 matches only form with at least 4 human players.** With `NoCpuPartner` (default on), 2v2 modes never fill empty seats with CPU partners. Fewer than 4 searchers wait until each cabinet's own matching timeout (~150 s), then return to practice mode and can search again. Fes 1on1 (world 20) still needs only 2 players.


This patches [Chiang-17/EXVS2-IB-Server](https://github.com/Chiang-17/EXVS2-IB-Server) (Infinite Boost card
server, v1.2.0, commit `7f4b280`) so that it:

* tells the cabinet where the **matchmaking server** (full URL) and a **STUN server** are (RegisterPcb),
* runs the **matchmaker in-process** on `/match` (alias `/mms`): unique node ids, EntryMatching / CheckMatching /
  CancelMatching, per-mode queues, solo shuffle, fixed pairs, CPU stand-ins, ranked class buckets with level widening,
* sends IB-style **LoadClassMatch** tables (hour-based schedule + unix fallback, grade→level patterns, search ratios),
* **stores ranked results** (rate, class, grade, class wins/losses from `SaveVsmOnResult`) and returns them in `PreLoadCard`,
* can be built and run **on Linux** (`-p:LinuxHost=true`) as well as Windows.

Upstream has **no license**, so it is not forked or redistributed here — only our changes, as a patch
(`online-matchmaking.patch`, a `git format-patch 7f4b280..security-hardening` of the local branch, 28 commits; the published series uses `<VPS_IP>` in the VPS tools commit). Commits 27–28 add security hardening — see [`docs/SECURITY.md`](../../docs/SECURITY.md).
The last ten commits are also kept as a standalone series in [`results-gap-and-rolling-fill/`](results-gap-and-rolling-fill/) (apply on top of the earlier 14-commit patch, tip `79b9fb4`); see [`RESULTS-GAP-AND-ROLLING-FILL.md`](RESULTS-GAP-AND-ROLLING-FILL.md).
Full change list and config reference: `ONLINE_MATCHMAKING.md` inside the patch.

Step-by-step hosting / player guide: [`docs/SETUP.md`](../../docs/SETUP.md).

## Build
Needs the .NET 9 SDK (`yay -S dotnet-sdk` on Arch; on Windows install .NET 9 SDK).
```bash
git clone https://github.com/Chiang-17/EXVS2-IB-Server && cd EXVS2-IB-Server
git checkout 7f4b280
git am /path/to/exvs2-matchmaking/server-sketch/ib-server/online-matchmaking.patch    # creates 28 commits

# Windows server (like upstream's release):
dotnet publish Server-Infinite -c Release -r win-x64
# or Linux server:
dotnet build Server-Infinite -c Release -p:LinuxHost=true -o out
# matchmaker unit tests (251 passing, including NoCpuPartner, v12 SoftWait, cross-server online tag, and security):
dotnet test Tests/Matchmaking.Tests
```
Copy your existing `ServerInfinite.db` next to the new build if you want to keep cards; the new migration
(`AddClassMatchGrade`) adds one column on first start. **Back the DB up first.**

## Configure
In `Configurations/server.json` under `CardServerConfig` → `OnlineMatching`:

| key | default | meaning |
|---|---|---|
| `Enabled` | `false` | `true` = send SRV_MATCH (full URL) + SRV_STUN in RegisterPcb |
| `MatchUrl` | `""` | `""` = built-in MMS `http://<host the cabinet used>/match`; or the external Python server, e.g. `http://203.0.113.10:5000/mms` |
| `StunHost` / `StunPort` | `""` / `3478` | STUN address; use an IP literal. `""` = same host as the card server |
| `BuiltinStun` | `false` | `true` = run STUN inside this server (UDP `StunPort` and `StunPort+1`), no coturn needed; set `StunHost` to this PC's IP as cabinets reach it. The socket binds to `StunHost` when it is a local IP (multi-homed fix) |
| `BuiltinStunPort` / `BuiltinStunAltPort` / `BuiltinStunAltIp` | `0` / `0` / `""` | `0` = `StunPort` / port+1; a second local IP enables full RFC 5780 change-IP tests |
| `StunUser` / `StunPass` | `""` | only if coturn requires long-term credentials |
| `PollingIntervalSeconds` | `3` | CheckMatching poll interval sent to the cabinet |
| `FillAfterSeconds` / `AllowPartialRooms` | `3` / `true` | short-handed room wait; with `NoCpuPartner` on this no longer forms 2v2 short rooms. Shipped default 3 |
| `FillTimerMode` / `MaxFillWaitSeconds` | `Rolling` / `3` | `Rolling`: the FillAfter timer restarts on each new compatible joiner; `FromFirst` = pre-v8. `MaxFillWaitSeconds` is a hard cap from the first searcher (`0` = no cap). Shipped default 3 |
| `InStoreFillAfterSeconds` / `InStoreMaxFillWaitSeconds` | `3` / `3` | in-store worlds (15/16) only; `0` = use the shared FillAfter / MaxFillWait. Shipped default 3 |
| `OneOnOneWorlds` | `"20"` | worlds that pair two solos immediately into a 2-client 1v1 (group 0 vs 1, no CPU seats). Default 20 = Fes 1on1. `""` = off |
| `CpuStandInSeats` | `false` | experimental: list a CPU client (owned by a cabinet) for each empty seat; did not fix the results-screen hang |
| `SoftAttributeWaitSeconds` | `15` | time win-rate bucket / veteran flag must match in free/mix modes |
| `StaleAfterSeconds` | `20` | drop a waiting cabinet that stopped polling (no ghost matches) |
| `NodeIdStateFile` / `FirstNodeId` | `mms_nodeids.json` / `1000` | node ids are never reused |
| `ClassMatchScheduleMode` | `Both` | `Both` / `Hours` / `UnixTime` (upstream) schedule rows in LoadClassMatch |
| `PersistClassMatchResult` | `true` | store ranked results from SaveVsmOnResult |
| `NetworkRealms` | `""` | players in different network realms (Radmin 26/8, Hamachi 25/8, 100.64/10, private = lan, rest = internet) are never matched together; `"off"` or `"name=cidr,..."` ([lm-and-online.md](../../analysis/lm-and-online.md)) |
| `InStoreScope` / `ShopKeys` | `Site` / `""` | in-store match (worlds 15/16) only within one shop: shop code + the shop's public IP (`ShopCode` = code only). `ShopKeys` names a shop on several IPs: `"SHOPA=203.0.113.10/32 203.0.113.11/32"` |
| `VerboseLog` | `false` | also log every CheckMatching poll (address/NAT lines are always logged once per entry / match) |
| `LogPostMatchTraffic` | `true` | logging only: `MMS-POST` / `STUN-POST` lines for matchmaker / STUN traffic from a cabinet up to 30 min after its match, `MMS-UNHANDLED` for unknown methods ([post-match-server-traffic.md](../../analysis/post-match-server-traffic.md)) |
| `LogResultGap` | `true` | logging only: `RESULT-SAVE` / `RESULT-WAIT` / `RESULT-GAP` lines from a cabinet's result save to its next request ([RESULTS-GAP-AND-ROLLING-FILL.md](RESULTS-GAP-AND-ROLLING-FILL.md)) |

Online tag (play with a chosen partner from another shop) has its own section, `CardServerConfig` → `OnlineTag`:

| key | default | meaning |
|---|---|---|
| `SendTagTeams` | `true` | send the card's tag teams in `LoadCard.MobileUserGroup.tag_teams` (36): the online-tag list |
| `TagStatus` | `1` | `TagTeamGroup.tag_status`. Must be 1 for the in-game オンラインタッグ list to be selectable (0 leaves the panel greyed and empty) |
| `ServerId` | (auto, 1–4000) | Distinct per card server when several share one matchmaker. Combined with the local card id to form a wire pilot id (`ServerId * 1_000_000 + local id`) |
| `InviteUrl` | (derived) | Shared `/tag` store. Leave empty: derived from `MatchUrl` by rewriting a trailing `/match` to `/tag`. Set only to override |
| `MaxTeams` | `20` | teams per card in that list |
| `OneTimeInviteCode` | `true` | the partner's invitation code changes after a team is created with it |

How it works and how a player invites a partner: [`docs/SETUP.md` B5](../../docs/SETUP.md#b5-invite-a-partner-online-tag)
and [`analysis/partner-invites.md`](../../analysis/partner-invites.md).

Environment variables work too and win over `server.json`: `CardServerConfig__OnlineMatching__Enabled=true`.

Network log lines (`NET ...`, `NET-WARN ...`, `MATCH-NET ...`, `drop ... reason=`) are explained in
[analysis/networking-issues.md §6](../../analysis/networking-issues.md#6-reading-the-network-log).

## Run the pieces
1. **STUN**: `BuiltinStun: true` (UDP 3478 + 3479 open), or coturn: `turnserver -c ../coturn/turnserver.conf` (set `external-ip`).
2. **Card server + MMS**: start the patched server (port 28080 by default, `Configurations/kestrel.json`).
   Port **28080** is the local card server and its web page. A public / VPS matchmaker listens on **TCP 28090**;
   players keep their own card server on 28080 and set `MatchUrl` to `http://<VPS_IP>:28090/match`.
3. *(optional)* external matchmaker instead of the built-in one: `python3 ../python/mms_server.py --port 5000`
   and set `MatchUrl` to `http://<ip>:5000/mms`.
4. **Cabinet**: back up `testmode_pcb.json`, set `battleMode: 0` in the active entry (with `svd1.py`), point the
   game's card server address at the patched server, then queue for a match and watch the server log
   (`MMS IssueNodeId`, `entry …`, `MATCH room=…`).

P2P battles still need reachable UDP between cabinets (public IP / UPnP, or a shared VPN such as Radmin).

## Check it without the game
```bash
pip install protobuf grpcio-tools
python -m grpc_tools.protoc -I ../../analysis/proto/from_exe --python_out=. game_server_nue.proto
PYTHONPATH=../python python3 check_card_server.py --url http://127.0.0.1:28080/            # RegisterPcb, LoadClassMatch, 4-cabinet shuffle
PYTHONPATH=../python python3 check_card_server.py --url http://127.0.0.1:28080/ --ranked-save  # + fake test card ranked result round-trip (writes to the DB)
```
Box result 2026-11-13 (Linux build): RegisterPcb → `SRV_MATCH http://127.0.0.1:28080/match` + `SRV_STUN 127.0.0.1:3478`;
LoadClassMatch parses strictly with schedule hit by hour and by unix time; 2-cabinet team+CPU, 4-solo shuffle,
pair+2 solos, and 8-cabinet ranked (two classes → two separate rooms) all matched; ranked save round-trip
(class 1→2, grade 0→7, rate 1500→1512.5, class win +1) OK; 10/10 unit tests pass; Windows (win-x64) build: 0 errors.

Load test 2026-11-13 (`../loadtest/loadtest.py`, 100–500 fake cabinets): see `../../analysis/load-test.md`;
matchmaker bugs found and fixed in this patch: double room on a repeated entry, node-id takeover by another
cabinet, ghost matches of cabinets that stopped polling, partner got ERR_MATCH_NOENTRY instead of
MATCH_CANCELED, one cabinet waiting in two queues at once, wall-clock-based timers.

Online tag 2026-11-13 (`../loadtest/online_tag_e2e.py`, fake cards + fake cabinets, Linux build): WebUI invite by
user id + code (wrong code / self / duplicate / reused code refused, code rotates), `LoadCard` tag_teams parses
strictly on both partners with `partner_id` = partner's pilot id, two tag pairs each form a 2-client world-5 room
(both group 0, leader first), mismatched keys never pair and get MATCH_CANCELED at the timeout, the two leaders'
team entries then match 2v2 with each pair on one side, casual recruits pair, ranked recruits of different classes
don't: 28/28 checks. The re-enabled WebUI Teams tab was checked in headless Chrome (renders, ADD creates the team).

Real game 2026-11-13: see [`../../analysis/real-game-test-2026-11-13.md`](../../analysis/real-game-test-2026-11-13.md)
(STUN bind fix, badge clamp, FillAfterSeconds 15, CPU stand-in experiment, results-screen hang).

Online tag 2026-11-15 (`../loadtest/cross_server_tag_e2e.py`, two Linux card servers + shared `/tag`):
create/join partner codes, colliding local card ids via wire ids, world-5 pair by shared code, team
cosmetics last-write-wins: 23/23. Real game the same morning: two cabinets on different card servers
picked オンラインタッグ (`TagStatus` 1) and were paired on the VPS matchmaker at 5:57 AM Pacific Time;
the duo then queued Mix Match and waited for two more humans (`NoCpuPartner`).

## Not done / risks
* Only tested with two cabinets on one PC; hole-punch / P2P between separate machines still untested.
* Results screen hangs when a cabinet's partner is a game-made CPU. `NoCpuPartner` (default on) prevents that in 2v2 modes by waiting for 4 humans. A Fes 1on1 through the VPS matchmaker completed on 2026-11-15 04:24 PT. See [RESULTS-GAP-AND-ROLLING-FILL.md](RESULTS-GAP-AND-ROLLING-FILL.md).
* Mode→world ids, class ids 1–4, and the hour-based schedule are inferred from static analysis.
* Matchmaker state is in memory (a restart drops waiting players); hidden MMR from the Python sketch is not ported
  (no reliable link between MMS am_id and card id yet) — ranked pairs by class + level only.
* The client is trusted for rate/grade (only NaN/out-of-range rates are rejected).
* Cross-server online tag was confirmed in the real game on 2026-11-15 5:57 AM Pacific Time (two card
  servers, shared `/tag` partner code, world-5 pair). A completed 4-human 2v2 after the duo forms is
  still untested. Same-server WebUI invite (User ID + Invitation Code) and partner recruit still need a
  real-game pass.

## Rematch cooldown and ROOM-END log (branch `rematch-cooldown`)
[`rematch-cooldown.patch`](rematch-cooldown.patch) is one commit (`git am`) on top of the v0.5.0 series (matchmaker at
`cdd7bf8`); it also applies on top of `online-results-save.patch`. Running on the LA matchmaker since 2026-11-16 7:47 AM PT.

Two 21-01 failures on four cabs were exact rematches of the room before (same four node ids), made 0 s and 20 s after that
room's first re-entry (~27 s after its results); every other solo rematch in the matchmaker's history formed 39 s or more
after it and played. The cause is not confirmed; the cooldown keeps such rooms out of that window.

| Setting (`OnlineMatching`) | Default | Effect |
|---|---|---|
| `RematchCooldownSeconds` | `30` | Nodes whose last room is the same humans-vs-humans room are not put together again in a room made only of solo entries until this many seconds after that room's first re-entry. Other cabs still match at once; rooms with a team entry (continued duo, after-CPU duo), earlier CPU / lone-team / pair rooms and pair worlds are unchanged. `0` = off. |
| `LogRoomEnd` | `true` | `ROOM-END` per cab after a match (`reentry`, `reentry-new-node`, `cancel-after-match`, `cancel`, `timeout`; seconds since the match; when it fetched the room) and `ROOM-SUMMARY` once every cab is accounted for. Logging only. |
| `RoomEndTimeoutSeconds` | `900` | A cab with no re-entry or cancel this long after its match is logged as `timeout`. |

Log lines: `REMATCH-COOLDOWN defer <world> nodes=[..] room=N pairs=[a+b,..] left=Ns`, `REMATCH-COOLDOWN placed room=M ..`,
`ROOM-END room=N <world> node=X serial=.. reason=.. +Ns since match fetched=+Ns|never order=k/n`,
`ROOM-SUMMARY room=N <world> humans=4 spread=Ns ends: node:reason@+Ns(fetch ..) ..`. The MMS protocol carries no UDPHP / RTT
result (that goes to the card server's CheckCommunication), so these lines are what the matchmaker can see.

Tests: `Matchmaking.Tests` 435/435 (15 new; every older scenario also passes with the new defaults on), cross-server e2e
108/108 (fake cabinets), and a replay of the LA matchmaker history: only the two failed rooms would have been held.

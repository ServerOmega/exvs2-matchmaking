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
(`online-matchmaking.patch`, a `git format-patch 7f4b280..HEAD` of the release/v0.5.0 series plus the `online-results-save`, `suit-stats-page`, `rematch-cooldown`, `global-leaderboards`, `status-endpoint`, `structured-logging` and `feature/custom-rooms` commits, 60 commits; the published series uses `<VPS_IP>` in the VPS tools commits and never includes a public VPS address). Commits 27–28 add security hardening — see [`docs/SECURITY.md`](../../docs/SECURITY.md). Later commits add friend requests, Teams pages, ContinuePair VsCpu at 18 s, the pair-cancel quarantine, and ContinuePairAfterCpuSeconds (fast CPU room after a CPU loss). Commit 47 (branch `online-results-save`, not released yet) stores online battle results like offline ones — see [Online battle results](#online-battle-results-branch-online-results-save); it is also kept alone as [`online-results-save.patch`](online-results-save.patch) (apply on top of the 46-commit v0.5.0 series). Commit 48 (branch `suit-stats-page`, not released yet) adds a Stats tab to View Card — see [Card stats page](#card-stats-page-branch-suit-stats-page); also kept alone as [`suit-stats-page.patch`](suit-stats-page.patch) (apply on top of commit 47). Commit 49 is the `rematch-cooldown` commit — see [Rematch cooldown](#rematch-cooldown-and-room-end-log-branch-rematch-cooldown); also kept alone as [`rematch-cooldown.patch`](rematch-cooldown.patch). Commit 50 (branch `global-leaderboards`, not released yet) adds global Class / Mix leaderboards through the matchmaker and sends the IB Class rate tables — see [Global leaderboards](#global-leaderboards-branch-global-leaderboards); also kept alone as [`global-leaderboards.patch`](global-leaderboards.patch) (apply on top of commit 49). Commit 51 points the card-server homepage's update notice at this repository. Commit 52 (branch `status-endpoint`, not released yet) adds a public read-only `GET /status` with cabinet totals for launchers — see [Public status endpoint](#public-status-endpoint-branch-status-endpoint); also kept alone as [`status-endpoint.patch`](status-endpoint.patch) (apply on top of commit 51). Commits 53–54 (branch `structured-logging`) add structured match events with one match id per room and stage timing, plus a `tools/match-timeline` reader; also kept alone as [`structured-logging.patch`](structured-logging.patch) (apply on top of commit 52). Commits 55–60 (branch `feature/custom-rooms`) add **Custom Match rooms**: LM LoadRoom (418) / RegisterRoom (419), a shared room registry on the matchmaker, one matchmaker bucket per room, the web Rooms page with auto-select for the cab, and 1v1 pairing for One fes rules — see [Custom Match rooms](#custom-match-rooms-branch-featurecustom-rooms) and [`docs/CUSTOM_ROOMS.md`](../../docs/CUSTOM_ROOMS.md); also kept alone as [`custom-rooms.patch`](custom-rooms.patch) (apply on top of commit 54).
The last ten commits are also kept as a standalone series in [`results-gap-and-rolling-fill/`](results-gap-and-rolling-fill/) (apply on top of the earlier 14-commit patch, tip `79b9fb4`); see [`RESULTS-GAP-AND-ROLLING-FILL.md`](RESULTS-GAP-AND-ROLLING-FILL.md).
Full change list and config reference: `ONLINE_MATCHMAKING.md` inside the patch.

Step-by-step hosting / player guide: [`docs/SETUP.md`](../../docs/SETUP.md).

## Build
Needs the .NET 9 SDK (`yay -S dotnet-sdk` on Arch; on Windows install .NET 9 SDK).
```bash
git clone https://github.com/Chiang-17/EXVS2-IB-Server && cd EXVS2-IB-Server
git checkout 7f4b280
git am /path/to/exvs2-matchmaking/server-sketch/ib-server/online-matchmaking.patch    # creates 60 commits

# Windows server (like upstream's release):
dotnet publish Server-Infinite -c Release -r win-x64
# or Linux server:
dotnet build Server-Infinite -c Release -p:LinuxHost=true -o out
# matchmaker unit tests (545 passing, including NoCpuPartner, ContinuePair, ContinuePairAfterCpu, pair-cancel quarantine, friends, Teams pages, security, rematch cooldown, the leaderboard store, /status, structured events and custom rooms):
dotnet test Tests/Matchmaking.Tests
# card-server tests (72: online battle results, card stats page, leaderboard snapshots + Class rate tables, custom room registry over real Kestrel, Rooms web UI; in-memory SQLite; on Windows drop -p:LinuxHost=true):
dotnet test Tests/Server.Tests -p:LinuxHost=true
```
Copy your existing `ServerInfinite.db` next to the new build if you want to keep cards; the new migration
(`AddClassMatchGrade`) adds one column on first start. **Back the DB up first.**

## Online battle results (branch `online-results-save`)
> Confirmed on real cabinets on 16 Nov 2026 (online Class solo and Mix matches saved to history and stats).

Until now an online battle (`SaveVsmOnResult`) stored only the badge and, for Class Match, rate / class / grade, so
internet games never showed up in View Card → battle history or in the stats. With
`OnlineMatching.PersistOnlineBattleResults` (default `true`) the result is now stored like an offline battle:

* **battle history** — mode, win/lose, stage, time, score, damage, burst, your suit, partner and human foes (CPU
  stand-ins are not listed; players from other card servers show as "Player N"), action log;
* **win / loss** — totals for every online battle; Class solo / team (counted once), **Mix → Free** win/lose,
  Fes win/lose;
* **player and per-suit statistics** (battles, wins, damage, defeats per suit), burst-type statistics, daily
  challenge counters;
* with `PersistOnlineProgress` (default `true`): GP, player level / exp, navigator familiarity, suit mastery and team
  points that the cabinet reports in the same save (each battle sends one save only, so nothing is applied twice).

A re-sent save of the same battle (same card, room, time, suit, mode) is ignored, also after a restart. Only battles
played with this build are recorded. No DB schema change; back up `ServerInfinite.db` before swapping builds anyway.
Set `"PersistOnlineBattleResults": false` to get the previous behaviour. Details: `ONLINE_MATCHMAKING.md` →
"Online battle results" inside the patch.

## Card stats page (branch `suit-stats-page`)
> Tested with DB tests, a local server and fake cards; not yet tried by a player.

View Card gets a new first tab, **Stats** (VS Mobile style). It is read-only and only shows the card you are logged in
with (same access-code check as the battle history). No DB schema change and no new settings.

* **Win rate by mode**: Total, Offline (solo + team), Class (solo), Class (team), Mix, Fes, Other.
* **Totals**: damage dealt, average damage, kills, no-damage battles, EX burst damage, Class 10-win streaks, and win
  rate per burst type.
* **By mobile suit** (sort by any column): battles, wins, losses, win rate, average damage dealt / taken, kills,
  kills per battle, no-damage battles, EX burst damage, last played. "All modes" shows the card's lifetime per-suit
  totals; picking one mode (Class, Mix, Offline...) shows the split counted from saved battle history.
* **Recent battles** (last 30): date, mode, suit, result, damage dealt / taken, time.

The game save has no per-suit death count, so there is no K/D column. Strings are English for now (other languages
fall back to English).

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

## Global leaderboards (branch `global-leaderboards`)
> Tested with unit tests and two local servers with fake cards (Linux). Not yet on a VPS and not yet tried by a
> player.

[`global-leaderboards.patch`](global-leaderboards.patch) is one commit (`git am`) on top of commit 49.

**Boards.** There are three public boards per matchmaker: **Class solo**, **Class team** and **Mix**. Each row shows
rank, name, class / rate (Class boards), wins, losses, win rate, matches and top suit. A card is ranked only after
`MinMatches` (5) matches on that board.
* Class boards are ordered by class, then rate.
* Mix is ordered by the Wilson 95% lower bound of the win rate, so 5-0 does not beat 45-5.

**How the data gets there.**
* Each card server sends a full snapshot of its own cards to `POST {tag}/leaderboard/submit`. `{tag}` is the online
  tag URL, with the same `X-Tag-Secret` header and the same rate limit.
* Snapshots go out every 10 minutes and about 15 s after each saved online Class / Mix result.
* A row holds:
  * a salted one-way card key: HMAC-SHA256 of the local card id under a random salt that never leaves that card
    server;
  * the card name, or none when the player turned "Show my name" off;
  * stats.

  **Access codes, chip ids and boot tokens are never sent or stored.**
* The matchmaker keeps rows per server id + key in `leaderboard.json`.
* It ignores stale snapshots: not newer than the last one from that server, or older than 24 h.
* It refuses or limits:

  | What | Limit | Answer |
  |---|---|---|
  | Snapshots from the future | more than 10 min ahead | 400 |
  | Snapshots per server | one per 20 s | 429 |
  | Body size | 512 KiB | 413 |
  | Rows | 2000 per snapshot, 5000 per server, 100000 in total | extra rows rejected |
  | Servers | 1000 | 507 |

* Rows a server has not refreshed for 60 days are dropped.

**Where to see it.**
* On the matchmaker: `http://<VPS_IP>:28090/leaderboard` is a public page, and `/leaderboard/data?board=class-solo|class-team|mix`
  returns JSON with names and stats only, with no keys or server ids.
  * In `PublicMatchmaker` mode this is the only non-`/match` / `/mms` / `/tag` path the internet may read, and it has
    its own per-IP limit (60/min, burst 20).
  * `Leaderboard.PublicPage=false` turns it off.
* Card-server web UI:
  * The front page gets a **Leaderboards** section with tabs (also `/GlobalLeaderboards`).
  * View Card → Stats gets a **Show my name on the global leaderboards** switch. Card secrets go in a POST body only.

**Settings** (`CardServerConfig.Leaderboard`). All are optional; an old `server.json` keeps working.
* `Enabled` (true): master switch.
* Card server: `SubmitEnabled` (true), `SubmitIntervalMinutes` (10), `SubmitAfterResultSeconds` (15),
  `SubmitMinMatches` (1), `HideNamesByDefault` (false; true makes names opt-in), `ViewCacheSeconds` (30).
* Matchmaker: `AcceptSubmissions` (true), `RegionName` ("", a label such as "LA" or "EU"), `MinMatches` (5),
  `MaxRows` (100), `PublicPage` (true), `PublicRequestsPerMinute` / `PublicBurst` (60 / 20).
* Abuse limits: `MinSubmitIntervalSeconds`, `MaxSubmitBytes`, `MaxEntriesPerSubmit`, `MaxEntriesPerServer`,
  `MaxTotalEntries`, `MaxServers`, `EntryExpiryDays`, `MaxClockSkewMinutes`, `MaxSnapshotAgeHours`.

**Class rate stuck at 1500 (+0).** On real cabinets every online Class result reported `before = after = 1500`,
`+0` and grade 0, for wins and losses alike. The cabinet computes the rate itself.

*Cause:* the `LoadClassMatch` reply filled only OverBoost-era fields, so an IB cabinet got initial rate 0 and no grade
thresholds or class-change rates.

*Fix:* this commit sends those tables (`OnlineMatching.ClassRateTables`, default on):
* initial rate `ClassInitialRate` (1500);
* 10 grade bands of `ClassGradeRateStep` (100) for each class, with 1500 in grade 5;
* class-change rates.

*Fallback:* if the rate still does not move, `OnlineMatching.ClassRateServerFallback` (default off) makes the card
server apply `+10 × (1 + score / 25000)` for a win and `−10` for a loss.

Both are untested on a cabinet.

**Tests.**
* `Server.Tests` 31/31 (7 new).
* `Matchmaking.Tests` 457/457 (19 new).
* Leaderboard e2e 44/44: two local servers, fake cards, results → boards, secret required, size / stale / bad-input
  answers, hide / show name, and no access code / chip id / salt / card key in the matchmaker's public output, files
  or logs.
* Cross-server e2e 103/103.

## Public status endpoint (branch `status-endpoint`)
> This is the **server player count** the launcher (v0.5.0+) shows in its matchmaking server list. Included in the
> 60-commit series; the LA matchmaker runs it since 17 Nov 2026.

`GET /status` on the matchmaker returns totals only, for the launcher's server list (player count and ping):

```json
{"service":"exvs2-matchmaking","version":"0.6.0-dev","online":16,"searching":14,"inMatch":2,"matches":1,
 "updatedAt":"2026-11-17T00:06:39Z","cacheSeconds":5}
```

* `searching` = human cabinets in the queue now; `inMatch` = cabinets placed in a room within the last 8 minutes
  (`InMatchWindowSeconds`) that have not searched again; `matches` = rooms with at least one of those; `online` =
  cabinets that searched, polled or were matched within the last 10 minutes (`OnlineWindowSeconds`), plus the two
  above. Counted per cabinet (pcb serial + public IP). Estimates: a cabinet in menus or practice does not talk to
  the matchmaker.
* The reply **never** holds card ids, access codes, chip ids, names, serials, node ids or IP addresses.
* With `Security.AccessMode = PublicMatchmaker` the internet may reach exactly `/status` (not `/status/...`); the
  WebUI and every other path stay LAN-only. Own per-IP limit (`Status.RequestsPerMinute` 60, `Burst` 20, then 429)
  and a reply cache (`Status.CacheSeconds` 5).
* `CardServerConfig.Status`: `PublicStatus` (true; false = 404), `CacheSeconds`, `RequestsPerMinute`, `Burst`,
  `OnlineWindowSeconds`, `InMatchWindowSeconds`, `Version`. Missing section = defaults, so an existing VPS config
  does not need editing.

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
| `PersistOnlineBattleResults` | `true` | store the whole online result like an offline battle (history, win/loss, stats, per-suit stats), once per battle; `false` = previous behaviour |
| `PersistOnlineProgress` | `true` | with the above: also apply the result's GP, level exp, navigator, mastery and team points |
| `NetworkRealms` | `""` | players in different network realms (Radmin 26/8, Hamachi 25/8, 100.64/10, private = lan, rest = internet) are never matched together; `"off"` or `"name=cidr,..."` ([lm-and-online.md](../../analysis/lm-and-online.md)) |
| `InStoreScope` / `ShopKeys` | `Site` / `""` | in-store match (worlds 15/16) only within one shop: shop code + the shop's public IP (`ShopCode` = code only). `ShopKeys` names a shop on several IPs: `"SHOPA=203.0.113.10/32 203.0.113.11/32"` |
| `VerboseLog` | `false` | also log every CheckMatching poll (address/NAT lines are always logged once per entry / match) |
| `LogPostMatchTraffic` | `true` | logging only: `MMS-POST` / `STUN-POST` lines for matchmaker / STUN traffic from a cabinet up to 30 min after its match, `MMS-UNHANDLED` for unknown methods ([post-match-server-traffic.md](../../analysis/post-match-server-traffic.md)) |
| `LogResultGap` | `true` | logging only: `RESULT-SAVE` / `RESULT-WAIT` / `RESULT-GAP` lines from a cabinet's result save to its next request ([RESULTS-GAP-AND-ROLLING-FILL.md](RESULTS-GAP-AND-ROLLING-FILL.md)) |
| `ContinuePairMode` / `ContinuePairSeconds` | `VsCpu` / `18` | a lone all-human pair waits this long for a 4-human room, then is sent versus two CPU stand-ins. 18 s is the original value (under the game's ~30 s pair timer; do not use 30). |
| `ContinuePairAfterCpuSeconds` | `2` | a pair re-entering after its own humans-vs-CPU room is sent a CPU room on the first poll (~3 s) instead of waiting 18 s. Negative = off. First searches still wait `ContinuePairSeconds`. Confirmed on cabinets 16 November 2026, 2:06 AM PT. |
| `PairCancelQuarantineSeconds` | `180` | after a pair cancel, hold those cabs out of human rooms until a clean restart (new node id) or this many seconds. `0` = off |
| `SoloPairVsCpuSeconds` | `0` (off) | leave off; sending leftover solos versus CPUs froze cabinets |
| `PairNeverCpu` / `CrossWorldTeamRooms` | `false` | test / experimental flags; leave off. The unpatched game does not practice-and-keep-search; a class pair cannot match class solos |

Pair behaviour, official cabinets, and known issues: [`docs/MATCHMAKING-BEHAVIOUR.md`](../../docs/MATCHMAKING-BEHAVIOUR.md), [`docs/KNOWN_ISSUES.md`](../../docs/KNOWN_ISSUES.md). Full change list: `ONLINE_MATCHMAKING.md` inside the patch.

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

## Custom Match rooms (branch `feature/custom-rooms`)
> Confirmed on real cabinets on 17 Nov 2026, 12:33 PM PT: four cabinets on **two different card servers** queued in
> the same custom room and the matchmaker built a 4-human 2v2 (no CPU); all four got `match_found` within ~3 s.
> One-rule 1v1 rooms (commit 60) are unit-tested and running on LA, but not yet tried on real cabinets.

Full guide, problems we hit and their fixes: [`docs/CUSTOM_ROOMS.md`](../../docs/CUSTOM_ROOMS.md) and
[`docs/FINDINGS-2026-11-17.md`](../../docs/FINDINGS-2026-11-17.md). Reference inside the patch: `CUSTOM_ROOMS.md`,
`CUSTOM_ROOM_OPTIONS.md` (every LM/cab room field), `CUSTOM_ROOM_VSMOBILE.md` (comparison with official VS.Mobile).

* **LM:** `LoadRoom` (418) lists the card's rooms; the reply needs `status = 1`, and only `tag_type` 2 (private list,
  up to 7) and 4 (the single public slot) are shown. `RegisterRoom` (419, `status = 0` = OK) stores the room the card
  picked.
* **Cab:** `PreLoadCard` sends `matching_tag` only when the card has a selected room; without one, Custom Match is skipped.
* **Shared registry:** the matchmaker hosts `/tag/rooms` (create / join / leave / close / lookup / select; lookup is a
  POST so room codes never appear in URLs). Card servers use it with `CustomRooms.LocalStore=false` (default when
  `MatchUrl` / `InviteUrl` is set), so rooms work across card servers.
* **Matchmaker:** custom-room worlds (6–9, 24, 26–33) are keyed on the room id, so each room is its own queue.
  `CustomRooms.TimeZone` / `DayResetHour` set when rooms open, close and reset.
* **Web Rooms page** (`/Cards/Rooms/{chip}` on the card server): create or join a room and it becomes the card's
  pick for the cab — no LM card touch needed. **Use this room** picks between several rooms; the last pick wins
  (web or LM). Leaving or closing clears the pick.
* **One fes rules** (10–14 One, 20–24 One XU): two solo entries in such a room are paired 1v1 right away with no CPU.
  **Dual Select is still a 2v2 rule** and waits for 4 humans with `NoCpuPartner`.

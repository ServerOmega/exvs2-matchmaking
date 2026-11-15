# Results-gap trace, rolling fill, NoCpuPartner and v12 (commits 15–24)

Follow-on commits to [`online-matchmaking.patch`](online-matchmaking.patch), also kept as a
`git format-patch` series in [`results-gap-and-rolling-fill/`](results-gap-and-rolling-fill/).
They apply to [Chiang-17/EXVS2-IB-Server](https://github.com/Chiang-17/EXVS2-IB-Server) at `7f4b280`
after the first 14 commits of `online-matchmaking.patch` (tip `79b9fb4`). Upstream has no license;
these patch files contain upstream context lines and are excluded from this repo's GPL grant the
same way `online-matchmaking.patch` is — personal use against your own copy only.

New users should apply the combined 24-commit `online-matchmaking.patch` (SETUP / the release
build already do that). If you already applied the earlier 14-commit patch:

```bash
git am /path/to/exvs2-matchmaking/server-sketch/ib-server/results-gap-and-rolling-fill/*.patch
```

SHAs below are from the local `rolling-fill-timer` / `results-gap-trace` branches after a
Co-authored-by rewrite; trees are unchanged.

## 1. Results-hang timing — `ec8d349` (`results-gap-trace`)

Logging only. After a cabinet saves a versus result, the server writes `RESULT-SAVE`, then
`RESULT-WAIT` at 30/60/120/300/600 s if nothing else arrives, then `RESULT-GAP` when the
cabinet's next request shows up (or not). Used to time the results-screen hang without a
stopwatch.

* Config: `OnlineMatching.LogResultGap` (default `true`).
* Tests: 5.

## 2. Rolling fill timer — `b7e1568`

`FillAfterSeconds` no longer counts only from the first searcher. In `FillTimerMode=Rolling`
(default) the wait restarts each time a new compatible cabinet joins, so two late searchers
can still merge into one 2v2 instead of forming a second 1v1. `FromFirst` is the pre-v8
behavior. `MaxFillWaitSeconds` (default 90, `0` = no cap) is a hard cap from the first
searcher. Four compatible solos still shuffle into a 2v2 immediately; pre-formed pairs stay
together.

* Config: `FillTimerMode` (`Rolling` / `FromFirst`), `FillAfterSeconds` (default 15),
  `MaxFillWaitSeconds` (default 90). A 4-cabinet Mix test on 2026-11-14 used a 30 s
  FillAfter with the 90 s cap and merged into one 2v2.
* Tests: 16.

## 3. In-store fill override — `9642bf9`

In-store worlds (15/16) use a longer window, because cabinets in one shop often arrive tens
of seconds apart (menus / card-in). Online worlds (Class / Mix) keep the shared 15/90
defaults.

* Config: `InStoreFillAfterSeconds` (default 60), `InStoreMaxFillWaitSeconds` (default 120).
  Set either to `0` to use the shared FillAfter / MaxFillWait.
* Tests: 5, including the 2026-11-14 23:00 PT in-store timeline (joins at t=0/2 and t=42/45
  → one 2v2 at t=45 with the 60/120 window; the old 30 s window had already closed a 1v1).

## 4. Fes 1on1 (no-CPU 1v1) — `51506e1`

Class / Mix / In-store are 2v2 rules: if the matchmaker sends only two humans, the game adds
CPU partners itself. The game's own CPU-free 1v1 is Fes 1on1 (mode 0x13 → MMS world 20).
Solo searches in `OneOnOneWorlds` pair first-come into a 2-client room (earlier searcher
group 0, the other group 1), immediately, with no fill timer and no stand-ins. Team entries
in those worlds are refused.

* Config: `OneOnOneWorlds` (default `"20"`). `""` restores the old 2v2 handling for world 20.
* Tests: 10.
* Deploy notes: the Fes *rule* is not this matchmaker key — it is `FesConfigurations` on the
  card server (`SaturdayType` / `SundayType` / the current day's `*Type`). To offer Fes 1on1,
  set that day's type to a `OneOnOne*` value (e.g. `OneOnOneAllCost`) and **restart the
  cabinets**; the Fes rule is sent in `LoadGameData` at boot. Then pick フェス and check the
  banner says 1on1. The 2-client group 0 vs 1 room shape is inferred and was not yet confirmed
  in a real match when this was written.

## Hang note (2026-11-14)

A full 4-human 2v2 cleared the results screen. Rooms that hung were 2 humans + 2 CPUs (the
game-added partners in a 2v2-rule short room). Fes 1on1 is the path to test a 1v1 with no
CPU seats. `LogResultGap` / `LogPostMatchTraffic` stay on by default for that test.


## 5. LoneTeamVsCpu — `c4b215d` (v10, default off)

A lone 2-human Teamplay entry still alone after the fill timer can get a room by itself
(both clients group 0); the game fills the other side with CPUs. Config
`OnlineMatching.LoneTeamVsCpu` (default `false`). Ignored when `NoCpuPartner` is on.

## 6. NoCpuPartner — `693f911` (v11, default on)

3-cab test 2026-11-15 02:18 PT: a Teamplay duo cleared results; the solo, whose partner was a
game-made CPU, hung. With `OnlineMatching.NoCpuPartner` (true by default in the shipped config),
2v2-rule worlds only form **full 4-human rooms** (4 solos, duo + 2 solos, or duo vs duo).
2–3 players wait until each cabinet's own matching timeout (~150 s), then return to practice
mode and can search again. Fes 1on1 (`OneOnOneWorlds`, default `"20"`) still needs only 2
players. The fill timer no longer forms short-handed 2v2 rooms while this is on.

## 7. SoftWait no longer delays a complete 4-human room — `6a14d73` (v12)

`SoftAttributeWaitSeconds` (default 15) still prefers same-flag (veteran / win-rate) rooms and
still keeps different flags apart for short-handed rooms. A complete 4-human room starts
immediately if no same-flag 4 is already waiting. Tested 2026-11-15 03:13 PT: a Teamplay duo +
2 solos with different Mix veteran flags used to wait ~14–16 s; they now match at once.
5 new tests (**150 total**).

## 8. Shipped fill-timer defaults — `8931272`

`FillAfterSeconds`, `MaxFillWaitSeconds`, `InStoreFillAfterSeconds` and
`InStoreMaxFillWaitSeconds` are now **3** in the shipped `server.json`, matching the tested
search timer. With `NoCpuPartner` on, the fill timer does not form short-handed 2v2 rooms.

## 9. VPS deploy tools — `905b051`

`tools/vps/` (`deploy.sh`, `exvs2-mm.service`, sample configs) builds a committed ref for
linux-x64 and installs it as systemd service `exvs2-mm`. Existing VPS `server.json` is kept
unless `--force-config`. Local card servers point `MatchUrl` / `StunHost` at the VPS.

## 10. 4-player disclaimer — `ecdccc9`

README and `ONLINE_MATCHMAKING.md`: in 2v2 modes, matches only form when at least 4 human
players are searching (no CPU partners). Fes 1on1 (world 20) needs only 2 players.

## Hang note (2026-11-15)

NoCpuPartner is on by default so solos no longer get a CPU partner in 2v2 modes. A Fes 1on1
match through the VPS matchmaker on 2026-11-15 04:24 PT completed (two cabs). The 0x10E video
memory crash on a 4-client one-PC setup is a separate graphics issue, not this matchmaker.

# Results-gap trace and rolling fill timer (commits 15–18)

Four follow-on commits to [`online-matchmaking.patch`](online-matchmaking.patch), also kept as a
`git format-patch` series in [`results-gap-and-rolling-fill/`](results-gap-and-rolling-fill/).
They apply to [Chiang-17/EXVS2-IB-Server](https://github.com/Chiang-17/EXVS2-IB-Server) at `7f4b280`
after the first 14 commits of `online-matchmaking.patch` (tip `79b9fb4`). Upstream has no license;
these patch files contain upstream context lines and are excluded from this repo's GPL grant the
same way `online-matchmaking.patch` is — personal use against your own copy only.

New users should apply the combined 18-commit `online-matchmaking.patch` (SETUP / the release
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

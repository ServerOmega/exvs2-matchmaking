# Test checklist

Tick items off as they're verified, and note results/captures next to them. First real-game test: **2026-11-13**, two cabinets on one PC — see [Real-game results](#real-game-results-2026-11-13) and [analysis/real-game-test-2026-11-13.md](analysis/real-game-test-2026-11-13.md).

## Setup (do first)
- [x] Back up `testmode_pcb.json`, then set `battleMode: 0` in the active entry with `_re/tools/svd1.py`; confirm the game switches to online (WAN) matching and no longer uses the LM — **confirmed 2026-11-13**
- [ ] Confirm the game binds to the correct network adapter / IP (currently Radmin VPN); use the hook's `IpAddress=` — without it the exe skips adapters whose name contains "2"/"Loopback" ([analysis/networking-issues.md](analysis/networking-issues.md))
- [ ] Windows: no leftover Block rules for `vsac29_Release.exe` in wf.msc; game/overlay adapter set to Private
- [ ] First real entry: read the `NET entry` line for each player (`local` = the hook's IP, `global` from STUN, no `stun-missing`, no unexpected `MISMATCH`). See [networking-issues.md §6](analysis/networking-issues.md#6-reading-the-network-log)
- [x] Get a card server whose RegisterPcb returns the match server `uri` plus a SRV_STUN entry; confirm IssueNodeId hits our server — patched EXVS2-IB-Server from [`server-sketch/ib-server`](server-sketch/ib-server/README.md), built-in STUN, 2026-11-13 ([results](analysis/real-game-test-2026-11-13.md))

## Basic matchmaking
- [x] Box load test with 100 / 200 / 500 fake cabinets against both matchmakers — no invariant violations after fixes ([analysis/load-test.md](analysis/load-test.md)); fake cabinets only
- [x] Box disconnect/rejoin test (14 probes + 150-person run with mass drop and server restart) — 6 bugs fixed, 14/14 probes pass on both servers ([analysis/disconnect-test.md](analysis/disconnect-test.md)); fake cabinets only
- [ ] Real game: what the cabinet does on MATCH_CANCELED vs ERR_MATCH_NOENTRY, and when a room member drops right after matching
- [x] EntryMatching + CheckMatching polling reaches the matchmaker (built-in `/match`; 2026-11-13). `mms_server.py` not tried in game
- [x] A matched room actually starts a battle (two cabinets on one PC, 2026-11-13; full matches in Mix Match and Class Match solo)
- [ ] Capture the cabinet-to-cabinet (hole-punch / P2P) packet format between **two machines**; keep the `MATCH-NET` line for that room
- [ ] Results screen hangs after every 2-cabinet versus match (also in local LM mode, no matchmaker): retest with cab2 in Windows Sandbox and on two real PCs
- [x] Box: one server for LM-store, home and multi-LM players (`server-sketch/loadtest/lm_mix.py`, 14 fake players): 14/14 matched on both servers after the serial+IP fix (3/14 before). Fake cabinets only ([analysis/lm-and-online.md](analysis/lm-and-online.md) §4)
- [ ] Real game, LM store: find **where battleMode is set**: on the LM machine (`testmode_lm.json` / LM test menu, pushed to the cabinets) or on each cabinet (`testmode_pcb.json`)? Which file / menu, and does a cabinet's own value survive an LM sync? Use backups and `svd1.py`; no EXIT & SAVE
- [ ] Real game, LM store: what the **LM machine itself** does when battleMode is 0 (still in-store/LAN matching? stays idle? any HTTP to the card server or MMS? capture with tcpdump)
- [ ] Real game: in-store match (world 15/16) from two different stores never meets; one store's cabinets do (server log `entry instore-... key=...|ip:<public IP>`)
- [x] Box: in-store match stays per shop although all stores send shop code JPN1 (`lm_mix.py --case instore`: 3 stores → 3 separate rooms; the same cabinets mix in Mix Match). Fake cabinets only
- [ ] Real game, LM store: with `battleMode: 0`, does an LM-attached cabinet go online, and does its in-store partner show up in `groups` (team sortie)? Keep both cabinets' `NET entry` lines
- [ ] Real game: loc_id and pcb_serial sent by two different POC installs (same `JPN1`/`0001`?). Look in the IssueNodeId / entry log
- [ ] Real game: two players on different networks with the default serial both match (no "same cabinet entered again" in the log)
- [ ] Real game: store pair vs online players: MATCH-NET shows `local same-NAT` for the pair and the battle starts
- [x] Box: IP/NAT log lines on both servers (`NET`, `NET-WARN`, `MATCH-NET`, drop reasons). Unit tests plus a smoke run with fake cabinets and documentation IPs
- [ ] Real game, LM over VPN + online over internet ([analysis/lm-over-vpn-split.md](analysis/lm-over-vpn-split.md) §3): cabinet with POC `DisableSocketHook = true`, `InterfaceName` = VPN adapter, VPN without default route (`route print -4`). Does it boot past Find LM / Connect LM? If not, capture `udp.port == 49000` on the VPN adapter (broadcast leaving? LM reply?) and retry with the VPN adapter's metric set to 1
- [ ] Real game, same setup: `NET entry` shows `local` = VPN IP, `global` = the internet public IP, realm `internet`; a match against a home (no-VPN) player starts and finishes
- [ ] Real game, same setup: during an online battle, is any traffic sent to the LM's VPN IP? Does a 30 s VPN outage drop the match?
- [ ] Real game: two cabinets of one LM in the same online room (same NAT) dial each other's VPN IP (`MATCH-NET` local same-NAT); battle starts
- [ ] Real game: LM over Tailscale (no broadcast). Expected to fail at Find LM; confirm
- [x] Per-mode queues: Mix Match (world 23) and Class Match solo (world 13) stay separate (2026-11-13); other modes not yet tried
- [x] `battleMode` other than 0 still uses the LM path (local LM matches work, 2026-11-13)
- [x] In-game cancel while searching sends CancelMatching and leaves the queue (2026-11-13)
- [x] Split setup: cabinet's own card server ≠ matchmaker (`MatchUrl` → main server); the two cabinets matched (2026-11-13)
- [x] Built-in STUN on a multi-homed Windows server PC: replies must leave from `StunHost` (fixed: bind to it), 2026-11-13

## Casual / shuffle
- [ ] 4 solo cabinets start a 2v2 using the server-assigned teams (`group_id`)
- [x] 1v1 / 2v1 rooms: the game plays them; the CPU partner is added by each cabinet locally (2026-11-13). `CpuStandInSeats` (server lists CPU seats) also accepted but changes nothing visible; off by default
- [x] `FillAfterSeconds`: 30 too slow for 2 players, 3 fine on a LAN; shipped default now 3 (with `NoCpuPartner` on, the fill timer no longer forms short-handed 2v2 rooms)
- [ ] Fixed pair: does the partner cabinet send its own entry, only poll, or neither?
- [ ] Record the in-game menu names of play modes 4, 5, 6 and their sub-modes (static analysis: 4 = Fes, 5 = Custom; 6 unknown)
- [ ] Team sortie with a CPU partner: is a result that omits the CPU entry accepted?

## Ranked (Class Match)
- [ ] Class Match menu appears with our `LoadClassMatch` tables
- [ ] Which class ID values IB uses; does class 0 break anything?
- [ ] How opponents' rank/grade is exchanged and displayed (P2P capture)
- [x] After a match, `SaveVsmOnResult` uploads the new rate (HTTP 200 on each cabinet's own card server, 2026-11-13); badge exp went negative after a loss → clamped at 0
- [ ] Next card read (`PreLoadCard`) shows the stored rate/grade in the Class Match screen

## Online tag / partner recruit ([analysis/partner-invites.md](analysis/partner-invites.md))
Box, fake cabinets + fake cards (2026-11-13): same-server invite tests + `server-sketch/loadtest/online_tag_e2e.py` 28/28.
2026-11-15: 170 matchmaker unit tests + `server-sketch/loadtest/cross_server_tag_e2e.py` 23/23. Keep the server
log lines named in each item.
- [x] Box: WebUI invite (user id + code; wrong / self / duplicate / reused code refused; code rotates), LoadCard tag_teams on both partners, world-5 pairing, mismatched keys + timeout, two tag pairs → 2v2, casual recruit pair, ranked recruit by class
- [x] Cross-server partner codes (box e2e): Create a code / Join on two card servers sharing `/tag`; wire ids; world-5 pair by shared code even when local card ids collide; team cosmetics last-write-wins through the matchmaker
- [x] Real game 2026-11-15 5:57 AM Pacific Time: two cabinets on **different** card servers (ServerId 1 and 2) created/joined a partner code, picked **オンラインタッグ** on TEAM SELECT (`TagStatus` 1), and were paired on the VPS matchmaker (`MATCH` world 5, shared code). About 25 s later they joined Mix Match as one duo. A 2v2 still waited for two more humans (`NoCpuPartner`).
- [x] `OnlineTag.TagStatus: 1` is required for the in-game list to be selectable (0 leaves the Online Tag panel greyed and empty). Default is now 1.
- [ ] Same-server WebUI invite (User ID + Invitation Code → ADD) still needs a real-game pass
- [ ] After the pair room: capture CheckMatching / P2P NAT for the world-5 duo (the 2026-11-15 test formed the team and then queued Mix Match as a duo)
- [ ] A completed 4-human 2v2 after an online-tag duo forms (vs another team or 2 solos); `SaveVsmOnResult` carries `tag_team_id` / partner
- [ ] Only one partner searches: after 90 s the cabinet gets `MATCH_CANCELED` (`drop … reason=matching timeout`); what does the game show (CAcSecPcbWantedFailer)?
- [ ] One partner cancels while waiting: the other keeps waiting until its own 90 s; no room with a stranger
- [ ] Two different tag teams searching at once never mix (different `key=` / codes)
- [ ] Results screen after a completed tag 2v2
- [ ] Partner recruit (急募) casual: two cabinets → `MATCH … recruit-casual pair`; who becomes leader (first listed = lower node id?); line_type PAIR_LEADER / PAIR_MEMBER in CheckCommunication
- [ ] Partner recruit ranked (Class Match): same class pairs (`recruit-ranked … key=…|class`), different classes don't
- [ ] Instant team (即席チーム) after a solo win: confirm no new server request is needed

## Results-hang fixes ([analysis/results-hang-fixes.md](analysis/results-hang-fixes.md) section 4)
Box, fake cabinets + fake cards (2026-11-14): 7 unit tests (`HangFixTests`) + `server-sketch/loadtest/hangfix_e2e.py`
15/15 with the flags on, 10/10 with them off. Not tested with the game yet.
- [ ] `tools\check-debugparam.ps1` on both cabinets (read-only): no `!!!` lines (#55 / #44)
- [ ] Server log after a match: any `Unhandled case`? Then `PostMatchStubs: true` and repeat; `NETREPORT` lines appear
- [ ] `OnlineMatching.HumansTeamVsCpu: true`: two solo cabinets become teammates vs 2 CPUs after `FillAfterSeconds`;
      battle starts? results screen ends?
- [ ] Same layout in LM mode, chosen by hand (teammates)
- [ ] During a hang: card key on one cabinet, then the other (card-reader symptom)

## Custom Match
- [ ] Press Custom Match with the LM running and log what the game requests

## Housekeeping
- [ ] Log-capture script for the user's launch method

## Real-game results (2026-11-13)
Times PT. Two cabinets (POC + SnowLauncher) on one Windows 11 PC, patched card server with in-process matchmaker
and built-in STUN. Details and the two-cabinets-on-one-PC recipe: [analysis/real-game-test-2026-11-13.md](analysis/real-game-test-2026-11-13.md).

**Works**
* Online queueing via `battleMode: 0` + built-in STUN; RegisterPcb / IssueNodeId / Entry / Check / Cancel.
* Split setup: cab1's card server was a second server instance whose `MatchUrl` pointed at the main matchmaker.
* Two cabinets matched and played full matches in Mix Match and Class Match solo; per-mode queues; in-game cancel.
* Results saved to each cabinet's own card server (class-match rate, badge).

**Fixed during the test**
* Built-in STUN on a multi-homed PC answered from the wrong source IP (the N2N adapter's) when bound to 0.0.0.0;
  the game dropped those replies → now bound to `StunHost`.
* Badge exp went 0 → −20 after a loss → clamped at 0.
* `FillAfterSeconds` 30 felt slow; 3 works on a LAN → shipped default now 3 (with `NoCpuPartner` on, unused for short 2v2 rooms).

**Open: results-screen hang after every 2-cabinet versus match**
* Servers and network are fine: captures show every message answered and the cabinets staying in sync; both card
  servers answered `SaveVsmOnResult` with 200. The games recover by themselves after a few minutes.
* Holding Start does not clear it. Server-side CPU stand-in seats were sent but did not fix it.
* It **also happens in local LM mode with no matchmaker**, with two LMs and with one shared LM.
* A solo route battle vs CPU does **not** hang.
* Conclusion: not caused by the matchmaking server; most likely two game instances on one OS interfering.
  Pending: Windows Sandbox test (cab2 in the Sandbox, own network stack) and a real two-PC test.

## Results-hang simulations (box, 2026-11-14 ~05:10 PT)
Fake cabinets + fake cards only, PC offline, no game / DLL run. Details: `analysis/results-hang-sim.md`.
* `server-sketch/sim/postmatch_replay.py` (post-match HTTP replay + fault proxy + SQLite lock): worst case 300.5 s only
  when the server never answers; with a working server the gate stays at F (9.8 s); a 35 s DB lock holds S/C 35 s
  (watchdog 8 s: 9.8 / 16.1 s).
* `server-sketch/sim/hang_model.py` (F/S/A/C + card prompts + reader variants, 24 scenarios vs evidence E1–E8).
* `tools/banapass-harness/build_and_test.sh`: patch applies, Windows syntax check OK, unit harness 32/32 as expected
  (original / v1 / v2); v1 stale-cancel race found and fixed in v2.
* `dotnet test Tests/Matchmaking.Tests`: **86/86** (13 `HangSimTests` + 10 `HumansVsCpuSimTests` runs of 6/24/120 cabinets).
* `server-sketch/loadtest/hangsim_e2e.py`: off 6/6, on 6/6. Regression: `hangfix_e2e.py` off 10/10, on 15/15;
  `online_tag_e2e.py` 28/28.

## Rolling fill, in-store wait, and Fes 1on1 (2026-11-14, patch commits 15–18)

Docs: [`server-sketch/ib-server/RESULTS-GAP-AND-ROLLING-FILL.md`](server-sketch/ib-server/RESULTS-GAP-AND-ROLLING-FILL.md).
Those commits, plus v10–v12, are in `online-matchmaking.patch` (now 26 commits) and as a standalone series in
`server-sketch/ib-server/results-gap-and-rolling-fill/`.

* [x] Rolling fill timer (`FillTimerMode=Rolling`, `FillAfterSeconds` 30, `MaxFillWaitSeconds` 90): four cabinets
  in Mix searched staggered and merged into one 2v2; that **4-human room cleared the results screen**.
* [x] In-store shuffle goes through the matchmaker. A 30 s shared window closed a 1v1 ~10 s before the late pair
  searched; those 2-human + 2-CPU rooms hung after results. Fix: `InStoreFillAfterSeconds` 60 /
  `InStoreMaxFillWaitSeconds` 120 (unit tests include that timeline). **Needs a 4-cab in-store retest** with
  everyone searching within a minute.
* [x] Fes 1on1 (`OneOnOneWorlds` default `"20"`): a 1v1 Fes match through the VPS matchmaker completed
  2026-11-15 04:24 PT (two cabinets). Restart cabinets after setting that day's `FesConfigurations.*Type`
  to a `OneOnOne*` value (the Fes rule loads at boot).
* Logging: `LogResultGap` (default on) times the hang (`RESULT-SAVE` / `RESULT-WAIT` / `RESULT-GAP`).

## NoCpuPartner, v12 SoftWait, and the VPS matchmaker (2026-11-15)

Docs: [`server-sketch/ib-server/RESULTS-GAP-AND-ROLLING-FILL.md`](server-sketch/ib-server/RESULTS-GAP-AND-ROLLING-FILL.md)
sections 5–10. 150 matchmaker unit tests pass.

* [x] `NoCpuPartner` (default on): 2v2 worlds only form full 4-human rooms. 3-cab test 2026-11-15 02:18 PT:
  the Teamplay duo cleared results; the solo with a game-made CPU partner hung. With the flag on, 2–3
  players wait for a 4th human or their own ~150 s matching timeout, then return to practice and can
  search again. **Disclaimer: 2v2 matches only form when at least 4 human players are present.**
* [x] v12 SoftWait: a complete 4-human room (e.g. a Teamplay duo + 2 solos with different Mix veteran
  flags) starts immediately instead of waiting ~15 s. Tested 2026-11-15 03:13 PT.
* [x] Fill timers shipped at 3 s (`FillAfterSeconds` / `MaxFillWaitSeconds` / in-store overrides).
* [x] VPS matchmaker (`<VPS_IP>:28090`, built-in STUN): a Fes 1on1 completed 2026-11-15 04:24 PT
  after local card servers pointed `MatchUrl` / `StunHost` at the VPS.

## Cross-server online tag (2026-11-15)

Docs: [`docs/SETUP.md`](docs/SETUP.md) B5 and `ONLINE_MATCHMAKING.md` inside the card-server patch
(now 26 commits). 170 matchmaker unit tests pass; `cross_server_tag_e2e.py` 23/23.

* [x] Shared partner codes live on the matchmaker (`/tag`). Each card server needs a distinct
  `OnlineTag.ServerId`. Leave `InviteUrl` empty so it is derived from `MatchUrl` (`/match` → `/tag`).
* [x] Team name / BGM / effect / background / emblem / name color saved on one card server is pushed to
  `/tag` and pulled on the other (last-write-wins, matchmaker timestamp).
* [x] `OnlineTag.TagStatus` default 1: with 0 the in-game オンラインタッグ panel stayed greyed and empty
  even after LoadCard sent `tag_teams=1`.
* [x] Real game 2026-11-15 5:57 AM Pacific Time: cab 1 (ServerId 1) and cab 2 (ServerId 2) searched
  Online Tag with the shared code and were paired immediately; they then entered Mix Match as a duo
  and waited for two more humans (expected under `NoCpuPartner`).

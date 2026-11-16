# DRAFT: Patching the cabinet game executable

> **This is a draft.** It describes optional, reversible changes to a copy of the
> *Extreme Vs. 2 Infinite Boost* cabinet executable that you already own. It is not a
> release, and it is not required to use the matchmaking server.

This repository does **not** include the game, the executable, patch bytes, file offsets,
hashes of the game executable, or the patch scripts themselves. The scripts are distributed
privately. You must already have a legitimate copy of the game. Never add a game executable,
a patched executable, or a script that contains patch bytes to this repository, to cloud
storage, or to a public server.

Related findings from the 15–16 November 2026 cabinet tests:
[findings-2026-11-15-16.md](findings-2026-11-15-16.md).

## Why a game-side patch is needed

Some behaviour is decided only on the cabinet. The matchmaker can answer a poll with “still
waiting” or with a finished room. It cannot skip the partner-lost prompt, keep a pair in
search after the game has cancelled, or stop a loser from going to GAME OVER.

**Pairs.** On an unpatched cabinet, a searching pair is cancelled by the game after about 30
seconds and the pair leader is shown a partner-lost / CPU prompt. Official Japanese cabinets
avoid a long idle search by starting waiting Practice (対戦待ちCPU戦) **without leaving the
queue**, so a human match can still form. A server-only “never send the pair a CPU room”
flag (`PairNeverCpu`) was tested on 15 November and is not enough: the unpatched game still
cancelled at ~30 seconds. The pair keep-searching patch is what lets a pair stay in the
search, closer to that official behaviour.

**Free-play losers.** Our cabinets run free-play, and online results are saved, but the
unpatched game still sends a loser to GAME OVER. There is no server or test-menu setting
that changes that decision. The free-play patch makes a loser take the same continue / search
path that a winner already uses.

## What each patch does

These patches stack. Each one is a separate layer and can be applied or removed on its own,
as long as the executable is a known starting point (original or already carrying the other
agreed layers).

### Pair keep-searching — A (recommended)

When a pair’s search ends without a battle, the pair leader no longer opens the partner-lost
prompt. It still cancels that search attempt, then automatically starts a new search with the
same partner. The cycle can repeat until a human room arrives or the players back out. In
between, they can practise if the usual practice handshake works.

In testing on 16 November, after this patch was applied to all four cabinet copies, a
searching pair stayed in search for the full ~150-second matching window and then re-entered
automatically, with no partner-lost prompt.

### Pair keep-searching — B (optional)

This only lengthens, from about 30 seconds to about 150 seconds, how long a pair will wait
for its shared practice-join handshake before the game gives up on that practice round. It
does not change real-match timeouts. A partner cabinet that has actually gone away is still
detected and is not held for the longer wait.

Use B only if patch A is already on and a searching pair is still stuck for a long time on a
bare “finding opponents” screen, never making it into waiting practice. It is not required
for the keep-searching loop itself.

### Free-play, no GAME OVER — FULL (default)

After a normal online match, a loss or a draw no longer ends the play. The loser goes back
to practice and searching on the same card, the same way a winner does, without GAME OVER
and without re-swiping. This also removes the 10-win cap: ten straight wins no longer force
the play to end.

Force quit from the OPTION menu still ends the play. Abort / error exits, event-mode and
return-match handling, and time rental are left alone. Offline CPU / training routes are
not covered.

In testing on 16 November (full version, stacked on pair patch A), losers from a four-human
online match searched again with the winners, on the same cards, with no GAME OVER.

### Free-play, no GAME OVER — LossOnly

Same idea, but only skips GAME OVER after a loss or a draw. Ten straight wins still end the
play. Use this if you want to keep the 10-win cap.

### Force-end / hold-Start (on hold, not recommended)

A patch that would open a force-end prompt by holding Start during practice, searching, or a
match is **on hold**. The game has no existing hook there to redirect, so that version would
be larger and riskier than the patches above.

A smaller, untested change would add an extra item to the OPTION window on the results
screen. It has not been confirmed that this item is really force end, and it is **not
recommended**. Do not apply it.

## Safety rules

1. **Own a legitimate copy** of the game. These scripts only edit an executable that is
   already on the cabinet PC.
2. **Close every cabinet game process first.** The scripts refuse to change a folder whose
   game process is running. The LM can stay closed or open as you prefer, but it is safer to
   close the cabinets and leave the card servers running.
3. **Back up the original executable** before the first change. The scripts write a verified
   backup in that cabinet folder’s `_re\exe-backup` directory. Keep those backups on the PC.
   Do not copy the executable into this repository, Drive, or a VPS.
4. **Hash verification, without publishing hashes.** The scripts check that the executable
   is a known starting point, verify the bytes they are about to change, write the change,
   read it back, and restore the backup if the check fails. If the executable is not a
   version they recognize, they refuse rather than guess.
5. **Patch each cabinet folder separately.** If you run more than one cabinet from the same
   PC, each copy lives in its own folder (for example the main game folder and `_P2`, `_P3`,
   `_P4`). Patch all of them, or a pair can be mixed: an unpatched leader still cancels at
   ~30 seconds and shows the prompt. The apply scripts accept an “all folders” flag so you
   do not have to do this by hand.
6. **Do not patch the Live Monitor executable.** The LM uses a different file. The pair and
   free-play logic that these patches change is cabinet-side only.
7. **Revert per layer.** Each layer has its own revert script. Reverting the free-play patch
   leaves the pair patch in place. Reverting the pair patch when free-play is also present
   is done at the byte layer so the other layer can be kept; follow the private script
   instructions. If anything looks wrong, close the cabinets and revert, or restore that
   folder’s backup from `_re\exe-backup`.
8. **Start order after a patch or a revert:** card servers, then the LM, then the cabinets.

## Matchmaker settings for patched pairs

Set these on the matchmaker **before** you rely on the pair keep-searching patch, and keep
`CrossWorldTeamRooms` off even if you are not using the patch:

| Setting | Value | Why |
|---|---|---|
| `PairNeverCpu` | `true` | Do not send a waiting pair a CPU room that would end the search. |
| `PairCancelQuarantineSeconds` | `0` | Each keep-searching cycle cancels and re-enters. A quarantine left at its default (180 seconds) can hold those re-entries as “still waiting” and block a real room. |
| `CrossWorldTeamRooms` | `false` | The experiment that mixed a pair with two solos from the linked world failed during loading on real cabinets, twice, on 16 November. Leave it off. |

`ContinuePair` CPU fallback and `ContinuePairAfterCpuSeconds` should also be off for
patched cabinets, or they will still be given CPU rooms. `NoCpuPartner` can stay on: four
human players are still required for a 2v2.

## Test plan

Do this with the cabinets idle, then start card servers, LM, and cabinets in that order.

1. **Lone pair.** A Class or Mix team pair searches with nobody else in the queue. Expect no
   partner-lost prompt and no black screen. The pair should stay in search through the
   ~150-second matching window and then re-enter automatically. Watch the matchmaker log for
   cancel / re-entry lines, not for a CPU room.
2. **Pair plus two solos, same mode.** Start the solos 40–60 seconds after the pair. Expect a
   four-human room. Do this in Mix if the other two players are solos; Class solo and Class
   team will not share a room.
3. **Continue after a win.** Win a match, continue as a team, and search with nobody else.
   Confirm the pair still keeps searching and does not silently split into solos.
4. **Manual back-out.** A player cancels the search. The pair should leave cleanly.
5. **Free-play loss.** Play an online match and watch the losing side. They should go back to
   practice and searching on the same card, with no GAME OVER and no re-swipe. Then lose
   twice in a row on one card and confirm the card server saved both results with the
   session still open.
6. **Force quit.** OPTION → force end should still end the play.
7. **Regressions.** Solos should still time out at about 150 seconds and be able to search
   again. A normal four-human room should still play and save. If a partner drops **during**
   a real battle, that mid-battle prompt should still appear (it is not part of these
   patches).

If anything fails, close the cabinets and run the matching revert script, or restore the
backup in that folder’s `_re\exe-backup`.

## Known risks

- **Mixed copies.** If only some cabinet folders are patched, a pair whose leader is
  unpatched behaves like an unpatched pair.
- **FULL free-play removes the 10-win cap.** The win counter can keep rising. Use LossOnly
  if you want the cap to remain. The card session stays open across a loss, similar to a
  long win streak; the lost battle is still saved before the continue decision.
- **Not gated on the free-play setting.** The no-GAME-OVER change applies whenever the
  general end-of-play path runs. That is acceptable on cabinets that already run free-play.
  In coin mode it would also let a loser continue.
- **HUD or pair-continue prompts** after a loss may look unusual. A losing pair may still be
  asked whether to break up the team. Report that if it happens.
- **Several game copies on one PC** already have separate problems (results-screen hangs,
  video-memory-management bug checks, loading-phase 21-01 disconnects). These patches do not
  fix those. Do not pin cabinet processes to a small set of CPU threads; that made loading
  problems worse in testing.
- **A new game version** will not match the scripts’ known starting points. The scripts
  should refuse. Do not edit the executable by hand.
- **Force-end / hold-Start** remains untested and is not recommended, as described above.

## What this guide will not include

Patch bytes, file offsets, disassembly, hashes of any game executable, and the scripts that
apply those bytes will stay private. If you did not receive the scripts through a private
channel, you cannot apply these patches from this repository alone — and that is intentional.

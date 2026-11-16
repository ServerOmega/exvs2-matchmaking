# Known issues

Experimental matchmaker, last updated **16 November 2026** (America/Los_Angeles). These are problems seen
on real cabinets or that follow from how the game and this server work. Longer background:
[MATCHMAKING-BEHAVIOUR.md](MATCHMAKING-BEHAVIOUR.md). Setup: [SETUP.md](SETUP.md).

Do not publish a VPS public IP; use `<VPS_IP>`.

## Matches take a long time to form

**Symptoms.** Cabinets sit on the search screen for a minute or more, or cancel and search again, even though
four people are trying to play. It can feel as if the matchmaker is slow.

**Cause.** The server matches **instantly** once four compatible humans are searching in the **same**
world / queue. The wait is almost always that they were not all searching together. Seen in a Class Match
test on 16 November 2026, 1:31–1:43 AM Pacific Time:

* **Not everyone is searching at once.** Losers may be on the title screen or waiting for an automatic
  card re-read (about 45–60 seconds). Winners may still be on the results screen or in a CPU match.
* **Different modes are different queues.** Mix Match is world **23**, Class Match solo is **13**, Class
  Match team is **14**. They never meet. In the 1:39–1:42 AM stretch, one cabinet searched Mix while the
  other three were in Class; no room could form until that cabinet cancelled, restarted, and came back
  into class solo at 1:41:23. Meanwhile the others hit the game's **150-second** search timeout, cancelled,
  and requeued. A match formed at 1:42:40, the moment all four were in class solo together.
* **The pair-cancel guard** can hold cabinets out of new human rooms for up to **180 seconds**, or until
  they enter with a fresh node id (title screen and a card swipe). At 1:33–1:37 AM, one cabinet was held
  for about 20 seconds after a pair split, then waited alone until its partner came back with a clean
  start; the match started at 1:37:33.
* **`NoCpuPartner` is on by design.** The server will not fill a short-handed 2v2 with a CPU teammate, so
  three humans wait for the fourth (or until each cabinet's own 150-second timeout).
* **A class pair cannot match class solos** (see the issue below), so those four can wait forever in
  Class Match even if they all search at once.

A possible later option is to start three humans plus one CPU after a delay (for example 60 seconds).
That is **not implemented** in this pre-release.

**Workaround.** Everyone pick the **same mode**. For a pair plus two solos, use **Mix Match**. Wait until
all four cabinets are on the search screen before anyone starts searching, when you can. After a pair
cancel or a black screen, send those cabinets through the title screen so the guard lifts at once.

**Status.** Understood; not a slow matchmaker. The optional 3-human + 1 CPU delay is a possible future
setting, off / absent today.

## Pair loses to CPUs, requeues, then sees a partner / CPU prompt and a black screen

**Symptoms.** A fixed pair (for example after Online Tag, or two cabinets that stayed together) is sent a
CPU match because nobody else joined in time. They lose, search again, and one or both cabinets show a
prompt about sticking with a CPU or that the partner was lost. If the two cabinets answer differently
(one Yes, one No), both can sit on a **black screen** for about two minutes.

**Cause.** The game, not the server, cancels a pair's search after about **30 seconds** on a bare
"finding opponents" screen and then shows that prompt. A pair that has just come out of a CPU match and
queues again can hit the same path. Splitting the pair (different answers, or only one cabinet letting go)
leaves the cabinets in a bad state. This is still **under investigation**: we do not yet have a server
reply that reliably avoids the prompt on this requeue.

**Workaround.** After a black screen, have the other cabinet release the partner, or wait about two
minutes. A clean path back through the title screen and a card swipe clears it faster. For pair nights,
**Mix Match** is the safer mode (see the class-match issue below). If a pair does cancel, this build's
pair-cancel quarantine holds those cabinets out of new human rooms until they come back through a clean
restart, or for up to three minutes, so they are not placed in a half-reset state.

**Status.** Open / under investigation. The quarantine (default 180 s, `PairCancelQuarantineSeconds`) is
in this pre-release and stops the follow-up 21-01 from a dirty re-entry. It does not remove the prompt.

## A class-match pair cannot match two class-match solos

**Symptoms.** Two cabinets queue as a class-match team. The other two queue as class-match solos. They
never end up in the same room. The pair may be sent versus CPUs after 18 seconds even if the solos
joined the queue at almost the same time.

**Cause.** Class Match solo (world **13**) and Class Match team (world **14**) are separate queues, like
official Class Match G, where solo and team have separate class tracks. The server links those worlds
for some regroup waiting, but it will not put a class pair and two class solos in one class room
(`CrossWorldTeamRooms` is an experimental option, off, and untested with the game). Even when all four
search together, timing can also go wrong: if the pair has already waited 18 seconds, they may already
have been sent a CPU room a moment before the solos arrived. Once a room is sent, it cannot be merged
later.

**Workaround.** Use **Mix Match** when a pair and two solos should play together. Or have the two solos
also pair up, so both teams are in the class team queue and can match each other.

**Status.** Limitation, matches official Class Match G. Mix Match is the mode built for this mix.

## The Live Monitor and cabinets must start after the card servers

**Symptoms.** The Live Monitor looks wrong or the cabinets never reach the card servers, even though the
card servers are running and healthy. Sometimes this is noticed only after a later 21-01.

**Cause.** The game does not retry its card-server check. If the LM and cabinets start while the card
servers are still down (for example they were restarted a few minutes later), the LM and cabinets fail
that check and never talk to the card servers again until they themselves are restarted.

**Workaround.** Leave the card servers running. Close the LM, the LM wrapper (`Run_iboost_LM_mode_v4`
or similar), the cabinets and the client wrapper, then start the cabinets with the usual four-client
script and confirm the LM window comes up *after* the card servers are already listening.

**Status.** Understood. This is a game / startup-order issue, not a matchmaker bug.

## Restarting the matchmaker (VPS) disconnects every cabinet (21-01)

**Symptoms.** Every cabinet shows Live Monitor error **21-01** at the same moment. Play stops until the
cabinets are restarted.

**Cause.** The matchmaker process going down drops the cabinets' match and STUN connection. A typical
case is a VPS deploy that restarts the service. The downtime can be only seconds, but the game does not
recover by itself.

**Workaround.** Restart the cabinets after the matchmaker is back up. Operators should warn players and
avoid restarting the VPS or the matchmaker service while cabinets are running.

**Status.** Expected while the matchmaker is in-memory. There is no reconnect without a cabinet restart.

## 21-01 when a half-reset cabinet joins a room

**Symptoms.** After a pair cancel or a black screen, some cabinets come back through the title screen
and others jump back into matchmaking mid-session. A new room forms, then three cabinets drop with 21-01
during loading and one stays up.

**Cause.** The cabinet that skipped a clean restart kept its old node id (no new `IssueNodeId`). The
server used to place that dirty entry in a room with freshly restarted cabinets. The other three then
dropped during loading.

**Workaround.** After a pair cancel or black screen, send those cabinets back through the title screen
(card swipe) before they search again.

**Status.** Mitigated in this pre-release by the pair-cancel quarantine (see the first issue). After a
pair cancel, those cabinets are held out of human rooms until a new node id or three minutes have
passed.

## 21-01 when the Live Monitor closes

**Symptoms.** Searching cabinets show 21-01 first. Cabinets already in a CPU (or other) match may only
show it when that match ends, so it can look as if "everyone" dropped a minute later.

**Cause.** The Live Monitor process is no longer running. 21-01 is the cabinets losing the LM. This has
happened when the LM was closed on the desktop, and earlier when it crashed. It is not caused by the
VPS being down (check that the matchmaker is still up) and not by ordinary STUN noise (see below).

**Workaround.** Start the card servers first, then the LM and the cabinets, as in the startup-order
issue. Do not close the LM window while the cabinets are running.

**Status.** Understood. Not a matchmaker bug.

## Junk STUN / match traffic from outside addresses

**Symptoms.** The VPS log or firewall shows a lot of unsolicited packets at the STUN and match ports
from a few internet addresses.

**Cause.** Ordinary internet noise hitting a public service. The same traffic was present before and
during matches that completed normally, including successful 4-player rooms, so it was not the cause of
the 21-01s above.

**Workaround.** None required for play. A tighter rate limit on this noise is a possible later hardening
step; it is not in this pre-release as a running change. Existing `/match` and `/tag` rate limits still
apply to those HTTP APIs.

**Status.** Observed, not blamed for disconnects.

## Two cabinets on one PC: results screen hangs after a versus match

**Symptoms.** After a 2-cabinet versus match on one PC, both cabinets sit on the results screen for
minutes, then recover by themselves.

**Cause.** Seen also in local LM mode with no matchmaker at all. It is not caused by this server. Most
likely two game instances on one OS interfering. A solo route battle versus CPU does not hang.

**Workaround.** Wait; the games recover. A two-location / two-PC test is still the way to confirm it
goes away on separate machines.

**Status.** Open, documented in [the 13 November 2026 test report](../analysis/real-game-test-2026-11-13.md).

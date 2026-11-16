# How this matchmaker behaves (and how official cabinets differ)

Plain-language notes from cabinet tests on **15–16 November 2026** (America/Los_Angeles) and from public
official Infinite Boost pages. Symptom lists and workarounds: [KNOWN_ISSUES.md](KNOWN_ISSUES.md).
Setup: [SETUP.md](SETUP.md).

This is a custom matchmaker on private cabinets. It is **not** affiliated with Bandai Namco. Official
timer values are mostly unpublished; where this document reports a number, it was measured on our
cabinets or read from this server's settings.

Do not publish a VPS public IP; use `<VPS_IP>`.

## Free-play and GAME OVER

Our cabinets run **free-play**. After a loss, the card is often re-read automatically about 45–60
seconds later, and the player can search again without inserting a credit. Winners who hit Continue
can re-enter the queue much sooner, often still together as a pair.

Official Japanese cabinets are **credit-driven**:

- **1-credit play:** keep playing after wins, up to ten in a row. One loss, or the ten-win cap, is
  GAME OVER.
- **2-credit play:** three matches are guaranteed (a waiting-CPU-battle loss counts as one of them),
  with extra matches from those wins.
- **Time rental:** a block of time, not used on every shop.

Official sources do not describe an automatic card re-read that silently puts a loser back into
matching. When our automatic re-read does not happen, official behaviour is what we see: the cabinet
returns to the title screen and stays there until someone swipes a card or presses Start. That gap is
why a continuing pair can finish a CPU fight before the losers are even back in the queue.

## The in-game pair timer and the partner-lost prompt

A pair that sits on a bare "finding opponents" screen is cancelled by **the game** after about **30
seconds**. That 30 seconds is a client limit, not a server setting. The cabinet then shows a
partner-lost prompt (whether to continue with a CPU). If the two cabinets answer differently, both
can go to a black screen for about two minutes.

Official Infinite Boost pages reviewed in mid-November 2026 do not document this exact message or a
published 30-second pair-search limit. Official cabinets appear to avoid a long idle search by moving
players into **waiting Practice** (対戦待ちCPU戦) while the search is still running. See
[Official Japanese cabinets](#official-japanese-cabinets) below.

## Rooms are final once they are sent

When this server answers CheckMatching with a room, **that room is finished**. It cannot later absorb
two more humans, and two 1v1 groups cannot be merged into one 2v2. If a pair is already in a CPU
room, later-arriving solos cannot join it.

Official Class Match G shuffle is described as gathering four solos and randomly assigning teams, not
as a staged merge of two already-started 1v1s. Official 1v1 in Infinite Boost is a **local 4-cabinet
rental rule**, not an online merge. Mix Match can put a fixed pair against two solos, but that is
unfiltered matching at search time, not a mid-search merge of two rooms.

## ContinuePair VsCpu at 18 seconds (why not 30)

To beat the game's 30-second pair timer, this server's default is `ContinuePairMode=VsCpu` and
`ContinuePairSeconds=18`. If a lone all-human pair has waited 18 seconds and no 4-human room has
formed, the server sends them a room against two CPU stand-ins.

**18 seconds is the original server value** from the continue-pair fix. It is under the game's ~30
second give-up, so the CPU room should arrive before the prompt. **Do not set the server timer to
30 seconds** — that races the in-game timer and can bring the black screen back.

12 seconds was tried later so the answer would be ready with more margin before the pair's second
CheckMatching poll (the pair leader typically polls at about 3 seconds, then every 15 seconds). After
the 16 November 2026 tests the default was restored to 18. In those tests, a Mix Match pair that
waited with only one other cabinet searching did get the CPU room at 18 seconds, with no prompt.

This is a workaround, not official behaviour. Official waiting Practice is still a search; our CPU
room **ends** the search.

## Solo pair versus CPU (off)

An experiment (`SoloPairVsCpuSeconds`) sent two leftover solos versus CPUs after a short wait, so
they would not sit idle. In testing this **froze cabinets**. The setting is **off by default** (0).
Leave it off.

## Class Match solo and team are separate worlds

Class Match solo is world **13**. Class Match team is world **14**. They are separate queues, in line
with official Class Match G (solo and team have separate class tracks). This server also links those
worlds, and free-solo (18) / free-team (19), for some regroup waiting so winners and losers are more
likely to meet again — but a class pair and two class solos still cannot share one **class** room.

`CrossWorldTeamRooms` is an experimental option that would form one room from a class (or free) team
and two solos in the linked world. It is **off** and has not been tested with the game.

For a night of a pair plus two solos, use **Mix Match**, which has no solo/team split and no class
filter. Or have the two solos also pair up, so both teams search in the team queue.

## PairNeverCpu test: the game does not practice and keep searching

`PairNeverCpu` (and `PairCpuFallbackSeconds=0`) was a server-only test: never send a waiting pair a
CPU room, and keep them in the queue, hoping later humans could still be matched. On the evening of
15 November 2026 the server did keep the pair waiting, but at about 30 seconds the **game** cancelled
the search and showed the partner-lost prompt. Because the two cabinets answered differently, both
went to a black screen.

**The unpatched game does not practice-and-keep-search.** The flag is off in this pre-release.
Official cabinets get a similar "occupy the cabinet while waiting" effect by starting waiting
Practice without leaving the queue. This server cannot do that by itself.

## Pair-cancel quarantine

After a pair cancel (or a stale / timeout drop of an all-human duo), this build holds those node ids
and cabinet serials out of new human rooms (`PairCancelQuarantineSeconds`, default **180**). A
quarantined re-entry is answered with the normal "still waiting" poll reply, never with a room. The
hold lifts when the cabinet enters with a **new node id** (IssueNodeId after a clean restart, or a
card swipe from the title screen) or when the timer expires.

This was added after a 16 November 2026 incident: a pair hit the 30-second prompt, black-screened,
then one cabinet re-entered mid-session on the same node and was placed in a 4-player room. The other
three cabinets got Live Monitor **21-01** during loading.

## 21-01 disconnects

21-01 means the cabinets lost the Live Monitor or could not finish loading a match. Causes seen in
testing:

1. **Matchmaker / VPS restart.** A deploy that restarts the service drops every cabinet for the
   downtime. Warn players first; restart the cabinets once the service is back.
2. **The Live Monitor closing or crashing.** Searching cabinets notice first; cabinets still in a
   match may only notice when that match ends.
3. **A half-reset cabinet joining a room** with freshly restarted cabinets (the quarantine above).

Startup order matters. The game does not retry its card-server check. Start the **card servers
first**, then the Live Monitor and the cabinets. If the LM and cabinets start while the card servers
are down, they fail that check and never talk to the card servers until they are restarted.

## Why searches can feel slow

The server forms a room **as soon as** four compatible humans are searching in the same world / queue.
It does not add a matching delay of its own.

Long waits come from the cabinets not all being in that state at once. A Class Match session on
16 November 2026, 1:31–1:43 AM Pacific Time, showed the usual causes together:

* Cabinets still on the title screen, results screen, or waiting for a 45–60 second card re-read.
* One cabinet in **Mix Match** (world 23) while the others were in **Class Match** (solo 13 or team 14).
  Those queues never mix. The Mix cabinet cancelled at 1:40:30 and re-entered class solo at 1:41:23;
  a four-solo class room formed at 1:42:40, the instant all four were in the same queue.
* The game's own **150-second** search timeout. Cabinets that have been waiting that long cancel and
  start a new search, which can desynchronize the group.
* The **pair-cancel quarantine** (default 180 seconds, or until a new node id). After a pair split at
  1:33, one cabinet was held briefly, then waited alone until its partner returned with a clean start
  at 1:37:33 — and the match started immediately.
* **`NoCpuPartner`:** three humans are not given a CPU teammate, so they wait for a fourth.
* The Class Match solo / team split, which can keep a pair and two solos apart even when all four
  search at once.

Tips: everyone pick the same mode; wait for all four to be on the search screen; use Mix Match when a
pair and solos should play together.

A possible later option is to start three humans plus one CPU after a delay. That is not in this
pre-release.

## Optional game-side change (last resort)

There is research into a small change on the game side that would raise the in-game pair-search
timeout (about 30 seconds) toward the general matching timeout (about 150 seconds). The aim would be
to let a pair stay in search longer, closer to official waiting Practice, without the partner-lost
prompt. That work is a **last resort**, is not part of this pre-release, and this document does not
include patch bytes, file offsets, or reproduction steps.

## Official Japanese cabinets

Summary of public official and community sources researched on 15 November 2026. Official launch of
Infinite Boost is 17 July 2025. Official operator manuals with exact timer values were not found.
Treat unpublished numbers (how long official cabinets search before Practice starts, grade-window
widths, mid-round interrupt timing) as unconfirmed.

**Modes.** Official online play has four modes:

- **Class Match G** — skill-based, inside a class, closer grades preferred. Solo sortie (shuffle) and
  team sortie (fixed pair) have **separate class tracks**. Partner Wanted (パートナー急募) is Class
  Match G only.
- **Mix Match** — replaces the previous title's Free Match. Everyone, with no solo/team split and no
  class filter. A Mix room can therefore put a solo group against a fixed pair. That mixing is a
  property of Mix, not of Class Match G.
- **Custom Match** — a private or public room. No class effect.
- **In-store Match** — only cabinets in the same shop.

Ranked online play officially requires a linked, authenticated Bandai Namco Passport, with a few
exceptions (in-store match, and Mix from midnight to 7:00 a.m., can be played with an unregistered
card or with no card). Our private cabinets do not implement that account requirement.

**Waiting for a match.** Official wording: during the matching wait for online battles, you play
Practice, officially a waiting CPU battle (対戦待ちCPU戦). You are still in the search. A human match
can still form; Partner Wanted can even complete during that fight, after which you reselect your
suit. Dedicated CPU modes (Training, Tutorial, standalone Practice chosen as a CPU mode, Route
Battle) are different: they are isolated from other players.

That is the main official / custom mismatch. Our 18-second CPU send **ends** the search, so later
cabinets cannot join. Official waiting Practice does not end the search.

**After a match.** Winners with remaining credit continue into the next search, and officially into
another waiting Practice if a human match is not ready. A 1-credit loser goes to GAME OVER. Return
Match (リターンマッチ) is a community-documented rematch feature; this server does not try to
reproduce it.

**Classes and grades.** Four classes: Pilot, Valiant, Ace, Extreme. Solo starts at Pilot; team starts
at Valiant (Pilot is solo-only). Each class has ten grades (10 starting, 1 highest normal); Extreme
also has Grade ∞. Promotion and demotion are judged after every match. Bandai Namco has not published
the width of the grade window or clock-second search limits.

**Sources (primary official pages first):**

- [Online battle modes](https://gundam-vs.jp/extreme/ac2ib/howto/game_mode/online/)
- [CPU / Training, including Practice during the matching wait](https://gundam-vs.jp/extreme/ac2ib/howto/game_mode/vs_cpu/)
- [Credit modes, time rental, 4-cabinet rental](https://gundam-vs.jp/extreme/ac2ib/howto/others/credit/)
- [Player status: classes and grades](https://gundam-vs.jp/extreme/ac2ib/howto/rules/status/)
- [atwiki glossary](https://w.atwiki.jp/exvs2infiniteboost/pages/172.html) (community, secondary)

Gundam VS. Mobile matching-adjustment notices could not be opened from the research environment
(HTTP 403).

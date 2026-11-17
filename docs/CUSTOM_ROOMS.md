# Custom Match rooms

Last updated **17 November 2026** (America/Los_Angeles). Applies to the 60-commit `online-matchmaking.patch`
(branch `feature/custom-rooms`, release `v0.6.0-pre`). Every card server **and** the matchmaker need this build.

## What works

* Friends make a private room on the card server's web page, share the room code, and everyone who joined meets
  in the same Custom Match queue — **even when their cabinets use different card servers**, as long as all card
  servers use the same matchmaker.
* **Confirmed on real cabinets, 17 Nov 2026, 12:33 PM PT:** four cabinets on two card servers queued Custom Match
  in the same room; the matchmaker built a full 4-human 2v2 with no CPU, and all four got "match found" within
  about 3 seconds.
* No exe patches are needed to play on our card server (see [SETUP.md](SETUP.md)).

## How to use it (players)

1. Open your card on the card server web page → **Custom Match Rooms**.
2. **Create** a room (name, solo or team, open/close time, class range, fes rule) or **Join** with a code from a
   friend. The room you create or join becomes your card's pick for the cab automatically.
3. In several rooms? Press **Use this room** on the one you want. The **last pick wins** (web or LM).
4. On the cab: touch your card and choose **Custom Match**. The bottom-right says searching.
5. Leaving or closing a room clears the pick. Rooms close at the daily reset.

Press **Ctrl+F5** on the Rooms page after a card-server update; an old cached page can show stale data.

### Which fes rule?

* **Dual Select** is a **2v2** rule (each player picks two units, then plays one of them in a normal 2v2). With
  `NoCpuPartner` it waits for **4 humans**, like any 2v2.
* **One (0–4)** and **One XU (0–4)** are the **1v1** rules. Two solo players in such a room are paired 1v1 right
  away with no CPU. *(Unit-tested and running on the LA matchmaker; not yet tried on real cabinets.)*
* No rule: a normal 2v2 custom room.

## How it works (operators)

| Piece | Behaviour |
|---|---|
| LM `LoadRoom` (418) | After a card touch the LM asks for the card's rooms. The reply needs `status = 1`; only `tag_type` **2** (private list, up to 7 rooms) and **4** (the single public slot, the yellow パブリックルーム box) are shown. Rooms outside their open/close window are dropped by the LM. |
| LM `RegisterRoom` (419) | Stores the room the card picked on the LM (`status = 0` = OK). Optional now that the web page picks for you. |
| Cab `PreLoadCard` | Sends `matching_tag` **only if the card has a selected room**. Without one the cab skips Custom Match (the registry answers 204 for "no pick"). |
| Shared registry | Lives on the matchmaker under `/tag/rooms` (create, join, leave, close, select, lookup). Lookup is a POST so room codes never appear in URLs or access logs; codes are masked in logs. Card servers call it with the existing `X-Tag-Secret`, so no new port or secret. |
| `CustomRooms.LocalStore` | `false` (use the matchmaker's registry) whenever `MatchUrl` / `InviteUrl` is set. `true` keeps rooms in-process for a single-PC test; such a server cannot share rooms with others. |
| Matchmaker key | Custom-room worlds 6–9, 24 and 26–33 are keyed on the **room id**, so each room is its own queue. `queue_start` events log the room id. |
| `CustomRooms.TimeZone`, `DayResetHour` | Time zone for open/close times and the daily reset. Set it on the matchmaker that hosts the registry (for example `America/Los_Angeles`). |
| Web UI | Card server `/Cards/Rooms/{chip}`, API `/ui/rooms/*` (access code + chip id in the POST body, never the URL). Times accept `HH:mm`, `HH:mm:ss`, 12-hour AM/PM and `24:00`. |

Most VS.Mobile room options (comment presets, class/win-rate bounds, rematch, unit limits) are display-only on the
LM. The cab itself uses the open/close window, solo vs team, the fes rule and the room id.

## Problems we hit and the fixes

| Problem | Cause | Fix |
|---|---|---|
| LM showed no rooms | LoadRoom reply had the wrong status / room kind | `status = 1`, `tag_type` 2 or 4 (commit 56) |
| Rooms closed at 4 PM Pacific | Registry used the server's UTC clock for the daily reset | `CustomRooms.TimeZone` setting |
| "Times must be HH:mm" on the Rooms page | Browsers send `HH:mm:ss` or AM/PM in some locales | Parser accepts every format (commit 58) |
| Card name on the web page stayed old after a rename | Cached page / name read from the wrong place | Name read from the card lookup; Ctrl+F5 after updates |
| Pictures vanished after a web UI update | `wwwroot` was replaced wholesale, dropping imported images | **Merge** the new `wwwroot` over the old one, never replace it |
| A card in a room never searched | The card had no room *picked* (joined, but not selected on an LM) | Web auto-select + **Use this room** (commit 59) |
| Cab showed "searching" but never reached the matchmaker | Cab `IpAddress` was a VPN-only address (N2N) with no internet route; requests went nowhere | Keep cabs on a LAN IP that can reach the internet. With web auto-select **one LM** can serve cabs on different card servers |
| Error **21-11** | Two LMs on the same LAN | Run one LM per LAN (or put the second on a separate subnet). Not needed for rooms any more |
| Error **21-32** | POC `DisableSocketHook = True` | Leave `DisableSocketHook = False` |
| Two solo players in a Dual Select room never matched | Dual Select is a 2v2 rule; `NoCpuPartner` waits for 4 humans (correct) | Use a **One** rule for 1v1 (commit 60 makes those pair 1v1) |
| PC crashed at match load with 4 cabs + LM on one PC | Resource limits (each copy ~4–5 GB committed) | Known issue; spread cabs over PCs for big local tests |

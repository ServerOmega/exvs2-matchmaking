# IP masking for EXVS2 IB P2P matches

Research notes (2026-11-15). Status: design proposal, nothing implemented yet.
Source of the matchmaker notes: committed tree `12ce6d8` (tag rename/delete). 
Updated later the same day with §16 (mixed rooms / per-player opt-out), after it was asked whether people on the relay and people off it can share a match.

## 0. Recommendation

Build a **small transparent UDP relay in the matchmaker process**, and have `CheckMatching` hand each cabinet the relay's public `ip:port` for every *other* human in the room — not their real addresses. Do not try to use Valve's Steam Datagram Relay, stock coturn TURN, Photon, or Epic EOS: the game only `sendto()`s raw IPv4 UDP to the addresses in the matching reply, and it does not speak those SDKs.

An SDR-*like* design (regional relays later, the matchmaker picking a relay, short-lived sessions, allowlisted sources) **does** fit, provided the addresses we hand the game are **real, routable IPv4 literals on the relay**, not Steam FakeIPs. Fake / link-local addresses would only work with a new client hook, which is a later optional project (and a good fit for the custom launcher), not the MVP.

Suggested default once it exists: host-level `RelayMode=fallback` for connectivity (hard NAT), plus a per-player **Hide my IP** / **Direct** preference (see §16). Mixed rooms are allowed: only pairs that involve a hiding player (or that cannot hole-punch) go through the relay; two Direct players in the same room still play each other directly. Same-house / same-NAT cabinets keep the current local-dial path.

A hiding player **can** stay hidden from a Direct opponent — that pair must use the relay in *both* directions. Mixing does not add much lag when the relay is near at least one of the two, or on the path between them (typical West Coast via the LA VPS: **+5–20 ms**). It *does* hurt when both players are close to each other but far from the only relay (two East Coast or two Asian players via LA: often **+70–150 ms**, and that slowest link sets the feel of the whole 2v2). Mitigate with a soft preference to group Hide with Hide, and with regional relays later.

Rough effort: **about 4–6 days** for an in-process MVP plus tests, then a real-game trial; per-player Hide/Direct on the WebUI is about **+1 day** on top of that; regional relays are a later week-plus and a few extra $5 VPS boxes.

## 1. How addresses are exchanged today

The matchmaker does not carry battle traffic. It only **relays addresses**. The game then plays **UDP P2P**.

1. `RegisterPcb` gives the cabinet `SRV_MATCH` (the `/match` URL) and `SRV_STUN` (`StunHost`:`StunPort`). On the VPS that is `<VPS_IP>`, TCP 28080 and UDP 3478/3479 (built-in STUN).
2. The cabinet runs STUN from its **game UDP socket** (bound to `0.0.0.0:48000` plus a terminal offset; a twin port block starts at 49000 for LM / broadcast). There is no UPnP.
3. `EntryMatching` sends a `Client` with:
   - `global_ipaddress` / `global_port` — XOR-MAPPED-ADDRESS from STUN
   - `local_ipaddress` / `local_port` — from adapter enumeration (or the POC hook's `IpAddress=`)
   - NAT mapping / filtering / allocation
   - `node_id`, `pcb_serial`, `loc_id`, `pref_code`, optional `subnet_id`
4. `CheckMatching` (world-5 shape, and the other WAN worlds) returns `room_id` + **every** `MatchedClient`, including the requester and any CPU stand-ins. Each `Client` is returned as stored; the handler does not rewrite addresses today (`MatchingQueueCommandHandlers` copies `c.Client` straight through).
5. The cabinet finds itself in that list by `node_id` (required). It then dials each peer (exe `0x140794590`, confirmed in disassembly):
   - if the peer's **global IP string equals mine** → dial the peer's **local** `ip:port` (same NAT / same house, no hairpin needed)
   - else → dial the peer's **global** `ip:port`
   "Mine" is the cabinet's own STUN result, not necessarily the copy of itself in the reply.

CPU stand-ins already use `0.0.0.0:0` for both address pairs, so a relay can ignore them.

**Consequence:** every human in a room learns every other human's public IP and mapped port. That is also listed in `docs/SECURITY.md` §6 as a remaining risk. Anyone who can read the protobuf on the cabinet, or capture the `/match` HTTP (plain, no TLS), sees the same list. Source-IP binding on `CheckMatching` stops a stranger on a different IP from polling your node, but it does not hide the roster from the people actually in the room.

## 2. What is already masked, and what is not

Already masked (`CardServerConfig.Security.MaskNetworkInLog`, default on):

- Public IPv4 in logs becomes `a.b.x.x` (`LogMask.MaskNetwork` / `NetworkAccess.MaskIp`). Private / loopback / link-local addresses are kept, which is deliberate for LAN debugging.
- Partner codes in logs become `AB******`.
- Card secrets (`MaskCardSecretsInLog`) are `<masked:N>` in request dumps, structured fields, and WebUI paths.

Not masked (the actual exposure):

- **`CheckMatching` replies** — real `global_ipaddress` / `local_ipaddress` / ports, sent to every cabinet in the room.
- The **game itself** after it receives that reply, and any local packet capture during the battle.
- Plain HTTP between cabinet, card server, and matchmaker (an observer on a cabinet's path already sees that cabinet's own traffic; they do not automatically see *other* players' IPs unless they also see a CheckMatching body).
- The WebUI, in the committed tree, does **not** show player IPs (no GlobalIp / SourceIp fields in WebUI or UI controllers). Keep the VPS in `PublicMatchmaker` so the website stays LAN-only anyway.
- If someone turns `MaskNetworkInLog` off, or copies older pre-hardening logs, VPS / card-server logs would show public IPs again.

STUN itself only reflects the sender's mapped address back to that sender. It does not tell players about each other.

## 3. Option 1 — a UDP relay (TURN-like forwarder)

### 3.1 Why not stock coturn TURN

The game's STUN client **parses** `XOR-RELAYED-ADDRESS` and can send RegisterPcb long-term credentials (`networking-issues.md` §6.1), but it has **not** been shown to encapsulate battle packets as TURN Send/Data indications. Battle traffic is raw UDP `sendto` to the address from CheckMatching. A standard TURN server would not forward those payloads correctly, and would wrap incoming peer traffic in a format the game would not understand.

Treat "does the game ever use a TURN allocation for battle?" as a useful but optional RE follow-up. The MVP should not depend on it.

### 3.2 How a transparent relay would work

The matchmaker already controls the only address list the game will dial. For each room it can:

1. Allocate **one UDP port per human** on the relay (four ports for a 4-human match).
2. In each cabinet's `CheckMatching` reply, **clone** the `Client` objects and rewrite every *other* human's `global_ipaddress` / `global_port` to `RelayHost`:`P_that_player`. Leave the requester's own entry alone (the game keys on `node_id`). Leave CPU stand-ins at `0.0.0.0`.
3. Forward raw UDP payloads. When A sends to `VPS:P_B`, the relay sends the payload to B's reflexive address and **source-NATs the packet from `VPS:P_A`**, so B's reply to "A" goes to `P_A` and the return path is unambiguous.

**Do not** advertise the same global IP to everyone and hope they still dial the relay. The game's same-global → local-dial rule (`0x140794590`) would then send them at each other's LAN addresses. The rewrite works because we change only *peers'* globals to the VPS IP, while each cabinet's idea of "my" global stays its real STUN result, which is different from the VPS.

Same-house players today rely on that local-dial rule. If we also rewrite them, their traffic would hairpin through the VPS. The MVP should skip the rewrite when both sides share a STUN global IP (same NAT) unless the operator forces `always` including LAN.

### 3.3 NAT, keepalives, and allowlists

- Prime each mapping from `EntryMatching`'s STUN `global_ip:port` (STUN and the battle socket are the same socket).
- Also **learn** the actual source the first time a cabinet sends to a relay port. Symmetric / port-dependent NAT often uses a different mapped port toward a new destination than STUN saw. Learning fixes that, and is also how the relay helps two hard-NAT players who cannot hole-punch to each other at all.
- If STUN and the relay share the VPS's public IPv4, mappings are more likely to stay stable on endpoint-independent NATs.
- Keepalives: the game already sends a high rate of small UDP (see §3.4); no extra application keepalive is required once both sides have sent one packet. A short learn window (a few seconds after the room is issued) is enough.
- Security: accept a packet on a session port only from the two learned (or STUN-primed) sources for that pair; drop everything else; expire the session after the room's `MatchedKeep` plus a generous battle window (e.g. 15 minutes). Tokens cannot go *inside* game packets (they are opaque), so the ticket is a **server-side allowlist**, not a Steam-style blob the client presents.

### 3.4 Bandwidth, latency, VPS capacity

Measured from the 2026-11-13 LAN captures in `captures/p1.tsv` (private, not published)–`p4.tsv` (game ports 48000–48001, mid-match windows):

| What | Observed |
|---|---|
| Typical payload | median 56 B, average ~62 B, p95 96 B; rare packets up to ~1 KB |
| Cross-cabinet unidirectional rates | two clusters: ~60 pps / ~27 kbps payload, and ~120 pps / ~73 kbps payload |
| Same-IP "self" flows | ~120 pps / ~54 kbps — likely LM / same-PC; **exclude** from relay estimates |
| That capture's inter-cabinet total | 3 bidirectional pairs, ~254 kbps payload (not a full mesh) |

Planning number for a **full 4-human mesh** (6 pairs, 12 unidirectional streams), including UDP/IP headers (~28 B) and a little headroom: **about 1 Mbps outbound per match**. A 3-minute battle is about **22 MB** of VPS egress.

The current VPS is a Vultr Los Angeles Regular Performance box (1 vCPU, 1 GB, public IPv4 `<VPS_IP>`). That plan is about **$5/month and includes 1 TB of outbound transfer**; overage is **$0.01/GB**; inbound does not count. 1 TB is tens of thousands of relayed matches. Ten concurrent 4-human rooms is about 10 Mbps and well within a small VPS. Fifty-plus concurrent rooms is more likely to hit **CPU / softirq** than the bandwidth quota; split relays or step up the plan if that ever happens.

Latency is one extra hop through Los Angeles:

- Two West Coast players: often only +10–30 ms versus direct, sometimes similar.
- Two East Coast or two Asian players: a trombone through LA can add **60–150 ms** versus a direct or regional path. That is the reason for regional relays later, not for the first build.

A 1 GB box already runs the matchmaker and STUN; relay state is a few kilobytes per room. The risk is CPU under many concurrent rooms, not RAM.

### 3.5 Ports

Reuse the public IPv4. Pick a dedicated UDP range (for example `40000–40999`), not 3478/3479 (STUN) and not 28080 (HTTP). Four humans → four ports. A /16-sized range is far more than a hobby host needs. Document the firewall: TCP 28080, UDP 3478–3479, plus the relay range.

## 4. Relay modes

| Mode | Hides IPs? | Helps hard NAT? | Notes |
|---|---|---|---|
| `off` (today) | No | No | Direct only. Two symmetric/CGNAT players often fail. |
| `fallback` | Only for rooms we decide cannot go direct | Yes | Heuristic: `stun-missing`, or both sides look like address/port-dependent NAT. Same-NAT pairs stay local. **True** "try direct, then fail over" is not available — the game does not tell the MMS that a battle failed to start, and it will not retry a second address list. |
| `always` | Yes, for every rewritten peer | Yes | Best privacy. Same-NAT should still be exempt unless a flag forces it, or same-house play pays a hairpin. |
| Opt-in (later) | For players who asked | Optional | The game has no UI for this. A WebUI / card-server flag that the VPS reads at entry time is enough. |

Recommendation: ship host-level `off|fallback|always`, default `fallback` until a real-game latency check is done. For privacy, prefer the per-player Hide/Direct flag in §16 over forcing `always` on the whole server: that lets Direct players keep a short path to each other in a mixed room. Do not promise "relay only after direct fails" without a client change.

## 5. Overlay VPN (n2n / ZeroTier / Tailscale / WireGuard / Radmin)

This is already the community workaround, documented in `analysis/networking-issues.md` and `analysis/lm-over-vpn-split.md`.

Everyone joins one overlay, binds the hook to the overlay IP, and puts STUN on the overlay too. The game then sees `global == local`, marks itself "no NAT", and dials virtual IPs. Players do not see each other's *ISP* IPs, but they do see overlay IPs. Those are still identifiers, just less useful for a residential DoS.

Tradeoffs versus a matchmaker relay:

- **Pros:** no VPS bandwidth, often direct-ish paths (Tailscale DERP / ZeroTier roots only when hole punch fails), already understood by the EXVS2-POC / Radmin community.
- **Cons:** every player must install and join a network; mixed overlay/internet queues break (the server already separates realms: Radmin 26/8, Hamachi 25/8, CGNAT/Tailscale 100.64/10, LAN, else `internet`); Tailscale does not carry the LM broadcast; commercial privacy VPNs (NordVPN and similar) are a bad idea (exit NAT, no inbound).
- A WireGuard / n2n **hub on the VPS** is essentially a relay that still requires client VPN software, and it still hands out virtual IPs.

Useful as a "players who want a private club can keep doing this" option. It is not a good default for a public internet matchmaker.

## 6. Does the game accept hostnames, or only IPv4?

Peer fields `global_ipaddress` and `local_ipaddress` are protobuf **strings**. The dial rule compares them as strings, then the socket path is `AF_INET` `sendto` to an explicit address (`networking-issues.md` §2.1). STUN parsing at `0x1407b9020` understands IPv4 and IPv6 mapped addresses, but the default path is IPv4; the POC hook only rewrites IPv4 binds. `StunHost` is already documented as "an IP literal is safest."

No `getaddrinfo` was found on the peer-dial path. A hostname in `global_ipaddress` would almost certainly fail `inet_addr` / `inet_pton` and would not be dialled. **Hand the game dotted IPv4 only.** Do not put FakeIPs in 169.254/16 or other unroutable ranges in these fields unless a hook intercepts `sendto` (see §8).

## 7. What other communities do

- **Fightcade:** still P2P. The UI hides IPs, but a capture shows the opponent's public address (community consensus, e.g. r/fightcade 2023). Fightcade "tunnels" exist as a fallback, not as default IP hiding.
- **Flycast Dojo** (the Naomi / Atomiswave emulator often used with Fightcade): added **regional UDP relays** in mid-2024 (us-west, us-east, Chile, Spain, Finland, Korea, Australia). Players opt into a nearby relay when hole punching fails; later builds can force relay. This is the closest analogue to what we should build: a raw-UDP forwarder plus a list of regions, not an SDK.
- **Parsec / game-streaming relays:** video, not a few hundred kbps of lockstep UDP. Not a useful template beyond "a hosted relay can hide IPs."
- **Rollback nets (GGPO and friends):** usually P2P; some front ends add a relay for failed NAT, same as Dojo.
- **EXVS2-POC / private arcade servers:** the usual advice is Radmin VPN, ZeroTier, or EasyN2N/n2n, with the hook bound to the overlay and everyone on one "LAN." Official-style WAN matching in the POC tree was incomplete (Issue #135, STUN / no match). Our internet matchmaker is the first widely used path that exposes real ISP IPs to strangers, which is why this question comes up now.
- **Photon / Epic EOS P2P:** hosted relays with SDKs, App IDs, and their own message framing. The exe cannot use them without a client rewrite.

## 8. Valve Steam Datagram Relay (SDR)

[Steamworks: Steam Datagram Relay](https://partner.steamgames.com/doc/features/multiplayer/steamdatagramrelay)

### 8.1 How SDR works

SDR is Valve's anycast-ish **relay backbone** plus an API. Game traffic can go peer-to-peer or client-to-dedicated-server through those relays.

- **Hiding IPs / DoS resistance:** peers and gameservers never learn each other's public IPs. Relays authenticate, encrypt, and rate-limit what they forward.
- **Ping-based routing:** clients measure latency to data centers (`ISteamNetworkingUtils` ping locations) and send that to the game coordinator. The coordinator (or Steam, for ordinary P2P) picks a route, sometimes a single relay, sometimes a pair, and sometimes a path that is *faster* than the public Internet because it rides Valve's backbone.
- **Tickets / auth:** for dedicated servers, the coordinator signs a `SteamDatagramRelayAuthTicket` that authorizes one client to one server for a limited time, with encrypted routing info. The client caches it (`ReceivedRelayAuthTicket`) and connects with `ConnectToHostedDedicatedServer`. Ordinary Steam P2P uses `CreateListenSocketP2P` / `ConnectP2P` and Steam as the signaling channel. Certificates (short-lived, per identity) do DH and encrypt end-to-end.
- **FakeIP:** a name that *looks* like IPv4, currently from **169.254.0.0/16**, port >1024, globally unique per App ID (`BeginAsyncRequestFakeIP`). It is **not routable**. Legacy code (Valve mentions Team Fortress 2 and the old Steam matchmaking APIs) can keep dealing in `ip:port`, while `ISteamNetworkingSockets` / `CreateFakeUDPPort` intercept those addresses and carry the packets over SDR or NAT-punched P2P. FakeIP cannot be combined with ticket-based dedicated-server auth.

### 8.2 Can we use it?

**No, not Valve's network.**

- It requires a **Steamworks App ID**, a partner CA key, and (for the official POP list) the Steam client or the closed partner SDK.
- Valve's terms for non-Steam platforms still require **a version of the game shipping on Steam**. This project is a hobby arcade matchmaker, not a Steam title.
- The open-source **[GameNetworkingSockets](https://github.com/ValveSoftware/GameNetworkingSockets)** library is **BSD-3-Clause** and explicitly does **not** need Steam. It implements the protocol, ICE-like NAT punch, and a hook for custom signaling. **SDR support is not in the open-source tree.** README_P2P.md says that when punch fails you should run your own TURN, or fail the connect; Valve's relay network is proprietary.

Even if GNS were used as a self-hosted relay protocol, **the EXVS2 exe would have to send GNS frames**, not raw battle UDP. That means a client hook or a rewrite. Without that, GNS does not help.

## 9. Comparable open alternatives

| Option | Use here? | Why |
|---|---|---|
| Self-hosted GameNetworkingSockets relays | Not for MVP | Protocol mismatch with the exe |
| Epic EOS / Photon relays | No | SDK + accounts + framing |
| Stock coturn TURN | No, unless RE proves the game uses relayed allocations for battle | TURN encapsulation vs raw UDP |
| Coturn or a custom process as a **transparent** forwarder | Possible, but a custom in-process forwarder is simpler to allowlist and to drive from `CheckMatching` | |
| Flycast-Dojo-style regional UDP relays | **Yes** — same shape as our MVP, later with more regions | |
| Several cheap regional VPS relays + matchmaker assignment | **Yes**, phase 2 | GeoIP or a STUN-binding RTT from each region; the game has no ping-to-relay API we can call |
| Overlay VPN (Tailscale DERP, etc.) | Optional club setup, not the public default | See §5 |

## 10. Does an SDR-like design fit EXVS2?

**The architecture fits; Valve's implementation and FakeIP do not.**

What we can copy from SDR:

- A network of relays (one at first: the LA VPS).
- The **matchmaker as game coordinator**: it already knows the room, so it can assign each peer an endpoint and expire it.
- **Per-session authorization** as a server-side allowlist (learned source addresses, not a ticket the exe would have to present).
- Later, **regional pick** from the player's STUN/public IP (GeoIP) or from a sidecar RTT (a Binding request to each relay's STUN, measured by the card server or by a tiny helper — not by the exe).

What we cannot copy without a hook:

- FakeIPs or any other virtual address. The game will `sendto` whatever dotted IPv4 we put in `global_ipaddress`. That address must answer on the public Internet.
- End-to-end encryption and SDR-style certificates (battle UDP stays plaintext, as it is today).
- Client-driven ping matrices and mid-match reroutes.

So the MVP is: **real relay `ip:port` in CheckMatching, transparent raw-UDP forward, allowlisted sources.** That is "SDR-shaped" from the players' point of view (they only ever see the relay) and "Dojo-shaped" in the implementation.

A later launcher / `sendto` hook could introduce FakeIPs or a local UDP proxy (cabinet always sends to `127.0.0.1:localport`, the hook forwards to the assigned relay). That would let us change routes without a new CheckMatching shape, but it is a different project.

## 11. MVP relay design

**Components** (all in Server-Infinite, same process as today's built-in STUN):

- `BuiltinUdpRelay` hosted service: binds the port range, session table, learn/allowlist, expiry.
- `RelayAllocator` used by the matchmaker when a room is formed: one port per human, remember `node_id → port`, STUN-prime sources.
- `CheckMatching` rewrite: per-requester clone of `Client`, overwrite other humans' global ip/port when the mode says so; do not mutate the stored entry (logs and same-cabinet detection still need the real STUN global).
- Config under `CardServerConfig.OnlineMatching` (names indicative):

```json
"RelayMode": "off",          // off | fallback | always
"RelayHost": "",             // empty = StunHost / this host's public IPv4
"RelayPortStart": 40000,
"RelayPortCount": 1000,
"RelaySessionSeconds": 900,
"RelayExemptSameNat": true
```

VPS firewall: allow the relay UDP range from the Internet, same as STUN.

**Same-NAT exemption:** if `RelayExemptSameNat` is true, peers that share a STUN global IP keep their real local/global fields so the exe local-dials on the LAN.

**Logging:** one `RELAY-NET room=… node=… via=ip:port` line per assignment, run through `MaskNetworkInLog`. Do not log payloads.

## 12. Tests to add

Unit / in-process:

- Rewrite: requester sees peers as `RelayHost:P_*`, sees themself unchanged, CPU stays `0.0.0.0`.
- Same-global pair is not rewritten when the exemption is on, and is rewritten when `always` forces it.
- `fallback` only rewrites a pair that is stun-missing or looks symmetric.
- Foreign packets to a session port are dropped; only the two learned sources pass.
- Ports return to the pool after expiry and are not reused for a live room.
- The same-global → local-dial helper (`NetDiag.DialAddr`) still describes the *pre-rewrite* path in `MATCH-NET` logs, and a new field notes when the reply was rewritten.

E2E with simulated peers (extend the existing fake-cabinet / hangfix e2e style, no real exe required for CI):

- Four fake cabinets, `RelayMode=always`: after CheckMatching, each "sends" UDP from its game port to the advertised peer addresses; the relay must deliver payloads to the other three; no fake cabinet is ever told another cabinet's real listen address.
- Two fakes behind one source IP (same NAT): exemption keeps local dial, no hairpin.
- A fake with a STUN global that does not match the UDP source it later uses (symmetric NAT): learning still connects them.
- `RelayMode=off`: CheckMatching still contains real globals (today's behaviour).
- Exhaust the port pool and confirm a clear error rather than overlapping sessions.
- **Mixed room (Hide + Direct):** four fakes, A/B Hide, C/D Direct. After CheckMatching:
  - A and B are never told C or D's real listen address (and vice versa);
  - C's reply lists D's real global (and D lists C's);
  - A↔B, A↔C, A↔D, B↔C, B↔D UDP is delivered only via the relay, and each recipient sees the source ip:port it was advertised;
  - C↔D packets go direct and never hit the relay;
  - an asymmetric rewrite (A told D's real IP, D told A's relay port) is asserted to be *rejected by the allocator* — not a supported mode.
- Incoming packet to a relay port whose source is the peer's real address, when the recipient was told the relay address, is not forwarded in a way that would present a mismatched source (the SNAT test: captured source on the recipient equals the advertised address).

Real-game trial (after you approve a build, not part of this research): one internet pair with `always`, confirm the battle starts, confirm a capture on one PC shows only the VPS IP for the opponent, measure RTT versus a direct match. A second trial: one Hide cab and one Direct cab in the same room, capture on the Direct PC shows only the VPS for the Hide opponent, and the battle starts.

## 13. Risks

- The game might reject a peer global that does not look like a STUN mapping, or might compare ports in a way we have not traced. Unlikely (the fields are just strings it dials) but the first real-game test is the proof.
- Address-dependent NAT toward a different *port* on the same VPS IP is usually fine; if not, learning from the first packet is the fix. Both sides must send — the game does that as soon as it has the roster.
- `always` will add a LA hop. Same-house testing will look fine if we exempt same-NAT; a two-location test is the one that matters.
- Relay ports on the VPS are a new public UDP surface. The allowlist must be tight, sessions must expire, and we should rate-limit new sessions the same way `/match` is already rate-limited.
- A bug that rewrites *all* globals to the VPS IP, including in the stored entry, would break same-cabinet detection (`NetDiag.SameCabinet` uses the STUN global) and would trigger the local-dial rule if a cabinet also thought its own global was the VPS.
- This does not encrypt battle traffic. It only hides residential IPs from other players. A relay operator (us, on the VPS) still sees everyone's addresses and payloads.
- Official-looking "privacy" should not be over-claimed: overlay clubs, the VPS itself, and anyone on a cabinet's local machine can still observe more than the remote opponent can.

## 14. Phased plan and effort

| Phase | What | Effort | Depends on |
|---|---|---|---|
| **0. Research** | This note | Done | — |
| **1. MVP** | In-process transparent relay, `RelayMode=off\|fallback\|always`, per-recipient CheckMatching rewrite, same-NAT exemption, unit + simulated e2e tests | **4–6 days** | Your go-ahead to code (separate branch, not deployed until you test) |
| **1b. Real-game trial** | One internet pair, capture confirms only VPS IPs, latency note | A session | Phase 1 build on the VPS between games; card servers do not need a rebuild if only the matchmaker rewrites replies |
| **2. Per-player Hide / Direct** | WebUI + card-server default, VPS pref store (same pattern as `/tag`), per-pair rewrite, soft same-mode grouping, mixed-room e2e | **~1–2 days** | Phase 1 |
| **3. Regional relays** | Cheap VPS boxes (e.g. NJ, Tokyo, Frankfurt, ~$5 each), matchmaker assigns by GeoIP / STUN RTT, same allowlist protocol | **1–2 weeks** plus monthly host cost | Phase 1 proven in real games |
| **4. Optional client hook** | Launcher-side `sendto` proxy or FakeIP-like local ports, so routes can change without relying on the exe | Larger, separate from the matchmaker | Only if we want mid-match reroutes or unroutable virtual addresses |
| Optional RE | Confirm the exe never uses `XOR-RELAYED-ADDRESS` for battle | Half a day in the binary | Not blocking |

Phase 1 is enough to answer "can we mask IPs on internet P2P games?" with a yes, at the cost of a Los Angeles hop and about 1 Mbps of VPS egress per 4-human match.

## 15. Sources

- Server tree `12ce6d8`: `Matchmaker.cs`, `MatchingQueueCommandHandlers.cs`, `NetDiag.cs` (`DialAddr`), `BuiltinStunServer.cs`, `LogMask.cs`, `SecurityConfigurations.cs`, `ONLINE_MATCHMAKING.md`, `docs/SECURITY.md` §6.
- Analysis: `analysis/networking-issues.md` (sockets, dial rule, VPN table, open TURN question), `analysis/matchmaking.md` §2.2–2.6 and §7.6 (hole-punch format not reversed), `analysis/lm-over-vpn-split.md` (sendto / RecvFrom, no `connect()`), `analysis/multi-instance.md` §3 (0x140794590 finds the peer in the matched list, then compares global IP strings via 0x1406c37b0).
- Captures: `captures/p1.tsv` (private, not published)–`p4.tsv`, 2026-11-13 (each cabinet already `sendto`s a distinct ip:port per peer; the mesh is per-pair).
- Valve: [Steam Datagram Relay](https://partner.steamgames.com/doc/features/multiplayer/steamdatagramrelay), [GameNetworkingSockets](https://github.com/ValveSoftware/GameNetworkingSockets) (BSD-3-Clause; SDR not included), [README_P2P.md](https://github.com/ValveSoftware/GameNetworkingSockets/blob/master/README_P2P.md).
- Flycast Dojo relay announcement (2024-06, regional list) and Fightcade P2P IP-exposure threads.
- Vultr Regular Performance 1 GB pricing / 1 TB outbound, checked against public 2026 price lists (confirm on vultr.com before budgeting).

## 16. Mixed rooms: opting out, and Hide + Direct in one match

Question (2026-11-15, later): can a player opt out of the relay, and can people on the relay and people off it still match and play with little or no extra lag?

**Short answer:** yes, they can share a room, and a hiding player can still hide from a Direct opponent. That pair must go through the relay *in both directions*. Two Direct players in the same room keep a direct path to each other. Extra lag is usually small (**+5–20 ms**) when the relay is near at least one of the pair or on the path between them. It becomes noticeable when both are close to each other but far from the only relay (two East Coast or two Asian players via the LA VPS: often **+70–150 ms**), because in a 2v2 the slowest pair sets the feel of the match. Prefer grouping Hide with Hide when we can, and add a regional relay (e.g. New Jersey, Tokyo) before that case is common.

### 16.1 Per-player opt-out / opt-in

Host-level `RelayMode` (off / fallback / always) is too coarse once some people want privacy and others want the shortest path. Add a per-player preference:

| Preference | Meaning |
|---|---|
| **Hide my IP** (opt-in to the privacy relay) | Other cabinets are never told my real global ip:port. Pairs I am in go through the relay, except same-NAT. |
| **Direct** (opt-out of the privacy relay) | I accept that *other Direct players* in my room will see my public IP. I still use the relay for any pair that involves a Hide player, or that `fallback` would relay for NAT. |

Consent, stated carefully:

- An opted-out (Direct) player **exposes their IP only to other Direct players** they are actually matched with.
- They do **not** expose it to a Hide player, and they do **not** learn a Hide player's IP.
- "Opt-out" is not "I refuse to send any packet to a relay." If that were the rule, a Hide+Direct pair could only be played by showing the hider's address, which breaks Hide. The honest wording in the WebUI should be: *Direct: shorter path against other Direct players; your IP is visible to them. You will still go through the relay when matched with someone who is hiding their IP.*
- Same-NAT / same-house: always local-dial. Those cabinets already see each other's LAN addresses; tromboning through the VPS would only add lag.

How the flag reaches the VPS: internet cabinets send `EntryMatching` **straight to the VPS**, not through the card server, so a WebUI checkbox cannot ride in the game's protobuf unless we abuse a field the exe already sends. Don't do that. Use the same out-of-band pattern as online tag (`X-Tag-Secret`):

- WebUI per-card setting, stored by the card server, pushed to the VPS as "pilot *am_id* prefers Hide|Direct" (EntryMatching already carries `BanapassportAmId`).
- A card-server default for uncarded play, keyed by `pcb_serial` + STUN global IP (the same cabinet identity the matchmaker already uses).
- Missing pref → **Direct** until the feature is proven in real games, so a player who never opened the WebUI keeps today's path. The host can flip the default later.

`RelayMode=always` on the VPS remains a host override (every internet pair relayed). `off` disables the privacy relay (NAT `fallback` can still be a separate bit if we want, or `fallback` stays the host default with per-player Hide on top).

### 16.2 Per-pair rewrite, and will the exe accept a mixed room?

`CheckMatching` already returns a full client list to each requester, and each cabinet already dials **each peer independently**. `0x140794590` [C] finds that peer in the matched list and picks local vs global for *that* peer only (`analysis/multi-instance.md` §3; `0x1406c37b0` is "my" global IP string, from the cabinet's own STUN result, not from the copy of itself in the reply). The socket layer is `sendto` to an explicit address, with no `connect()` (`analysis/lm-over-vpn-split.md` §1.1; RecvFrom at `0x140305070` / `0x140305110`). The 2026-11-13 captures show the same thing: one cabinet sends to several different `ip:port`s at once, one flow per peer.

So A can be told "B is `VPS:P_B`" and "C is `C_public:port`" in the same reply, and will send to both. A mixed room is natural for this exe, not a special case.

**Each pair's rewrite must be symmetric.** For the ordered pair (what A is told about B, and what B is told about A):

| A pref | B pref | What A is told for B | What B is told for A | Path |
|---|---|---|---|---|
| Hide | Hide | `VPS:P_B` | `VPS:P_A` | relay both ways |
| Hide | Direct | `VPS:P_B` | `VPS:P_A` | relay both ways (protects A, and keeps sources consistent) |
| Direct | Direct | B's real global (or local if same NAT) | A's real global | direct both ways |
| either, same NAT | | B's real local | A's real local | local dial, no relay |

Can a Hide player stay hidden from a Direct player? **Yes**, but only on the Hide+Direct row above. If we tried the "asymmetric" shortcut — tell A that B is at B's real IP (so A sends direct) and tell B that A is at the relay — then:

- B's capture / CheckMatching would not show A's IP, but **A's packets would arrive at B from A's real public IP**, which leaks A and almost certainly fails session matching (see below).
- A would receive B's replies from the relay, not from the real address A was told to dial.

Do **not** implement that shortcut.

**Source consistency (will A accept packets from the address it was told?):** the hole-punch / RUDP packet format was **not reversed** (`analysis/matchmaking.md` §7.6). There is no confirmed disassembly of a "drop if `recvfrom` source ≠ advertised peer" check. That said, the stack is `CRUDPSocket_Impl` / `CP2PSignalingTerminal` with `Proc_WaitPartnerStun` / `Proc_WaitHolePunching`, and it already keys each peer by the address chosen from the roster [C for the dial, M for recv demux]. In every comparable UDP session model, a packet whose source is not the address we are punching to is ignored or opens a different session. **Treat source matching as required** until a capture or a short RE pass proves otherwise.

Therefore the relay must **source-NAT** so that when A was told B = `VPS:P_B`, every packet A receives for B comes *from* `VPS:P_B` (the "one port per player, SNAT from `P_src`" design in §11). The MVP already needed that for a fully-relayed room; mixed rooms do not change it.

### 16.3 Lag in a 2v2 with mixed paths

A 4-human match is a mesh of six pairs. The game is a 60 fps lockstep-style arcade fighter (there is a `keyDelay` debug parameter; the exact delay formula is not reversed). Practically, **the slowest pair sets the room's delay**. Relaying only the pairs that involve a Hide player is already the right way to keep lag down: the Direct–Direct edges stay short.

Relayed RTT for a pair is about `RTT(player, relay) + RTT(other, relay)` (the VPS hop itself is well under 1 ms). Direct RTT is often shorter than that sum (triangle inequality), unless the relay sits on or near the path.

Typical numbers with the current **Los Angeles** VPS (`<VPS_IP>`), one-way / RTT ballpark:

| Pair | Direct RTT (typical) | Via LA relay | Added |
|---|---|---|---|
| Two West Coast players | 10–30 ms | 15–50 ms | **+5–20 ms** — rarely noticeable |
| West Coast + East Coast | ~60–80 ms | ~70–90 ms (East–LA ~60–80, West–LA ~5–15) | **+5–20 ms** — the transcontinental path already dominates |
| Two East Coast players | 20–40 ms | ~120–160 ms (each ~60–80 to LA) | **+70–120 ms** — noticeable (roughly 4–8 frames at 60 Hz) |
| Two players in Japan / Korea | 10–40 ms regional | ~200–240 ms | **+150 ms or more** — bad |
| LA + Tokyo | ~100–120 ms | similar, relay is on the West end of the path | usually **+5–20 ms** |

When mixing adds little:

- One Hide player in a mostly West Coast room, LA relay: the Hide edges pick up +5–20 ms; Direct–Direct edges stay short; the room feels almost like today.
- One West Coast Hide player in an East Coast room, or one East Coast Hide player in a West Coast room: the long path already exists; the relay adds little on top.

When mixing (or hiding at all) *does* add noticeable lag:

- Several Hide players, or a mixed Hide+Direct room, **all in one region far from the only relay** (four New York players, or four Tokyo players, with only the LA VPS). Direct–Direct edges would have been 20–40 ms, but every Hide edge trombones through LA and the whole 2v2 waits on ~140–200 ms.

Ways to keep that rare:

1. **Relay only the pairs that need it** (Hide involved, or NAT `fallback`) — always, including in mixed rooms.
2. **Regional relays** (phase 3): pick the relay closest to the *pair* (or to their midpoint). Two East Coast players via New Jersey go back to the +5–20 ms bucket. This is the real fix for the bad case.
3. **Soft same-mode grouping** in the matchmaker: wait a few seconds (reuse the existing fill-timer idea) to pair Hide with Hide and Direct with Direct before mixing. Do not hard-split the queue — a public 2v2 queue is already thin.
4. **Optional added-latency cap:** if the estimated relayed RTT for a Hide edge is more than **X ms above** a direct estimate (suggest X = 50 ms, configurable), then, in order: try a closer regional relay; wait briefly for a same-region or same-mode room; if the Hide player has allowed it, offer direct (exposing their IP) rather than a bad trombone; otherwise still form the room on the relay and accept the lag rather than refusing a match with no UI to explain why. Never silently drop someone out of matching.

Until there is a second region, the honest expectation is: West Coast and cross-coast mixed rooms should feel fine; an all-East-Coast or all-Asia room with someone on Hide will feel the LA hop until we add a relay closer to them.

### 16.4 Fairness and default policy

Forcing every mixed room onto the relay, or refusing to mix, are both worse than per-pair paths. Recommendation:

- **Allow mixed rooms.** Per-pair path as in the table in §16.2.
- **Soft-prefer** same preference when filling a 2v2 (a short wait, not a separate queue). A Hide player should not routinely be the one person in an otherwise Direct East Coast room if another Hide player is also searching — but they should not sit unmatched either.
- **Defaults:** host `RelayMode=fallback` (NAT only). Per-player pref defaults to **Direct** until the relay has been tried in a real internet match; then the host can switch the default to Hide if they want a privacy-first public server. Same-NAT always exempt.
- Do not let a Direct player "demand" a fully direct room against a Hide player. That would be opting the *other* person out of their privacy. The Direct player can choose not to search, or can accept the relayed edge.

### 16.5 Tests (mixed rooms)

Listed under §12 as well. The important invariants: per-pair rewrite as in the table; SNAT source equals the advertised address; Direct–Direct never hits the relay; an asymmetric rewrite is refused by the allocator; a four-fake e2e covers A/B Hide + C/D Direct in one room.


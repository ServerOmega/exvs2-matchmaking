#!/usr/bin/env python3
"""End-to-end cross-server online tag test (Step C).

Two card-server instances with colliding local card ids (both card #1), both talking to one
matchmaker (server A's in-process MMS). Fake cards and fake cabinets only.

  1. Create a card on A and a card on B; both get local id 1, but different wire pilot ids
     (ServerId*1_000_000 + 1).
  2. B creates a partner code on the shared /tag API (via B's WebUI); A joins it.
     B refreshes Teams and both LoadCard lists show the same partner_id / pair key.
  3. A third card on a fresh identity does not appear in either team.
  4. Fake cabs talk to A's /match: the two partners pair on world 5; an unrelated cab with a
     colliding local-style attr2 (or a different code) does not join them.
  4b. Friends (2026-11-15): a results-screen friend request (RegisterOption 306) from a card on A to a card on B
     is pending until B accepts (or B also asks); then both list each other and share a joined online tag team.
     Block / NG flow, LoadCard field 25, paging / search / bulk, /tag/friends behind the shared secret.

Usage:
  cross_server_tag_e2e.py --url-a http://127.0.0.1:28101/ --url-b http://127.0.0.1:28102/
  cross_server_tag_e2e.py --publish-dir /path/to/linux-x64   # starts both servers itself

Needs game_server_nue_pb2 and loadtest.py (same as online_tag_e2e.py). Never prints card secrets.
"""
import argparse, json, os, re, secrets, shutil, signal, subprocess, sys, time, urllib.error, urllib.request, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for extra in ("/workspace/pbgen", os.path.join(HERE, "..", "..", "pbgen")):
    if os.path.isdir(extra):
        sys.path.insert(0, extra)
import loadtest as L
import game_server_nue_pb2 as pb

RESULTS = []
CHILDREN = []
EXTRA_CARDS = []   # friends section cards, included in the log-leak checks
# security hardening 2026-11-15: shared /tag secret for this run only (random, never printed)
TAG_SECRET = secrets.token_urlsafe(32)


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("[%s] %s %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)
    return ok


def post_pb(url, q, strict=True):
    req = urllib.request.Request(url, data=q.SerializePartialToString(), method="POST", headers={
        "Content-Type": "application/x-protobuf", "X-Nue-Protobuf-Revision": "141"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read()
    out = pb.Response()
    (out.ParseFromString if strict else out.MergeFromString)(data)
    return out


def raw_status(url, path, headers=None, body=None):
    """HTTP status of a request (JSON body when given). Never prints headers (they may carry the secret)."""
    data = None if body is None else json.dumps(body).encode()
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url.rstrip("/") + path, data=data, method="POST" if body is not None else "GET", headers=h)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def base(method, serial="XSPCB0001"):
    q = pb.Request(); q.type = method; q.request_id = uuid.uuid4().hex
    q.pcb_serial = serial; q.loc_id = "XSLOC0001"; q.token = ""
    return q


def json_call(url, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url.rstrip("/") + path, data=data, method="POST" if body is not None else "GET",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return json.loads(raw or b"null")
        except Exception:
            return {"success": False, "message": "http %s" % e.code}


class Card:
    def __init__(self, url, n, run, serial="XSPCB0001"):
        self.url = url
        self.access = "TESTXSTAG%05d%08d" % (run % 100000, n)
        self.chip = "TESTXSTCHIP%04d%04d" % (run % 10000, n)
        self.serial = serial
        p = self.pre_load()
        if p.is_new_card:
            q = base(pb.MTHD_REGISTER_CARD, serial)
            r = q.register_card; r.session_id = p.session_id; r.is_card = True
            r.access_code = self.access; r.chip_id = self.chip; r.mucha_country_code = "JPN"
            post_pb(url, q, strict=False)
            p = self.pre_load()
        self.session, self.pilot = p.session_id, p.load_player.pilot_id

    def pre_load(self):
        q = base(pb.MTHD_PRE_LOAD_CARD, self.serial)
        p = q.pre_load_card; p.is_card = True; p.access_code = self.access; p.chip_id = self.chip; p.mucha_country_code = "JPN"
        return post_pb(self.url, q, strict=False).pre_load_card

    def load_card(self):
        q = base(pb.MTHD_LOAD_CARD, self.serial)
        q.load_card.session_id = self.session; q.load_card.pilot_id = self.pilot
        return post_pb(self.url, q, strict=True).load_card

    def teams(self):
        return json_call(self.url, "/ui/team/getTeams/%s/%s" % (self.access, self.chip))

    def create_code(self):
        return json_call(self.url, "/ui/team/crossServerInvite", {
            "accessCode": self.access, "chipId": self.chip})

    def join_code(self, code):
        return json_call(self.url, "/ui/team/joinCrossServer", {
            "accessCode": self.access, "chipId": self.chip, "code": code})

    def upsert_teams(self, teams):
        return json_call(self.url, "/ui/team/upsertTeams", {
            "accessCode": self.access, "chipId": self.chip, "teams": teams})

    # friends 2026-11-15 (card secrets only in POST bodies)
    def register_option(self, friend=0, ng=0):
        q = base(pb.MTHD_REGISTER_OPTION, self.serial)
        o = q.register_option; o.mobile_user_id = self.pilot
        if friend: o.friend_pilot_id = friend
        if ng: o.ng_pilot_id = ng
        return post_pb(self.url, q, strict=False)

    def friends(self, tab="friends", q=None, sort="added", dir=None, page=1, page_size=25):
        body = {"accessCode": self.access, "chipId": self.chip, "tab": tab, "sort": sort, "page": page, "pageSize": page_size}
        if q is not None: body["q"] = q
        if dir: body["dir"] = dir
        return json_call(self.url, "/ui/friends/list", body) or {}

    def friend_ids(self, tab="friends"):
        return [i.get("pilotId") for i in self.friends(tab, page_size=100).get("items") or []]

    def friend_act(self, action, ids, delete_tag_teams=False):
        return json_call(self.url, "/ui/friends/" + action, {
            "accessCode": self.access, "chipId": self.chip, "pilotIds": list(ids), "deleteTagTeams": delete_tag_teams}) or {}

    def friend_target(self, action, pilot, delete_tag_teams=False):
        return json_call(self.url, "/ui/friends/" + action, {
            "accessCode": self.access, "chipId": self.chip, "pilotId": pilot, "deleteTagTeams": delete_tag_teams}) or {}


class Cab:
    def __init__(self, mms, name):
        self.conn = L.Conn(mms, L.Stats()); self.name = name
        self.serial, self.loc = "XSPCB%s%04d" % (name, os.getpid() % 10000), "XSLOC" + name
        r = self.conn.call({"type": L.ISSUE, "request_id": L.rid(), "issue_node_id": {
            "pcb_serial": self.serial, "loc_id": self.loc, "issue_at": int(time.time()), "issue_count": 2}}, "issue")
        self.node = r["issue_node_id"]["node_id"][0]; self.apply = 1
        self.ip = "198.18.88.%d" % (10 + (ord(name[0]) % 200))

    def me(self):
        return L.client(self.node, self.serial, self.loc, self.ip, 40000)

    def entry(self, world, attr2, am, timeout=90, groups=(), new_apply=True):
        if new_apply:
            self.apply += 1
        e = {"apply_id": self.apply, "myclient": self.me(),
             "myplayer": {"banapassport_am_id": am, "parameters": [
                 {"attribute_id": 1, "parameter": 0}, {"attribute_id": 2, "parameter": attr2},
                 {"attribute_id": 3, "parameter": 0}, {"attribute_id": 4, "parameter": 0}]},
             "world": {"mucha_game_id": "GIB1", "version": 1, "world_id": world}, "groups": list(groups),
             "matching_timeout": timeout, "seq_num": 1, "create_room_flag": 1, "entry_at": int(time.time())}
        return self.conn.call({"type": L.ENTRY, "request_id": L.rid(), "entry_matching": e}, "entry").get("code", 0)

    def check(self):
        r = self.conn.call({"type": L.CHECK, "request_id": L.rid(), "check_matching": {
            "node_id": self.node, "check_at": int(time.time())}}, "check")
        cm = r.get("check_matching") or {}
        return r.get("code", 0), cm.get("room_id"), [(c.get("group_id", 0), c["client"]["node_id"]) for c in cm.get("clients", [])]

    def wait(self, secs):
        t0 = time.time()
        while time.time() - t0 < secs:
            code, room, cl = self.check()
            if code != 0 or cl:
                return code, room, cl
            time.sleep(0.4)
        return self.check()


def wait_http(url, secs=40):
    t0 = time.time()
    while time.time() - t0 < secs:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.4)
    return False


def start_server(publish_dir, work, port, server_id, match_url, invite_url, enabled=True):
    for name in ("Server-Infinite", "Configurations", "Certificates", "wwwroot"):
        src = os.path.join(publish_dir, name)
        dst = os.path.join(work, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        elif os.path.isfile(src):
            shutil.copy2(src, dst)
        elif os.path.isfile(src + ".dll"):
            shutil.copy2(src + ".dll", dst + ".dll")
    # copy all publish files
    for fn in os.listdir(publish_dir):
        s, d = os.path.join(publish_dir, fn), os.path.join(work, fn)
        if os.path.isdir(s):
            if fn in ("Configurations", "Certificates", "wwwroot", "web_ui", "WebUIInfinite.Client"):
                shutil.copytree(s, d, dirs_exist_ok=True)
        elif not os.path.exists(d):
            shutil.copy2(s, d)
    env = os.environ.copy()
    env["ASPNETCORE_ENVIRONMENT"] = "Development"
    env["Kestrel__Endpoints__BaseServer__Url"] = "http://127.0.0.1:%d" % port
    env["CardServerConfig__OnlineMatching__Enabled"] = "true" if enabled else "false"
    env["CardServerConfig__OnlineMatching__BuiltinStun"] = "false"
    env["CardServerConfig__OnlineMatching__MatchUrl"] = match_url
    env["CardServerConfig__OnlineTag__ServerId"] = str(server_id)
    env["CardServerConfig__OnlineTag__InviteUrl"] = invite_url
    env["CardServerConfig__OnlineTag__SendTagTeams"] = "true"
    env["CardServerConfig__OnlineTag__TagSecret"] = TAG_SECRET
    env["CardServerConfig__Security__AccessMode"] = "LanOnly"
    env["CardServerConfig__Security__ExemptLoopbackFromRateLimit"] = "false"   # so the /tag limit can be seen from 127.0.0.1
    env["DOTNET_PrintLogo"] = "false"
    exe = os.path.join(work, "Server-Infinite")
    dll = os.path.join(work, "Server-Infinite.dll")
    if os.path.isfile(exe) and os.access(exe, os.X_OK):
        cmd = [exe]
    elif os.path.isfile(dll):
        cmd = ["dotnet", dll]
    else:
        raise SystemExit("no Server-Infinite in %s" % work)
    log = open(os.path.join(work, "server.log"), "w")
    proc = subprocess.Popen(cmd, cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    CHILDREN.append((proc, log))
    return proc


def cleanup():
    for proc, log in CHILDREN:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
        try:
            log.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url-a", default="")
    ap.add_argument("--url-b", default="")
    ap.add_argument("--publish-dir", default="")
    ap.add_argument("--work-dir", default="")
    a = ap.parse_args()
    run = int(time.time())
    started = False
    try:
        if a.publish_dir:
            work = a.work_dir or os.path.join("/tmp", "xs-tag-e2e-%d" % os.getpid())
            os.makedirs(work, exist_ok=True)
            wa, wb = os.path.join(work, "a"), os.path.join(work, "b")
            os.makedirs(wa, exist_ok=True); os.makedirs(wb, exist_ok=True)
            port_a, port_b = 28101, 28102
            url_a = "http://127.0.0.1:%d/" % port_a
            url_b = "http://127.0.0.1:%d/" % port_b
            match = "http://127.0.0.1:%d/match" % port_a
            tag = "http://127.0.0.1:%d/tag" % port_a
            start_server(a.publish_dir, wa, port_a, 1, match, tag, enabled=True)
            start_server(a.publish_dir, wb, port_b, 2, match, tag, enabled=True)
            started = True
            if not wait_http(url_a) or not wait_http(url_b):
                for d in (wa, wb):
                    lp = os.path.join(d, "server.log")
                    if os.path.isfile(lp):
                        print("---- %s ----" % lp)
                        print(open(lp).read()[-4000:])
                sys.exit("servers did not become ready")
        else:
            if not a.url_a or not a.url_b:
                sys.exit("give --url-a and --url-b, or --publish-dir")
            url_a, url_b = a.url_a, a.url_b

        # 1. colliding local ids, distinct wire ids
        A = Card(url_a, 1, run, "XSPCBAAAA")
        B = Card(url_b, 1, run, "XSPCBBBBB")
        print("wire pilots: A=%d B=%d" % (A.pilot, B.pilot))
        check("both cards got the same colliding local-style first id on the wire prefix",
              A.pilot % 1000000 == B.pilot % 1000000 and A.pilot != B.pilot,
              "A=%d B=%d" % (A.pilot, B.pilot))
        check("A is on ServerId 1 (1_000_000 block) and B on ServerId 2",
              A.pilot // 1000000 == 1 and B.pilot // 1000000 == 2,
              "A=%d B=%d" % (A.pilot, B.pilot))

        # 2. create / join
        created = B.create_code()
        code = (created or {}).get("code") or ""
        check("B created an 8-character partner code", bool((created or {}).get("success")) and len(code) == 8,
              "len=%d" % len(code))
        check("joining a missing code is refused", not (A.join_code("ZZZZZZZZ") or {}).get("success"))
        joined = A.join_code(code)
        check("A joined B's code", bool((joined or {}).get("success")), str({k: joined[k] for k in joined if k != "accessCode"} if isinstance(joined, dict) else joined))

        ta, tb = A.teams(), B.teams()
        def remote_ok(teams, partner):
            lst = (teams or {}).get("teams") or []
            return any(t.get("isRemote") and t.get("partnerPilotId") == partner and t.get("sharedTagCode") == code for t in lst)
        check("A's Teams tab lists B as a remote partner", remote_ok(ta, B.pilot), "yourPilotId=%s teams=%s" % ((ta or {}).get("yourPilotId"), [(t.get("partnerPilotId"), t.get("isRemote"), t.get("sharedTagCode")) for t in (ta or {}).get("teams") or []]))
        check("B's Teams tab lists A after a refresh (creator sync)", remote_ok(tb, A.pilot), "yourPilotId=%s teams=%s" % ((tb or {}).get("yourPilotId"), [(t.get("partnerPilotId"), t.get("isRemote"), t.get("sharedTagCode")) for t in (tb or {}).get("teams") or []]))

        partner_of = {}
        for me, other in ((A, B), (B, A)):
            try:
                lc = me.load_card()
            except Exception as ex:
                check("LoadCard strict parse (pilot %d)" % me.pilot, False, repr(ex))
                continue
            tags = list(lc.mobile_user_group.tag_teams)
            ok = len(tags) >= 1 and any(t.partner_id == other.pilot for t in tags)
            check("LoadCard of wire %d lists partner_id %d" % (me.pilot, other.pilot), ok,
                  str([(t.id, t.partner_id, t.tag_status) for t in tags]))
            check("LoadCard of wire %d sends tag_status=1 (in-game list default)" % me.pilot,
                  any(t.partner_id == other.pilot and t.tag_status == 1 for t in tags),
                  str([(t.id, t.partner_id, t.tag_status) for t in tags]))
            if tags:
                partner_of[me.pilot] = next((t.partner_id for t in tags if t.partner_id == other.pilot), tags[0].partner_id)

        key_a = min(A.pilot, partner_of.get(A.pilot, 0))
        key_b = min(B.pilot, partner_of.get(B.pilot, 0))
        check("both sides derive the same pair key", key_a == key_b and key_a != 0, "A=%s B=%s" % (key_a, key_b))

        # 2b. team cosmetics sync through /tag (last-write-wins)
        ta = A.teams()
        remote = next((t for t in (ta or {}).get("teams") or [] if t.get("sharedTagCode") == code), None)
        check("A has a remote team to edit", remote is not None)
        if remote is not None:
            remote["name"] = "CROSS NAME"
            remote["bgmId"] = 3
            remote["effectId"] = 7
            remote["backgroundPartsId"] = 2
            remote["emblemId"] = 4
            remote["nameColorId"] = 5
            saved = A.upsert_teams((ta or {}).get("teams") or [])
            check("A saved new team name, BGM, and effect", bool((saved or {}).get("success")), str(saved))
        def cosmetics(t):
            return (t.get("name"), t.get("bgmId"), t.get("effectId"),
                    t.get("backgroundPartsId"), t.get("emblemId"), t.get("nameColorId"))
        want = ("CROSS NAME", 3, 7, 2, 4, 5)
        tb2 = B.teams()
        bt = next((t for t in (tb2 or {}).get("teams") or [] if t.get("sharedTagCode") == code), {})
        check("B's Teams tab pulls A's name, BGM, and effect", cosmetics(bt) == want,
              "got=%s" % (cosmetics(bt),))
        try:
            lc_b = B.load_card()
            tags = list(lc_b.mobile_user_group.tag_teams)
            hit = next((t for t in tags if t.partner_id == A.pilot), None)
            # Python proto exposes Name; BGM/effect are legacy tags 50-57 checked via the Teams tab above.
            ok_lc = hit is not None and hit.name == "CROSS NAME"
            check("B's LoadCard lists the synced team name", ok_lc,
                  str(None if hit is None else hit.name))
        except Exception as ex:
            check("B's LoadCard lists the synced name, BGM, and effect", False, repr(ex))
        # last write wins: B overwrites, A picks it up
        if bt:
            bt["name"] = "LAST WRITE"
            bt["bgmId"] = 6
            B.upsert_teams((tb2 or {}).get("teams") or [])
            ta2 = A.teams()
            at = next((t for t in (ta2 or {}).get("teams") or [] if t.get("sharedTagCode") == code), {})
            check("A's Teams tab pulls B's later name and BGM (last write wins)",
                  at.get("name") == "LAST WRITE" and at.get("bgmId") == 6,
                  "got=%s %s" % (at.get("name"), at.get("bgmId")))

        # 3. unrelated third card on A (local id 2) is not in the team
        C = Card(url_a, 2, run, "XSPCCcccc")
        check("unrelated card on A has a different wire id and no team with B",
              C.pilot != A.pilot and not any(t.get("partnerPilotId") == B.pilot for t in (C.teams() or {}).get("teams") or []),
              "C=%d" % C.pilot)

        # 4. world 5 pairing against A's matchmaker
        mms = post_pb(url_a, base(pb.MTHD_REGISTER_PCB, "XSPCBMM")).register_pcb
        match = [s.uri for s in mms.server_info if s.server_type == pb.SRV_MATCH][-1]
        print("MMS", match)
        cab_a, cab_b, cab_x = Cab(match, "A"), Cab(match, "B"), Cab(match, "X")
        check("entry A world 5", cab_a.entry(5, key_a, A.pilot) == 0)
        check("entry B world 5", cab_b.entry(5, key_b, B.pilot) == 0)
        # Unrelated: same attr2 as the pair (if it used a colliding local min) plus a different am_id, short timeout
        check("entry X world 5 (unrelated)", cab_x.entry(5, key_a, 9_000_001, timeout=6) == 0)
        ra, rb = cab_a.wait(10), cab_b.wait(2)
        lead = cab_a if A.pilot < B.pilot else cab_b
        ok = ra[1] and ra[1] == rb[1] and ra[2] == rb[2] and len(ra[2]) == 2 and all(g == 0 for g, _ in ra[2]) \
            and {n for _, n in ra[2]} == {cab_a.node, cab_b.node} and ra[2][0][1] == lead.node
        check("cross-server partners: one 2-client room, both group 0, leader first", ok, str((ra, rb)))
        rx = cab_x.wait(10)
        check("unrelated searcher does not join them", (rx[1] != ra[1] if ra[1] else True) and not (rx[2] and ra[1] and any(n == cab_x.node for _, n in (ra[2] or []))), str(rx))
        # canceled or still waiting alone is fine; must not be in the partners' room
        if rx[1] and ra[1]:
            check("unrelated room is not the partners' room", rx[1] != ra[1], str(rx))


        # 4b. friend requests and block lists (2026-11-15), across the two card servers
        time.sleep(16)   # let the /tag token bucket refill (burst 60, 4/s) so this section never sees a 429
        F1 = Card(url_a, 3, run, "XSPCBFR01")
        F2 = Card(url_b, 2, run, "XSPCBFR02")
        EXTRA_CARDS.extend([F1, F2])
        print("friend cards: F1=%d F2=%d" % (F1.pilot, F2.pilot))
        r = F1.register_option(friend=F2.pilot)
        check("friends: RegisterOption (306) answers Success with an empty register_option body",
              r.error == 0 and r.HasField("register_option"), "error=%s" % r.error)
        inc = []
        for _ in range(20):
            inc = F2.friends("incoming").get("items") or []
            if any(i.get("pilotId") == F1.pilot for i in inc):
                break
            time.sleep(0.5)
        f1name = F1.friends().get("yourName")
        hit = next((i for i in inc if i.get("pilotId") == F1.pilot), {})
        check("friends: A-side game request reaches the B-side player as a received request", bool(hit), str([i.get("pilotId") for i in inc]))
        check("friends: the request carries the sender's current name", hit.get("name") == f1name, "name ok" if hit.get("name") == f1name else "mismatch")
        check("friends: the request is marked as from the game and stamps last played", hit.get("source") == "game" and bool(hit.get("lastPlayedUtc")), str(hit.get("source")))
        check("friends: the sender sees it as a sent request", F2.pilot in F1.friend_ids("outgoing"), "")
        check("friends: no tag team before the request is accepted",
              not any(t.get("partnerPilotId") == F2.pilot for t in (F1.teams() or {}).get("teams") or []), "")
        acc = F2.friend_act("accept", [F1.pilot])
        res = (acc.get("results") or [{}])[0]
        check("friends: B accepts on the Friends page", acc.get("success") and res.get("result") == "Accepted", str(res.get("result")))
        check("friends: accepting created one online tag team", acc.get("tagTeamsCreated") == 1, str(acc.get("tagTeamsCreated")))
        check("friends: both see each other as friends",
              F1.pilot in F2.friend_ids() and F2.pilot in F1.friend_ids(), "")
        lst = F2.friends()
        check("friends: tab counts after accept (1 friend, 0 requests)",
              (lst.get("counts") or {}).get("friends") == 1 and (lst.get("counts") or {}).get("incoming") == 0, str(lst.get("counts")))
        check("friends: the friend row shows the shared online tag team", any(i.get("hasTagTeam") for i in lst.get("items") or []), "")
        t2 = [t for t in (F2.teams() or {}).get("teams") or [] if t.get("partnerPilotId") == F1.pilot and t.get("isRemote")]
        t1 = [t for t in (F1.teams() or {}).get("teams") or [] if t.get("partnerPilotId") == F2.pilot and t.get("isRemote")]
        check("friends: B's Teams tab lists the new joined team with A", len(t2) == 1, str(len(t2)))
        check("friends: A's Teams tab lists the same team after a sync", len(t1) == 1 and t1[0].get("sharedTagCode") == t2[0].get("sharedTagCode") if t1 and t2 else False, "")
        for me, other in ((F1, F2), (F2, F1)):
            try:
                tags = list(me.load_card().mobile_user_group.tag_teams)
                check("friends: LoadCard of %d lists the friend %d as an online tag partner" % (me.pilot, other.pilot),
                      any(t.partner_id == other.pilot for t in tags), str([t.partner_id for t in tags]))
            except Exception as ex:
                check("friends: LoadCard strict parse after friendship (%d)" % me.pilot, False, repr(ex))

        # mutual: both ask from the results screen (C on A, B on B)
        C.register_option(friend=B.pilot)
        time.sleep(1.0)
        B.register_option(friend=C.pilot)
        ok = False
        for _ in range(20):
            if C.pilot in B.friend_ids() and B.pilot in C.friend_ids():
                ok = True
                break
            time.sleep(0.5)
        check("friends: two game requests in opposite directions become a friendship", ok, "")
        check("friends: the mutual friendship made a C-B online tag team",
              any(t.get("partnerPilotId") == B.pilot for t in (C.teams() or {}).get("teams") or []), "")

        time.sleep(16)   # /tag bucket refill (this section makes ~150 matchmaker calls in total)
        # block: B-side F2 blocks F1, team kept (no explicit choice)
        blk = F2.friend_act("block", [F1.pilot], delete_tag_teams=False)
        check("friends: block answers Blocked", ((blk.get("results") or [{}])[0]).get("result") == "Blocked", str(blk.get("results")))
        check("friends: blocking ends the friendship on both sides", F1.pilot not in F2.friend_ids() and F2.pilot not in F1.friend_ids(), "")
        check("friends: the blocked player is on the Blocked tab", F1.pilot in F2.friend_ids("blocked"), "")
        check("friends: blocking without the option keeps the online tag team",
              any(t.get("partnerPilotId") == F1.pilot for t in (F2.teams() or {}).get("teams") or []), "")
        w = F1.friend_target("request", F2.pilot)
        check("friends: the blocked player cannot send a request from the web", ((w.get("results") or [{}])[0]).get("result") == "RefusedBlocked", str(w.get("results")))
        F1.register_option(friend=F2.pilot)
        time.sleep(1.5)
        check("friends: a game request from the blocked player is dropped",
              F1.pilot not in F2.friend_ids("incoming") and F2.pilot not in F1.friend_ids("outgoing"), "")
        w = F2.friend_target("request", F1.pilot)
        check("friends: the blocker must unblock before requesting", ((w.get("results") or [{}])[0]).get("result") == "RefusedYouBlocked", "")
        try:
            ng = list(F2.load_card().mobile_user_group.partner_recruit_am_id_nglist)
            check("friends: LoadCard field 25 (partner_recruit_am_id_nglist) carries the block", F1.pilot in ng, str(ng))
        except Exception as ex:
            check("friends: LoadCard strict parse with an NG list", False, repr(ex))
        try:
            check("friends: no NG list for a card without blocks", len(list(F1.load_card().mobile_user_group.partner_recruit_am_id_nglist)) == 0, "")
        except Exception as ex:
            check("friends: LoadCard strict parse without an NG list", False, repr(ex))
        # NG from the results screen
        A.register_option(ng=9_000_777)
        ok = False
        for _ in range(20):
            if 9_000_777 in A.friend_ids("blocked"):
                ok = True
                break
            time.sleep(0.5)
        check("friends: ng_pilot_id from the game adds a block", ok, "")
        unb = F2.friend_act("unblock", [F1.pilot])
        check("friends: unblock answers Unblocked", ((unb.get("results") or [{}])[0]).get("result") == "Unblocked", "")
        try:
            check("friends: the NG list is empty again after unblocking", F1.pilot not in list(F2.load_card().mobile_user_group.partner_recruit_am_id_nglist), "")
        except Exception as ex:
            check("friends: LoadCard after unblock", False, repr(ex))

        time.sleep(16)   # /tag bucket refill
        # remove with the explicit "also delete online tag teams" choice
        rm = C.friend_act("remove", [B.pilot], delete_tag_teams=True)
        check("friends: remove answers Removed and deletes the shared tag team", ((rm.get("results") or [{}])[0]).get("result") == "Removed"
              and (rm.get("tagTeamsDeleted") or 0) >= 1, str((rm.get("results"), rm.get("tagTeamsDeleted"))))
        check("friends: C's Teams tab no longer lists the C-B team",
              not any(t.get("partnerPilotId") == B.pilot for t in (C.teams() or {}).get("teams") or []), "")

        # big lists: bulk block 30, page / search / bulk unblock (one matchmaker call per bulk action)
        ids = list(range(9_000_801, 9_000_831))
        bb = A.friend_act("block", ids)
        check("friends: bulk block of 30 ids", bb.get("success") and len(bb.get("results") or []) == 30, str(len(bb.get("results") or [])))
        p2 = A.friends("blocked", page=2, page_size=10)
        check("friends: blocked tab pages server-side (31 total, 4 pages, 10 on page 2)",
              p2.get("total") == 31 and p2.get("totalPages") == 4 and p2.get("page") == 2 and len(p2.get("items") or []) == 10,
              "total=%s pages=%s n=%s" % (p2.get("total"), p2.get("totalPages"), len(p2.get("items") or [])))
        sr = A.friends("blocked", q="9000815")
        check("friends: search by pilot id finds exactly one", [i.get("pilotId") for i in sr.get("items") or []] == [9_000_815], "")
        big = A.friends("blocked", page_size=5000)
        check("friends: page size is capped at 100", big.get("pageSize") == 100, str(big.get("pageSize")))
        ub = A.friend_act("unblock", ids)
        check("friends: bulk unblock", ub.get("success") and (A.friends("blocked").get("counts") or {}).get("blocked") == 1, "")
        check("friends: more than 100 ids in one call is refused", not A.friend_act("block", list(range(9_100_001, 9_100_102))).get("success"), "")

        # card checks and /tag/friends security
        bad = json_call(url_a, "/ui/friends/list", {"accessCode": "0" * 20, "chipId": F1.chip, "tab": "friends"}) or {}
        check("friends: a wrong access code gets no list", not bad.get("success") and not bad.get("items"), "")
        st, _ = raw_status(url_a, "/tag/friends/%d" % F1.pilot)
        check("friends: GET /tag/friends without the secret is refused (401)", st == 401, "status=%d" % st)
        st, _ = raw_status(url_a, "/tag/friends/%d?tab=friends&page=1&pageSize=25" % F1.pilot, {"X-Tag-Secret": TAG_SECRET})
        check("friends: GET /tag/friends with the secret works (200)", st == 200, "status=%d" % st)
        st, _ = raw_status(url_a, "/tag/friends/request", body={"fromPilotId": 9_000_901, "toPilotId": F1.pilot})
        check("friends: POST /tag/friends/request without the secret is refused (401)", st == 401, "status=%d" % st)
        time.sleep(16)   # refill the /tag bucket again before the rate-limit check below

        # 5. security hardening (2026-11-15)
        sec = {"X-Tag-Secret": TAG_SECRET}
        for path in ("/tag/invites/for/%d" % A.pilot, "/tag/invites/%s" % code):
            st, _ = raw_status(url_a, path)
            check("GET %s without the secret is refused (401)" % re.sub(r"/[0-9A-Z]{8}$", "/<code>", path), st == 401, "status=%d" % st)
            st, _ = raw_status(url_a, path, {"X-Tag-Secret": "wrong-" + TAG_SECRET[:4]})
            check("GET %s with a wrong secret is refused (401)" % re.sub(r"/[0-9A-Z]{8}$", "/<code>", path), st == 401, "status=%d" % st)
            st, _ = raw_status(url_a, path, sec)
            check("GET %s with the secret works (200)" % re.sub(r"/[0-9A-Z]{8}$", "/<code>", path), st == 200, "status=%d" % st)
        st, _ = raw_status(url_a, "/tag/invites", body={"pilotId": 9_000_123, "name": "x"})
        check("POST /tag/invites without the secret is refused (401)", st == 401, "status=%d" % st)
        st, _ = raw_status(url_a, "/tag/invites/join", body={"code": code, "pilotId": 9_000_124, "name": "x"})
        check("POST /tag/invites/join without the secret is refused (401)", st == 401, "status=%d" % st)
        st, body = raw_status(url_a, "/tag/register", sec, {"amId": 9_000_125, "codes": [code]})
        acc = (json.loads(body or b"{}") or {}).get("accepted")
        check("a stranger cannot register someone else's code for world 5", st == 200 and acc == 0, "status=%d accepted=%s" % (st, acc))

        st, body = raw_status(url_a, "/ui/card/getAll?PageSize=50")
        cards = json.loads(body or b"[]") if st == 200 else []
        leaked = [c for c in cards if c.get("chipId")]
        mine = [c for c in cards if c.get("cardId") == A.pilot % 1000000]
        check("WebUI card list still works from the LAN (200)", st == 200 and len(cards) >= 1, "status=%d n=%d" % (st, len(cards)))
        check("WebUI card list carries no chip ids", not leaked, "leaked=%d" % len(leaked))
        check("WebUI card list shows a masked hint", bool(mine) and mine[0].get("chipIdHint", "").endswith(A.chip[-4:])
              and A.chip not in mine[0].get("chipIdHint", ""), "")
        st, body = raw_status(url_a, "/ui/card/getAll?PageSize=50&SearchKeyword=" + A.chip[:-3])
        check("partial chip-id search finds nothing (no chip-id oracle)",
              st == 200 and not any(c.get("cardId") == mine[0]["cardId"] for c in json.loads(body or b"[]")) if mine else False, "")
        st, body = raw_status(url_a, "/ui/card/getAll?PageSize=50&SearchKeyword=" + A.chip)
        check("full chip-id search still finds the card", st == 200 and len(json.loads(body or b"[]")) >= 1, "")
        if mine:
            st, body = raw_status(url_a, "/ui/card/authorize", body={"cardId": mine[0]["cardId"], "chipId": "", "accessCode": "0" * 20})
            r = json.loads(body or b"{}")
            check("authorize with a wrong access code fails and returns no chip id", not r.get("success") and not r.get("chipId"), "")
            st, body = raw_status(url_a, "/ui/card/authorize", body={"cardId": mine[0]["cardId"], "chipId": "", "accessCode": A.access})
            r = json.loads(body or b"{}")
            check("authorize with the access code returns the chip id (Customize/Teams flow)",
                  r.get("success") is True and r.get("chipId") == A.chip, "")
            # fix2: the WebUI re-checks a saved login by chip id (cardId 0); another card's chip never passes
            st, body = raw_status(url_a, "/ui/card/authorize", body={"cardId": 0, "chipId": A.chip, "accessCode": A.access})
            r = json.loads(body or b"{}")
            check("fix2: saved login re-check by chip id works", r.get("success") is True and r.get("chipId") == A.chip, "")
            st, body = raw_status(url_a, "/ui/card/authorize", body={"cardId": 0, "chipId": C.chip, "accessCode": A.access})
            r = json.loads(body or b"{}")
            check("fix2: an access code with another card's chip id is refused", not r.get("success") and not r.get("chipId"), "")
        tb3 = B.teams()
        check("Teams tab still works after the security checks", bool((tb3 or {}).get("teams")), "")

        # /tag rate limit (loopback exemption is off in this run): hammering a missing code gets 429s
        codes = []
        for i in range(400):
            st, _ = raw_status(url_a, "/tag/invites/ZZZZ%04d" % i, sec)
            codes.append(st)
        check("/tag is rate limited per source (429 after the burst)", 429 in codes and codes[0] == 404,
              "first=%d n429=%d" % (codes[0], codes.count(429)))

        # log masking: no partner code, no full public IP, no secret in server A's / B's logs
        if started:
            for d, name in ((wa, "A"), (wb, "B")):
                txt = ""
                for root, _, files in os.walk(d):
                    for fn in files:
                        if fn.endswith(".txt") or fn == "server.log":
                            try:
                                txt += open(os.path.join(root, fn), errors="replace").read()
                            except Exception:
                                pass
                check("server %s log never contains the shared secret" % name, TAG_SECRET not in txt, "")
                check("server %s log never contains the partner code" % name, code not in txt, "")
                cards = (A, B, C) + tuple(EXTRA_CARDS)
                leaks = [c.access for c in cards if c.access in txt] + [c.chip for c in cards if c.chip in txt]
                check("fix2: server %s log never contains a card access code or chip id" % name, not leaks, "%d leaks" % len(leaks))
                check("fix2: server %s log shows masked WebUI paths" % name,
                      "/ui/team/getTeams/<masked:" in txt or name == "B" and "<masked:" in txt or "getTeams" not in txt, "")
                check("server %s log masks public cabinet IPs" % name, not re.search(r"198\.18\.88\.\d+", txt),
                      "%d hits" % len(re.findall(r"198\.18\.88\.\d+", txt)))
    finally:
        if started:
            cleanup()

    bad = [n for n, ok_ in RESULTS if not ok_]
    print("\n%d/%d checks passed" % (len(RESULTS) - len(bad), len(RESULTS)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

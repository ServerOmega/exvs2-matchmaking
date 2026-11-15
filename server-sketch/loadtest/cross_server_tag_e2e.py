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

Usage:
  cross_server_tag_e2e.py --url-a http://127.0.0.1:28101/ --url-b http://127.0.0.1:28102/
  cross_server_tag_e2e.py --publish-dir /path/to/linux-x64   # starts both servers itself

Needs game_server_nue_pb2 and loadtest.py (same as online_tag_e2e.py). Never prints card secrets.
"""
import argparse, json, os, shutil, signal, subprocess, sys, time, urllib.error, urllib.request, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for extra in ("/workspace/pbgen", os.path.join(HERE, "..", "..", "pbgen")):
    if os.path.isdir(extra):
        sys.path.insert(0, extra)
import loadtest as L
import game_server_nue_pb2 as pb

RESULTS = []
CHILDREN = []


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
    finally:
        if started:
            cleanup()

    bad = [n for n, ok_ in RESULTS if not ok_]
    print("\n%d/%d checks passed" % (len(RESULTS) - len(bad), len(RESULTS)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

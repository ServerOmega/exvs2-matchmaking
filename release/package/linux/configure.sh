#!/usr/bin/env bash
# EXVS2 matchmaking server - Linux configure (step 2). Writes Configurations/server.json + kestrel.json.
# Usage: ./linux/configure.sh                     (asks questions)
#        ./linux/configure.sh --ip 203.0.113.10 [--http-port 28090] [--stun-port 3478] [--fill 3] [--yes]
#                             [--access-mode LanOnly|PublicMatchmaker|Open] [--tag-secret-file FILE]
# Security (docs/SECURITY.md): a public IP defaults to PublicMatchmaker (internet reaches only /match, /mms, /tag);
# private / VPN addresses default to LanOnly. OnlineTag.TagSecret is generated once if missing (or read from FILE).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
SERVER_DIR="${SERVER_DIR:-$ROOT/server-linux}"
CFG="$SERVER_DIR/Configurations"

IP=""; HTTP_PORT=28090; STUN_PORT=3478; FILL=3; YES=0; ACCESS=""; SECRET_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --ip) IP="$2"; shift 2 ;;
    --http-port) HTTP_PORT="$2"; shift 2 ;;
    --stun-port) STUN_PORT="$2"; shift 2 ;;
    --fill) FILL="$2"; shift 2 ;;
    --yes|-y) YES=1; shift ;;
    --access-mode) ACCESS="$2"; shift 2 ;;
    --tag-secret-file) SECRET_FILE="$2"; shift 2 ;;
    -h|--help) sed -n 2,7p "$0"; exit 0 ;;
    *) echo "Unknown option $1" >&2; exit 1 ;;
  esac
done

[ -f "$CFG/server.json" ] || { echo "ERROR: $CFG/server.json not found. Run ./linux/build-server.sh first." >&2; exit 1; }
command -v python3 >/dev/null || { echo "ERROR: python3 is needed to edit the JSON files (sudo apt install python3)." >&2; exit 1; }

valid_ip() { [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; }

if [ -z "$IP" ]; then
  echo "Which address will the PLAYERS use to reach this server?"
  echo "  - VPS / port forwarding: your PUBLIC IP"
  echo "  - VPN (Tailscale, ZeroTier, Radmin, N2N...): this machine's VPN IP"
  echo "  - Only your home network: this machine's LAN IP"
  echo
  echo "IPv4 addresses on this machine:"
  ip -4 -o addr show 2>/dev/null | awk '$2!="lo"{split($4,a,"/"); printf "    %-15s (%s)\n", a[1], $2}' || true
  pub=""
  if [ "$YES" = 0 ]; then
    read -r -p "Look up this machine's public IP online (api.ipify.org)? [Y/n] " a
    if [[ ! "$a" =~ ^[nN] ]]; then pub="$(curl -fsS --max-time 5 https://api.ipify.org || true)"; fi
    [ -n "$pub" ] && echo "    Public IP: $pub"
  fi
  default="${pub:-$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<NF;i++) if($i=="src") print $(i+1)}')}"
  while :; do
    read -r -p "Server address (IPv4) [$default]: " IP; IP="${IP:-$default}"
    valid_ip "$IP" && break; echo "    That is not an IPv4 address like 203.0.113.10. Try again."
  done
  echo "The public/VPS matchmaker listens on 28090; a card server the game and its web page talk to stays on 28080."
  read -r -p "Listen port for THIS server (28090 = public matchmaker) [$HTTP_PORT]: " a; HTTP_PORT="${a:-$HTTP_PORT}"
fi
valid_ip "$IP" || { echo "ERROR: --ip must be an IPv4 address" >&2; exit 1; }
case "$IP" in 127.*) echo "WARNING: 127.x only works for games on this same machine." ;; esac

case "$ACCESS" in ""|LanOnly|PublicMatchmaker|Open) ;; *) echo "ERROR: --access-mode must be LanOnly, PublicMatchmaker or Open" >&2; exit 1 ;; esac
if [ -n "$SECRET_FILE" ] && [ ! -s "$SECRET_FILE" ]; then echo "ERROR: --tag-secret-file $SECRET_FILE is missing or empty" >&2; exit 1; fi
cp "$CFG/server.json" "$CFG/server.json.bak"
cp "$CFG/kestrel.json" "$CFG/kestrel.json.bak"
python3 - "$CFG" "$IP" "$HTTP_PORT" "$STUN_PORT" "$FILL" "$ACCESS" "$SECRET_FILE" <<'PY'
import json, sys, os, ipaddress, secrets
cfg, ip, http_port, stun_port, fill = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5])
access, secret_file = sys.argv[6], sys.argv[7]
def load(p):
    with open(p, encoding="utf-8-sig") as f: return json.load(f)
def save(p, d):
    with open(p, "w", encoding="utf-8") as f: json.dump(d, f, indent=2, ensure_ascii=False); f.write("\n")
sp = os.path.join(cfg, "server.json"); s = load(sp)
c = s.setdefault("CardServerConfig", {})
om = c.setdefault("OnlineMatching", {})
fill_v = int(fill) if fill.is_integer() else fill
om.update({"Enabled": True, "MatchUrl": "", "StunHost": ip, "StunPort": stun_port, "BuiltinStun": True,
           "FillAfterSeconds": fill_v, "MaxFillWaitSeconds": fill_v,
           "InStoreFillAfterSeconds": fill_v, "InStoreMaxFillWaitSeconds": fill_v,
           "AllowPartialRooms": True, "NoCpuPartner": True, "CpuStandInSeats": False})
ot = c.setdefault("OnlineTag", {})
for k, v in {"SendTagTeams": True, "TagStatus": 1, "MaxTeams": 20, "OneTimeInviteCode": True}.items(): ot.setdefault(k, v)
sec = c.setdefault("Security", {})
a = ipaddress.ip_address(ip); extra = ""
vpn = {"100.64.0.0/10": "Tailscale/CGNAT", "26.0.0.0/8": "Radmin", "25.0.0.0/8": "Hamachi"}
if not access:
    lan = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16"]
    if any(a in ipaddress.ip_network(n) for n in lan): access = "LanOnly"
    else:
        for net in vpn:
            if a in ipaddress.ip_network(net): access, extra = "LanOnly", net
        access = access or "PublicMatchmaker"
sec["AccessMode"] = access
if extra and not sec.get("ExtraAllowedCidrs"): sec["ExtraAllowedCidrs"] = extra
sec.setdefault("BindMatchNodesToSourceIp", True); sec.setdefault("MaskNetworkInLog", True)
generated = False
if secret_file:
    ot["TagSecret"] = open(secret_file).readline().strip()
elif not ot.get("TagSecret"):
    ot["TagSecret"] = secrets.token_urlsafe(30); generated = True
save(sp, s)
os.chmod(sp, 0o600)
print(f"  Security.AccessMode = {access}" + (f" (+{extra})" if extra else ""))
if generated:
    print("  OnlineTag.TagSecret generated (shared secret for other card servers that use this matchmaker for online tag).")
    print("  Read it with:  python3 -c \"import json;print(json.load(open('" + sp + "'))['CardServerConfig']['OnlineTag']['TagSecret'])\"")
    print("  Share it privately; never publish server.json.")
kp = os.path.join(cfg, "kestrel.json"); k = load(kp)
k.setdefault("Kestrel", {}).setdefault("Endpoints", {}).setdefault("BaseServer", {})["Url"] = f"http://0.0.0.0:{http_port}"
save(kp, k)
PY

cat <<MSG

Saved (old files kept as *.bak):
  Configurations/server.json : OnlineMatching Enabled=true, StunHost=$IP, StunPort=$STUN_PORT (+$((STUN_PORT+1))), BuiltinStun=true, FillAfterSeconds=$FILL
  Configurations/kestrel.json: listen on http://0.0.0.0:$HTTP_PORT

Open these ports (see Public-Server.txt):
  TCP $HTTP_PORT        card server + matchmaker + card website
  UDP $STUN_PORT, $((STUN_PORT+1))  STUN
  e.g. ufw:  sudo ufw allow $HTTP_PORT/tcp && sudo ufw allow $STUN_PORT:$((STUN_PORT+1))/udp
  and in your VPS provider's firewall / security group too.

Players use:  card server address $IP  (see Connect-Your-Game.txt)
Next: ./linux/start-server.sh
MSG
echo "The matchmaker is on 28090; your own card server (and its web page) is on 28080."
[ "$HTTP_PORT" = 28080 ] && echo "NOTE: 28080 is the game's card-server port (and its web page). For a public/VPS matchmaker that players reach through MatchUrl, use 28090."

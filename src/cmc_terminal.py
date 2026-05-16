#!/usr/bin/env python3
"""
CMC – Monitoring and Control Console  (Terminal TUI, no graphical interface)
Traffic Control System – SNMPv2c Manager

Communicates with the Central System (CS) SNMP agent at 127.0.0.1:10161
"""

import os
import sys
import json
import curses
import asyncio
import threading
import time
import glob
import argparse

from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    get_cmd,
    set_cmd,
)
from pysnmp.proto.rfc1902 import Integer

# ── SNMP Configuration ────────────────────────────────────────────────────────
SNMP_HOST      = '127.0.0.1'
SNMP_PORT      = 10161
SNMP_COMMUNITY = 'public'
POLL_INTERVAL  = 5   # seconds between automatic refreshes
SNMP_BATCH     = 60  # OIDs per GET PDU

# ── OIDs (experimental base 2026) ─────────────────────────────────────────────
_BASE      = '1.3.6.1.3.2026'
_ROAD_BASE = f'{_BASE}.1.3.1.1'   # roadsTable: .1.3.1.1.<col>.<road_id>

OID_SYSTEM_STATUS  = f'{_BASE}.1.2.1.0'
OID_SIM_ELAPSED    = f'{_BASE}.1.2.2.0'
OID_VEHC_ENTERED   = f'{_BASE}.1.2.3.0'
OID_VEHC_EXITED    = f'{_BASE}.1.2.4.0'
OID_VEHC_IN_SYSTEM = f'{_BASE}.1.2.5.0'

SCALAR_OIDS = [
    OID_SYSTEM_STATUS, OID_SIM_ELAPSED,
    OID_VEHC_ENTERED,  OID_VEHC_EXITED, OID_VEHC_IN_SYSTEM,
]

# roadsTable column indices
COL_ROAD_NAME    = 2
COL_CAPACITY     = 3
COL_VEHICLE_CNT  = 4
COL_TRAFFIC_RATE = 5
COL_LIGHT_COLOR  = 6
COL_SHIFT_INT    = 7
COL_GREEN_DUR    = 8
COL_RED_DUR      = 9

ROAD_COLS = [
    COL_ROAD_NAME, COL_CAPACITY, COL_VEHICLE_CNT,
    COL_TRAFFIC_RATE, COL_LIGHT_COLOR, COL_SHIFT_INT,
    COL_GREEN_DUR, COL_RED_DUR,
]

COL_TO_ATTR = {
    COL_ROAD_NAME:    'roadName',
    COL_CAPACITY:     'capacity',
    COL_VEHICLE_CNT:  'vehicleCount',
    COL_TRAFFIC_RATE: 'trafficRate',
    COL_LIGHT_COLOR:  'trafficLightColor',
    COL_SHIFT_INT:    'colorShiftInterval',
    COL_GREEN_DUR:    'greenDuration',
    COL_RED_DUR:      'redDuration',
}

STATUS_LABEL = {0: '???', 1: 'STOPPED', 2: 'RUNNING', 3: 'PAUSED'}
LIGHT_LABEL  = {0: '?',   1: 'RED',    2: 'GREEN'}
TYPE_ABBREV  = {'source': 'SRC', 'sink': 'SNK', 'normal': 'NRM'}

CONFIGS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'traffic-configs'
)

# ── SNMP helpers ───────────────────────────────────────────────────────────────

async def _async_get(host, port, community, oids):
    """GET multiple OIDs in batches. Returns {sent_oid: value}."""
    result = {}
    eng = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create(
            (host, port), timeout=2, retries=1
        )
        for i in range(0, len(oids), SNMP_BATCH):
            chunk = oids[i : i + SNMP_BATCH]
            var_binds = [ObjectType(ObjectIdentity(oid)) for oid in chunk]
            err_ind, err_stat, _, vbs = await get_cmd(
                eng,
                CommunityData(community, mpModel=1),
                transport,
                ContextData(),
                *var_binds,
            )
            if err_ind or err_stat:
                continue
            # GET preserves variable order → map by position
            for j, vb in enumerate(vbs):
                if j >= len(chunk):
                    break
                raw = vb[1]
                cls = raw.__class__.__name__
                if cls in ('NoSuchObject', 'NoSuchInstance', 'EndOfMibView'):
                    continue
                if cls in ('OctetString', 'DisplayString'):
                    result[chunk[j]] = raw.prettyPrint()
                else:
                    try:
                        result[chunk[j]] = int(raw)
                    except Exception:
                        result[chunk[j]] = raw.prettyPrint()
    finally:
        eng.close_dispatcher()
    return result


async def _async_set(host, port, community, oid, value):
    """SET a single integer OID. Returns True on success."""
    eng = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create(
            (host, port), timeout=2, retries=1
        )
        err_ind, err_stat, _, _ = await set_cmd(
            eng,
            CommunityData(community, mpModel=1),
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid), Integer(value)),
        )
        return not bool(err_ind or err_stat)
    finally:
        eng.close_dispatcher()


def snmp_get(oids, host, port, community):
    return asyncio.run(_async_get(host, port, community, oids))


def snmp_set(oid, value, host, port, community):
    return asyncio.run(_async_set(host, port, community, oid, value))


# ── Configuration loading ───────────────────────────────────────────────────────

def list_configs():
    """Returns sorted list of .json files in traffic-configs/."""
    return sorted(glob.glob(os.path.join(CONFIGS_DIR, '*.json')))


def load_road_meta(path):
    """Reads the config file and returns (roads_meta, connections_list, step_time)."""
    with open(path) as f:
        data = json.load(f)
    roads = {}
    for r in data['roads']:
        roads[r['roadId']] = {
            'roadName':    r['roadName'],
            'type':        r.get('type', 'normal'),
            'capacity':    r['capacity'],
            'trafficRate': r['trafficRate'],
        }
    conns = [
        (c['originRoadId'], c['destinationRoadId'], c['trafficDistributionRate'])
        for c in data.get('connections', [])
    ]
    step_time = data.get('simulation', {}).get('stepTime', 5)
    return roads, conns, step_time


def choose_config():
    """Interactive menu (pre-curses) to choose the road map."""
    configs = list_configs()
    if not configs:
        print(f'[!] No configuration files found in {CONFIGS_DIR}')
        sys.exit(1)

    print('\n=== CMC – Traffic Control Monitor & Control ===')
    print(f'\nAvailable maps in  {CONFIGS_DIR} :\n')
    for i, p in enumerate(configs, 1):
        print(f'  [{i}]  {os.path.basename(p)}')
    print()

    while True:
        try:
            raw = input(f'Choose map [1-{len(configs)}]: ').strip()
            idx = int(raw) - 1
            if 0 <= idx < len(configs):
                return configs[idx]
        except (ValueError, EOFError):
            pass
        print(f'  Invalid choice. Enter a number between 1 and {len(configs)}.')


MAX_LOG_ENTRIES = 60   # maximum entries in the event log

class AppState:
    """Thread-safe container for SNMP-collected data."""

    def __init__(self, roads_meta: dict, conns: list, step_time: int = 5):
        self.lock = threading.Lock()

        # System scalars
        self.connected      = False
        self.sys_status     = 0
        self.sim_elapsed    = 0
        self.vehc_entered   = 0
        self.vehc_exited    = 0
        self.vehc_in_sys    = 0
        self.last_poll_t    = 0.0
        self.sim_step_time  = step_time  # simulation step time (seconds)

        # Road table (initialised from config, updated by SNMP)
        self.roads: dict[int, dict] = {}
        for rid, meta in roads_meta.items():
            self.roads[rid] = {
                'roadName':           meta['roadName'],
                'type':               meta.get('type', 'normal'),
                'capacity':           meta['capacity'],
                'trafficRate':        meta['trafficRate'],
                'vehicleCount':       0,
                'trafficLightColor':  0,
                'colorShiftInterval': 0,
                'greenDuration':      0,
                'redDuration':        0,
                'delta':              0,   # change since last poll
            }

        # Forward topology:  orig -> [(dest, rate)]
        self.adj: dict[int, list] = {}
        # Reverse topology:  dest -> [(orig, rate)]  (for movement inference)
        self.rev_adj: dict[int, list] = {}
        for orig, dest, rate in conns:
            self.adj.setdefault(orig, []).append((dest, rate))
            self.rev_adj.setdefault(dest, []).append((orig, rate))

        # Traffic event log
        self.event_log: list[str] = []   # pre-formatted strings

        # UI state
        self.message    = 'Connecting to SNMP agent…'
        self.msg_ok     = True
        self.scroll_off = 0
        self.log_scroll = 0   # event log panel scroll offset


# ── Polling ────────────────────────────────────────────────────────────────────

def do_poll(state: AppState, host, port, community):
    """Fetches all relevant OIDs and updates AppState."""
    with state.lock:
        road_ids = sorted(state.roads.keys())

    # Build OID list and return map
    all_oids   = list(SCALAR_OIDS)
    oid_road_map: list[tuple[str, int, str]] = []   # (oid, road_id, attr)

    for rid in road_ids:
        for col in ROAD_COLS:
            oid = f'{_ROAD_BASE}.{col}.{rid}'
            all_oids.append(oid)
            oid_road_map.append((oid, rid, COL_TO_ATTR[col]))

    result = snmp_get(all_oids, host, port, community)

    with state.lock:
        if not result:
            state.connected = False
            return

        state.connected   = True
        state.last_poll_t = time.time()
        ts = time.strftime('%H:%M:%S')

        # Scalars
        def _get(oid, fallback):
            return result.get(oid, fallback)

        state.sys_status   = _get(OID_SYSTEM_STATUS,  state.sys_status)
        state.sim_elapsed  = _get(OID_SIM_ELAPSED,    state.sim_elapsed)
        state.vehc_entered = _get(OID_VEHC_ENTERED,   state.vehc_entered)
        state.vehc_exited  = _get(OID_VEHC_EXITED,    state.vehc_exited)
        state.vehc_in_sys  = _get(OID_VEHC_IN_SYSTEM, state.vehc_in_sys)

        # Save previous counts before updating
        prev_counts = {rid: state.roads[rid]['vehicleCount'] for rid in state.roads}

        # Road table columns
        for oid, rid, attr in oid_road_map:
            if oid in result and rid in state.roads:
                state.roads[rid][attr] = result[oid]

        # Compute deltas
        deltas = {}
        for rid in state.roads:
            delta = state.roads[rid]['vehicleCount'] - prev_counts.get(rid, 0)
            state.roads[rid]['delta'] = delta
            deltas[rid] = delta

        new_events = []

        # ── 1. GENERATION on source roads (proactive) ───────────────────────
        # Calculates how many vehicles should be generated in this step.
        if state.sys_status == 2:   # only while simulation is running
            step = state.sim_step_time
            for rid, road in state.roads.items():
                if road.get('type') != 'source':
                    continue
                tr  = road.get('trafficRate', 0)
                cap = road.get('capacity', 0)
                vc  = road.get('vehicleCount', 0)
                if tr <= 0 or vc >= cap:
                    continue
                expected = int(tr * step)
                if expected == 0 and tr > 0:
                    expected = 1   # at least 1 when rate is defined
                rname = road['roadName']
                new_events.append(
                    f'[{ts}] [GENERATE RTG={tr:>2}/s] ──▶ {rname:<5}  ~{expected} veh'
                )

        # ── 2. MOVEMENTS (inferred from destination) ─────────────────────
        # For each destination that GAINED vehicles (delta>0), find plausible
        # origins: green light + had vehicles before the step.
        # This handles source roads whose net delta is 0
        # (they generated AND exported in the same step).
        for dest, delta in deltas.items():
            if delta <= 0:
                continue
            if dest not in state.roads:
                continue
            rname_dest = state.roads[dest]['roadName']
            for orig, rate in state.rev_adj.get(dest, []):
                if orig not in state.roads:
                    continue
                orig_light = state.roads[orig].get('trafficLightColor', 0)
                orig_prev  = prev_counts.get(orig, 0)
                if orig_light != 2 or orig_prev <= 0:
                    continue  # origin was not green or had no vehicles
                rname_orig = state.roads[orig]['roadName']
                # Estimate vehicles moved based on distribution rate proportion
                total_out = sum(r for _, r in state.adj.get(orig, []))
                fraction  = rate / total_out if total_out > 0 else 1.0
                estimated = max(1, round(delta * fraction))
                new_events.append(
                    f'[{ts}] {rname_orig:>5} ──▶ {rname_dest:<5}  ~{estimated} veh'
                )

        # ── 3. EXITS at sink roads (delta<0, no outgoing connections) ────────
        for rid, delta in deltas.items():
            if delta >= 0 or rid in state.adj:
                continue
            rname = state.roads[rid]['roadName'] if rid in state.roads else str(rid)
            new_events.append(
                f'[{ts}] {rname:>5} ──▶ [NET EXIT]  {abs(delta)} veh'
            )

        if new_events:
            state.event_log.extend(new_events)
            if len(state.event_log) > MAX_LOG_ENTRIES:
                state.event_log = state.event_log[-MAX_LOG_ENTRIES:]


def poll_loop(state: AppState, host, port, community, stop_ev: threading.Event):
    while not stop_ev.is_set():
        do_poll(state, host, port, community)
        stop_ev.wait(POLL_INTERVAL)


# ── Command processing ──────────────────────────────────────────────────────────────────

HELP_MSG = (
    'Commands: start | stop | pause | set rtg <id> <val> '
    '| r=refresh | h=help | q=quit      Keys: ↑↓=table  PgUp/PgDn=log  F5=refresh'
)

HELP_FULL = """\
  start                   – Start simulation    (systemStatus=2)
  stop                    – Stop simulation     (systemStatus=1)
  pause                   – Pause simulation    (systemStatus=3)
  set rtg <id> <val>      – Change RTG of road <id>  [0-100 veh/s]
  set green <id> <val>    – Override green duration of road <id>  [>=10 s]
  set red   <id> <val>    – Override red duration of road <id>    [>=10 s]
  set capacity <id> <val> – Change capacity of road <id>          [1-1000]
  refresh / r             – Force immediate refresh
  help / h                – Show this help
  quit / q                – Exit CMC
  Keys: ↑↓=log scroll   PgUp/PgDn=table scroll   F5=refresh"""


def handle_cmd(raw: str, state: AppState, host, port, community):
    """Executes a command. Returns (message, success). '__QUIT__' → exit."""
    parts = raw.strip().split()
    if not parts:
        return '', True

    cmd = parts[0].lower()

    if cmd in ('quit', 'q', 'exit'):
        return '__QUIT__', True

    if cmd in ('help', 'h', '?'):
        return HELP_FULL, True

    if cmd in ('refresh', 'r'):
        do_poll(state, host, port, community)
        return 'Table refreshed.', True

    if cmd == 'start':
        ok = snmp_set(OID_SYSTEM_STATUS, 2, host, port, community)
        if ok:
            do_poll(state, host, port, community)
        return ('Simulation started  (status=running).' if ok else 'SNMP SET error.'), ok

    if cmd == 'stop':
        ok = snmp_set(OID_SYSTEM_STATUS, 1, host, port, community)
        if ok:
            do_poll(state, host, port, community)
        return ('Simulation stopped  (status=stopped).' if ok else 'SNMP SET error.'), ok

    if cmd == 'pause':
        ok = snmp_set(OID_SYSTEM_STATUS, 3, host, port, community)
        if ok:
            do_poll(state, host, port, community)
        return ('Simulation paused  (status=paused).' if ok else 'SNMP SET error.'), ok

    if cmd == 'set':
        sub = parts[1].lower() if len(parts) >= 2 else ''
        if sub not in ('rtg', 'green', 'red', 'capacity'):
            return 'Usage: set rtg|green|red|capacity <road_id> <value>', False
        if len(parts) < 4:
            return f'Usage: set {sub} <road_id> <value>', False
        try:
            rid = int(parts[2])
            val = int(parts[3])
        except ValueError:
            return 'road_id and value must be integers.', False
        with state.lock:
            if rid not in state.roads:
                return f'Road {rid} does not exist in the loaded map.', False

        if sub == 'rtg':
            if not (0 <= val <= 100):
                return 'RTG must be between 0 and 100 (veh/s).', False
            oid  = f'{_ROAD_BASE}.{COL_TRAFFIC_RATE}.{rid}'
            attr = 'trafficRate'
            desc = f'RTG of road {rid} set to {val} veh/s.'
        elif sub == 'green':
            if val < 10:
                return 'Green duration must be >= 10 s.', False
            oid  = f'{_ROAD_BASE}.{COL_GREEN_DUR}.{rid}'
            attr = 'greenDuration'
            desc = f'Green duration of road {rid} set to {val} s.'
        elif sub == 'red':
            if val < 10:
                return 'Red duration must be >= 10 s.', False
            oid  = f'{_ROAD_BASE}.{COL_RED_DUR}.{rid}'
            attr = 'redDuration'
            desc = f'Red duration of road {rid} set to {val} s.'
        else:  # capacity
            if val < 1:
                return 'Capacity must be >= 1.', False
            oid  = f'{_ROAD_BASE}.{COL_CAPACITY}.{rid}'
            attr = 'capacity'
            desc = f'Capacity of road {rid} set to {val}.'

        ok = snmp_set(oid, val, host, port, community)
        if ok:
            with state.lock:
                state.roads[rid][attr] = val
            return desc, True
        return 'SNMP SET error.', False

    return f'Unknown command: "{cmd}"  (type "help")', False


# (header, width, alignment: l/c/r)
_TCOLS = [
    ('ID',       3, 'r'),
    ('Name',     6, 'l'),
    ('Type',     4, 'l'),
    ('V / Cap',  9, 'c'),
    ('Occup%',       6, 'r'),
    ('Traffic Light', 13, 'c'),
    ('Nxt chg(s)',   10, 'r'),
    ('Grn dur(s)',   10, 'r'),
    ('Red dur(s)',    9, 'r'),
    ('RTG',           5, 'r'),
]
_COL_SEP = '  '


def _cell(val, width, align):
    s = str(val)[:width]
    if align == 'l':
        return s.ljust(width)
    if align == 'r':
        return s.rjust(width)
    return s.center(width)


def table_header() -> str:
    return _COL_SEP.join(_cell(lbl, w, a) for lbl, w, a in _TCOLS)


def road_row(rid: int, r: dict) -> tuple[str, int]:
    """Returns (formatted row, trafficLightColor)."""
    vc    = r.get('vehicleCount', 0)
    cap   = r.get('capacity', 1) or 1
    occ   = int(100 * vc / cap)
    light = r.get('trafficLightColor', 0)
    shift = r.get('colorShiftInterval', 0)
    green = r.get('greenDuration', 0)
    red   = r.get('redDuration', 0)
    rate  = r.get('trafficRate', 0)
    rtype = r.get('type', 'normal')
    rname = r.get('roadName', f'V{rid}')

    cells = [
        (str(rid),                       3, 'r'),
        (rname,                          6, 'l'),
        (TYPE_ABBREV.get(rtype, rtype),  4, 'l'),
        (f'{vc}/{cap}',                  9, 'c'),
        (f'{occ}%',                      6, 'r'),
        (LIGHT_LABEL.get(light, '?'),   13, 'c'),
        (str(shift),                    10, 'r'),
        (str(green),                    10, 'r'),
        (str(red),                       9, 'r'),
        (str(rate),                      5, 'r'),
    ]
    line = _COL_SEP.join(_cell(v, w, a) for v, w, a in cells)
    return line, light


_CP_TITLEBAR = 1   # black on cyan
_CP_GREEN    = 2   # green
_CP_RED      = 3   # red
_CP_YELLOW   = 4   # yellow
_CP_CYAN     = 5   # cyan
_CP_TBLHDR   = 6   # cyan bold (table header)
_CP_OKMSG    = 7   # green (success message)
_CP_ERRMSG   = 8   # red (error message)


def _init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(_CP_TITLEBAR, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(_CP_GREEN,    curses.COLOR_GREEN,  -1)
    curses.init_pair(_CP_RED,      curses.COLOR_RED,    -1)
    curses.init_pair(_CP_YELLOW,   curses.COLOR_YELLOW, -1)
    curses.init_pair(_CP_CYAN,     curses.COLOR_CYAN,   -1)
    curses.init_pair(_CP_TBLHDR,   curses.COLOR_CYAN,   -1)
    curses.init_pair(_CP_OKMSG,    curses.COLOR_GREEN,  -1)
    curses.init_pair(_CP_ERRMSG,   curses.COLOR_RED,    -1)


def _safe_addstr(win, y, x, text, attr=0):
    max_y, max_x = win.getmaxyx()
    if y < 0 or y >= max_y or x < 0 or x >= max_x:
        return
    avail = max_x - x - (1 if y == max_y - 1 else 0)
    if avail <= 0:
        return
    try:
        win.addstr(y, x, text[:avail], attr)
    except curses.error:
        pass


def draw(stdscr, state: AppState, cmd_buf: str, config_name: str, host: str, port: int):
    max_y, max_x = stdscr.getmaxyx()
    stdscr.erase()

    # Take snapshot without holding the lock during drawing
    with state.lock:
        connected    = state.connected
        sys_status   = state.sys_status
        sim_elapsed  = state.sim_elapsed
        v_entered    = state.vehc_entered
        v_exited     = state.vehc_exited
        v_in_sys     = state.vehc_in_sys
        last_t       = state.last_poll_t
        message      = state.message
        msg_ok       = state.msg_ok
        scroll_off   = state.scroll_off
        log_scroll   = state.log_scroll
        road_ids     = sorted(state.roads.keys())
        road_snap    = {rid: dict(state.roads[rid]) for rid in road_ids}
        event_log    = list(state.event_log)

    title = (
        f' CMC – Traffic Control Monitor & Control'
        f'   Map: {config_name}'
        f'   Agent: {host}:{port} '
    )
    _safe_addstr(stdscr, 0, 0,
                 title.ljust(max_x)[:max_x],
                 curses.color_pair(_CP_TITLEBAR) | curses.A_BOLD)

    conn_str = 'CONNECTED   ' if connected else 'DISCONNECTED'
    conn_cp  = _CP_GREEN if connected else _CP_RED
    stat_str = STATUS_LABEL.get(sys_status, '???')
    stat_cp  = {1: _CP_RED, 2: _CP_GREEN, 3: _CP_YELLOW}.get(sys_status, _CP_CYAN)
    h, r     = divmod(sim_elapsed, 3600)
    m, s     = divmod(r, 60)
    elapsed  = f'{h:02d}h{m:02d}m{s:02d}s'
    ago      = f'{int(time.time()-last_t)}s ago' if last_t else '–'

    x = 1
    _safe_addstr(stdscr, 1, x, 'SNMP: ')
    x += 6
    _safe_addstr(stdscr, 1, x, conn_str,
                 curses.color_pair(conn_cp) | curses.A_BOLD)
    x += len(conn_str)
    _safe_addstr(stdscr, 1, x, '   Simulation: ')
    x += 15
    _safe_addstr(stdscr, 1, x, stat_str,
                 curses.color_pair(stat_cp) | curses.A_BOLD)
    x += len(stat_str)
    _safe_addstr(stdscr, 1, x, f'   Time: {elapsed}   last update: {ago}')

    _safe_addstr(stdscr, 2, 1, 'Vehicles   Entered: ')
    x = 21
    _safe_addstr(stdscr, 2, x, str(v_entered),
                 curses.color_pair(_CP_GREEN) | curses.A_BOLD)
    x += len(str(v_entered))
    _safe_addstr(stdscr, 2, x, '   Exited: ')
    x += 11
    _safe_addstr(stdscr, 2, x, str(v_exited),
                 curses.color_pair(_CP_RED) | curses.A_BOLD)
    x += len(str(v_exited))
    _safe_addstr(stdscr, 2, x, '   In system: ')
    x += 14
    _safe_addstr(stdscr, 2, x, str(v_in_sys),
                 curses.color_pair(_CP_CYAN) | curses.A_BOLD)

    hdr = ' ' + table_header()
    _safe_addstr(stdscr, 3, 0, hdr,
                 curses.color_pair(_CP_TBLHDR) | curses.A_BOLD | curses.A_UNDERLINE)

    # ── Layout: split screen vertically ───────────────────────────────────────────
    # Fixed lines: title(0) status(1) counters(2) header(3)
    # Fixed bottom: separator + message + hint + prompt = 4 lines
    # Central area split: table (60%) | log (40%), minimum 4 lines each
    body_top    = 4          # first body line
    body_bottom = max_y - 4  # last exclusive body line
    body_h      = max(8, body_bottom - body_top)

    # table takes 60% of body, log takes remaining 40%
    table_h_raw = int(body_h * 0.60)
    log_h_raw   = body_h - table_h_raw
    table_h     = max(4, table_h_raw)
    log_h       = max(4, log_h_raw)
    # ensure both fit within body
    if table_h + log_h > body_h:
        table_h = max(4, body_h - log_h)

    table_end_y = body_top + table_h   # first line after table
    log_start_y = table_end_y + 1      # +1 for separator between table and log
    log_end_y   = min(log_start_y + log_h, body_bottom)

    # ── Road table 
    total      = len(road_ids)
    max_scroll = max(0, total - table_h)
    scroll_off = max(0, min(scroll_off, max_scroll))

    with state.lock:
        state.scroll_off = scroll_off

    visible = road_ids[scroll_off: scroll_off + table_h]

    for i, rid in enumerate(visible):
        row_y = body_top + i
        if row_y >= table_end_y:
            break
        line, light = road_row(rid, road_snap[rid])
        rtype = road_snap[rid].get('type', 'normal')
        if light == 2:
            cp = _CP_GREEN
        elif light == 1:
            cp = _CP_RED
        else:
            cp = _CP_CYAN
        bold = curses.A_BOLD if rtype == 'source' else 0
        _safe_addstr(stdscr, row_y, 1, line, curses.color_pair(cp) | bold)

    # Table scroll indicator
    if total > table_h:
        ind = f' ↑↓ {scroll_off+1}-{min(scroll_off+table_h,total)}/{total} '
        try:
            stdscr.addstr(body_top, max(0, max_x - len(ind) - 1), ind,
                          curses.color_pair(_CP_YELLOW) | curses.A_BOLD)
        except curses.error:
            pass

    # ── Separator between table and log 
    if table_end_y < max_y - 4:
        _safe_addstr(stdscr, table_end_y, 0,
                     '─── Movement Log ' + '─' * max(0, max_x - 15))

    # ── Log panel 
    log_lines = log_h - 1  # visible lines
    total_log  = len(event_log)
    max_lscroll = max(0, total_log - log_lines)
    log_scroll  = max(0, min(log_scroll, max_lscroll))

    with state.lock:
        state.log_scroll = log_scroll

    # show most recent entries at the bottom (scroll up to see older entries)
    visible_log = event_log[-(log_lines + log_scroll): total_log - log_scroll or None]
    if log_scroll == 0:
        visible_log = event_log[-log_lines:]
    else:
        visible_log = event_log[-(log_lines + log_scroll): -log_scroll]

    for i, entry in enumerate(visible_log):
        ly = log_start_y + i
        if ly >= log_end_y:
            break
        # colour line by type
        if '▶' in entry and 'NET EXIT' in entry:
            lcp = curses.color_pair(_CP_RED)
        elif 'GENERATE' in entry:
            lcp = curses.color_pair(_CP_GREEN)
        elif 'RED' in entry:
            lcp = curses.color_pair(_CP_RED)
        else:
            lcp = curses.color_pair(_CP_CYAN)
        _safe_addstr(stdscr, ly, 1, entry, lcp)

    if total_log > log_lines and log_start_y < max_y - 4:
        lind = f' PgUp/PgDn {log_scroll+1}-{min(log_scroll+log_lines,total_log)}/{total_log} '
        try:
            stdscr.addstr(log_start_y, max(0, max_x - len(lind) - 1), lind,
                          curses.color_pair(_CP_YELLOW))
        except curses.error:
            pass

    sep_y  = max_y - 4
    msg_y  = max_y - 3
    hint_y = max_y - 2
    cmd_y  = max_y - 1

    _safe_addstr(stdscr, sep_y, 0, '─' * (max_x - 1))

    if message:
        msg_cp = _CP_OKMSG if msg_ok else _CP_ERRMSG
        _safe_addstr(stdscr, msg_y, 1, message,
                     curses.color_pair(msg_cp))

    hint = ' start|stop|pause   set rtg|green|red|capacity <id> <val>   r=refresh   h=help   q=quit   [↑↓=log  PgUp/PgDn=table  F5=refresh]'
    _safe_addstr(stdscr, hint_y, 0, hint,
                 curses.color_pair(_CP_YELLOW))

    prompt   = '> '
    cmd_line = (prompt + cmd_buf)[: max_x - 2]
    _safe_addstr(stdscr, cmd_y, 0, cmd_line, curses.A_BOLD)
    try:
        stdscr.move(cmd_y, min(len(cmd_line), max_x - 2))
    except curses.error:
        pass

    stdscr.refresh()


def tui(stdscr, state: AppState, config_name: str, host: str, port: int, community: str):
    _init_colors()
    curses.curs_set(1)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.timeout(500)   # max refresh every 500 ms

    cmd_buf = ''

    # Start polling thread
    stop_ev = threading.Event()
    threading.Thread(
        target=poll_loop,
        args=(state, host, port, community, stop_ev),
        daemon=True,
    ).start()

    # First immediate poll in background
    threading.Thread(
        target=do_poll,
        args=(state, host, port, community),
        daemon=True,
    ).start()

    while True:
        max_y, _   = stdscr.getmaxyx()
        body_h     = max(8, max_y - 8)
        table_h    = max(4, int(body_h * 0.60))
        log_h      = max(4, body_h - table_h)

        with state.lock:
            total      = len(state.roads)
            total_log  = len(state.event_log)
        max_scroll  = max(0, total - table_h)
        max_lscroll = max(0, total_log - (log_h - 1))

        draw(stdscr, state, cmd_buf, config_name, host, port)

        ch = stdscr.getch()
        if ch == curses.ERR:
            continue
        # ── Log navigation (↑/↓) ────────────────────────────────────────────
        if ch == curses.KEY_UP:
            with state.lock:
                state.log_scroll = min(max_lscroll, state.log_scroll + 1)
            continue

        if ch == curses.KEY_DOWN:
            with state.lock:
                state.log_scroll = max(0, state.log_scroll - 1)
            continue

        # PgUp/PgDn scroll the road table
        if ch == curses.KEY_PPAGE:
            with state.lock:
                state.scroll_off = max(0, state.scroll_off - (table_h - 1))
            continue

        if ch == curses.KEY_NPAGE:
            with state.lock:
                state.scroll_off = min(max_scroll, state.scroll_off + (table_h - 1))
            continue

        # F5 → immediate refresh
        if ch == curses.KEY_F5:
            threading.Thread(
                target=do_poll,
                args=(state, host, port, community),
                daemon=True,
            ).start()
            with state.lock:
                state.message = 'Refreshing…'
                state.msg_ok  = True
            continue

        # ── Text input 
        if ch in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            cmd = cmd_buf.strip()
            cmd_buf = ''
            if not cmd:
                continue
            msg, ok = handle_cmd(cmd, state, host, port, community)
            if msg == '__QUIT__':
                stop_ev.set()
                return
            with state.lock:
                state.message = msg
                state.msg_ok  = ok
            continue

        if ch in (curses.KEY_BACKSPACE, 127, 8):
            cmd_buf = cmd_buf[:-1]
            continue

        if 32 <= ch < 127:
            cmd_buf += chr(ch)
            with state.lock:
                state.message = ''
            continue


# ── Entry point 

def main():
    ap = argparse.ArgumentParser(
        description='CMC – Monitoring and Control Console (Terminal TUI)'
    )
    ap.add_argument(
        '--config',
        help='Config filename (inside traffic-configs/)',
    )
    ap.add_argument(
        '--host',
        default=SNMP_HOST,
        help=f'SNMP agent host (default: {SNMP_HOST})',
    )
    ap.add_argument(
        '--port',
        default=SNMP_PORT,
        type=int,
        help=f'SNMP agent port (default: {SNMP_PORT})',
    )
    ap.add_argument(
        '--community',
        default=SNMP_COMMUNITY,
        help=f'SNMP community string (default: {SNMP_COMMUNITY})',
    )
    args = ap.parse_args()

    # Resolve config file path
    if args.config:
        path = os.path.join(CONFIGS_DIR, args.config)
        if not os.path.isfile(path):
            # Try as absolute/relative path
            if os.path.isfile(args.config):
                path = args.config
            else:
                print(f'[!] Config file not found: {args.config}')
                sys.exit(1)
    else:
        path = choose_config()

    config_name = os.path.basename(path)
    roads_meta, conns, step_time = load_road_meta(path)
    state = AppState(roads_meta, conns, step_time)

    print(f'\n[*] Map loaded  : {config_name}  ({len(roads_meta)} roads)')
    print(f'[*] SNMP agent  : {args.host}:{args.port}  (community={args.community})')
    print('[*] Starting terminal interface…')
    time.sleep(0.4)

    try:
        curses.wrapper(tui, state, config_name, args.host, args.port, args.community)
    except KeyboardInterrupt:
        pass

    print('\n[*] CMC terminated.')


if __name__ == '__main__':
    main()

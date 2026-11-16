#!/usr/bin/env python3
"""Adaptive multi-connection HTTP(S) downloader behind the `dl` shell function.

Many servers throttle each connection, so more parallel connections means more
speed, up to the point where the server (or your line) starts stalling them.
aria2c stops at 16 connections per server; this goes up to 128 and finds the
best count by itself. No separate speed test: the download itself is the probe.
It starts at 16 connections, doubles them every few seconds while the total
speed keeps rising, settles on the best level (1 … 128), and every minute tries
one level up again, because servers change their mood.

Segments work like IDM: each connection keeps reading its own stretch of the
file, and a new connection splits the largest gap nobody is working on. The
terminal shows a live colour map of the file with every segment growing.

aria2c-compatible:
- progress is kept in `<file>.aria2`, a genuine aria2c control file, so aria2c
  can resume a download started here and this resumes one started by aria2c
- Ctrl-C once: stop cleanly and keep progress; twice: stop immediately
- options: -d/--dir, -o/--out, --summary-interval; anything else → exit 3 so the
  caller hands the whole command to aria2c
- exit codes: 0 done · 1 failed (progress kept) · 3 not for us, use aria2c ·
  7 stopped with Ctrl-C (download unfinished, like aria2c)
- NO_COLOR=1 turns colours off; piped output gets plain periodic status lines

Standard library only.
"""
import atexit
import http.client
import math
import os
import re
import shutil
import signal
import ssl
import struct
import sys
import threading
import time
import urllib.parse

PIECE = 1 << 20                  # aria2c's default --piece-length (1M)
LEVELS = [1, 4, 8, 16, 32, 64, 128]
START = LEVELS.index(16)
WARMUP = 1.0                     # seconds ignored after a change (TLS handshakes)
WINDOW = 3.0                     # seconds measured per level
GAIN = 1.10                      # a higher level must be ≥ 10 % faster to stay
REPROBE = 60.0                   # try one level up again this often
TIMEOUT = 20                     # stalled connection → piece retried elsewhere
SAVE_EVERY = 5.0
TICK = 0.25                      # screen refresh
UA = "aria2/1.37.0"              # same as aria2c, servers tuned for it accept it


class NotForUs(Exception):
    """The server or the command line needs plain aria2c (exit 3)."""


# ---------------------------------------------------------------- formatting --
def size_fmt(n):
    """905 KiB, 9.4 MiB, 123 MiB, 5.1 GiB."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1000 or unit == "TiB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}" if n < 100 else f"{n:.0f} {unit}"
        n /= 1024


def time_fmt(sec):
    """1h 05m, 12m 40s, 7s."""
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s" if m else f"{s}s"


# ------------------------------------------------------------------ terminal --
class Style:
    """ANSI colours for one stream; plain text when it is not a terminal."""

    def __init__(self, stream):
        term = os.environ.get("TERM", "")
        self.on = stream.isatty() and term != "dumb" and not os.environ.get("NO_COLOR")
        rich = "256" in term or bool(os.environ.get("COLORTERM"))
        enc = (getattr(stream, "encoding", "") or "").lower()
        self.utf = "utf" in enc

        def mk(c256, c8):
            code = c256 if rich else c8
            return (lambda s: f"\033[{code}m{s}\033[0m") if self.on else (lambda s: s)
        self.bold = mk("1", "1")
        self.dim = mk("38;5;245", "2")
        self.name = mk("1;38;5;255", "1;37")
        self.green = mk("1;38;5;42", "1;32")
        self.amber = mk("1;38;5;214", "1;33")
        self.red = mk("1;38;5;203", "1;31")
        self.blue = mk("38;5;75", "36")
        self.track = mk("38;5;239", "90")         # empty part of bars and the map


OUT, ERR = Style(sys.stdout), Style(sys.stderr)
BARS = " ▁▂▃▄▅▆▇█"


def notice(msg):
    """One-line hand-over message on stderr (dl then runs aria2c)."""
    print(ERR.dim(f"dl: {msg}, handing over to aria2c"), file=sys.stderr, flush=True)


class Screen:
    """A live area at the bottom of the output, redrawn in place."""

    def __init__(self):
        self.live = sys.stdout.isatty() and os.environ.get("TERM") != "dumb"
        self.drawn = 0                    # lines of the live area on screen
        self.hidden = False

    def _up(self):
        return "\r" + (f"\033[{self.drawn - 1}A" if self.drawn > 1 else "")

    def draw(self, lines):
        if not self.live:
            return
        buf = ""
        if not self.hidden:
            buf, self.hidden = "\033[?25l", True
        buf += (self._up() + "\033[J") if self.drawn else ""
        buf += "\n".join(lines)
        self.drawn = len(lines)
        sys.stdout.write(buf)
        sys.stdout.flush()

    def clear(self):
        if self.live and self.drawn:
            sys.stdout.write(self._up() + "\033[J")
            self.drawn = 0

    def keep(self):
        """Leave the live area on screen and continue below it."""
        if self.drawn:
            sys.stdout.write("\n")
            self.drawn = 0
        self.show_cursor()

    def say(self, text):
        self.clear()
        print(text, flush=True)

    def show_cursor(self):
        if self.hidden:
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
            self.hidden = False


# --------------------------------------------------------------------- HTTP --
def proxy_for(scheme):
    for key in (f"{scheme}_proxy", f"{scheme.upper()}_PROXY", "all_proxy", "ALL_PROXY"):
        if os.environ.get(key):
            p = urllib.parse.urlsplit(os.environ[key])
            if p.scheme not in ("http", ""):
                raise NotForUs(f"{p.scheme} proxy")
            return p.hostname, p.port or 8080
    return None


def connect(url):
    u = urllib.parse.urlsplit(url)
    port = u.port or (443 if u.scheme == "https" else 80)
    proxy = proxy_for(u.scheme)
    if u.scheme == "https":
        cls, kw = http.client.HTTPSConnection, {"context": ssl.create_default_context()}
    else:
        cls, kw = http.client.HTTPConnection, {}
    if proxy:
        conn = cls(proxy[0], proxy[1], timeout=TIMEOUT, **kw)
        conn.set_tunnel(u.hostname, port)
    else:
        conn = cls(u.hostname, port, timeout=TIMEOUT, **kw)
    return conn


def get_range(conn, url, start, end):
    u = urllib.parse.urlsplit(url)
    path = (u.path or "/") + ("?" + u.query if u.query else "")
    conn.request("GET", path, headers={"Range": f"bytes={start}-{end}", "User-Agent": UA,
                                       "Accept-Encoding": "identity"})
    return conn.getresponse()


def resolve(url):
    """Follow redirects with a 1-byte range request → (final url, size, filename)."""
    for _ in range(10):
        conn = connect(url)
        try:
            r = get_range(conn, url, 0, 0)
            r.read()
        finally:
            conn.close()
        if r.status in (301, 302, 303, 307, 308) and r.getheader("Location"):
            url = urllib.parse.urljoin(url, r.getheader("Location"))
            continue
        if r.status in (429, 503):
            raise NotForUs(f"server is refusing requests (HTTP {r.status} {r.reason}), try again later")
        if r.status != 206:
            raise NotForUs(f"no range support (HTTP {r.status})")
        m = re.search(r"/(\d+)\s*$", r.getheader("Content-Range") or "")
        if not m:
            raise NotForUs("server does not report the file size")
        name = None
        cd = r.getheader("Content-Disposition") or ""
        m2 = (re.search(r"filename\*\s*=\s*[^']*'[^']*'([^;]+)", cd)
              or re.search(r'filename\s*=\s*"?([^";]+)"?', cd))
        if m2:
            name = os.path.basename(urllib.parse.unquote(m2.group(1)).strip())
        return url, int(m.group(1)), name
    raise NotForUs("too many redirects")


def name_from(url):
    return urllib.parse.unquote(os.path.basename(urllib.parse.urlsplit(url).path))


# ------------------------------------------------- aria2c control file (v1) --
def read_control(path, size):
    """→ (piece length, set of completed pieces) or None if unusable."""
    try:
        data = open(path, "rb").read()
        if struct.unpack(">H", data[:2])[0] != 1:
            return None
        off = 6
        (ihl,) = struct.unpack(">I", data[off:off + 4]); off += 4 + ihl
        plen, total = struct.unpack(">IQ", data[off:off + 12]); off += 12 + 8
        (blen,) = struct.unpack(">I", data[off:off + 4]); off += 4
        bits = data[off:off + blen]
        n = -(-total // plen)
        if total != size or not plen or blen != -(-n // 8):
            return None
        return plen, {i for i in range(n) if bits[i >> 3] & (0x80 >> (i & 7))}
    except (OSError, struct.error, IndexError, ZeroDivisionError):
        return None


def write_control(path, plen, size, done):
    n = -(-size // plen)
    bits = bytearray(-(-n // 8))
    for i in done:
        bits[i >> 3] |= 0x80 >> (i & 7)
    blob = (struct.pack(">H", 1) + b"\0\0\0\0" + struct.pack(">I", 0)
            + struct.pack(">IQQ", plen, size, 0) + struct.pack(">I", len(bits)) + bytes(bits)
            + struct.pack(">I", 0))
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(blob)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)



# ----------------------------------------------------------------- download --
class Download:
    def __init__(self, url, final, size, out, screen):
        self.url, self.final, self.size, self.out = url, final, size, out
        self.screen = screen
        self.ctrl = out + ".aria2"
        self.lock = threading.Lock()
        self.plen, done = PIECE, set()
        if os.path.exists(self.ctrl):
            got = read_control(self.ctrl, size)
            if got is None:
                raise NotForUs(f"{self.ctrl} belongs to a different download")
            self.plen, done = got
        self.n = -(-size // self.plen)
        self.done = done
        self.donelog = sorted(done)       # completion order, for the segment map
        self.todo = set(range(self.n)) - done
        self.partial = {}                 # piece in flight → bytes written so far
        self.conns = {}                   # worker → its segment, for the connection list
        self.crate = {}                   # worker → (bytes seen, smoothed speed)
        self.last_draw = time.time()
        self.got = 0                      # bytes received this session
        self.target = 0
        self.alive = set()
        self.refusals = 0                 # HTTP 429/503 answers: too many connections
        self.cap = len(LEVELS) - 1        # highest level the server tolerates
        self.stop = False
        self.testing = False              # trying a different connection count
        self.last_resolve = time.time()
        self.map = None                   # segment map cache, see segment_map()
        self.fd = os.open(out, os.O_RDWR | os.O_CREAT, 0o644)
        if os.fstat(self.fd).st_size != size:
            os.ftruncate(self.fd, size)
        self.save()

    # -- bookkeeping
    def piece_len(self, i):
        return min(self.plen, self.size - i * self.plen)

    def save(self):
        with self.lock:
            done = set(self.done)
        write_control(self.ctrl, self.plen, self.size, done)

    def have(self, partial=True):
        """Bytes that count: completed pieces (+ pieces in flight)."""
        with self.lock:
            short = self.plen - self.piece_len(self.n - 1) if (self.n - 1) in self.done else 0
            return len(self.done) * self.plen - short + (sum(self.partial.values()) if partial else 0)

    def finished(self):
        with self.lock:
            return len(self.done) == self.n

    def take(self, wid, prev):
        with self.lock:
            if self.stop or wid >= self.target:
                return None
            if not self.todo:            # end game: a failed piece may come back
                return -1 if self.partial else None
            if prev is not None and prev + 1 in self.todo:
                i = prev + 1                  # keep reading the same segment
            else:
                i = self.split()              # a new segment starts here
                c = self.conns.setdefault(wid, {"bytes": 0})
                c["start"] = i * self.plen
            self.todo.discard(i)
            self.partial[i] = 0
            c = self.conns.setdefault(wid, {"bytes": 0, "start": i * self.plen})
            c.update(piece=i, pos=i * self.plen)
            c.setdefault("state", "connecting")
            return i

    def split(self):
        """IDM-style: take a gap nobody is heading into, else halve the largest one."""
        best_score, best = -1, None
        run_start = prev = None
        for i in sorted(self.todo) + [None]:
            if run_start is not None and (i is None or i != prev + 1):
                length = prev - run_start + 1
                owned = (run_start - 1) in self.partial       # a connection reads into it
                score, at = (length // 2, run_start + length // 2) if owned else (length, run_start)
                if score > best_score:
                    best_score, best = score, at
                run_start = None
            if i is not None and run_start is None:
                run_start = i
            prev = i
        return best

    def give_back(self, i, ok):
        with self.lock:
            self.partial.pop(i, None)
            if ok:
                self.done.add(i)
                self.donelog.append(i)
            else:
                self.todo.add(i)

    # -- workers
    def worker(self, wid):
        conn, prev = None, None
        try:
            while True:
                i = self.take(wid, prev)
                if i is None:
                    return
                if i < 0:
                    time.sleep(0.2)
                    continue
                start = i * self.plen
                end = start + self.piece_len(i) - 1
                ok = False
                try:
                    if conn is None:
                        self.conn_state(wid, "connecting")
                        conn = connect(self.final)
                    r = get_range(conn, self.final, start, end)
                    if r.status != 206:
                        r.read()
                        if r.status in (429, 503):          # too many connections
                            self.conn_state(wid, "server busy")
                            with self.lock:
                                self.refusals += 1
                            ra = r.getheader("Retry-After") or ""
                            self.nap(min(int(ra), 60) if ra.isdigit() else 5)
                        if r.status in (401, 403, 404, 410):
                            self.reresolve()    # signed redirect links expire
                        raise IOError(f"HTTP {r.status}")
                    self.conn_state(wid, "receiving")
                    pos = start
                    while pos <= end and not self.stop:   # surplus workers finish their piece, then exit
                        buf = r.read1(min(262144, end - pos + 1))   # read1: return what has arrived
                        if not buf:
                            raise IOError("connection closed")
                        os.pwrite(self.fd, buf, pos)
                        pos += len(buf)
                        with self.lock:
                            self.got += len(buf)
                            self.partial[i] = pos - start
                            c = self.conns[wid]
                            c["pos"] = pos
                            c["bytes"] += len(buf)
                    ok = pos > end
                    if not ok:
                        conn.close()
                        conn = None
                except (OSError, http.client.HTTPException, ssl.SSLError):
                    if conn:
                        conn.close()
                    conn = None
                    if not self.stop:
                        self.conn_state(wid, "retrying")
                        time.sleep(1)
                self.give_back(i, ok)
                prev = i if ok else None
        finally:
            if conn:
                conn.close()
            with self.lock:
                self.alive.discard(wid)
                self.conns.pop(wid, None)

    def conn_state(self, wid, state):
        with self.lock:
            if wid in self.conns:
                self.conns[wid]["state"] = state

    def nap(self, sec):
        end = time.time() + sec
        while time.time() < end and not self.stop:
            time.sleep(0.2)

    def reresolve(self):
        with self.lock:
            if time.time() - self.last_resolve < 20:
                return
            self.last_resolve = time.time()
        try:
            final, size, _ = resolve(self.url)
            if size == self.size:
                self.final = final
        except (OSError, http.client.HTTPException, NotForUs):
            pass

    def set_level(self, n):
        with self.lock:
            self.target = n = max(1, n)
            room = len(self.todo)                       # no point starting idle workers
            start = [w for w in range(n) if w not in self.alive][:room]
            self.alive.update(start)
        for w in start:
            threading.Thread(target=self.worker, args=(w,), daemon=True).start()

    # -- display
    def file_map(self, width):
        """The whole file as a strip of columns, each a slice of it that fills
        upwards: green = downloaded, amber = a connection is writing there."""
        cells = max(1, min(width, self.size))
        bound = [c * self.size // cells for c in range(cells + 1)]
        if not self.map or self.map[0] != cells:
            self.map = [cells, [0] * cells, 0]          # cells, done bytes per cell, log read
        _, filled, seen = self.map

        def spread(start, length, into):
            end, c = start + length, start * cells // self.size
            while start < end and c < cells:
                seg = min(end, bound[c + 1]) - start
                if seg > 0:
                    into[c] += seg
                    start += seg
                c += 1

        with self.lock:
            new = self.donelog[seen:]
            partial = dict(self.partial)
        self.map[2] = seen + len(new)
        for i in new:
            spread(i * self.plen, self.piece_len(i), filled)
        extra, busy = [0] * cells, [False] * cells
        for i, p in partial.items():
            busy[min(cells - 1, (i * self.plen + p) * cells // self.size)] = True
            spread(i * self.plen, p, extra)

        top, bottom = ["  "], ["  "]
        for c in range(cells):
            f = (filled[c] + extra[c]) / max(1, bound[c + 1] - bound[c])
            lvl = 16 if f >= 0.999 else (max(1, round(f * 16)) if f > 0 or busy[c] else 0)
            if not OUT.utf:
                bottom.append(OUT.green("#") if lvl == 16 else OUT.amber("+") if busy[c]
                              else OUT.green("+") if lvl else OUT.track("."))
                continue
            paint = OUT.amber if busy[c] else OUT.green
            bottom.append(paint(BARS[min(lvl, 8)]) if lvl else OUT.track("▁"))
            top.append(paint(BARS[lvl - 8]) if lvl > 8 else " ")
        return (["".join(top)] if OUT.utf else []) + ["".join(bottom)]

    def conn_lines(self, width, max_rows):
        """IDM-style list: every connection with its own segment's progress."""
        now = time.time()
        dt, self.last_draw = max(now - self.last_draw, 1e-3), now
        with self.lock:
            rows = []
            for wid, c in self.conns.items():
                if "piece" not in c:
                    continue
                j = c["piece"] + 1                      # segment ends where the next one starts
                while j < self.n and j in self.todo:
                    j += 1
                end = min(j * self.plen, self.size)
                rows.append((c["start"], wid, (c["pos"] - c["start"]) / max(1, end - c["start"]),
                             c["bytes"], c["state"]))
        alpha = 1 - math.exp(-dt / 2.0)                 # ~2 s smoothing
        for _, wid, _, got, _ in rows:
            seen, speed = self.crate.get(wid, (got, 0.0))
            self.crate[wid] = (got, speed + alpha * ((got - seen) / dt - speed))
        rows.sort()
        if not rows or max_rows < 1:
            return []
        ncol = max(1, (width + 3) // 35)
        colw = (width - 3 * (ncol - 1)) // ncol
        bw = colw - 22
        shown = rows if len(rows) <= ncol * max_rows else rows[:ncol * (max_rows - 1)]
        cells = []
        for _, wid, prog, _, state in shown:
            prog = min(max(prog, 0.0), 1.0)
            k = max(1, round(prog * bw)) if prog > 0 else 0   # an active segment always shows its head
            bar = (OUT.amber(("━" if OUT.utf else "=") * k) + OUT.track(("─" if OUT.utf else "-") * (bw - k)))
            if state == "receiving":
                tail = f"{size_fmt(self.crate[wid][1]) + '/s':>11}"
            else:
                tail = OUT.amber(f"{state:>11}") if state == "server busy" else OUT.dim(f"{state:>11}")
            cells.append(f"{OUT.dim(f'{wid + 1:>3}')} {bar} {prog * 100:3.0f}%  {tail}")
        nrow = -(-len(cells) // ncol)                   # read top to bottom, then across
        lines = ["  " + "   ".join(cells[r::nrow]) for r in range(nrow)]
        if len(shown) < len(rows):
            lines.append("  " + OUT.dim(f"and {len(rows) - len(shown)} more connections"))
        return lines

    def status(self, rate, cols):
        have = self.have()
        with self.lock:
            busy = len(self.partial)
        parts = [OUT.green(f"{have * 100 / self.size:5.1f}%"),
                 f"{OUT.bold(size_fmt(have))} {OUT.dim('of')} {size_fmt(self.size)}",
                 OUT.bold(f"{size_fmt(rate)}/s")]
        if have < self.size:
            parts.append(f"{time_fmt((self.size - have) / rate)} {OUT.dim('left')}" if rate > 0
                         else OUT.amber("waiting for the server"))
        if self.stop:
            parts.append(OUT.amber("stopping, press Ctrl-C again to quit now"))
        elif self.testing:
            parts.append(OUT.amber(f"testing {self.target} connections"))
        else:
            parts.append(f"{busy} {OUT.dim('connections')}")
        line = "  " + "   ".join(parts)
        while len(parts) > 1 and visible(line) > cols - 1:
            parts.pop()
            line = "  " + "   ".join(parts)
        return line

    def render(self, rate, state=None, final=False):
        if self.screen.live:
            cols, lines = shutil.get_terminal_size((80, 24))
            width = max(20, min(cols - 4, 120))
            frame = [""] + self.file_map(width)
            if not final:                              # the summary follows instead
                frame += ["", self.status(rate, cols)]
                conns = self.conn_lines(width, lines - len(frame) - 4)
                frame += [""] + conns if conns else []
            self.screen.draw(frame + [""] if final else frame)      # final: blank line before the summary
        elif state is not None and state["every"] and time.time() - state["plain"] >= state["every"]:
            state["plain"] = time.time()
            print(self.status(rate, 10 ** 6), flush=True)

    def note(self, text):
        self.screen.say("  " + text)

    def run(self, summary_every):
        t0 = time.time()
        state = {"rate": 0.0, "refused": False, "plain": t0, "every": summary_every}
        samples = []                                   # (time, bytes) for a 3 s rolling rate

        def tick():
            now = time.time()
            samples.append((now, self.got))
            while samples and now - samples[0][0] > WINDOW:
                samples.pop(0)
            if len(samples) > 1 and samples[-1][0] > samples[0][0]:
                state["rate"] = (samples[-1][1] - samples[0][1]) / (samples[-1][0] - samples[0][0])
            self.render(state["rate"], state)

        def wait(sec):
            end = time.time() + sec
            while time.time() < end and busy():
                time.sleep(TICK)
                tick()

        def measure():
            """Average speed over WINDOW after WARMUP, while showing progress."""
            wait(WARMUP)
            g, t, ref = self.got, time.time(), self.refusals
            wait(WINDOW)
            state["refused"] = self.refusals > ref
            return (self.got - g) / max(time.time() - t, 0.001)

        def busy():
            return not (self.stop or self.finished())

        def settled(n, speed, why=""):
            self.note(f"{why}Using {OUT.bold(n)} connections "
                      + OUT.dim(f"({size_fmt(speed)}/s measured)"))

        # ramp up: double connections while the total keeps rising
        self.testing = True
        lvl = START
        self.set_level(LEVELS[lvl])
        best_lvl, best = lvl, measure()
        while busy() and state["refused"] and lvl > 0:   # refused already at 16: go down
            lvl -= 1
            self.cap = lvl
            self.set_level(LEVELS[lvl])
            best_lvl, best = lvl, measure()
        while busy() and lvl + 1 <= self.cap:
            lvl += 1
            self.set_level(LEVELS[lvl])
            r = measure()
            if state["refused"]:                       # server says: too many
                self.cap = lvl - 1
                break
            if r >= best * GAIN:
                best_lvl, best = lvl, r
            else:
                break
        if busy() and best_lvl == START and self.cap >= START:   # maybe fewer is better
            for lvl in range(START - 1, -1, -1):
                self.set_level(LEVELS[lvl])
                r = measure()
                if r > best * GAIN:
                    best_lvl, best = lvl, r
                else:
                    break
        self.testing = False
        if busy():
            self.set_level(LEVELS[best_lvl])
            settled(LEVELS[best_lvl], best)

        # steady state, re-probing one level up every minute
        last_probe = last_save = time.time()
        while busy():
            r = measure()
            if state["refused"] and best_lvl > 0:      # server started refusing: step down
                best_lvl -= 1
                self.cap = best_lvl
                self.set_level(LEVELS[best_lvl])
                self.note(OUT.amber("Server refused extra connections (HTTP 429/503). ")
                          + f"Now using {OUT.bold(LEVELS[best_lvl])}")
            if time.time() - last_save > SAVE_EVERY:
                self.save()
                last_save = time.time()
            if busy() and time.time() - last_probe > REPROBE and best_lvl + 1 <= self.cap:
                last_probe = time.time()
                self.testing = True
                self.set_level(LEVELS[best_lvl + 1])
                r2 = measure()
                self.testing = False
                if r2 >= r * GAIN and not state["refused"]:
                    best_lvl += 1
                    settled(LEVELS[best_lvl], r2)
                else:
                    self.set_level(LEVELS[best_lvl])
            if busy():
                self.set_level(LEVELS[best_lvl])       # replace workers that exited
        tick()
        return time.time() - t0, self.got


ANSI = re.compile(r"\033\[[0-9;?]*[A-Za-z]")


def visible(s):
    return len(ANSI.sub("", s))


def parse(argv):
    """url [-d DIR] [-o NAME] [--summary-interval=SEC]; anything else → aria2c."""
    url, d, o, summ = None, ".", None, 60
    it = iter(argv)
    for a in it:
        m = re.match(r"^(--dir|--out|--summary-interval)=(.*)$", a)
        key, val = (m.group(1), m.group(2)) if m else (a, None)
        if key in ("-d", "--dir", "-o", "--out", "--summary-interval"):
            val = val if val is not None else next(it, None)
            if val is None:
                raise NotForUs(f"{key} needs a value")
            if key in ("-d", "--dir"):
                d = val
            elif key in ("-o", "--out"):
                o = val
            else:
                if not val.isdigit():
                    raise NotForUs(f"{key} needs a number")
                summ = int(val)
        elif a.startswith("-") or url is not None:
            raise NotForUs(f"option or extra argument {a!r}")
        else:
            url = a
    if not url or not re.match(r"^https?://", url):
        raise NotForUs("not an http(s) link")
    return url, d, o, summ


def main():
    try:
        url, outdir, out, summ = parse(sys.argv[1:])
        final, size, cd_name = resolve(url)
        if size == 0:
            raise NotForUs("empty file")
    except NotForUs as e:
        notice(e)
        return 3
    except (OSError, http.client.HTTPException) as e:
        notice(f"cannot reach the server ({e})")
        return 3

    name = (out or cd_name or name_from(url) or name_from(final) or "index.html").replace("/", "_")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, name)
    if os.path.exists(path) and not os.path.exists(path + ".aria2"):
        if os.path.getsize(path) == size:
            print(f"  {OUT.green('✓' if OUT.utf else 'OK')} Already downloaded  {OUT.dim(path)}")
            return 0
        stem, ext = os.path.splitext(path)       # aria2c's auto-file-renaming
        k = 1
        while os.path.exists(f"{stem}.{k}{ext}"):
            k += 1
        path = f"{stem}.{k}{ext}"

    screen = Screen()
    try:
        d = Download(url, final, size, path, screen)
    except NotForUs as e:
        notice(e)
        return 3
    atexit.register(screen.show_cursor)

    host = urllib.parse.urlsplit(final).hostname or "?"
    resumed = d.have()
    print(f"\n  {OUT.name(os.path.basename(path))}")
    print("  " + OUT.dim(f"{size_fmt(size)} from {host}")
          + (OUT.blue(f", resuming at {resumed * 100 / size:.1f}%") if resumed else ""))

    presses = []

    def on_signal(*_):
        presses.append(1)
        if len(presses) == 1:
            d.stop = True                            # status line says "stopping…"
        else:
            d.save()
            screen.keep()
            sys.stdout.write(f"  {OUT.amber('Stopped immediately.')} Progress is saved; "
                             "run the same dl command to resume.\n")
            sys.stdout.flush()
            os._exit(7)
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGHUP, on_signal)      # terminal closed: save and stop

    try:
        took, got = d.run(summ)
    except Exception as e:                       # keep progress whatever happened
        d.stop = True
        d.save()
        screen.keep()
        print(f"  {OUT.red('✗' if OUT.utf else 'X')} {OUT.red('Download failed:')} {e}", file=sys.stderr)
        print("    " + OUT.dim("Progress is saved. Run the same dl command to resume."), file=sys.stderr)
        return 1

    avg = got / max(took, 0.001)
    if d.finished():
        os.fsync(d.fd)
        os.close(d.fd)
        os.remove(d.ctrl)
        d.render(avg, final=True)
        screen.keep()
        print(f"  {OUT.green('✓' if OUT.utf else 'OK')} {OUT.bold('Done')}  {size_fmt(size)} in "
              f"{time_fmt(took)}, {OUT.bold(size_fmt(avg) + '/s')} on average")
        print("    " + OUT.dim(os.path.abspath(path)))
        return 0
    time.sleep(0.5)                              # let workers drop their pieces
    d.save()
    with d.lock:
        d.partial.clear()                        # unfinished pieces are not kept
    d.render(avg, final=True)
    screen.keep()
    have = d.have(partial=False)
    print(f"  {OUT.amber('Paused')} at {OUT.bold(f'{have * 100 / size:.1f}%')}, "
          f"{size_fmt(have)} of {size_fmt(size)} kept")
    print("    " + OUT.dim("Run the same dl command to resume (aria2c -c works too)."))
    return 7


if __name__ == "__main__":
    sys.exit(main())

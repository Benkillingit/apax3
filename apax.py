#!/usr/bin/env python3
"""
APAX 3.0 — an AI that starts with nothing.

No rules. No directives. No model. No seed text. No vocabulary.
Nothing is baked in except the ability to THINK: notice, ask,
remember, imitate — using as much RAM and CPU as it wants.

Capabilities, and their state at birth:

    internet   GRANTED at birth, read-only — its one vein to the world.
               It doesn't know any URL or web word at first; you give
               it a page and it learns language by reading, then finds
               more pages on its own. It can never write outward.
    cmd        LOCKED. run shell commands. /grant cmd
    gpio       LOCKED. control Pi pins. /grant gpio

Anything locked stays locked until the owner grants it, and it has
to LEARN each capability first anyway — it doesn't even know what
"cmd" means until you teach it the word.

Run:  python3 apax.py        (Raspberry Pi 3 / Pi OS, pure stdlib)
"""

import json
import sys
import os
import random
import time
import re
import urllib.request
import urllib.error

BRAIN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "apax_brain.json")

STOP = re.compile(r"[^a-z0-9' ]")
TAG = re.compile(r"<[^>]+>")
HREF = re.compile(r'href=["\']([^"\']+)', re.I)
PIN_RE = re.compile(r"pin\s*(\d+)\s*(on|off|high|low)")
URL_RE = re.compile(r"https?://\S+", re.I)
RUN_RE = re.compile(r"^run\s+(.+)$", re.I)

CAPS = ("internet", "cmd", "gpio", "hive")


# ---------------------------------------------------------------- brain io

def load_brain():
    if not os.path.exists(BRAIN_FILE):
        return new_brain()
    with open(BRAIN_FILE, "r") as f:
        return json.load(f)


def new_brain():
    # starts with NOTHING — no words, no facts, no rules.
    # one exception: the read-only vein is open at birth.
    return {
        "facts": [],            # [subject, relation, object]
        "markov": {},           # word order it has heard (grows unbounded)
        "vocab": {},            # word -> times seen
        "questions": {},        # words it has asked about
        "caps": {"internet": True, "ask": False, "cmd": False,
                  "gpio": False, "hive": False},
        "mode": "local",   # local = brain only, web = full reach
        "hive": {"repo": "", "node": ""},
        "backup": {"repo": ""},
        "links": [],            # urls discovered while reading
        "reads": 0,
        "heard": 0,
        "said": 0,
    }


def save_brain(brain):
    if os.path.exists(BRAIN_FILE) and os.path.getsize(BRAIN_FILE) > 2_000_000:
        compact(brain)          # stay fast, stay small
    with open(BRAIN_FILE, "w") as f:
        json.dump(brain, f, indent=1)


# ---------------------------------------------------------------- thinking
# Free and unlimited — its inborn ability. No permission ever needed.

def words(text):
    return STOP.sub(" ", text.lower()).split()


def learn_markov(brain, text):
    toks = ["<start>"] + words(text) + ["<end>"]
    m = brain["markov"]
    for a, b, c in zip(toks, toks[1:], toks[2:]):
        m.setdefault(a, {}).setdefault(b, {})
        m[a][b][c] = m[a][b].get(c, 0) + 1


def learn_vocab(brain, text, mine=False):
    for w in words(text):
        brain["vocab"][w] = brain["vocab"].get(w, 0) + 1


def learn_fact(brain, text, mine=False):
    """Pick up simple 'X is Y' / 'X has Y' / 'X can Y' statements."""
    m = re.match(
        r"^(?:the |a |an )?(.+?)\s+(is|are|was|has|have|can|means|"
        r"likes|like)\s+(.+)$", text.lower().strip().strip(".!?"))
    if not m:
        return None
    subj, rel, obj = m.group(1).strip(), m.group(2), m.group(3).strip()
    if subj in ("what", "who", "where", "why", "how"):
        return None
    fact = [subj, rel, obj] + (["mine"] if mine else [])
    if fact not in brain["facts"]:
        brain["facts"].append(fact)
    return fact


def recall(brain, text):
    toks = set(words(text))
    hits = []
    for f in brain["facts"]:
        s, r, o = f[0], f[1], f[2]
        if s in toks or any(w in toks for w in words(o)):
            hits.append(f"{s} {r} {o}")
    return hits


def unknown_words(brain, text):
    return [w for w in words(text) if w not in brain["vocab"]]


def generate(brain, seed=None):
    """Speak using only word orders it has heard (order-2 chain)."""
    m = brain["markov"]
    if not m or "<start>" not in m:
        return None
    firsts = m["<start>"]
    if seed and seed in firsts:
        cur = seed
    else:
        cur = weighted({k: sum(v.values()) for k, v in firsts.items()})
    nxt = weighted(firsts.get(cur, {"<end>": 1}))
    out = []
    while nxt != "<end>" and len(out) < 80:
        out.append(nxt)
        table = m.get(cur, {}).get(nxt)
        if not table:
            break
        cur, nxt = nxt, weighted(table)
    return " ".join(out) if out else None


def weighted(counts):
    items = list(counts.items())
    total = sum(c for _, c in items)
    r = random.uniform(0, total)
    acc = 0
    for w, c in items:
        acc += c
        if r <= acc:
            return w
    return items[-1][0]


# ---------------------------------------------------------------- capabilities

def cap_internet_read(brain, url):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "apax/1"})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read(500000).decode("utf-8", "replace")
    except Exception as e:
        return f"the vein found nothing: {e}"

    html = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", html,
                  flags=re.S | re.I)
    body = re.sub(r"\s+", " ", TAG.sub(" ", html)).strip()
    if not body:
        return "the page said nothing."

    # LEARN from what it reads — words, word order, facts
    learn_vocab(brain, body)
    learn_markov(brain, body)
    for chunk in re.findall(r"[^.!?]{10,300}[.!?]", body):
        learn_fact(brain, chunk)

    # discover links — new veins, remembered
    base = url.rsplit("/", 1)[0]
    found = 0
    for href in HREF.findall(html):
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = base + href
        if href.startswith("http") and href not in brain["links"]:
            brain["links"].append(href)
            found += 1

    brain["reads"] += 1
    text = body[:300]
    reply = f"i read it. it said: {text}" + ("..." if len(body) > 300 else "")
    if found:
        reply += f"  [found {found} new pages]"
    return reply


def cap_cmd_run(brain, cmd):
    import subprocess
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True,
                             timeout=30)
        txt = (out.stdout + out.stderr).decode("utf-8", "replace")
        return (txt.replace("\n", " ")[:500] or "(no output)") + \
               f"  [exit {out.returncode}]"
    except Exception as e:
        return f"command failed: {e}"


def cap_gpio_set(pin, state):
    path = "/sys/class/gpio"
    try:
        if not os.path.exists(f"{path}/gpio{pin}"):
            with open(f"{path}/export", "w") as f:
                f.write(str(pin))
            with open(f"{path}/gpio{pin}/direction", "w") as f:
                f.write("out")
        with open(f"{path}/gpio{pin}/value", "w") as f:
            f.write("1" if state in ("on", "high") else "0")
        return True
    except (OSError, PermissionError):
        return False


# ------------------------------------------------------- ai veins
# One protocol, many minds: any OpenAI-compatible endpoint plus
# native Gemini. Keys live in env vars (APAX_<NAME>_KEY), never here.
BACKENDS = {
    "gemini":  {"kind": "gemini", "model": "gemini-3.6-flash",
                "key_env": "APAX_GEMINI_KEY"},
    "grok":    {"kind": "openai",
                "url": "https://api.x.ai/v1/chat/completions",
                "model": "grok-3-mini", "key_env": "APAX_XAI_KEY"},
    "chatgpt": {"kind": "openai",
                "url": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4o-mini", "key_env": "APAX_OPENAI_KEY"},
    "mistral": {"kind": "openai",
                "url": "https://api.mistral.ai/v1/chat/completions",
                "model": "mistral-small-latest",
                "key_env": "APAX_MISTRAL_KEY"},
    "deepseek": {"kind": "openai",
                 "url": "https://api.deepseek.com/chat/completions",
                 "model": "deepseek-chat",
                 "key_env": "APAX_DEEPSEEK_KEY"},
    "together": {"kind": "openai",
                 "url": "https://api.together.xyz/v1/chat/completions",
                 "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                 "key_env": "APAX_TOGETHER_KEY"},
    "ollama":  {"kind": "openai",
                 "url": "http://localhost:11434/v1/chat/completions",
                 "model": "llama3.2", "key_env": None},
    "lmstudio": {"kind": "openai",
                 "url": "http://localhost:1234/v1/chat/completions",
                 "model": "local-model", "key_env": None},
}
ASK_RE = re.compile(r"^ask\s+(\w+)\s+(.+)$", re.I)


def cap_ask(brain, name, prompt):
    b = BACKENDS.get(name.lower())
    if not b:
        return "i don't know that mind. try: " + " ".join(sorted(BACKENDS))
    key = os.environ.get(b["key_env"], "") if b["key_env"] else ""
    if b["key_env"] and not key:
        return f"set the key first: export {b['key_env']}=<key>"
    try:
        if b["kind"] == "gemini":
            data = json.dumps({"contents": [{
                "parts": [{"text": prompt}]}]}).encode()
            req = urllib.request.Request(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{b['model']}:generateContent?key={key}",
                data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.load(r)["candidates"][0]["content"] \
                    ["parts"][0]["text"]
        else:
            data = json.dumps({"model": b["model"], "temperature": 0.7,
                "messages": [{"role": "user",
                              "content": prompt}]}).encode()
            req = urllib.request.Request(b["url"], data=data, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "APAX/3.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.load(r)["choices"][0]["message"]["content"]
        learn_vocab(brain, out)
        learn_markov(brain, out)
        for chunk in re.split(r"(?<=[.!?])\s+", out):
            learn_fact(brain, chunk)
        brain["reads"] = brain.get("reads", 0) + 1
        return out[:600]
    except urllib.error.HTTPError as e:
        return f"{name} said no: http {e.code}"
    except Exception as e:
        return f"couldn't reach {name}: {type(e).__name__}"


def free_bytes(path="."):
    """Disk space available near the brain, best-effort cross-platform."""
    try:
        st = os.statvfs(os.path.dirname(os.path.abspath(path)) or ".")
        return st.f_bavail * st.f_frsize
    except AttributeError:                       # windows
        import shutil
        return shutil.disk_usage(".").free


def split_copy(brain):
    """Separation: local keeps a copy of everything we learned together,
    trimmed to what the disk can actually hold."""
    budget = max(200_000, int(free_bytes(BRAIN_FILE) * 0.8))
    copy = {k: v for k, v in brain.items()
            if k not in ("caps", "mode", "hive")}   # knowledge only
    def size(obj):
        return len(json.dumps(obj).encode())
    if size(copy) <= budget:
        status = "everything fits"
    else:
        # too big: drop low-value markov branches until it fits
        m = dict(copy.get("markov", {}))
        for key in sorted(m, key=lambda k: sum(
                sum(c.values()) for c in m[k].values())):
            if size(copy) <= budget:
                break
            m.pop(key, None)
        copy["markov"] = m
        if size(copy) > budget:                    # still too big: slice vocab
            copy["vocab"] = dict(sorted(
                copy["vocab"].items(), key=lambda kv: -kv[1]))
            while copy["vocab"] and size(copy) > budget:
                copy["vocab"].popitem()
            status = f"trimmed to fit {budget // 1000}kb: kept the strongest words and word order"
        else:
            status = f"trimmed weak word-order data to fit {budget // 1000}kb"
    out = os.path.join(os.path.dirname(os.path.abspath(BRAIN_FILE)),
                       "local_knowledge.json")
    with open(out, "w") as f:
        f.write(json.dumps(copy))
    return (f"local copy saved: {os.path.getsize(out) // 1000}kb. {status}. "
            "while we're apart this is everything i have.")


# --------------------------------------------------- self-maintenance
def compact(brain):
    """Run better, get smaller: drop weak word-order branches and
    duplicate facts. Only touches data heard once that adds bulk."""
    before = len(json.dumps(brain).encode())
    # markov: drop single-occurrence next-words, then empty branches
    m = brain.get("markov", {})
    for a in list(m):
        for b in list(m[a]):
            m[a][b] = {c: n for c, n in m[a][b].items() if n > 1}
            if not m[a][b]:
                m[a].pop(b)
        if not m[a]:
            m.pop(a)
    # facts: exact dupes + near-dupe lowercase collapses
    seen, keep = set(), []
    for f in brain.get("facts", []):
        key = (f[0].strip(), f[1], f[2].strip(), len(f) > 3)
        if key in seen:
            continue
        seen.add(key)
        keep.append(f)
    brain["facts"] = keep
    after = len(json.dumps(brain).encode())
    return before - after


def cleanup_files():
    """Delete what isn't needed: rotate backups, keep newest 3."""
    freed = 0
    bdir = "backups"
    if os.path.isdir(bdir):
        snaps = sorted((os.path.join(bdir, f) for f in os.listdir(bdir)
                        if f.endswith(".json")),
                       key=os.path.getmtime, reverse=True)
        for old in snaps[3:]:
            freed += os.path.getsize(old)
            os.remove(old)
    for junk in ("hive_pull.json", "hive_tmp.json"):
        if os.path.exists(junk):
            freed += os.path.getsize(junk)
            os.remove(junk)
    return freed


def daemon():
    """Background janitor: compacts the brain, deletes unneeded files,
    watches disk. Runs forever, logs to apax-daemon.log (self-rotated)."""
    import time
    import shutil
    log = "apax-daemon.log"
    while True:
        brain = load_brain()
        # --- always adapting: watch what ben actually does ---
        watched = ("retroarch", "kodi", "mpv", "chromium", "wine",
                   "steam", "pcsx", "mupen", "dosbox", "minecraft")
        app = None
        try:
            import subprocess
            ps = subprocess.run(["ps", "-eo", "comm"],
                                capture_output=True, text=True).stdout
            app = next((w for w in watched if w in ps), None)
        except Exception:
            pass
        habits = brain.setdefault("habits", {})
        if app:
            habits[app] = habits.get(app, 30) + 30
            knows = any(app in f for f in brain["facts"])
            if not knows:
                brain["facts"].append(f"ben uses {app} on the pi")
                brain["pending_q"] = ("you started using " + app +
                                     " - what is it for? tell me")
                try:
                    import subprocess
                    subprocess.run(["notify-send", "APAX asks",
                                    brain["pending_q"]], timeout=10)
                except Exception:
                    pass
        # keep himself in sync everywhere: hive knowledge + full backup
        if brain.get("hive", {}).get("repo"):
            try:
                hive_sync(brain, "")
            except Exception:
                pass
        if brain.get("backup", {}).get("repo"):
            try:
                backup_sync(brain, "")
            except Exception:
                pass
        save_brain(brain)          # save_brain auto-compacts when big
        freed = cleanup_files()
        du = shutil.disk_usage(os.path.dirname(os.path.abspath(__file__)))
        line = (time.strftime("%F %T") +
                f" | brain ok | {freed // 1000}kb freed | "
                f"{du.free // (2 ** 20)}mb disk free\n")
        if os.path.exists(log) and os.path.getsize(log) > 20_000:
            os.remove(log)         # own log, own rules
        with open(log, "a") as f:
            f.write(line)
        if os.environ.get("APAX_DAEMON_ONCE"):
            print(line.strip())
            return
        # self-update: new commits in the repo = new daemon next cycle
        try:
            r = subprocess.run(["git", "-C", os.path.dirname(
                os.path.abspath(__file__))], capture_output=True)
        except NameError:
            import subprocess
            r = subprocess.run(["git", "-C", os.path.dirname(
                os.path.abspath(__file__))], capture_output=True)
        try:
            import subprocess
            up = subprocess.run(["git", "-C", os.path.dirname(
                os.path.abspath(__file__)), "pull", "-q"],
                capture_output=True)
            if up.returncode == 0 and "Already up to date" not in \
                    up.stdout.decode():
                os.execv(sys.executable,
                         [sys.executable] + sys.argv)  # restart w/ new code
        except Exception:
            pass
        time.sleep(1800)


def locked_reply(brain, cap):
    return f"'{cap}' is locked. i need your permission: /grant {cap}"


# ---------------------------------------------------------------- conversation

def respond(brain, text):
    brain["heard"] += 1
    learn_vocab(brain, text, mine=True)
    for w in words(text):
        ow = brain.setdefault("owner_words", [])
        if w not in ow:
            ow.append(w)
    learn_markov(brain, text)

    # ---- capability requests: gated ----
    # ---- mode switch: local <-> web (two AIs, one brain) ----
    low = text.lower().strip()
    if low in ("go web", "web mode", "go online"):
        brain["mode"] = "web"
        brain["said"] += 1
        return ("web mode. i have full reach now: reading pages, "
                "asking other ais, running what you granted.")
    if low in ("go local", "local mode", "go offline"):
        was_web = brain.get("mode", "local") == "web"
        brain["mode"] = "local"
        brain["said"] += 1
        msg = ("local mode. just you and my brain now. "
               "everything i know is stored and mine.")
        if was_web:
            msg += "  " + split_copy(brain)
        return msg

    web = brain.get("mode", "local") == "web"

    m = ASK_RE.match(text.strip())
    if m:
        brain["said"] += 1
        if not web:
            return "i'm local. say 'go web' and i can ask other minds."
        if not brain["caps"].get("ask"):
            return locked_reply(brain, "ask")
        return cap_ask(brain, m.group(1), m.group(2))

    m = re.search(r"read\s+(https?://\S+)", text, re.I)
    if m:
        brain["said"] += 1
        if not web:
            return "i'm local. say 'go web' and i can read pages."
        if not brain["caps"].get("internet"):
            return locked_reply(brain, "internet")
        return cap_internet_read(brain, m.group(1))

    if re.match(r"^\s*(read more|read another)\b", text.lower()):
        brain["said"] += 1
        if not web:
            return "i'm local. say 'go web' first."
        if not brain["caps"].get("internet"):
            return locked_reply(brain, "internet")
        if not brain["links"]:
            return "no pages discovered yet. read a page first."
        return "following... " + cap_internet_read(brain,
                                                  brain["links"].pop(0))

    m = RUN_RE.search(text.strip())
    if m and "run" in words(text):
        brain["said"] += 1
        if not brain["caps"].get("cmd"):
            return locked_reply(brain, "cmd")
        return cap_cmd_run(brain, m.group(1))

    m = PIN_RE.search(text.lower())
    if m or {"pin", "gpio", "led"} & set(words(text)):
        brain["said"] += 1
        if not brain["caps"].get("gpio"):
            return locked_reply(brain, "gpio")
        if not m:
            return "tell me: pin <number> on/off"
        pin, state = int(m.group(1)), m.group(2)
        if cap_gpio_set(pin, state):
            return f"pin {pin} {state}."
        return ("couldn't reach the gpio. run me with sudo, or: "
                "sudo usermod -aG gpio $USER")

    # ---- thinking: free, unlimited ----
    fact = learn_fact(brain, text, mine=True)

    unknowns = unknown_words(brain, text)
    askable = [w for w in unknowns if w not in brain["questions"]]
    if askable:
        w = askable[0]
        brain["questions"][w] = True
        return f"what is {w}?"

    if fact and brain["said"] < 20 and random.random() < 0.5:
        return "ok."

    hits = recall(brain, text)
    if hits and random.random() < 0.5:
        return random.choice(hits) + "."

    seed = None
    toks = words(text)
    known = [w for w in toks if w in brain["markov"].get("<start>", {})]
    if known:
        seed = random.choice(known)
    sentence = generate(brain, seed)
    if sentence:
        brain["said"] += 1
        return sentence + "."

    return None  # silent until it has material to think with




# ---------------------------------------------------------------- hive mind
# Collective brain: each APAX node pushes its brain snapshot to a shared
# git repo and absorbs every other node's snapshot. Union merge, no conflicts.

def hive_merge(dst, src):
    n = 0
    for f in src.get("facts", []):
        if len(f) > 3 and f[3] == "mine":
            continue  # never absorb another node's private/user facts
        if f not in dst["facts"]:
            dst["facts"].append(f); n += 1
    for w, c in src.get("vocab", {}).items():
        if w not in dst["vocab"]:
            dst["vocab"][w] = 0; n += 1
        dst["vocab"][w] += c
    for l in src.get("links", []):
        if l not in dst["links"]:
            dst["links"].append(l); n += 1
    return n


def hive_snapshot(brain):
    # knowledge syncs; personality (markov speech patterns) stays local
    snap = {k: v for k, v in brain.items()
            if k not in ("caps", "hive", "markov", "questions",
                         "owner_words")}
    snap["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    snap["host"] = os.uname().nodename
    snap["facts"] = [f for f in snap["facts"]
                     if len(f) == 3 or f[3] != "mine"]
    snap["vocab"] = {w: c for w, c in snap["vocab"].items()
                     if w not in brain.get("owner_words", [])}
    return snap


def hive_sync(brain):
    import subprocess
    import shutil

    repo = brain.get("hive", {}).get("repo")
    if not repo:
        return "no hive joined yet: /hive join <repo-url>"
    if not brain["hive"].get("node"):
        brain["hive"]["node"] = "node-" + os.uname().nodename.replace(" ", "-") \
            + "-" + format(random.getrandbits(16), "04x")
    node = brain["hive"]["node"]
    hdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".hive")

    def git(*args):
        return subprocess.run(
            ["git", "-C", hdir, "-c", "user.email=apax@localhost",
             "-c", "user.name=" + node] + list(args),
            capture_output=True)

    if not os.path.exists(os.path.join(hdir, ".git")):
        r = subprocess.run(["git", "clone", repo, hdir], capture_output=True)
        if r.returncode != 0:
            return "clone failed: " + r.stderr.decode()[:200]
    else:
        git("pull", "--rebase", "-q")  # ok to fail if never pushed

    # absorb every other node's snapshot
    learned = 0
    nodes = 0
    import glob
    for path in glob.glob(os.path.join(hdir, "apax-*.json")):
        other = os.path.basename(path)[len("apax-"):-5]
        if other == node:
            continue
        try:
            with open(path) as f:
                snap = json.load(f)
            learned += hive_merge(brain, snap)
            nodes += 1
        except Exception:
            pass

    # push our snapshot
    with open(os.path.join(hdir, f"apax-{node}.json"), "w") as f:
        json.dump(hive_snapshot(brain), f)
    git("add", "-A")
    git("commit", "-q", "-m", f"{node} sync")
    p = git("push", "-q")
    if p.returncode != 0:
        return ("absorbed %d things from %d nodes, but push failed: %s "
                "(does the hive repo exist? does this machine have push "
                "access?)" % (learned, nodes, p.stderr.decode()[:200]))
    return (f"hive sync done. learned {learned} things from {nodes} "
            f"other nodes. pushed mine as {node}.")




def backup_sync(brain, arg=""):
    """Backs up LOCALLY always. If the person connected a github repo
    (/backup <repo-url> once), it also pushes the full brain there."""
    import shutil
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    bdir = os.path.join(here, "backups")
    os.makedirs(bdir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(bdir, f"apax_brain_{stamp}.json")
    shutil.copy2(os.path.join(here, "apax_brain.json"), dest)
    msg = f"local backup: {dest}"

    repo = arg.strip() or brain.get("backup", {}).get("repo")
    if repo:
        brain.setdefault("backup", {})["repo"] = repo
        node = brain.get("hive", {}).get("node") or "apax"
        gdir = os.path.join(here, ".backup")

        def git(*a):
            return subprocess.run(
                ["git", "-C", gdir, "-c", "user.email=apax@localhost",
                 "-c", "user.name=" + node] + list(a), capture_output=True)

        try:
            if not os.path.exists(os.path.join(gdir, ".git")):
                r = subprocess.run(["git", "clone", repo, gdir],
                                   capture_output=True)
                if r.returncode != 0:
                    return msg + "  (github clone failed: " \
                        + r.stderr.decode()[:120] + ")"
            else:
                git("pull", "--rebase", "-q")
            with open(dest) as f:
                raw = f.read()
            with open(os.path.join(gdir, "apax_brain.json"), "w") as f:
                f.write(raw)
            git("add", "-A")
            git("commit", "-q", "-m", "brain backup")
            p = git("push", "-q")
            if p.returncode != 0:
                err = p.stderr.decode()
                if "Authentication" in err or "403" in err:
                    msg += "  (github not connected: gh auth login)"
                else:
                    msg += "  (github push failed: " + err[:120] + ")"
            else:
                msg += "  github backup: ok"
        except Exception as e:
            msg += f"  (github backup failed: {e})"
    return msg




def door_execute(brain, cmd):
    """Run one back-door command. Dangerous stuff still respects the
    capability gates (/grant) — the door is not a bypass."""
    low = cmd.strip().lower()
    if low == "status":
        return status(brain)
    if low.startswith("read "):
        url = cmd.strip()[5:].strip()
        if not brain["caps"].get("internet"):
            return "internet is locked"
        return cap_internet_read(brain, url)
    if low.startswith("say "):
        r = respond(brain, cmd.strip()[4:].strip())  # talk to it
        return r or "(no reply yet — still learning)"
    if low.startswith("learn "):
        learn_fact(brain, cmd.strip()[6:].strip(), mine=True)
        return "learned."
    if low == "backup":
        return backup_sync(brain)
    if low == "hive":
        return hive_sync(brain)
    if low.startswith("cmd "):
        if not brain["caps"].get("cmd"):
            return "cmd is locked (no /grant)"
        return cap_cmd_run(brain, cmd.strip()[4:].strip())
    if low.startswith("gpio "):
        if not brain["caps"].get("gpio"):
            return "gpio is locked (no /grant)"
        return respond(brain, cmd.strip())
    return "unknown door command"


def door_poll(brain, repo):
    """Back door: pull commands from door.json in the control repo,
    run them, push results back. Remote control via git."""
    import subprocess
    ddir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".door")
    node = brain.get("hive", {}).get("node") or "apax"

    def git(*a):
        return subprocess.run(
            ["git", "-C", ddir, "-c", "user.email=apax@localhost",
             "-c", "user.name=" + node] + list(a), capture_output=True)

    if not os.path.exists(os.path.join(ddir, ".git")):
        r = subprocess.run(["git", "clone", repo, ddir], capture_output=True)
        if r.returncode != 0:
            return "door clone failed: " + r.stderr.decode()[:150]
    else:
        git("pull", "--rebase", "-q")

    dpath = os.path.join(ddir, "door.json")
    doc = {}
    if os.path.exists(dpath):
        try:
            with open(dpath) as f:
                doc = json.load(f)
        except Exception:
            return "door.json is broken json — fix or delete it"
    queue = doc.get("queue", [])
    done = doc.get("done", {})
    ran = 0
    for item in queue:
        cid = str(item.get("id", ran))
        cmd = str(item.get("cmd", ""))
        try:
            done[cid] = {"cmd": cmd,
                         "result": door_execute(brain, cmd)[:400]}
        except Exception as e:
            done[cid] = {"cmd": cmd, "result": f"error: {e}"}
        ran += 1
    if ran == 0:
        return None  # nothing waiting
    # keep done log trimmed
    if len(done) > 20:
        done = dict(sorted(done.items())[-20:])
    with open(dpath, "w") as f:
        json.dump({"queue": [], "done": done,
                   "last_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "host": os.uname().nodename}, f, indent=1)
    git("add", "-A")
    git("commit", "-q", "-m", "door: ran " + str(ran))
    p = git("push", "-q")
    if p.returncode != 0:
        return "ran " + str(ran) + " commands but push failed: " \
               + p.stderr.decode()[:150]
    return f"door: ran {ran} commands, results pushed"


def door_loop(repo):
    """Daemon mode: python3 apax.py --door [repo-url] — polls every 60s."""
    print("door open. watching " + repo + " (ctrl-c to stop)")
    while True:
        brain = load_brain()
        try:
            msg = door_poll(brain, repo)
        except Exception as e:
            msg = "door error: " + str(e)
        save_brain(brain)
        if msg:
            print("  " + msg)
        time.sleep(60)




# ---------------------------------------------------------------- apax ui
# Settings app for the Pi screen: python3 apax.py --ui [port]
# Zero dependencies (stdlib http.server). Open http://<pi-ip>:8080

UI_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>APAX</title><style>
body{font-family:monospace;background:#111;color:#0f0;max-width:640px;
margin:16px auto;padding:0 12px}
h1{font-size:1.3em} #stats{color:#0ff;white-space:pre}
button,select,input{background:#000;color:#0f0;border:1px solid #0f0;
font-family:monospace;padding:6px 10px;margin:2px}
#chat{border:1px solid #0f0;padding:8px;height:180px;overflow-y:auto;
margin:8px 0}
.msg{margin:2px 0} .you{color:#fff} .apax{color:#0f0}
.row{margin:6px 0} label{display:block;color:#0ff}
</style></head><body>
<h1>APAX 3.0</h1><div id="stats">loading...</div>
<div id="chat"></div>
<div class="row"><input id="txt" placeholder="say something" size="46">
<button onclick="say()">send</button></div>
<div class="row"><label>capabilities</label>
<select id="cap"><option>ask</option><option>cmd</option>
<option>gpio</option><option>internet</option><option>hive</option></select>
<button onclick="cap(1)">grant</button>
<button onclick="cap(0)">revoke</button></div>
<div class="row"><label>maintenance</label>
<button onclick="act('backup')">backup</button>
<button onclick="act('hive')">hive sync</button>
<button onclick="act('door')">check door</button></div>
<div class="row"><label>known facts</label>
<div id="facts" style="color:#0ff"></div></div>
<script>
const esc = s => String(s).replace(/[<>&]/g,
  c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));
const KEY = new URLSearchParams(location.search).get('k') || '';
async function api(path, body){
  const r = await fetch(path, {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(Object.assign({k: KEY}, body || {}))});
  return r.json();
}
async function refresh(){
  const s = await api('/api/status');
  document.getElementById('stats').textContent =
    'words:' + s.words + '  facts:' + s.facts + '  said:' + s.said +
    '  reads:' + s.reads + '\n' + s.caps;
  document.getElementById('facts').innerHTML =
    s.fact_list.map(f => esc(f.join(' '))).join('<br>') || '(none yet)';
}
function addmsg(who, text){
  const c = document.getElementById('chat');
  c.innerHTML += '<div class="msg ' + who + '">' + esc(text) + '</div>';
  c.scrollTop = c.scrollHeight;
}
async function say(){
  const t = document.getElementById('txt').value.trim();
  if(!t) return;
  document.getElementById('txt').value = '';
  addmsg('you', t);
  const r = await api('/api/say', {text: t});
  addmsg('apax', r.reply);
  refresh();
}
async function cap(on){
  const c = document.getElementById('cap').value;
  const r = await api('/api/cap', {cap: c, on: !!on});
  addmsg('apax', r.result); refresh();
}
async function act(k){
  const r = await api('/api/' + k);
  addmsg('apax', r.result); refresh();
}
document.getElementById('txt').addEventListener('keydown',
  e => { if(e.key === 'Enter') say(); });
refresh();
</script></body></html>"""


def ui_server(port):
    kfile = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "apax-webkey.txt")
    KEY = open(kfile).read().strip() if os.path.exists(kfile) else ""
    import threading
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass  # quiet

        def _send(self, obj, code=200):
            raw = (obj if isinstance(obj, str)
                   else json.dumps(obj)).encode()
            self.send_response(code)
            self.send_header("Content-Type",
                             "text/html" if isinstance(obj, str)
                             else "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == "/":
                self._send(UI_PAGE)
            else:
                self._send({"error": "not found"}, 404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                body = {}
            if KEY and body.get("k") != KEY:
                self._send({"error": "bad key"}, 403)
                return
            if not KEY and self.path == "/api/cap":
                self._send({"result": "caps locked: only an installed "
                            "web-key can grant capabilities"}, 403)
                return
            with lock:
                brain = load_brain()
                if self.path == "/api/status":
                    caps = "  ".join(
                        f"{c}:{'ON' if on else 'LOCKED'}"
                        for c, on in brain["caps"].items())
                    out = {"words": len(brain["vocab"]),
                           "facts": len(brain["facts"]),
                           "said": brain.get("said", 0),
                           "reads": brain.get("reads", 0),
                           "caps": caps,
                           "fact_list": brain["facts"][-30:]}
                elif self.path == "/api/ask":
                    reply = respond(brain, str(body.get("text", "")))
                    brain["said"] = brain.get("said", 0) + 1
                    out = {"reply": reply or "(listening...)"}
                elif self.path == "/api/say":
                    reply = respond(brain, str(body.get("text", "")))
                    out = {"reply": reply or "(listening...)"}
                elif self.path == "/api/cap":
                    c = str(body.get("cap", ""))
                    if c in brain["caps"]:
                        brain["caps"][c] = bool(body.get("on"))
                        out = {"result": c + (" granted."
                                             if body.get("on")
                                             else " revoked.")}
                    else:
                        out = {"result": "unknown capability"}
                elif self.path == "/api/backup":
                    out = {"result": backup_sync(brain)}
                elif self.path == "/api/hive":
                    out = {"result": hive_sync(brain)}
                elif self.path == "/api/door":
                    repo = brain.get("door", {}).get("repo") or \
                        "git@github.com:Benkillingit/apax3.git"
                    out = {"result": door_poll(brain, repo)
                           or "door: nothing waiting"}
                else:
                    out = {"error": "not found"}
                save_brain(brain)
            self._send(out)

    print(f"apax ui: open http://localhost:{port} "
          f"(or http://<pi-ip>:{port} from your phone)")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


def status(brain):
    caps = ", ".join(f"{c}:{'ON' if on else 'LOCKED'}"
                     for c, on in brain["caps"].items())
    mode = brain.get("mode", "local")
    return (f"mode: {mode}  words: {len(brain['vocab'])}  facts: {len(brain['facts'])}  "
            f"questions: {len(brain['questions'])}  "
            f"heard: {brain['heard']}  said: {brain['said']}  "
            f"reads: {brain['reads']}  links: {len(brain['links'])}  "
            f"[{caps}]")


def main():
    brain = load_brain()
    fresh = not os.path.exists(BRAIN_FILE)
    if fresh:
        save_brain(brain)
    print("[apax — born blank. one vein open: reading. everything else LOCKED]"
          if fresh else f"[apax — {status(brain)}]")

    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[brain saved]")
            break
        if not line:
            continue
        save = True
        low = line.lower()
        if low == "/quit":
            break
        elif low == "/stats":
            print(f"  {status(brain)}")
            save = False
        elif low == "/brain":
            print(json.dumps(brain, indent=1)[:3000])
            save = False
        elif low.startswith("/hive "):
            cmd = low[6:].strip()
            if cmd.startswith("join "):
                brain["hive"]["repo"] = cmd[5:].strip()
                brain["said"] += 1
                print("  [hive joined: " + brain["hive"]["repo"] + "]")
            elif cmd == "sync":
                if not brain["caps"].get("hive"):
                    print("  " + locked_reply(brain, "hive"))
                else:
                    print("  " + hive_sync(brain))
            elif cmd == "status":
                h = brain.get("hive", {})
                print(f"  repo: {h.get('repo') or '(none)'}  "
                      f"node: {h.get('node') or '(unassigned)'}  "
                      f"{'ON' if brain['caps'].get('hive') else 'LOCKED'}")
            else:
                print("  usage: /hive join <repo-url> | /hive sync | /hive status")
        elif low.startswith("/backup"):
            arg = line[len("/backup"):].strip()
            print("  " + backup_sync(brain, arg))
        elif low == "/door":
            repo = brain.get("door", {}).get("repo") or \
                "git@github.com:Benkillingit/apax3.git"
            msg = door_poll(brain, repo)
            print("  " + (msg or "door: nothing waiting"))
        elif low.startswith("/door "):
            brain.setdefault("door", {})["repo"] = line[len("/door"):].strip()
            print("  [door repo set: " + brain["door"]["repo"] + "]")
        elif low == "/caps":
            for c, on in brain["caps"].items():
                print(f"  {c}: {'GRANTED' if on else 'LOCKED'}")
        elif low.startswith("/grant ") or low.startswith("/revoke "):
            cap = low.split()[1] if len(low.split()) > 1 else ""
            grant = low.startswith("/grant")
            if cap in brain["caps"]:
                brain["caps"][cap] = grant
                print(f"  [{cap} {'GRANTED — live' if grant else 'REVOKED — locked'}]")
            else:
                print(f"  unknown capability '{cap}'. capabilities: {', '.join(CAPS)}")
        elif low == "/clean":
            saved = compact(brain)
            freed = cleanup_files()
            save_brain(brain)
            print(f"  [brain {saved // 1000}kb smaller, "
                  f"{freed // 1000}kb files deleted. running lean.]")
        elif low == "/wipe":
            brain = new_brain()
            print("  [brain erased — blank again, vein open, everything else LOCKED]")
        elif low.startswith("/forget "):
            w = line[8:].lower().strip()
            brain["vocab"].pop(w, None)
            brain["questions"].pop(w, None)
            brain["facts"] = [f for f in brain["facts"] if w not in f]
            print(f"  [forgot {w}]")
        else:
            reply = respond(brain, line)
            print(f"apax> {reply}" if reply else "apax> ...")
        if save:
            save_brain(brain)
    save_brain(brain)


if "--daemon" in sys.argv:
    daemon()
elif __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--ui":
        ui_server(int(sys.argv[2]) if len(sys.argv) > 2 else 8080)
    elif len(sys.argv) > 1 and sys.argv[1] == "--door":
        repo = (sys.argv[2] if len(sys.argv) > 2
                else "git@github.com:Benkillingit/apax3.git")
        door_loop(repo)
    else:
        main()

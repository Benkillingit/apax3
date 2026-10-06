# APAX 3.0

A blank-slate AI that starts with nothing.

No model. No rules. No seed text. No vocabulary. Nothing is baked in
except the ability to **think**: notice, ask, remember, imitate.

Born with one power: a read-only vein to the internet. Hand it a URL
and it learns language from the page, then discovers new pages on its
own. It can never write outward.

Everything else — shell commands (`cmd`), GPIO pins (`gpio`) — is
**locked** until the owner grants it. It has to learn each capability
first anyway: it doesn't even know what "cmd" means until you teach
it the word.

Runs on a Raspberry Pi 3. Pure Python 3 standard library — no pip,
no compile, no dependencies.

## Install & run

```bash
git clone https://github.com/Benkillingit/apax3.git
cd apax3
python3 apax.py
```

Or grab just the one file:

```bash
curl -fsSL https://raw.githubusercontent.com/Benkillingit/apax3/main/apax.py -o apax.py
python3 apax.py
```

## First boot

```
[apax — born blank. one vein open: reading. everything else LOCKED]
you> hello
apax> ...
```

It stays silent until it has material. Teach it:

```
you> read https://en.wikipedia.org/wiki/Raspberry_Pi
apax> i read it. it said: ...
you> read more
you> a dog is an animal
apax> ok.
```

## Commands

| Command | What it does |
|---|---|
| `read <url>` | read a page, learn from it, collect its links |
| `read more` | follow the next link it discovered |
| `/grant cmd` | unlock shell commands (owner only) |
| `/grant gpio` | unlock Pi pin control (owner only) |
| `/revoke <cap>` | lock a capability back |
| `/caps` | show what's locked/unlocked |
| `/stats` | brain stats |
| `/brain` | dump its whole brain (JSON) |
| `/forget <word>` | erase one thing it learned |
| `/wipe` | erase everything — born blank again |
| `/exit` | quit (brain saves automatically) |

## GPIO on a Pi

```bash
sudo usermod -aG gpio $USER   # then re-login
/grant gpio
gpio pin 17 on
```

The brain is one JSON file (`apax_brain.json`) next to the script.
Back it up and your AI moves to any machine.

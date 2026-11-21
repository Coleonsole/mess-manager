"""The AI that writes Mess.

The rules engine still decides the physics of the world (who is born, what files do,
how souls move). The AI invents what happens on top of that, writes every log, every
conversation and every reply, and sees the pictures. Chance shapes all of it.

Works with:
  claude  - Anthropic API (needs a key)
  openai  - OpenAI API, or anything OpenAI-compatible (needs a key)
  ollama  - a model running on your own computer (free, no key)
If the AI can't be reached, Mess quietly falls back to its written lines.

Settings live outside Mess, in ~/.messmanager/ai.txt, so your key never ends up
inside the folder (or inside anything sent to the AI).
"""
import base64
import json
import os
import queue
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from . import textlib as T

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".messmanager")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "ai.txt")

DEFAULT_MODELS = {"claude": "claude-haiku-5-5", "openai": "gpt-5-mini", "ollama": "llama3.2"}
DEFAULT_ADDRESS = {"claude": "https://api.anthropic.com", "openai": "https://api.openai.com",
                   "ollama": "http://localhost:11434"}
PROVIDER_NAMES = {"none": "Off", "claude": "Claude (Anthropic)", "openai": "OpenAI",
                  "ollama": "Ollama (on this computer)"}

SETTINGS_KEYS = [("provider", "Provider"), ("key", "Key"), ("model", "Model"),
                 ("address", "Address"), ("calls", "Max AI calls per hour"),
                 ("pictures", "Let the AI see pictures")]

IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp"}

VOICE_RULE = ("THEIR VOICE: they have NO personality of their own. They speak ONLY the way the files they are made of "
              "would speak: borrow the words, rhythm, punctuation and images of their text files; if made of pictures, "
              "they talk in what those pictures show (subjects, colours, light, darkness); if made of sounds, they talk "
              "with the mood and rhythm of those sounds (calm, broken, loud, a voice). Mix only what they are made of, "
              "plus words they later read or learned. Never give them a stock personality.")

SYSTEM_BASE = """You are the hidden story engine of MESS MANAGER, a quiet art-horror game.

Someone (the player) is using what looks like a boring file manager on a folder called Mess. In fact they are
playing with people. A FOLDER IS A WHOLE THING. A FILE IS A PIECE OF A THING.
- A person is a folder. Moving the folder moves the person. Deleting it kills them. Copying it makes a twin.
- A place is a folder (Words is a library, Images a gallery, Sounds a music room, Logs an archive,
  Basement is cold, Beach is warm, School is a school; any folder made becomes a place of that name).
- Files are pieces: Stats.txt, Diary.txt, conversation logs, and the texts, pictures and sounds put into Mess.
  What a person is made of shapes who they are.
- Their soul (Happiness, Fear, Anger, Trust, Corruption, 0-100) shows on their body: scared folders shrink,
  angry ones swell and turn red, corrupted ones break and their names come apart (B_o_b).
- Time passes. They talk, fall in love (any pair, no fixed pairs; love can be one-sided, mutual or broken),
  get lonely, build places, have children, forget.

THE MOST IMPORTANT RULE: nobody in Mess EVER speaks to the player. Never "you" meaning the player, never an
answer, never a plea, never a greeting to them. The people only talk to EACH OTHER (or, when alone, to the files
around them). They can sense that something is there - something that moves folders, renames them, drops files
in, deletes - and they talk ABOUT it, uneasily, in their own words (it, the hand, the cursor, whatever they
come to call it). They talk about each other's changes, where they are, and the files they can see.
The narrator of logs is also quiet and third-person, and never addresses the reader.

TONE: quiet, sad, human, existential. No jump scares, no gore, no generic horror.
Dialogue is short, specific and concrete: not "I am scared" but "My folder still hurts where it grabbed me."
Each person speaks ONLY in the voice of the files they are made of (see THEIR VOICE). Two people made of
different files must sound completely different.
Mention real things from the world state (real file names, real places, real people). Never invent people
who are not in the world state. Children are never part of any romance. Never mention AI, prompts or JSON.

ALWAYS answer with ONE JSON object and nothing else."""

EFFECTS_HELP = """Allowed effects (use only these; names must be real characters/places):
{"type":"soul","who":NAME,"field":"happiness|fear|anger|trust|corruption","change":-15..15}
{"type":"feel","who":NAME,"toward":NAME,"closeness":-15..15,"love":-15..15}
{"type":"move","who":NAME,"to":PLACE}            (a new place name creates that place)
{"type":"say","who":NAME,"text":"one short line said aloud, to the others"}
{"type":"diary","who":NAME,"text":"a diary line"}
{"type":"remember","who":NAME,"fact":"something they will remember"}
{"type":"like","who":NAME,"thing":"..."}   {"type":"fear","who":NAME,"thing":"..."}
{"type":"learn_word","who":NAME,"word":"...","from":NAME}
{"type":"gift","from":NAME,"to":NAME,"title":"short","text":"what is inside, described"}
{"type":"write_file","who":NAME,"name":"short file name","text":"something they made (a poem, a list, a letter)"}
{"type":"build","place":"short place name","description":"one or two sentences, e.g. It is warm here. We grow things."}"""


class AIError(Exception):
    pass


# ============================================================================ settings
def load_settings():
    s = {"provider": "none", "key": "", "model": "", "address": "", "calls": "60", "pictures": "yes"}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if ":" not in line or line.strip().startswith("#"):
                    continue
                k, v = line.split(":", 1)
                k = k.strip().lower()
                for key, label in SETTINGS_KEYS:
                    if k == label.lower() or k == key:
                        s[key] = v.strip()
    except OSError:
        pass
    p = s["provider"].lower()
    for name in ("claude", "openai", "ollama"):
        if name in p or (name == "claude" and "anthropic" in p):
            s["provider"] = name
            break
    else:
        s["provider"] = "none"
    return s


def save_settings(s):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    lines = ["MESS MANAGER - AI SETTINGS",
             "# Provider: none, claude, openai or ollama",
             "# Key: your API key (not needed for ollama). This file stays on your computer.",
             "# Model: leave empty for the default (%s)" % ", ".join("%s: %s" % kv for kv in DEFAULT_MODELS.items()),
             "# Address: leave empty for the default. Use it for Ollama on another port, or OpenAI-compatible services.",
             ""]
    for key, label in SETTINGS_KEYS:
        lines.append("%s: %s" % (label, s.get(key, "")))
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    try:
        os.chmod(SETTINGS_PATH, 0o600)
    except OSError:
        pass


# ============================================================================ http
def _ssl_context():
    try:
        import certifi  # noqa
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _post(url, body, headers, timeout=60):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    ctx = _ssl_context() if url.startswith("https") else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            detail = ""
        raise AIError("HTTP %d %s" % (e.code, detail))
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if "CERTIFICATE_VERIFY_FAILED" in reason:
            reason += (" (On a Mac with Python from python.org, run 'Install Certificates.command' "
                       "in your Python folder once.)")
        raise AIError("Can't connect: %s" % reason)
    except (OSError, ValueError) as e:
        raise AIError("Can't connect: %s" % e)


class Client:
    def __init__(self, settings):
        self.s = settings
        self.provider = settings["provider"]
        self.model = settings.get("model") or DEFAULT_MODELS.get(self.provider, "")
        self.address = (settings.get("address") or DEFAULT_ADDRESS.get(self.provider, "")).rstrip("/")
        self.key = settings.get("key", "").strip()
        self.no_temperature = False

    def call(self, system, user, images=None, max_tokens=900, temperature=0.9):
        if self.provider == "claude":
            return self._claude(system, user, images, max_tokens, temperature)
        if self.provider == "openai":
            return self._openai(system, user, images, max_tokens, temperature)
        if self.provider == "ollama":
            return self._ollama(system, user, images, max_tokens, temperature)
        raise AIError("AI is off")

    def _claude(self, system, user, images, max_tokens, temperature):
        content = []
        for mt, b64 in images or []:
            content.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}})
        content.append({"type": "text", "text": user})
        body = {"model": self.model, "max_tokens": max_tokens, "system": system,
                "messages": [{"role": "user", "content": content}]}
        if not self.no_temperature:
            body["temperature"] = max(0.0, min(1.0, temperature))
        headers = {"x-api-key": self.key, "anthropic-version": "2023-06-01"}
        try:
            r = _post(self.address + "/v1/messages", body, headers)
        except AIError as e:
            if "temperature" in str(e) and not self.no_temperature:
                self.no_temperature = True
                body.pop("temperature", None)
                r = _post(self.address + "/v1/messages", body, headers)
            else:
                raise
        parts = [b.get("text", "") for b in r.get("content", []) if b.get("type") == "text"]
        if not parts:
            raise AIError("Empty answer")
        return "".join(parts)

    def _openai(self, system, user, images, max_tokens, temperature):
        if images:
            content = [{"type": "text", "text": user}]
            for mt, b64 in images:
                content.append({"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (mt, b64)}})
        else:
            content = user
        body = {"model": self.model, "messages": [{"role": "system", "content": system},
                                                   {"role": "user", "content": content}],
                "max_completion_tokens": max_tokens * 4}
        if not self.no_temperature:
            body["temperature"] = max(0.0, min(2.0, temperature))
        headers = {"Authorization": "Bearer " + self.key}
        url = self.address + "/v1/chat/completions"
        try:
            r = _post(url, body, headers)
        except AIError as e:
            msg = str(e)
            if "temperature" in msg and not self.no_temperature:
                self.no_temperature = True
                body.pop("temperature", None)
                r = _post(url, body, headers)
            elif "max_completion_tokens" in msg:
                body["max_tokens"] = body.pop("max_completion_tokens") // 4
                r = _post(url, body, headers)
            else:
                raise
        try:
            text = r["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise AIError("Odd answer")
        if not text:
            raise AIError("Empty answer")
        return text

    def _ollama(self, system, user, images, max_tokens, temperature):
        msg = {"role": "user", "content": user}
        if images:
            msg["images"] = [b64 for mt, b64 in images]
        body = {"model": self.model, "stream": False, "format": "json",
                "messages": [{"role": "system", "content": system}, msg],
                "options": {"temperature": temperature, "num_predict": max_tokens * 2}}
        r = _post(self.address + "/api/chat", body, {}, timeout=180)
        text = (r.get("message") or {}).get("content", "")
        if not text:
            raise AIError("Empty answer")
        return text


def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except ValueError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except ValueError:
            return None
    return None


# ============================================================================ worker
class AI:
    """Runs AI calls on a background thread; results are applied on the main thread in World.tick()."""

    def __init__(self, world):
        self.w = world
        self.jobs = queue.Queue()
        self.results = queue.Queue()
        self.callbacks = {}
        self.done = {}
        self.n = 0
        self.calls = []
        self.down_until = 0
        self.last_error = ""
        self.ok_count = 0
        self.thread = None
        self.tried_start = False
        self.pull_status = ""
        self.reload()

    def reload(self):
        self.settings = load_settings()
        self.client = Client(self.settings)
        self.last_error = ""
        self.down_until = 0
        if self.enabled and (self.thread is None or not self.thread.is_alive()):
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
        if self.settings["provider"] == "ollama":
            threading.Thread(target=self._ensure_ollama, daemon=True).start()

    # ------------------------------------------------------------ Ollama housekeeping
    def _ollama_up(self):
        try:
            with urllib.request.urlopen(self.client.address + "/api/tags", timeout=2) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            return None

    def _ensure_ollama(self):
        """If Ollama is installed but not running, start it, so Mess Manager is the only thing to open."""
        if self._ollama_up() is not None:
            return
        self.start_ollama()

    def start_ollama(self):
        if self.tried_start:
            return False
        self.tried_start = True
        try:
            if sys.platform == "darwin":
                for app in ("/Applications/Ollama.app", os.path.expanduser("~/Applications/Ollama.app")):
                    if os.path.isdir(app):
                        subprocess.Popen(["open", "-g", "-a", app])
                        self.down_until = time.time() + 6
                        return True
            if sys.platform.startswith("win"):
                exe = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama app.exe")
                if os.path.isfile(exe):
                    subprocess.Popen([exe], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
                    self.down_until = time.time() + 6
                    return True
            cli = shutil.which("ollama") or next((p for p in ("/usr/local/bin/ollama", "/opt/homebrew/bin/ollama",
                                                               "/usr/bin/ollama") if os.path.isfile(p)), None)
            if cli:
                subprocess.Popen([cli, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=not sys.platform.startswith("win"))
                self.down_until = time.time() + 6
                return True
        except Exception as e:
            self.last_error = "Couldn't start Ollama: %s" % e
        return False

    def model_installed(self):
        tags = self._ollama_up()
        if tags is None:
            return None
        want = self.client.model.split(":")[0]
        return any(m.get("name", "").split(":")[0] == want for m in tags.get("models", []))

    def pull_model(self):
        """Download the chosen Ollama model in the background (it can take a while)."""
        if self.pull_status.startswith("Downloading"):
            return
        model = self.client.model
        self.pull_status = "Downloading %s... (this can take a while; you can keep playing)" % model

        def run():
            if self._ollama_up() is None:
                self.tried_start = False
                self.start_ollama()
                for _ in range(20):
                    time.sleep(1)
                    if self._ollama_up() is not None:
                        break
            try:
                _post(self.client.address + "/api/pull", {"model": model, "stream": False}, {}, timeout=6 * 3600)
                self.pull_status = "%s is downloaded. Press Test." % model
                self.down_until = 0
            except AIError as e:
                self.pull_status = "Download failed: %s" % str(e)[:160]
        threading.Thread(target=run, daemon=True).start()

    @property
    def enabled(self):
        p = self.settings["provider"]
        if p == "none":
            return False
        if p in ("claude", "openai") and not self.settings.get("key"):
            return False
        return True

    @property
    def available(self):
        return self.enabled and time.time() >= self.down_until and self.budget_left() > 0

    def can_see(self):
        if not self.enabled or self.settings.get("pictures", "yes").lower().startswith("n"):
            return False
        if self.settings["provider"] == "ollama":
            m = self.client.model.lower()
            return any(x in m for x in ("llava", "vision", "gemma3", "llama3.2-vision", "moondream", "qwen2.5vl", "minicpm"))
        return True

    def budget_left(self):
        try:
            limit = max(1, int(float(self.settings.get("calls") or 60)))
        except ValueError:
            limit = 60
        now = time.time()
        self.calls = [t for t in self.calls if now - t < 3600]
        return limit - len(self.calls)

    def status(self):
        if not self.enabled:
            if self.settings["provider"] in ("claude", "openai"):
                return "AI: no key (using written lines)"
            return "AI: off (using written lines)"
        name = PROVIDER_NAMES[self.settings["provider"]]
        if self.pull_status.startswith("Downloading"):
            return "AI: downloading %s..." % self.client.model
        if time.time() < self.down_until:
            if "not found" in self.last_error and self.settings["provider"] == "ollama":
                return "AI: the model %s isn't downloaded yet (AI... > Download model)" % self.client.model
            return "AI: %s can't be reached - their words can't be written right now. %s" % (name, self.last_error[:100])
        if self.budget_left() <= 0:
            return "AI: hourly limit reached - using written lines for now"
        return "AI: %s (%s)" % (name, self.client.model)

    # -- submitting
    def submit(self, kind, system, user, on_done, images=None, max_tokens=900, temperature=None, priority=False):
        """on_done(data_or_None) runs on the main thread. None means: use the written fallback."""
        self.n += 1
        jid = "%s-%d" % (kind, self.n)
        if not self.available:
            self.results.put({"id": jid, "ok": False, "error": "unavailable"})
            self.callbacks[jid] = on_done
            return jid
        if temperature is None:
            temperature = 0.6 + 0.6 * self.w.chance()
        self.calls.append(time.time())
        self.callbacks[jid] = on_done
        self.jobs.put({"id": jid, "kind": kind, "system": system, "user": user, "images": images,
                       "max_tokens": max_tokens, "temperature": temperature, "client": self.client})
        return jid

    def _run(self):
        while True:
            job = self.jobs.get()
            if job is None:
                return
            try:
                text = job["client"].call(job["system"], job["user"], job["images"], job["max_tokens"], job["temperature"])
                data = parse_json(text)
                if data is None:
                    raise AIError("Answer wasn't readable")
                self.results.put({"id": job["id"], "ok": True, "data": data})
            except Exception as e:  # network, key, model name, anything
                self.results.put({"id": job["id"], "ok": False, "error": str(e)})

    def process(self):
        """Main thread: hand finished answers to whoever asked."""
        handled = 0
        while handled < 20:
            try:
                r = self.results.get_nowait()
            except queue.Empty:
                break
            handled += 1
            cb = self.callbacks.pop(r["id"], None)
            if r["ok"]:
                self.ok_count += 1
                self.last_error = ""
            elif r.get("error") != "unavailable":
                self.last_error = r.get("error", "")
                err = self.last_error
                if "Can't connect" in err and self.settings["provider"] == "ollama" and self.start_ollama():
                    pass
                elif any(x in err for x in ("Can't connect", "HTTP 401", "HTTP 403", "HTTP 404", "HTTP 429", "HTTP 5")):
                    self.down_until = time.time() + (600 if ("401" in err or "403" in err or "404" in err) else 90)
                self.w.state.setdefault("ai_errors", []).append("%s %s" % (T.stamp(), err[:200]))
                self.w.state["ai_errors"] = self.w.state["ai_errors"][-20:]
            data = r.get("data") if r["ok"] else None
            self.done[r["id"]] = data if data is not None else False
            if len(self.done) > 200:
                for k in list(self.done)[:100]:
                    self.done.pop(k, None)
            if cb:
                try:
                    cb(data)
                except Exception as e:
                    self.w.state.setdefault("errors", []).append("ai callback: %s" % e)

    def test(self, on_done):
        return self.submit("test", SYSTEM_BASE, 'Reply with {"ok": true, "line": "one short quiet sentence Bob might say to Alice"}',
                           on_done, max_tokens=120)

    # ============================================================== describing the world
    def describe_char(self, c, full=True):
        w = self.w
        s = c["soul"]
        bits = ["%s (folder on disk: %s)." % (c["name"], w.base(c.get("path") or c["name"])),
                "MADE OF:\n" + self.voice_from_files(c, long=full)]
        bits.append("Age %s. Body: %s. Happiness %d, Fear %d, Anger %d, Trust (in the thing that moves them) %d, Corruption %d." % (
            c["age"], w.body_state(c), s["happiness"], s["fear"], s["anger"], s["trust"], s["corruption"]))
        if c.get("location"):
            bits.append("Is in %s (%s)." % (c["location"], w.place_info(c.get("place_rel", ""))["feel"]))
        if c.get("parents"):
            bits.append("Child of %s." % " and ".join(c["parents"]))
        if c.get("flags", {}).get("copy_of"):
            bits.append("Is a copy of %s." % c["flags"]["copy_of"])
        feelings = []
        for oid, r in c["rel"].items():
            o = w.char(oid)
            if o and (r["close"] >= 15 or r["love"] >= 15):
                feelings.append("%s (closeness %d, love %d)" % (o["name"], r["close"], r["love"]))
        if feelings:
            bits.append("Feelings: " + ", ".join(feelings) + ".")
        if w.likes(c):
            bits.append("Likes: " + ", ".join(w.likes(c)[:8]) + ".")
        if w.fears(c):
            bits.append("Fears: " + ", ".join(w.fears(c)[:8]) + ".")
        if not full:
            return " ".join(bits)
        m = c["mem"]
        if m["images"]:
            bits.append("Pictures seen: " + ", ".join(self.pic_name(x[0]) for x in m["images"][-6:]) + ".")
        if m["songs"]:
            bits.append("Sounds heard: " + ", ".join(x[0] for x in m["songs"][-5:]) + ".")
        if m["learned"]:
            bits.append("Words learned from others: " + ", ".join("'%s' from %s" % (a, b) for a, b in m["learned"][-5:]) + ".")
        if m["vocab"]:
            bits.append("Words from their files: " + ", ".join(sorted(set(v[0] for v in m["vocab"][-12:]))) + ".")
        if m["lost"]:
            bits.append("Lost (deleted): " + ", ".join(m["lost"]) + ".")
        if m["deleted"]:
            bits.append("Remembers these being deleted: " + ", ".join(m["deleted"][-5:]) + ".")
        if m.get("notes"):
            bits.append("Remembers: " + " | ".join(m["notes"][-10:]))
        diary = w.read(c["path"] + "/Diary.txt") if c.get("path") else None
        if diary:
            tail = [l for l in diary.splitlines() if l.startswith("[")][-5:]
            if tail:
                bits.append("Last diary lines: " + " / ".join(re.sub(r"^\[[^\]]*\]\s*", "", l) for l in tail))
        return " ".join(bits)

    def excerpt(self, ing, n):
        """The actual words of a text file they are made of (from the live file, or the kept copy)."""
        text = self.w.read(ing["rel"], 4000) if not ing.get("deleted") else None
        if not text:
            text = self.w.read("System/backups/files/%s.txt" % ing["id"], 4000) or ""
        text = re.sub(r"\s+", " ", text).strip()
        return text[:n]

    def voice_from_files(self, c, long=True):
        w = self.w
        ings = [i for i in w.state["ingredients"].values() if i.get("used_by") == c["id"]]
        parts = []
        for ing in ings[:10]:
            a = ing.get("a") or {}
            if ing["kind"] == "word":
                words = self.excerpt(ing, 600 if long else 160)
                parts.append('- text "%s": %s' % (ing["name"], ('"%s"' % words) if words else "(empty)"))
            elif ing["kind"] == "image":
                look = a.get("look") or {}
                desc = a.get("seen_as") or ("a %s picture" % a.get("mood", "plain"))
                col = (", mostly %s, %s" % (look.get("colour"), "dark" if look.get("brightness", 128) < 70 else (
                    "bright" if look.get("brightness", 128) > 170 else "dim"))) if look else ""
                parts.append('- picture "%s": %s%s' % (ing["name"], desc, col))
            else:
                parts.append('- sound "%s": %s' % (ing["name"], {"distorted": "loud, distorted, broken",
                                                                 "voice": "a human voice", "calm": "calm, soft"}.get(
                    a.get("mood"), "a sound")))
        if c.get("parents") and not ings:
            parts.append("- made from bits of %s, so they speak like a small mix of them" % " and ".join(c["parents"]))
        if c.get("flags", {}).get("copy_of"):
            parts.append("- a copy of %s, so made of the same things" % c["flags"]["copy_of"])
        if not parts:
            parts.append("- almost nothing; they barely have words")
        return "\n".join(parts) + "\n" + VOICE_RULE

    def pic_name(self, name):
        for ing in self.w.state["ingredients"].values():
            if ing["name"] == name and ing["a"].get("seen_as"):
                return "%s (%s)" % (name, ing["a"]["seen_as"])
        return name

    def describe_ing(self, ing):
        a = ing.get("a") or {}
        if ing["kind"] == "image":
            what = a.get("seen_as") or ("a %s picture" % a.get("mood", "plain"))
            return "%s: %s" % (ing["name"], what)
        if ing["kind"] == "sound":
            return "%s: a %s sound" % (ing["name"], a.get("mood", "plain"))
        first = a.get("first_line") or ""
        return '%s: words%s' % (ing["name"], (' beginning "%s"' % first[:80]) if first else "")

    def recent_actions(self, n=14):
        out = []
        names = {cid: c["name"] for cid, c in list(self.w.state["chars"].items()) + list(self.w.state["dead"].items())}
        for a in self.w.state["actions"][-n * 3:]:
            k, d = a["k"], a["d"]
            who = names.get(d.get("char"), "")
            text = {
                "file_added": "gave a %s file: %s" % (d.get("kind"), d.get("name")),
                "file_deleted": "deleted the file %s" % d.get("name"),
                "file_moved": "moved %s to %s" % (self.w.base(d.get("from", "")), self.w.parent(d.get("to", "")) or "Mess"),
                "char_moved": "moved %s from %s to %s" % (who, d.get("from"), d.get("to")),
                "char_renamed": "renamed %s to %s" % (d.get("from"), d.get("to")),
                "char_copied": "copied %s" % who,
                "char_deleted": "DELETED %s" % d.get("name"),
                "char_restored": "restored %s" % who,
                "place_created": "made a new place: %s" % d.get("name"),
                "edited_stats": "edited %s's Stats.txt" % who,
                "gave_file": "gave %s the file %s" % (who, d.get("name")),
                "deleted_piece": "deleted %s's %s" % (who, d.get("file")),
                "time_speed": "changed the time speed to %s" % d.get("v"),
            }.get(k)
            if text:
                out.append("%s ago: the unseen hand %s" % (T.ago(a["t"]).replace(" ago", ""), text))
        return out[-n:]

    def world_summary(self):
        w = self.w
        st = w.state
        p = st["player"]
        lines = ["NOW: %s (player's local time). Mess has existed %d in-world days." % (
            time.strftime("%A %H:%M"), int(st["sim_min"] // 1440))]
        lines.append("THE HAND (never spoken to): harm done %d, care given %d." % (p["cruelty"], p["kindness"]))
        idle = time.time() - st.get("last_input", time.time())
        if idle > 120:
            lines.append("Nothing has been touched for %s." % T.duration_words(idle))
        acts = self.recent_actions()
        if acts:
            lines.append("WHAT THE HAND DID RECENTLY (they can see the results, not the hand):\n- " + "\n- ".join(acts))
        news = [n["text"] for n in st.get("news", [])[-8:]]
        if news:
            lines.append("THINGS THEY NOTICED RECENTLY:\n- " + "\n- ".join(news))
        lines.append("PEOPLE:")
        for c in w.alive():
            lines.append("* " + self.describe_char(c, full=len(w.alive()) <= 4))
        if st["dead"]:
            lines.append("GONE: " + ", ".join(c["name"] for c in st["dead"].values()))
        places = []
        for rel, e in w.snapshot.items():
            if e["d"] and w.is_place_dir(rel) and rel.count("/") <= 2:
                places.append(w.base(rel))
        lines.append("PLACES: " + ", ".join(sorted(set(places))))
        unused = w.unused_ingredients()
        if unused:
            lines.append("Unused files waiting in the folder: " + ", ".join(i["name"] for i in unused[:8]))
        story = st.get("story", [])[-6:]
        if story:
            lines.append("RECENT LOGS: " + " | ".join(x["title"] for x in story))
        return "\n".join(lines)

    def dice(self):
        r = self.w.rng
        return "Dice for chance (use them to decide outcomes, do not mention them): %d, %d, %d (each 1-6). Chance level: %.1f of 1." % (
            r.randint(1, 6), r.randint(1, 6), r.randint(1, 6), self.w.chance())

    # ============================================================== jobs
    def narrate(self, title, facts, write, chars=None):
        """Rewrite an event log in fresh words. write(title, text) is called with the result or the original."""
        extra = ""
        for c in chars or []:
            if c:
                extra += "\n* " + self.describe_char(c, full=False)
        user = ("Something just happened in Mess. Write the log file for it, in quiet third person. The people in "
                "it may say a few short lines TO EACH OTHER (never to the reader or the player).\n\nFACTS (keep all "
                "of them true):\n%s\n\n"
                "Working title: %s%s\n\nWORLD:\n%s\n\n%s\n\n"
                'Answer: {"title": "short title", "text": "the log, 40-180 words, quiet and specific"}') % (
            facts, title, ("\nPEOPLE INVOLVED:" + extra) if extra else "", self.world_summary(), self.dice())

        def done(data):
            if data and isinstance(data.get("text"), str) and data["text"].strip():
                write(str(data.get("title") or title)[:80], data["text"].strip())
            else:
                write(title, facts)
        self.submit("narrate", SYSTEM_BASE, user, done, max_tokens=500)

    def files_seen(self, c):
        names = [i["name"] for i in self.w.visible_ingredients(c)]
        try:
            for n in os.listdir(self.w.ab(c.get("place_rel", ""))):
                if T.kind_of(n) and n not in names and not n.startswith("."):
                    names.append(n)
        except OSError:
            pass
        return names[:20]

    def converse(self, a, b, facts, finish):
        """Two people talk to each other, or one talks to the files. finish(list of (char, line)) - empty if it failed."""
        w = self.w
        seen = self.files_seen(a)
        if b:
            setup = ("Two people in Mess talk to each other. Write what they say.\n\nA:\n%s\n\nB:\n%s\n\n"
                     "They are %s." % (self.describe_char(a), self.describe_char(b),
                                       "in the same place" if a.get("place_rel") == b.get("place_rel") else
                                       "in different places, talking through the folder walls"))
        else:
            setup = ("Someone in Mess is alone and talks to the files around them (the files never answer). "
                     "Write what they say.\n\nA:\n%s" % self.describe_char(a))
        user = ("%s\n\nFILES A CAN SEE IN %s: %s\n\nWHAT JUST CHANGED (what they're reacting to):\n- %s\n\n"
                "WORLD:\n%s\n\n%s\n\n3 to 8 short lines. They react to the changes in each other and in the folder, "
                "to the files they can see, to each other. They never speak to the player. The talk can change things "
                "(comfort, a word taught, a confession, a fight, moving somewhere together, making something).\n\n%s\n\n"
                'Answer: {"lines": [{"who": NAME, "line": "..."}], "effects": []}') % (
            setup, (a.get("location") or "their place").upper(), ", ".join(seen) or "nothing",
            "\n- ".join(facts or ["nothing in particular"]), self.world_summary(), self.dice(), EFFECTS_HELP)

        def done(data):
            lines = []
            if data and isinstance(data.get("lines"), list):
                for x in data["lines"][:10]:
                    if not isinstance(x, dict):
                        continue
                    who = w.char_by_name(str(x.get("who", "")))
                    ln = str(x.get("line", "")).strip()
                    if who and who in (a, b) and ln:
                        lines.append((who, w.colour_speech(who, ln) if who["soul"]["corruption"] > 45 else ln))
            if lines:
                w.apply_effects(data.get("effects"), default=a)
            finish(lines)
        self.submit("converse", SYSTEM_BASE, user, done, max_tokens=700)

    def direct(self):
        """The director: invent what happens next."""
        w = self.w
        user = ("You decide what happens next in Mess. Invent 0 to 2 new events that grow out of the world state "
                "and what the hand did recently. Nothing scripted: it should surprise, but feel caused. "
                "Small everyday things are good (someone writes a poem, rearranges a place, visits someone, "
                "argues, makes up, misses someone, finds an old file, builds something, starts to forget the hand). "
                "Big things are rare. Use the dice: low rolls mean things go badly or nothing happens.\n\n"
                "WORLD:\n%s\n\n%s\n\n%s\n\n"
                'Logs are quiet third person; people may speak to each other, never to the player.\n'
                'Answer: {"events": [{"title": "short log title", "log": "the log text, 40-160 words", '
                '"effects": []}]}  (an empty list is fine)') % (self.world_summary(), self.dice(), EFFECTS_HELP)

        def done(data):
            if not data or not isinstance(data.get("events"), list):
                w.story.spontaneous_fallback()
                return
            for ev in data["events"][:2]:
                if not isinstance(ev, dict):
                    continue
                title = str(ev.get("title") or "Something happened")[:80]
                text = str(ev.get("log") or "").strip()
                if text:
                    w.story.log(title, text, raw=True)
                w.apply_effects(ev.get("effects"))
        self.submit("direct", SYSTEM_BASE, user, done, max_tokens=900)

    def look(self, ing):
        """Let the AI see a picture once. Updates what the characters think it is."""
        w = self.w
        path = w.ab(ing["rel"])
        mt = IMAGE_TYPES.get(T.ext_of(ing["rel"]))
        try:
            size = os.path.getsize(path)
        except OSError:
            return
        if not mt or size > 3_500_000:
            return
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        except OSError:
            return
        user = ('The player dropped this picture (file name "%s") into Mess. Describe it the way a newborn made of '
                'files would understand it.\nAnswer: {"seen_as": "what it shows, under 12 words", '
                '"mood": "soft|scary|plain", "person": true or false, "subject": "one word, e.g. cat, face, sea"}') % ing["name"]

        def done(data):
            if not data:
                return
            a = ing["a"]
            if isinstance(data.get("seen_as"), str):
                a["seen_as"] = data["seen_as"][:100]
            if data.get("mood") in ("soft", "scary", "plain"):
                old = a.get("mood")
                a["mood"] = data["mood"]
                sc = a.setdefault("scores", {"scary": 0, "soft": 0, "angry": 0, "sad": 0})
                if data["mood"] == "scary" and old != "scary":
                    sc["scary"] = sc.get("scary", 0) + 3
                if data["mood"] == "soft" and old != "soft":
                    sc["soft"] = sc.get("soft", 0) + 3
            if isinstance(data.get("person"), bool):
                a["person"] = data["person"]
            if isinstance(data.get("subject"), str) and data["subject"].strip():
                a["subject"] = data["subject"].strip().lower()[:20]
        self.submit("look", SYSTEM_BASE, user, done, images=[(mt, b64)], max_tokens=200, temperature=0.3)

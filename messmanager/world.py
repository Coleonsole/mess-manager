"""The Mess: a real folder on the player's disk, and the lives inside it.

The World polls the real file system (so changes made in Explorer, Finder or a Linux
file manager count just as much as changes made in Mess Manager), turns every
difference into a player action, simulates souls, and writes the consequences back
to disk as real folders and plain .txt files.

Folders are whole things (people, places, system). Files are pieces of things.
"""
import hashlib
import json
import os
import random
import re
import shutil
import time
import uuid

from . import textlib as T
from . import media

CHARS = "Characters"
PLACES = "Places"
WORDS = "Places/Words"
IMAGES = "Places/Images"
SOUNDS = "Places/Sounds"
LOGS = "Places/Logs"
SYSTEM = "System"
WORLD = "World"
NEAT = {"word": WORDS, "image": IMAGES, "sound": SOUNDS}
NEAT_NAME = {"word": "Words", "image": "Images", "sound": "Sounds"}
GAME_FILES = {"stats.txt", "diary.txt", "chat.txt", "body.txt", ".soul", "talking_to_the_files.txt"}
ROOT_KEEP = {"how to play.txt", "rules.txt"}
SOUL = ".soul"

PLACE_KEYS = [
    # keyword, temperature, light, feel
    ("basement", -2, -2, "It's cold here, and the light doesn't reach the corners."),
    ("cellar", -2, -2, "It's cold and it smells of old files."),
    ("attic", -1, -1, "Dusty. Things are kept here that nobody opens."),
    ("beach", 2, 2, "It's warm. I can hear something like waves in the file sizes."),
    ("sea", 1, 2, "It's wide and it goes on past the scrollbar."),
    ("ocean", 1, 2, "It's wide and it goes on past the scrollbar."),
    ("words", 0, 1, "It's a library. Everything here is quiet and made of sentences."),
    ("images", 0, 2, "It's a gallery. The walls are covered in thumbnails."),
    ("sounds", 1, 0, "It's a music room. The air hums a little."),
    ("logs", 0, -1, "It's an archive. Everything that happened is filed here."),
    ("school", 1, 2, "It's a school. It smells like new files."),
    ("characters", 1, 1, "It's home, I think. Everyone's folder starts here."),
    ("mess", 0, 0, "It's messy. Things get dropped here and then taken away."),
    ("garden", 2, 2, "It's warm. Something is growing in the folder size."),
    ("kitchen", 2, 1, "Warm. It smells like someone made something."),
    ("bedroom", 1, -1, "Soft and dim. Somewhere to stop being looked at."),
    ("room", 1, 0, "It's a small room. It feels like someone's."),
    ("forest", 0, -1, "Lots of tall folders. Easy to get lost."),
    ("church", 0, 1, "Quiet. It feels like being listened to."),
    ("hospital", -1, 2, "Clean and too bright. Everybody here is being fixed."),
    ("graveyard", -2, -2, "This is where gone things go. It's very quiet."),
    ("cemetery", -2, -2, "This is where gone things go. It's very quiet."),
    ("playground", 1, 2, "Bright. There's room to run."),
    ("library", 0, 1, "Quiet, full of sentences."),
    ("park", 1, 2, "Open. The folder feels bigger than it is."),
    ("home", 2, 1, "It's home. It's the word that means home."),
    ("house", 1, 1, "A house. Folders inside folders, like rooms."),
    ("dark", -1, -2, "It's dark. I can't see my own icon."),
    ("void", -2, -2, "There isn't anything here. Not even a size."),
    ("trash", -1, -1, "This is where you put things you don't want."),
    ("bin", -1, -1, "This is where you put things you don't want."),
    ("recycle", -1, -1, "This is where you put things you don't want."),
    ("winter", -2, 1, "Cold and white."),
    ("snow", -2, 1, "Cold and white."),
    ("summer", 2, 2, "Warm and bright."),
    ("sun", 2, 2, "Warm and bright."),
    ("night", -1, -2, "It's night in here. It's always night in here."),
    ("downloads", 0, 0, "Crowded. Nobody knows where anything came from."),
    ("desktop", 0, 1, "Everything is out in the open."),
    ("lighthouse", 0, 2, "Tall. There's a light at the top that never goes out."),
    ("shelter", 2, 0, "We built it so nothing could find us."),
    ("bakery", 2, 1, "Warm. Nobody here eats, but it smells right."),
]
PLACE_WORDS = {"warm": (2, 0), "hot": (2, 0), "cold": (-2, 0), "freezing": (-3, 0),
               "dark": (0, -2), "bright": (0, 2), "light": (0, 1), "safe": (1, 0),
               "scary": (-1, -1), "quiet": (0, 0), "loud": (0, 0), "cosy": (2, 0), "cozy": (2, 0)}

HOW_TO_PLAY = """HOW TO PLAY MESS MANAGER

This is a file manager for a messy folder. That's all.

Just write what you want to happen, drop in a photo or a song. The game will read it.

To move a person, move their whole folder.
To change a person, edit a file inside their folder.

THINGS TO KNOW
- Drop files into Mess (text, pictures, sounds). They get tidied into Places/Words,
  Places/Images and Places/Sounds. A little note tells you where they went.
- Five files can become someone. Ten files can become someone else.
- What the files are made of matters. A cat photo is soft. A scary photo is not.
  A calm song calms. A loud, distorted one does something else.
- A person is a folder inside Characters (or inside a place).
  Open their folder. Open Stats.txt to see how they are. You can change it. Write in plain English.
- They don't talk to you. They talk to each other, about what happens to them and what they see.
  The Overheard panel on the right shows what's said. Their conversations are also saved as files.
- Every folder that isn't a person or the System is a place.
  Make a folder called Beach and it becomes a beach.
  Move someone's folder into it and they are at the beach.
- Write anything in any .txt file, in plain English, and it becomes true. For example:
      Bob likes apples
      Bob is scared of the dark
      Bob cannot die
      Alice goes to Beach
      It is warm here          (inside a place folder: makes that place warm)
  Delete the line and it stops being true.
- World/Stats.txt has the Time Speed. 1 means real time. 60 means one hour passes
  every minute.
- You can do all of this in Mess Manager or in your normal file manager
  (Explorer, Finder, Files). Mess notices either way.
- World/Stats.txt also has Chance. 0 means everything follows from what you do.
  1 means anything can happen.
- The AI... button lets an AI (Ollama, on your own computer) write what they say to each other
  and the things that happen. Without it, they still live, but their words can't be written down.
- The System folder is just the game's own files. You don't need to touch it.

There is no way to win. There is no ending. The folder just keeps going.
"""

RULES_TXT = """RULES

Write rules here, in plain English, one per line. Anyone in Mess can read this file.

"""


def _h(text):
    return hashlib.md5(text.encode("utf-8", "replace")).hexdigest()


class World:
    TICK_SAVE = 20.0
    AFK_SECONDS = 120
    BACKUP_EVERY = 120

    def __init__(self, root, quiet=False):
        self.root = os.path.abspath(root)
        self.quiet = quiet
        self.rng = random.Random()
        self.whispers = []          # (name, text) queue for the UI
        self.open_files = set()     # rel paths currently open in an editor
        self.snapshot = {}
        self.souls = {}
        self.pending_sort = {}
        self.rules = {}
        self.rules_dirty = True
        self.place_rules = {}
        self.room_rules = {}
        self.world_rules = {}
        self.gone_world = False
        self.last_tick = time.time()
        self.last_save = 0
        self.last_backup = 0
        self.dirty_tree = True
        self.in_offline = False
        self.pixel_reader = None     # set by the UI when Pillow is missing
        self.path_aliases = {}       # old rel -> new rel, so open windows can follow moved files
        self.state = None
        from . import story
        from . import ai
        self.story = story.Story(self)
        self.ai = ai.AI(self)

    # ------------------------------------------------------------ paths
    def ab(self, rel):
        return os.path.join(self.root, *rel.split("/")) if rel else self.root

    def rp(self, path):
        r = os.path.relpath(path, self.root).replace(os.sep, "/")
        return "" if r == "." else r

    @staticmethod
    def parent(rel):
        return rel.rsplit("/", 1)[0] if "/" in rel else ""

    @staticmethod
    def base(rel):
        return rel.rsplit("/", 1)[-1]

    @staticmethod
    def join(a, b):
        return (a + "/" + b) if a else b

    def exists(self, rel):
        return os.path.exists(self.ab(rel))

    def unique(self, parent_rel, name):
        stem, ext = (name.rsplit(".", 1) + [""])[:2] if "." in name and not name.startswith(".") else (name, "")
        cand = name
        n = 2
        while self.exists(self.join(parent_rel, cand)):
            cand = ("%s (%d).%s" % (stem, n, ext)) if ext else ("%s %d" % (stem, n))
            n += 1
        return self.join(parent_rel, cand)

    # ------------------------------------------------------------ setup
    def setup(self):
        os.makedirs(self.root, exist_ok=True)
        self.load_state()
        for d in (CHARS, PLACES, WORDS, IMAGES, SOUNDS, LOGS, SYSTEM, WORLD, SYSTEM + "/backups",
                  SYSTEM + "/backups/files"):
            os.makedirs(self.ab(d), exist_ok=True)
        if not self.exists("How To Play.txt"):
            self.write("How To Play.txt", HOW_TO_PLAY)
        if not self.exists("Rules.txt"):
            self.write("Rules.txt", RULES_TXT)
        self.write(SYSTEM + "/README.txt",
                   "These are Mess Manager's own files: save data, backups and timestamps.\n"
                   "Nobody who lives in Mess can see this folder. You don't need to edit anything here.\n")
        now = time.time()
        gone = now - self.state.get("last_seen", now)
        old_snap = self.state.pop("_snapshot", None) or self._load_snapshot()
        self.snapshot, self.souls = self.scan()
        if old_snap:
            # things the player did in Explorer / Finder while the game was closed
            self.process_changes(old_snap.get("entries", {}), old_snap.get("souls", {}),
                                 self.snapshot, self.souls, offline=True)
        self.refresh_char_paths()
        self.parse_rules()
        self.state["sessions"] = self.state.get("sessions", 0) + 1
        if gone > 60 and self.state.get("last_seen"):
            self.offline(gone)
        self.state["last_seen"] = now
        self.state["last_input"] = now
        self.state["session_start"] = now
        self.state["afk_session"] = None
        self.after_game_changes()
        self.save()

    def new_state(self):
        now = time.time()
        return {
            "version": 1, "created": now, "last_seen": now, "last_input": now,
            "sim_min": 0.0, "time_speed": 1.0,
            "player": {"name": None, "cruelty": 0, "kindness": 0, "promises": [],
                       "deleted": [], "kind_days": [], "lies": 0},
            "ingredients": {}, "ingredient_order": [], "total_added": 0,
            "chars": {}, "dead": {}, "fired": {}, "actions": [], "generated": [],
            "notes": [], "return_queue": [], "bob": None, "alice": None,
            "places_built": [], "hashes": {}, "afk_n": {}, "sessions": 0,
        }

    def load_state(self):
        p = self.ab(SYSTEM + "/state.json")
        try:
            with open(p, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        except Exception:
            self.state = self.new_state()
        base = self.new_state()
        for k, v in base.items():
            self.state.setdefault(k, v)

    def _load_snapshot(self):
        try:
            with open(self.ab(SYSTEM + "/snapshot.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save(self):
        if self.gone_world or not os.path.isdir(self.root):
            return
        self.state["last_seen"] = time.time()
        try:
            os.makedirs(self.ab(SYSTEM), exist_ok=True)
            for name, data in (("state.json", self.state),
                               ("snapshot.json", {"entries": self.snapshot, "souls": self.souls})):
                tmp = self.ab(SYSTEM + "/" + name + ".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                os.replace(tmp, self.ab(SYSTEM + "/" + name))
            alive = ", ".join("%s (%s)" % (c["name"], c.get("location", "?")) for c in self.alive())
            self.write(SYSTEM + "/timestamps.txt",
                       "Mess created: %s\nLast seen: %s\nSessions: %d\nSim minutes lived: %d\nAlive: %s\n" % (
                           T.stamp(self.state["created"]), T.stamp(), self.state.get("sessions", 0),
                           self.state["sim_min"], alive or "nobody"), track=False)
        except OSError:
            pass
        self.last_save = time.time()

    def chance(self):
        try:
            return max(0.0, min(1.0, float(self.state.get("chance", 0.5))))
        except (TypeError, ValueError):
            return 0.5

    def roll(self, p):
        return self.rng.random() < p

    # ------------------------------------------------------------ io helpers
    def write(self, rel, text, track=True):
        p = self.ab(rel)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            if track and self.state:
                self.state["hashes"][rel] = _h(text)
            return True
        except OSError:
            return False

    def append(self, rel, text):
        p = self.ab(rel)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(text)
            self.state["hashes"][rel] = self.hash_file(rel)
            return True
        except OSError:
            return False

    def read(self, rel, limit=200000):
        try:
            with open(self.ab(rel), "r", encoding="utf-8", errors="replace") as f:
                return f.read(limit)
        except OSError:
            return None

    def hash_file(self, rel):
        t = self.read(rel)
        return _h(t) if t is not None else None

    def gen(self, rel):
        if rel not in self.state["generated"]:
            self.state["generated"].append(rel)
            if len(self.state["generated"]) > 3000:
                self.state["generated"] = self.state["generated"][-2000:]

    def action(self, kind, detail):
        self.state["actions"].append({"t": time.time(), "sim": self.state["sim_min"], "k": kind, "d": detail})
        if len(self.state["actions"]) > 800:
            self.state["actions"] = self.state["actions"][-600:]

    def recent_actions(self, kind, within_sec):
        now = time.time()
        return [a for a in self.state["actions"] if a["k"] == kind and now - a["t"] <= within_sec]

    # ------------------------------------------------------------ scanning
    def scan(self):
        entries, souls = {}, {}
        if not os.path.isdir(self.root):
            return entries, souls
        for dirpath, dirnames, filenames in os.walk(self.root):
            rel_dir = self.rp(dirpath)
            if rel_dir == SYSTEM or rel_dir.startswith(SYSTEM + "/"):
                dirnames[:] = []
                continue
            for d in dirnames:
                rel = self.join(rel_dir, d)
                try:
                    st = os.stat(os.path.join(dirpath, d))
                    entries[rel] = {"d": 1, "s": 0, "m": st.st_mtime, "i": st.st_ino}
                except OSError:
                    pass
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                if fn == SOUL:
                    try:
                        with open(full, "r", encoding="utf-8") as f:
                            sid = f.read().strip()[:40]
                        if sid:
                            souls.setdefault(sid, []).append(rel_dir)
                    except OSError:
                        pass
                    continue
                if fn.endswith(".tmp"):
                    continue
                rel = self.join(rel_dir, fn)
                try:
                    st = os.stat(full)
                    entries[rel] = {"d": 0, "s": st.st_size, "m": st.st_mtime, "i": st.st_ino}
                except OSError:
                    pass
        return entries, souls

    def char_dirs(self):
        return {c["path"]: c for c in self.alive() if c.get("path")}

    def owner_char(self, rel):
        """The character whose folder contains rel (rel itself may be the folder)."""
        dirs = self.char_dirs()
        r = rel
        while True:
            if r in dirs:
                return dirs[r]
            if not r:
                return None
            r = self.parent(r)

    def dir_kind(self, rel):
        if rel in ("",):
            return "place"
        if rel == SYSTEM or rel.startswith(SYSTEM + "/"):
            return "system"
        if rel == WORLD or rel.startswith(WORLD + "/"):
            return "system"
        if rel in self.char_dirs():
            return "character"
        return "place"

    def is_place_dir(self, rel):
        if not os.path.isdir(self.ab(rel)):
            return False
        if self.dir_kind(rel) != "place":
            return False
        return self.owner_char(rel) is None

    def place_name(self, rel_dir):
        return "Mess" if rel_dir == "" else self.base(rel_dir)

    # ------------------------------------------------------------ characters
    def alive(self):
        return list(self.state["chars"].values())

    def char(self, cid):
        return self.state["chars"].get(cid)

    def char_by_name(self, name):
        n = name.lower()
        for c in self.alive():
            if c["name"].lower() == n:
                return c
        return None

    def refresh_char_paths(self):
        for sid, paths in self.souls.items():
            c = self.state["chars"].get(sid)
            if c and paths:
                if c.get("path") not in paths:
                    c["path"] = paths[0]
        for c in self.alive():
            if c.get("path"):
                c["location"] = self.place_name(self.parent(c["path"]))
                c["place_rel"] = self.parent(c["path"])

    def body_name(self, c):
        s = c["soul"]
        n = c["name"]
        if s["corruption"] >= 60:
            n = "_".join(n)
        elif s["fear"] >= 65:
            n = n + " (1)"
        if c.get("returned_suffix"):
            n = n + " (again)"
        return T.safe_name(n)

    def body_state(self, c):
        s = c["soul"]
        if s["corruption"] >= 60:
            return "corrupted"
        if s["anger"] >= 65:
            return "angry"
        if s["fear"] >= 65:
            return "scared"
        if s["happiness"] >= 60:
            return "happy"
        if s["happiness"] < 35:
            return "sad"
        return "calm"

    def make_character(self, name, voice, ings, place_rel=CHARS, age=None, parents=None, silent=False):
        cid = uuid.uuid4().hex[:12]
        sc = {"scary": 0, "soft": 0, "angry": 0, "sad": 0}
        likes, fears, vocab = [], [], []
        mem = {"player_name": None, "deleted": [], "lies": 0, "lie_notes": [], "kind_after_cruel": 0,
               "vocab": [], "learned": [], "images": [], "songs": [], "lost": [], "seen": [],
               "scary_image": None, "soft_image": None, "person_image": None, "voice_memo": None,
               "loud_song": None, "last_tone": None, "scary_vocab": [], "files_read": [],
               "ingredient_paths": [], "talked_to_files": []}
        for ing in ings:
            a = ing.get("a") or {}
            for k in sc:
                sc[k] += a.get("scores", {}).get(k, 0)
            nm = ing["name"]
            mem["seen"].append(nm)
            mem["ingredient_paths"].append(ing["rel"])
            for w in a.get("vocab", [])[:6]:
                vocab.append([w, nm])
                if w in T.SCARY_WORDS:
                    mem["scary_vocab"].append(w)
            if a.get("kind") == "image":
                mem["images"].append([nm, ing["rel"]])
                if a.get("mood") == "scary":
                    mem["scary_image"] = [nm, ing["rel"]]
                    fears.append("the picture " + nm)
                elif a.get("mood") == "soft":
                    mem["soft_image"] = [nm, ing["rel"]]
                    if a.get("subject") not in (None, "something", "person"):
                        likes.append(a["subject"] + "s")
                if a.get("person"):
                    mem["person_image"] = [nm, ing["rel"]]
            elif a.get("kind") == "sound":
                mem["songs"].append([a.get("title", nm), ing["rel"]])
                if a.get("mood") == "distorted":
                    mem["loud_song"] = [a.get("title", nm), ing["rel"]]
                    fears.append("loud noises")
                elif a.get("mood") == "voice":
                    mem["voice_memo"] = [nm, ing["rel"]]
                else:
                    likes.append('the song "%s"' % a.get("title", nm))
            elif a.get("kind") == "word":
                mem["files_read"].append(nm)
                s = a.get("scores", {})
                if s.get("soft", 0) > s.get("scary", 0):
                    likes += [w for w in a.get("vocab", []) if w in T.SOFT_WORDS][:2]
                if s.get("scary", 0) > 0:
                    fears += ["the " + w for w in a.get("vocab", []) if w in T.SCARY_WORDS][:2]
        mem["vocab"] = vocab[:40]
        distorted = sum(1 for i in ings if (i.get("a") or {}).get("mood") == "distorted")
        soul = {
            "happiness": T.clamp(55 + 4 * sc["soft"] - 3 * sc["scary"] - 3 * sc["sad"] - 2 * sc["angry"]),
            "fear": T.clamp(12 + 5 * sc["scary"] + 2 * sc["sad"]),
            "anger": T.clamp(5 + 5 * sc["angry"]),
            "trust": {"bob": 75, "alice": 30, "child": 80}.get(voice, 50),
            "corruption": T.clamp(10 * distorted + 2 * max(0, sc["scary"] - 4)),
        }
        if voice == "alice":
            soul["fear"] = T.clamp(soul["fear"] - 10)
        if voice == "hollow":
            soul["happiness"] = T.clamp(soul["happiness"] - 15)
        c = {
            "id": cid, "name": name, "voice": voice, "born": time.time(),
            "born_sim": self.state["sim_min"],
            "age": age if age is not None else {"bob": 18, "alice": 20}.get(voice, self.rng.randint(17, 34)),
            "soul": soul, "base_likes": list(dict.fromkeys(likes))[:8],
            "base_fears": list(dict.fromkeys(fears))[:8], "rel": {}, "mem": mem,
            "ingredients": [i["name"] for i in ings], "path": None, "location": None,
            "last_talk": 0, "last_player_move": 0, "player_moves": [], "pending": [],
            "used": [], "kind_days": [], "convo_n": {}, "parents": parents or [],
            "flags": {}, "notes": [], "next_move": self.state["sim_min"] + self.rng.uniform(20, 40),
            "loves": None, "diary_n": 0,
        }
        place_rel = place_rel if self.is_place_dir(place_rel) or place_rel == CHARS else CHARS
        os.makedirs(self.ab(place_rel), exist_ok=True)
        rel = self.unique(place_rel, T.safe_name(name))
        os.makedirs(self.ab(rel), exist_ok=True)
        with open(self.ab(rel + "/" + SOUL), "w", encoding="utf-8") as f:
            f.write(cid)
        media.hide_file(self.ab(rel + "/" + SOUL))
        c["path"] = rel
        c["location"] = self.place_name(place_rel)
        c["place_rel"] = place_rel
        self.state["chars"][cid] = c
        self.souls[cid] = [rel]
        if mem.get("scary_image"):
            # made from a frightening picture: it comes back at night
            c["flags"]["nightmare_due"] = self.state["sim_min"] + 20
            c["flags"]["nightmare_image"] = mem["scary_image"][0]
        for ing in ings:
            st = self.state["ingredients"].get(ing["id"])
            if st:
                st["used_by"] = cid
        self.diary(c, "I woke up. I'm made of %s." % ", ".join(c["ingredients"]) if c["ingredients"]
                   else "I woke up.")
        for o in self.alive():
            if o["id"] != cid:
                self.rel(c, o)
                self.rel(o, c)
        self.sync_body(c, force=True)
        self.feed("A folder appeared: %s." % rel)
        if not silent:
            others = [o for o in self.alive() if o["id"] != cid]
            self.want_talk(c, others[0] if others else None, "%s has just woken up, made of %s." % (
                name, ", ".join(c["ingredients"]) or "nothing"))
        return c

    def rel(self, a, b):
        r = a["rel"].get(b["id"])
        if r is None:
            seed = int(hashlib.md5((a["id"] + b["id"]).encode()).hexdigest()[:6], 16)
            r = {"close": 5.0, "love": 0.0, "together": 0.0, "apart": 0.0,
                 "chem": 0.6 + (seed % 1000) / 1000.0, "name": b["name"]}
            a["rel"][b["id"]] = r
        r["name"] = b["name"]
        return r

    # ------------------------------------------------------------ voice
    def colour_speech(self, c, text):
        """Vocabulary drift and corruption: what they've read leaks into how they talk."""
        sv = c["mem"].get("scary_vocab") or []
        if len(sv) >= 3 and self.rng.random() < 0.2:
            w = self.rng.choice(sv)
            text += self.rng.choice([" There's %s in everything today." % w,
                                     " Sorry. '%s'. That word keeps coming out of me." % w,
                                     " I keep thinking the word '%s'." % w])
        cor = c["soul"]["corruption"] / 100.0
        if cor > 0.45:
            text = T.light_glitch(text, cor)
        return text

    FACTS = {
        "moved": "{name} was moved to {place}.",
        "moved_cold": "{name} was moved to {place}. It is cold there.",
        "moved_dark": "{name} was moved to {place}. It is dark there.",
        "moved_warm": "{name} was moved to {place}. It is warm there.",
        "love_separated": "{name} was moved to {place}, away from {love}.",
        "love_together": "{name} was moved to {place}, where {love} is.",
        "renamed": "{oldname}'s folder was renamed. It says {newname} now.",
        "copied": "{name} was copied.",
        "restored": "{name}'s folder came back, called {newname}.",
        "grief": "{name} noticed that {lost} is gone.",
        "neat_moved": "{file} was taken out of {folder}. It belongs to {name}.",
        "scary_image": "{name} saw {image}. It frightened them.",
        "person_image": "{name} saw {image} and thinks they know the person in it.",
        "soft_image": "{name} saw {image}. It made them softer.",
        "new_image": "{name} saw {image}.",
        "loud_sound": "{name} heard {song}. It hurt.",
        "voice_memo": "{name} heard a voice: {song}.",
        "new_sound": "{name} heard {song}.",
        "scary_near": "{name} read {file}. The words were sharp.",
        "new_file": "{name} read {file}.",
        "love_fall": "{name} wants to be wherever {other} is.",
    }
    TALK_ABOUT = {"moved", "moved_cold", "moved_dark", "moved_warm", "love_separated", "love_together", "renamed",
                  "copied", "restored", "grief", "neat_moved", "scary_image", "person_image", "loud_sound",
                  "voice_memo", "scary_near", "soft_image"}

    def feed(self, text, who=None, kind="fact"):
        """Everything the player can overhear or notice. Nothing in here is said to the player."""
        if not text:
            return
        self.state.setdefault("feed", []).append({"t": time.time(), "who": who or "", "text": text, "kind": kind})
        self.state["feed"] = self.state["feed"][-300:]
        self.whispers.append((who or "", text))
        if len(self.whispers) > 40:
            self.whispers = self.whispers[-30:]

    def whisper(self, c, text):
        self.feed(text)

    def react(self, c, cat, extra=None, diary=True):
        """Something happened to c. Record the fact; let them talk about it with whoever is near."""
        m = c["mem"]
        ctx = {"name": c["name"], "place": c.get("location") or "somewhere",
               "image": m["images"][-1][0] if m["images"] else "a picture",
               "song": m["songs"][-1][0] if m["songs"] else "a sound",
               "file": (m["files_read"][-1] if m["files_read"] else "a file"),
               "lost": m["lost"][-1] if m["lost"] else "someone",
               "love": self.char(c["loves"])["name"] if c.get("loves") and self.char(c["loves"]) else "the one they love",
               "other": "someone", "oldname": c["name"], "newname": c["name"], "folder": "its folder"}
        for k in ("scary_image", "soft_image", "person_image"):
            if m.get(k) and cat == k:
                ctx["image"] = m[k][0]
        if cat == "loud_sound" and m.get("loud_song"):
            ctx["song"] = m["loud_song"][0]
        if cat == "voice_memo" and m.get("voice_memo"):
            ctx["song"] = m["voice_memo"][0]
        ctx.update({k: v for k, v in (extra or {}).items() if v is not None})
        tmpl = self.FACTS.get(cat)
        if not tmpl:
            return None
        try:
            fact = tmpl.format(**ctx)
        except (KeyError, IndexError):
            return None
        self.feed(fact)
        if diary:
            self.diary(c, fact)
        self.state.setdefault("news", []).append({"t": time.time(), "who": c["id"], "text": fact})
        self.state["news"] = self.state["news"][-40:]
        if cat in self.TALK_ABOUT:
            witness = self.nearest_other(c)
            self.want_talk(c, witness, fact)
        return fact

    def nearest_other(self, c):
        others = [o for o in self.alive() if o["id"] != c["id"]]
        if not others:
            return None
        here = [o for o in others if o.get("place_rel") == c.get("place_rel")]
        pool = here or others
        return max(pool, key=lambda o: self.rel(c, o)["close"] + self.rng.random() * 3)

    def want_talk(self, a, b, fact):
        """Ask for a conversation about something that just changed (the AI writes it)."""
        q = self.state.setdefault("talk_queue", [])
        for item in q:
            if item["a"] == a["id"] and item.get("b") == (b["id"] if b else None):
                item["facts"] = (item["facts"] + [fact])[-5:]
                return
        q.append({"a": a["id"], "b": b["id"] if b else None, "facts": [fact], "t": time.time()})
        self.state["talk_queue"] = q[-6:]

    def diary(self, c, text):
        if not c.get("path"):
            return
        rel = c["path"] + "/Diary.txt"
        if not self.exists(rel):
            self.write(rel, "%s's Diary\n(Everything I remember. You can read it. You can write in it, too.)\n\n" % c["name"])
        self.append(rel, "[%s] %s\n" % (T.stamp(), text))
        c["diary_n"] = c.get("diary_n", 0) + 1

    # ------------------------------------------------------------ likes / fears / places
    def likes(self, c):
        r = self.rules.get(c["id"], {})
        return list(dict.fromkeys(c["base_likes"] + sorted(r.get("likes", []))))

    def fears(self, c):
        r = self.rules.get(c["id"], {})
        return list(dict.fromkeys(c["base_fears"] + sorted(r.get("fears", []))))

    def place_info(self, rel_dir):
        name = self.place_name(rel_dir).lower()
        temp, light, feel = 0, 0, None
        for key, t, l, f in PLACE_KEYS:
            if key in name:
                temp, light, feel = t, l, f
                break
        pr = self.place_rules.get(rel_dir)
        if pr:
            temp += pr.get("temp", 0)
            light += pr.get("light", 0)
            if pr.get("feel"):
                feel = pr["feel"]
        if not feel:
            feel = "It's a place called %s. It's quiet." % self.place_name(rel_dir)
        return {"temp": temp, "light": light, "feel": feel}

    # ------------------------------------------------------------ body sync (soul -> folder)
    def stats_text(self, c):
        s = c["soul"]
        loves = []
        for oid, r in c["rel"].items():
            if r["love"] >= 35:
                o = self.char(oid)
                if o:
                    word = "very much" if r["love"] >= 80 else ("yes" if r["love"] >= 60 else "a little")
                    loves.append("%s (%s)" % (o["name"], word))
        lines = [
            c["name"].upper(),
            "(This file is %s. You can change it. Just write in plain English.)" % c["name"],
            "",
            "Happiness: %d" % s["happiness"],
            "Fear: %d" % s["fear"],
            "Anger: %d" % s["anger"],
            "Trust: %d" % s["trust"],
            "Corruption: %d" % s["corruption"],
            "Age: %d" % c["age"],
            "Body: %s" % self.body_state(c),
            "Where: %s" % (c.get("location") or "?"),
            "Likes: %s" % (", ".join(self.likes(c)) or "nothing yet"),
            "Fears: %s" % (", ".join(self.fears(c)) or "nothing yet"),
            "Loves: %s" % (", ".join(loves) or "nobody yet"),
            "Made from: %s" % (", ".join(c["ingredients"]) or "nothing you gave"),
        ]
        if c.get("parents"):
            lines.append("Parents: %s" % ", ".join(c["parents"]))
        lines += ["", "--- Write below this line. %s will read it. ---" % c["name"]]
        lines += c.get("notes", [])
        text = "\n".join(lines) + "\n"
        cor = s["corruption"]
        if cor >= 60:
            text = T.glitch_text(text, (cor - 40) / 80.0)
        return text

    def parse_stats(self, c, text):
        """The player edited Stats.txt in plain English."""
        changed = []
        before, _, after = text.partition("--- Write below this line")
        for line in before.splitlines():
            m = re.match(r"\s*(happiness|fear|anger|trust|corruption)\s*[:=]\s*(-?\d+)", line, re.I)
            if m:
                k, v = m.group(1).lower(), T.clamp(int(m.group(2)))
                if abs(c["soul"][k] - v) >= 1:
                    c["soul"][k] = v
                    changed.append(k)
                continue
            m = re.match(r"\s*age\s*[:=]\s*(\d+)", line, re.I)
            if m:
                a = int(m.group(1))
                if a != c["age"] and 0 < a < 200:
                    c["age"] = a
                    changed.append("age")
                continue
            m = re.match(r"\s*(likes|fears)\s*[:=]\s*(.*)", line, re.I)
            if m:
                key = "base_" + m.group(1).lower()
                vals = [v.strip() for v in m.group(2).split(",") if v.strip()]
                vals = [v for v in vals if v.lower() not in ("nothing yet", "nothing")]
                rulevals = self.rules.get(c["id"], {}).get(m.group(1).lower(), set())
                vals = [v for v in vals if v not in rulevals]
                if vals != c[key]:
                    c[key] = vals[:12]
                    changed.append(m.group(1).lower())
                continue
            m = re.match(r"\s*where\s*[:=]\s*(.+)", line, re.I)
            if m and m.group(1).strip().lower() != (c.get("location") or "").lower():
                dest = self.find_place(m.group(1).strip(), create=True)
                if dest is not None:
                    self.move_char(c, dest, by="file")
                    changed.append("where")
        notes_part = after.split("\n", 1)[1] if "\n" in after else ""
        notes = [ln for ln in notes_part.splitlines() if ln.strip()]
        if notes != c.get("notes", []):
            c["notes"] = notes[:60]
            self.rules_dirty = True
            changed.append("notes")
        if changed:
            self.action("edited_stats", {"char": c["id"], "fields": changed})
            self.story.trigger("stats_edited", c=c, fields=changed)
        return changed

    def body_text(self, c):
        st = self.body_state(c)
        s = c["soul"]
        if st == "scared":
            unit, n = "small. small. ", 12
        elif st == "angry":
            unit, n = "%s IS HERE. THIS IS %s'S SPACE. " % (c["name"].upper(), c["name"].upper()), 60 + int(s["anger"]) * 6
        elif st == "corrupted":
            unit, n = T.glitch_text("this is %s's body. " % c["name"], 0.7), 80
        else:
            unit, n = "This is %s's body. It is made of files. It is warm. " % c["name"], 40
        return ("BODY OF %s\n(This file is the size of %s. It changes when they do.)\n\n" % (
            c["name"].upper(), c["name"])) + unit * n + "\n"

    def sync_body(self, c, force=False):
        if not c.get("path") or not os.path.isdir(self.ab(c["path"])):
            return
        # Player-edited Stats.txt is read before it is rewritten.
        srel = c["path"] + "/Stats.txt"
        cur = self.read(srel)
        known = self.state["hashes"].get(srel)
        if cur is not None and known and _h(cur) != known:
            self.state["hashes"][srel] = _h(cur)
            self.parse_stats(c, cur)
        drel = c["path"] + "/Diary.txt"
        dcur = self.read(drel)
        dknown = self.state["hashes"].get(drel)
        if dcur is not None and dknown and _h(dcur) != dknown:
            self.state["hashes"][drel] = _h(dcur)
            self.rules_dirty = True
            self.story.trigger("diary_written", c=c)
        # name follows soul
        want = self.body_name(c)
        cur_name = self.base(c["path"])
        if cur_name != want:
            target = self.join(self.parent(c["path"]), want)
            if not self.exists(target):
                try:
                    os.rename(self.ab(c["path"]), self.ab(target))
                    self._relocate(c["path"], target)
                    c["path"] = target
                    self.souls[c["id"]] = [target]
                    self.dirty_tree = True
                except OSError:
                    pass
        if srel not in self.open_files:
            text = self.stats_text(c)
            if force or self.state["hashes"].get(c["path"] + "/Stats.txt") != _h(text):
                self.write(c["path"] + "/Stats.txt", text)
        brel = c["path"] + "/Body.txt"
        bt = self.body_text(c)
        if force or self.state["hashes"].get(brel) != _h(bt):
            self.write(brel, bt)
        if not self.exists(c["path"] + "/" + SOUL):
            try:
                with open(self.ab(c["path"] + "/" + SOUL), "w", encoding="utf-8") as f:
                    f.write(c["id"])
                media.hide_file(self.ab(c["path"] + "/" + SOUL))
            except OSError:
                pass

    def _relocate(self, old, new):
        """Keep ingredient paths, memories and hashes pointing at moved things."""
        self.path_aliases[old] = new
        if len(self.path_aliases) > 400:
            for k in list(self.path_aliases)[:200]:
                self.path_aliases.pop(k, None)

        def fix(p):
            if p == old:
                return new
            if p and p.startswith(old + "/"):
                return new + p[len(old):]
            return p
        for ing in self.state["ingredients"].values():
            ing["rel"] = fix(ing["rel"])
        for c in self.alive():
            if c.get("path"):
                c["path"] = fix(c["path"])
            m = c["mem"]
            for key in ("images", "songs"):
                for item in m[key]:
                    item[1] = fix(item[1])
            for key in ("scary_image", "soft_image", "person_image", "voice_memo", "loud_song"):
                if m.get(key):
                    m[key][1] = fix(m[key][1])
            m["ingredient_paths"] = [fix(p) for p in m.get("ingredient_paths", [])]
        self.state["generated"] = [fix(p) for p in self.state["generated"]]
        self.state["hashes"] = {fix(k): v for k, v in self.state["hashes"].items()}
        self.open_files = {fix(p) for p in self.open_files}

    # ------------------------------------------------------------ rules (files are the code)
    def text_files_for_rules(self):
        out = []
        for rel, e in self.snapshot.items():
            if e["d"] or T.kind_of(rel) != "word":
                continue
            if rel.startswith(LOGS + "/") or rel.startswith(SYSTEM + "/"):
                continue
            b = self.base(rel).lower()
            if b in ("chat.txt", "body.txt", "stats.txt", "how to play.txt", "talking_to_the_files.txt") or b.startswith("conversation_with_"):
                continue
            if b.startswith("note - "):
                continue
            out.append(rel)
        return out

    def parse_rules(self):
        rules = {c["id"]: {"likes": set(), "fears": set(), "immortal": False, "mood": {},
                           "love": set(), "goto": None, "age": None} for c in self.alive()}
        place_rules, room_rules = {}, {}
        names = []
        for c in self.alive():
            for nm in [c["name"]] + c.get("aliases", []):
                names.append((nm.lower(), c["id"]))
        names.sort(key=lambda x: -len(x[0]))
        everyone = [c["id"] for c in self.alive()]
        sources = []
        for rel in self.text_files_for_rules():
            text = self.read(rel, 60000) or ""
            owner = self.owner_char(rel)
            sources.append((rel, text, owner["id"] if owner else None))
        for c in self.alive():
            if c.get("notes"):
                sources.append((c["path"] + "/Stats.txt", "\n".join(c["notes"]), c["id"]))
        speed = None
        for rel, text, owner in sources:
            folder = self.parent(rel)
            fname = self.base(rel).lower()
            room_of = None
            m = re.match(r"(.+?)['’]s room", fname)
            if m:
                rc = self.char_by_name(m.group(1).strip())
                if rc:
                    room_of = rc["id"]
            for raw in text.splitlines():
                line = raw.strip().lower().rstrip(".!")
                if not line:
                    continue
                sm = re.match(r"time speed\s*[:=]\s*([\d.]+)", line)
                if sm:
                    speed = float(sm.group(1))
                    continue
                # places: "it is warm here"
                pm = re.match(r"(?:it is|it's|its|this place is|here it is|this room is)\s+(?:very\s+)?(\w+)(?: here)?$", line)
                if pm and pm.group(1) in PLACE_WORDS:
                    t, l = PLACE_WORDS[pm.group(1)]
                    if room_of:
                        room_rules[room_of] = room_rules.get(room_of, 0) + t + l
                    elif owner:
                        room_rules[owner] = room_rules.get(owner, 0) + t + l
                    elif self.is_place_dir(folder):
                        pr = place_rules.setdefault(folder, {"temp": 0, "light": 0})
                        pr["temp"] += t
                        pr["light"] += l
                        pr["feel"] = raw.strip()
                    continue
                subjects, rest = [], None
                for nm, cid in names:
                    if line.startswith(nm + " ") or line.startswith(nm + "'s ") or line == nm:
                        subjects, rest = [cid], line[len(nm):].strip()
                        break
                if not subjects:
                    for word in ("everyone", "everybody", "all of them", "they all"):
                        if line.startswith(word + " "):
                            subjects, rest = everyone, line[len(word):].strip()
                            break
                if not subjects:
                    for word in ("nobody", "no one", "noone"):
                        if line.startswith(word + " can die") or line.startswith(word + " dies"):
                            for cid in everyone:
                                rules[cid]["immortal"] = True
                            break
                if not subjects and owner and (line.startswith("i ") or line.startswith("i'm ") or line.startswith("i am ")):
                    subjects = [owner]
                    rest = re.sub(r"^i('m| am)\s+", "is ", line)
                    rest = re.sub(r"^i\s+", "", rest)
                    rest = re.sub(r"^(like|love|fear|hate)\b", lambda m: m.group(1) + "s", rest)
                    rest = rest.replace("can't", "cannot")
                if not subjects and owner and fname not in ("diary.txt",):
                    # lines in a person's own files with no name are about them
                    if re.match(r"(likes|loves|fears|hates|is |cannot|can't|goes to|lives in)", line):
                        subjects, rest = [owner], line
                if not subjects or rest is None:
                    continue
                for cid in subjects:
                    self._apply_rule(rules[cid], rest, cid)
        self.rules = rules
        self.place_rules = place_rules
        self.room_rules = room_rules
        if speed is not None:
            self.state["time_speed"] = max(0.1, min(1440.0, speed))
        self.rules_dirty = False
        # goto rules are edge-triggered
        prev = self.state.setdefault("goto_seen", {})
        for cid, r in rules.items():
            g = r.get("goto")
            if g and prev.get(cid) != g:
                c = self.char(cid)
                dest = self.find_place(g, create=True)
                if c and dest is not None and dest != c.get("place_rel"):
                    self.move_char(c, dest, by="file")
            prev[cid] = g
        for cid, r in rules.items():
            c = self.char(cid)
            if not c:
                continue
            if r["age"]:
                c["age"] = r["age"]
            for oid in r["love"]:
                o = self.char(oid)
                if o and o["id"] != cid:
                    rr = self.rel(c, o)
                    rr["love"] = max(rr["love"], 70)
            if r["immortal"] and not c["flags"].get("immortal_seen"):
                c["flags"]["immortal_seen"] = True
                self.story.trigger("cannot_die", c=c)

    def _apply_rule(self, r, rest, cid):
        rest = rest.strip()
        rest = re.sub(r"^'s\s+", "", rest)
        m = re.match(r"(?:likes|loves|adores|enjoys|really likes)\s+(.+)", rest)
        if m:
            obj = m.group(1).strip()
            target = self.char_by_name(obj)
            if target and rest.startswith("loves"):
                r["love"].add(target["id"])
            else:
                r["likes"].add(obj)
            return
        m = re.match(r"(?:is scared of|is afraid of|is frightened of|fears|hates|is terrified of)\s+(.+)", rest)
        if m:
            r["fears"].add(m.group(1).strip())
            return
        if re.match(r"(cannot|can't|can not|will not|won't|will never|does not|doesn't|never) die", rest) or rest in ("is immortal", "lives forever", "is forever"):
            r["immortal"] = True
            return
        m = re.match(r"(?:goes to|lives in|moves to|is in|is at|stays in|walks to)\s+(?:the\s+)?([\w ]+)", rest)
        if m:
            r["goto"] = m.group(1).strip()
            return
        m = re.match(r"is (\d+)(?: years old)?$", rest)
        if m:
            r["age"] = int(m.group(1))
            return
        m = re.match(r"is (?:very |really |so )?(\w+)", rest)
        if m:
            w = m.group(1)
            moods = {
                "happy": ("happiness", 85), "glad": ("happiness", 80), "joyful": ("happiness", 90),
                "sad": ("happiness", 20), "unhappy": ("happiness", 20), "depressed": ("happiness", 10),
                "scared": ("fear", 80), "afraid": ("fear", 80), "terrified": ("fear", 95),
                "brave": ("fear", 5), "calm": ("fear", 10), "fearless": ("fear", 0),
                "angry": ("anger", 80), "furious": ("anger", 95), "mad": ("anger", 75),
                "peaceful": ("anger", 0), "gentle": ("anger", 3), "kind": ("anger", 3),
                "corrupt": ("corruption", 85), "corrupted": ("corruption", 85), "broken": ("corruption", 70),
                "clean": ("corruption", 0), "pure": ("corruption", 0), "healed": ("corruption", 0),
                "trusting": ("trust", 90), "loyal": ("trust", 90), "suspicious": ("trust", 15),
                "lonely": ("happiness", 30), "safe": ("fear", 5), "loved": ("happiness", 85),
            }
            if w in moods:
                k, v = moods[w]
                r["mood"][k] = v

    def find_place(self, name, create=False):
        n = name.strip().lower()
        if n in ("mess", "home") and n == "mess":
            return ""
        best = None
        for rel, e in self.snapshot.items():
            if e["d"] and self.base(rel).lower() == n and self.is_place_dir(rel):
                if best is None or rel.count("/") < best.count("/"):
                    best = rel
        if best is not None:
            return best
        if create:
            rel = self.join(PLACES, T.safe_name(name.strip().title()))
            try:
                os.makedirs(self.ab(rel), exist_ok=True)
                self.dirty_tree = True
                return rel
            except OSError:
                return None
        return None

    # ------------------------------------------------------------ moving people (the game's own hand)
    def move_char(self, c, dest_rel, by="self"):
        if not c.get("path") or dest_rel == c.get("place_rel"):
            return False
        if not os.path.isdir(self.ab(dest_rel)):
            return False
        target = self.join(dest_rel, self.base(c["path"]))
        if self.exists(target):
            return False
        try:
            os.rename(self.ab(c["path"]), self.ab(target))
        except OSError:
            return False
        old_place = c.get("location")
        self._relocate(c["path"], target)
        c["path"] = target
        self.souls[c["id"]] = [target]
        c["place_rel"] = dest_rel
        c["location"] = self.place_name(dest_rel)
        self.dirty_tree = True
        self.action("char_moved_" + by, {"char": c["id"], "from": old_place, "to": c["location"]})
        if by == "self":
            self.diary(c, "I moved myself from %s to %s." % (old_place, c["location"]))
        elif by == "file":
            self.react(c, "moved", {"place": c["location"]})
        return True

    # ------------------------------------------------------------ ingredients
    def ingredient_eligible(self, rel):
        k = T.kind_of(rel)
        if not k:
            return False
        if rel in self.state["generated"]:
            return False
        for pre in (SYSTEM + "/", WORLD + "/", LOGS + "/"):
            if rel.startswith(pre):
                return False
        b = self.base(rel).lower()
        if "/" not in rel and (b in ROOT_KEEP or b.startswith("note - ")):
            return False
        owner = self.owner_char(rel)
        if owner and (b in GAME_FILES or b.startswith("conversation_with_") or b.startswith("gift")):
            return False
        if b.startswith("conversation_with_") or b.startswith("gift"):
            return False
        return True

    def register_ingredient(self, rel, tk_pixels=None):
        for ing in self.state["ingredients"].values():
            if ing["rel"] == rel and not ing.get("deleted"):
                return ing
        if tk_pixels is None and T.kind_of(rel) == "image" and not media.HAVE_PIL and self.pixel_reader:
            try:
                tk_pixels = self.pixel_reader(self.ab(rel))
            except Exception:
                tk_pixels = None
        a = media.analyse(self.ab(rel), self.base(rel), tk_pixels)
        if not a:
            return None
        content = a.pop("content", None)
        iid = uuid.uuid4().hex[:10]
        ing = {"id": iid, "rel": rel, "name": self.base(rel), "kind": a["kind"], "a": a,
               "added": time.time(), "used_by": None, "deleted": False}
        self.state["ingredients"][iid] = ing
        self.state["ingredient_order"].append(iid)
        self.state["total_added"] += 1
        # keep a copy so that someone who loved it can bring it back
        try:
            if a["kind"] == "word" and content is not None:
                self.write(SYSTEM + "/backups/files/%s.txt" % iid, content, track=False)
            elif os.path.getsize(self.ab(rel)) < 25 * 1024 * 1024:
                shutil.copy2(self.ab(rel), self.ab(SYSTEM + "/backups/files/%s%s" % (iid, T.ext_of(rel))))
        except OSError:
            pass
        self.action("file_added", {"name": ing["name"], "kind": ing["kind"]})
        if ing["kind"] == "image" and self.ai.can_see():
            self.ai.look(ing)
        return ing

    def unused_ingredients(self):
        out = []
        for iid in self.state["ingredient_order"]:
            ing = self.state["ingredients"].get(iid)
            if ing and not ing["used_by"] and not ing["deleted"] and self.exists(ing["rel"]):
                out.append(ing)
        return out

    def active_count(self):
        return sum(1 for i in self.state["ingredients"].values() if not i["deleted"])

    def check_births(self, reason="present"):
        st = self.state
        unused = self.unused_ingredients()
        if not st["bob"] and len(unused) >= 5:
            ings = unused[:5]
            c = self.make_character("Bob", "bob", ings)
            st["bob"] = c["id"]
            self.story.trigger("born_bob", c=c, ings=ings)
            return c
        if st["bob"] and not st["alice"] and st["total_added"] >= 10 and len(unused) >= 5:
            ings = unused[-5:]
            c = self.make_character("Alice", "alice", ings)
            st["alice"] = c["id"]
            self.story.trigger("born_alice", c=c, ings=ings)
            return c
        return None

    def spawn_random(self, why="gone"):
        unused = self.unused_ingredients()
        if len(unused) < 5 or not self.state["alice"]:
            return None
        # five that sit together if possible, otherwise the oldest five
        by_folder = {}
        for ing in unused:
            by_folder.setdefault(self.parent(ing["rel"]), []).append(ing)
        group = max(by_folder.values(), key=len)
        ings = group[:5] if len(group) >= 5 else unused[:5]
        sc = {"scary": 0, "soft": 0, "angry": 0, "sad": 0}
        imgs = 0
        for i in ings:
            for k in sc:
                sc[k] += i["a"].get("scores", {}).get(k, 0)
            imgs += i["kind"] == "image"
        total = sum(sc.values())
        if total <= 1:
            voice = "hollow"
        elif sc["angry"] >= max(sc["scary"], sc["soft"]) and sc["angry"] > 0:
            voice = "feral"
        elif sc["scary"] > sc["soft"]:
            voice = "nervous"
        elif imgs >= 3:
            voice = "dreamer"
        else:
            voice = "gentle"
        used = {c["name"] for c in self.alive()} | {c["name"] for c in self.state["dead"].values()}
        name = None
        for i in ings:
            for w in T.name_words(i["name"]):
                cap = w.capitalize()
                if cap in T.NAME_POOL and cap not in used:
                    name = cap
                    break
            if name:
                break
        if not name:
            seed = int(hashlib.md5("".join(i["id"] for i in ings).encode()).hexdigest()[:6], 16)
            pool = [n for n in T.NAME_POOL if n not in used] or [n + " II" for n in T.NAME_POOL]
            name = pool[seed % len(pool)]
        place = self.parent(ings[0]["rel"])
        if not self.is_place_dir(place):
            place = CHARS
        c = self.make_character(name, voice, ings, place_rel=place, silent=True)
        finder = None
        others = [o for o in self.alive() if o["id"] != c["id"]]
        if others:
            finder = min(others, key=lambda o: 0 if o.get("place_rel") == place else 1)
        self.story.trigger("born_random", c=c, ings=ings, finder=finder, why=why)
        return c

    def spawn_child(self, a, b):
        names_used = {c["name"] for c in self.alive()} | {c["name"] for c in self.state["dead"].values()}
        pool = [n for n in T.CHILD_NAMES if n not in names_used] or [n + " Jr" for n in T.CHILD_NAMES]
        name = pool[int(time.time()) % len(pool)]
        school = self.find_place("School")
        if school is None:
            school = self.join(PLACES, "School")
            os.makedirs(self.ab(school), exist_ok=True)
            self.write(school + "/About School.txt",
                       "School\nWe made this so the little ones have somewhere to learn.\nIt is bright here.\n")
            self.gen(school + "/About School.txt")
            self.state["places_built"].append("School")
            self.dirty_tree = True
            self.snapshot[school] = {"d": 1, "s": 0, "m": time.time(), "i": 0}
        ings = []
        c = self.make_character(name, "child", ings, place_rel=school, age=6,
                                parents=[a["name"], b["name"]], silent=True)
        c["base_likes"] = list(dict.fromkeys(self.likes(a)[:2] + self.likes(b)[:2]))
        c["base_fears"] = list(dict.fromkeys(self.fears(a)[:1] + self.fears(b)[:1]))
        c["mem"]["vocab"] = (a["mem"]["vocab"][:4] + b["mem"]["vocab"][:4])
        c["ingredients"] = []
        for p in (a, b):
            r = self.rel(c, p)
            r["close"] = 80
            r2 = self.rel(p, c)
            r2["close"] = 80
        self.sync_body(c, force=True)
        return c

    # ------------------------------------------------------------ change processing
    def process_changes(self, old, old_souls, new, new_souls, offline=False):
        now = time.time()
        old_souls = {k: list(v) for k, v in old_souls.items()}
        new_souls = {k: list(v) for k, v in new_souls.items()}
        handled_dirs = set()
        # 1) people (folders with a soul)
        for sid, opaths in old_souls.items():
            npaths = list(new_souls.get(sid, []))
            c = self.state["chars"].get(sid)
            if not c:
                continue
            if not npaths:
                handled_dirs.update(opaths)
                self.on_char_deleted(c, offline=offline)
                continue
            op = opaths[0]
            if op in npaths:
                main = op
            else:
                main = npaths[0]
            for extra in npaths:
                if extra != main:
                    self.on_char_copied(c, extra)
                    handled_dirs.add(extra)
            if main != op:
                handled_dirs.update([op, main])
                self.on_char_moved(c, op, main, offline=offline)
        for sid, npaths in new_souls.items():
            if sid in old_souls:
                continue
            if sid in self.state["dead"]:
                self.on_char_restored(sid, npaths[0])
                handled_dirs.update(npaths)
            elif sid in self.state["chars"]:
                c = self.state["chars"][sid]
                if c.get("path") not in npaths:
                    c["path"] = npaths[0]
        for sid in list(new_souls):
            if sid in self.souls and sid not in old_souls:
                pass
        merged = dict(new_souls)
        for sid, paths in self.souls.items():
            if sid in self.state["chars"] and sid not in merged:
                merged[sid] = paths
        self.souls = merged
        self.refresh_char_paths()
        # 2) plain files and place folders
        removed = {r: e for r, e in old.items() if r not in new}
        added = {r: e for r, e in new.items() if r not in old}
        moved = []
        by_ino = {}
        for r, e in added.items():
            if e.get("i"):
                by_ino.setdefault((e["i"], e["d"], e["s"] if not e["d"] else 0), []).append(r)
        for r, e in list(removed.items()):
            key = (e.get("i"), e["d"], e["s"] if not e["d"] else 0)
            if e.get("i") and key in by_ino and by_ino[key]:
                dst = by_ino[key].pop(0)
                moved.append((r, dst, e["d"]))
                removed.pop(r)
                added.pop(dst, None)
        # folders moved: move what was under them too
        dir_moves = [(a, b) for a, b, d in moved if d]
        def under_moved(r, side):
            for a, b in dir_moves:
                base = a if side == 0 else b
                if r.startswith(base + "/"):
                    return True
            return False
        for a, b in dir_moves:
            for r in list(removed):
                if r.startswith(a + "/"):
                    removed.pop(r)
            for r in list(added):
                if r.startswith(b + "/"):
                    added.pop(r)
        for a, b, d in moved:
            if d:
                if a in handled_dirs or b in handled_dirs:
                    self._relocate(a, b)
                    continue
                self.on_dir_moved(a, b)
            else:
                if under_moved(a, 0):
                    continue
                self.on_file_moved(a, b, offline)
        dead_paths = [c.get("path") for c in self.state["dead"].values() if c.get("path")]
        for r, e in removed.items():
            if any(r == p or r.startswith(p + "/") for p in handled_dirs):
                continue
            if any(r.startswith(p + "/") for p in dead_paths if p):
                continue
            if e["d"]:
                self.action("folder_deleted", {"name": self.base(r)})
            else:
                self.on_file_deleted(r, offline)
        for r, e in sorted(added.items()):
            if any(r == p or r.startswith(p + "/") for p in handled_dirs):
                continue
            if e["d"]:
                self.on_dir_added(r)
            else:
                self.on_file_added(r)
        for r, e in new.items():
            o = old.get(r)
            if o and not e["d"] and (o["s"] != e["s"] or abs(o["m"] - e["m"]) > 0.001):
                self.on_file_modified(r)

    def on_char_moved(self, c, old, new, offline=False):
        c["path"] = new
        old_place = self.place_name(self.parent(old))
        new_parent = self.parent(new)
        renamed = self.base(old) != self.base(new)
        moved = self.parent(old) != new_parent
        self._relocate(old, new)
        c["path"] = new
        if renamed:
            expected = self.body_name(c)
            if self.base(new) != expected:
                oldname = c["name"]
                newname = T.clean_char_name(self.base(new))
                if newname.lower() != oldname.lower():
                    c["name"] = newname
                    c.setdefault("aliases", [])
                    if oldname not in c["aliases"]:
                        c["aliases"].append(oldname)
                    c["flags"]["renamed_from"] = oldname
                    c.pop("returned_suffix", None)
                    self.action("char_renamed", {"char": c["id"], "from": oldname, "to": newname})
                    self.react(c, "renamed", {"oldname": oldname, "newname": newname})
                    self.story.trigger("renamed", c=c, old=oldname, new=newname)
                    for o in self.alive():
                        if c["id"] in o["rel"]:
                            o["rel"][c["id"]]["name"] = newname
                    self.rules_dirty = True
                else:
                    c.pop("returned_suffix", None)
                # make sure folder shows what the soul looks like (rename will happen in sync)
        if moved:
            owner = self.owner_char(new_parent) if new_parent else None
            c["place_rel"] = new_parent
            c["location"] = self.place_name(new_parent)
            if owner and owner["id"] != c["id"]:
                # a person was put inside a person. People are not places.
                line = "%s was put inside %s. A person is not a place. %s climbed out." % (c["name"], owner["name"], c["name"])
                self.feed(line)
                self.diary(c, line)
                self.move_char(c, self.parent(owner["path"]), by="self")
                return
            c["last_player_move"] = time.time()
            c["player_moves"] = [t for t in c["player_moves"] if time.time() - t < 600] + [time.time()]
            self.action("char_moved", {"char": c["id"], "from": old_place, "to": c["location"]})
            info = self.place_info(new_parent)
            if c.get("loves") and self.char(c["loves"]) and self.char(c["loves"]).get("place_rel") != new_parent:
                cat = "love_separated"
                self.story.trigger("separated", c=c, other=self.char(c["loves"]))
            elif c.get("loves") and self.char(c["loves"]) and self.char(c["loves"]).get("place_rel") == new_parent:
                cat = "love_together"
            elif info["temp"] <= -2:
                cat = "moved_cold"
            elif info["light"] <= -2:
                cat = "moved_dark"
            elif info["temp"] >= 2:
                cat = "moved_warm"
            else:
                cat = "moved"
            if not offline:
                self.react(c, cat, {"place": c["location"]})
            else:
                self.diary(c, "While the game was closed, you moved me to %s." % c["location"])
            self.state["player"]["cruelty"] += 1 + 2 * (len(c["player_moves"]) > 2)
            c["soul"]["fear"] = T.clamp(c["soul"]["fear"] + 2 + 3 * (len(c["player_moves"]) > 2))
            c["soul"]["trust"] = T.clamp(c["soul"]["trust"] - (2 if len(c["player_moves"]) > 2 else 0))
            if len(c["player_moves"]) >= 3:
                self.story.trigger("moved_too_much", c=c)
            self.story.trigger("arrived_place", c=c, place=c["location"], info=info)

    def on_char_copied(self, c, path):
        new_id = uuid.uuid4().hex[:12]
        try:
            with open(self.ab(path + "/" + SOUL), "w", encoding="utf-8") as f:
                f.write(new_id)
        except OSError:
            return
        twin = json.loads(json.dumps(c))
        twin["id"] = new_id
        twin["name"] = T.clean_char_name(self.base(path))
        if twin["name"].lower() == c["name"].lower():
            twin["name"] = c["name"] + " Two"
        twin["path"] = path
        twin["place_rel"] = self.parent(path)
        twin["location"] = self.place_name(twin["place_rel"])
        twin["born"] = time.time()
        twin["flags"] = {"copy_of": c["name"]}
        twin["pending"] = []
        twin["rel"] = {k: dict(v) for k, v in c["rel"].items()}
        twin["soul"]["fear"] = T.clamp(twin["soul"]["fear"] + 15)
        twin["soul"]["corruption"] = T.clamp(twin["soul"]["corruption"] + 8)
        self.state["chars"][new_id] = twin
        self.souls[new_id] = [path]
        for x, y in ((c, twin), (twin, c)):
            r = self.rel(x, y)
            r["close"] = 50
            r["chem"] = 0.25
            r["twin"] = True
        c["soul"]["fear"] = T.clamp(c["soul"]["fear"] + 10)
        self.action("char_copied", {"char": c["id"], "copy": new_id})
        self.react(c, "copied")
        self.react(twin, "copied")
        self.story.trigger("copied", c=c, twin=twin)
        self.rules_dirty = True

    def on_char_deleted(self, c, offline=False):
        r = self.rules.get(c["id"], {})
        if r.get("immortal") and self.restore_from_backup(c):
            self.action("char_deleted_but_returned", {"char": c["id"]})
            self.story.trigger("returned", c=c)
            return
        cid = c["id"]
        self.state["chars"].pop(cid, None)
        c["died"] = time.time()
        c["died_sim"] = self.state["sim_min"]
        self.state["dead"][cid] = c
        p = self.state["player"]
        p["cruelty"] += 25
        p["deleted"].append(c["name"])
        self.action("char_deleted", {"char": cid, "name": c["name"]})
        self.check_promises("deleted " + c["name"])
        for o in self.alive():
            rr = o["rel"].get(cid)
            o["mem"]["deleted"].append(c["name"])
            if rr and (rr["close"] >= 15 or rr["love"] >= 30):
                o["mem"]["lost"].append(c["name"])
                o["soul"]["happiness"] = T.clamp(o["soul"]["happiness"] - 15 - rr["love"] / 5)
                o["soul"]["trust"] = T.clamp(o["soul"]["trust"] - 15)
                o["soul"]["fear"] = T.clamp(o["soul"]["fear"] + 10)
                if o.get("loves") == cid:
                    o["loves"] = None
                self.react(o, "grief", {"lost": c["name"]})
        self.story.trigger("deleted_char", c=c)
        self.rules_dirty = True

    def restore_from_backup(self, c):
        src = self.ab(SYSTEM + "/backups/" + c["id"])
        if not os.path.isdir(src):
            return False
        c["returned_suffix"] = True
        dest = self.unique(CHARS, self.body_name(c))
        try:
            shutil.copytree(src, self.ab(dest))
            with open(self.ab(dest + "/" + SOUL), "w", encoding="utf-8") as f:
                f.write(c["id"])
            media.hide_file(self.ab(dest + "/" + SOUL))
        except OSError:
            return False
        c["path"] = dest
        c["place_rel"] = CHARS
        c["location"] = "Characters"
        self.souls[c["id"]] = [dest]
        c["soul"]["fear"] = T.clamp(c["soul"]["fear"] + 25)
        c["soul"]["corruption"] = T.clamp(c["soul"]["corruption"] + 12)
        c["soul"]["trust"] = T.clamp(c["soul"]["trust"] - 20)
        self.react(c, "restored", {"newname": self.base(dest)})
        self.dirty_tree = True
        return True

    def on_char_restored(self, sid, path):
        c = self.state["dead"].pop(sid)
        c["path"] = path
        c["place_rel"] = self.parent(path)
        c["location"] = self.place_name(c["place_rel"])
        self.state["chars"][sid] = c
        c["soul"]["fear"] = T.clamp(c["soul"]["fear"] + 20)
        c["soul"]["corruption"] = T.clamp(c["soul"]["corruption"] + 10)
        self.action("char_restored", {"char": sid})
        self.react(c, "restored", {"newname": self.base(path)})
        for o in self.alive():
            if c["name"] in o["mem"]["lost"]:
                o["mem"]["lost"].remove(c["name"])
                o["soul"]["happiness"] = T.clamp(o["soul"]["happiness"] + 15)
        self.story.trigger("restored", c=c)
        self.rules_dirty = True

    def on_dir_moved(self, a, b):
        self._relocate(a, b)
        self.action("folder_moved", {"from": a, "to": b})
        if self.base(a) != self.base(b):
            for c in self.alive():
                if c.get("path", "").startswith(b + "/") and self.parent(c["path"]) == b:
                    line = "The place %s is called %s now." % (self.base(a), self.base(b))
                    self.whisper(c, line)
                    self.diary(c, line)
        self.refresh_char_paths()
        self.rules_dirty = True

    def on_dir_added(self, r):
        if self.owner_char(r):
            owner = self.owner_char(r)
            if owner and r != owner["path"]:
                # a folder inside a person: that isn't a piece of them. It gets put down outside.
                dest = self.unique(owner.get("place_rel", ""), self.base(r))
                try:
                    os.rename(self.ab(r), self.ab(dest))
                    line = "A folder, %s, was put inside %s. It wasn't a piece of them, so it was put down outside." % (
                        self.base(r), owner["name"])
                    self.whisper(owner, line)
                    self.diary(owner, line)
                    self.dirty_tree = True
                except OSError:
                    pass
            return
        if self.dir_kind(r) != "place":
            return
        self.action("place_created", {"name": self.base(r)})
        info = self.place_info(r)
        self.feed("A new place appeared: %s. %s" % (self.base(r), info["feel"]))
        self.story.trigger("place_created", rel=r)

    def on_file_moved(self, a, b, offline=False):
        self._relocate(a, b)
        self.action("file_moved", {"from": a, "to": b})
        name = self.base(b)
        k = T.kind_of(name)
        from_neat = any(a.startswith(p + "/") for p in NEAT.values())
        to_neat = any(b.startswith(p + "/") for p in NEAT.values())
        owner_b = self.owner_char(b)
        owner_a = self.owner_char(a)
        ing = next((i for i in self.state["ingredients"].values() if i["rel"] == b), None)
        if owner_b and not owner_a and ing:
            self.give_to(owner_b, ing)
            return
        if k and from_neat and not to_neat:
            for c in self.alive():
                if ing and (ing["used_by"] == c["id"] or name in c["mem"]["seen"]):
                    folder = NEAT_NAME.get(k, "its folder")
                    self.react(c, "neat_moved", {"file": name, "folder": folder})
                    self.story.trigger("neat_moved", c=c, file=name, folder=folder)
                    break

    def give_to(self, c, ing):
        if not ing["used_by"]:
            ing["used_by"] = c["id"]
            c["ingredients"].append(ing["name"])
        self.perceive(c, ing, given=True)
        self.action("gave_file", {"char": c["id"], "name": ing["name"]})

    def on_file_deleted(self, r, offline=False):
        name = self.base(r)
        owner = self.owner_char(r)
        b = name.lower()
        if owner and b in GAME_FILES:
            self.action("deleted_piece", {"char": owner["id"], "file": name})
            self.story.trigger("piece_deleted", c=owner, file=name)
            return
        if r.startswith(LOGS + "/"):
            self.action("deleted_log", {"name": name})
            for c in self.alive():
                if c["name"].lower() in b:
                    line = "The log '%s' was deleted. %s remembers it anyway." % (name, c["name"])
                    self.feed(line)
                    self.diary(c, line)
                    break
            return
        ing = next((i for i in self.state["ingredients"].values() if i["rel"] == r and not i["deleted"]), None)
        self.action("file_deleted", {"name": name})
        self.check_promises("deleted " + name)
        if not ing:
            return
        ing["deleted"] = True
        ing["deleted_at"] = time.time()
        self.state["player"]["deleted"].append(name)
        lover = None
        for c in self.alive():
            if ing["used_by"] == c["id"] or name in c["mem"]["seen"]:
                c["mem"]["deleted"].append(name)
                if ing["used_by"] == c["id"]:
                    lover = c
        if lover:
            lover["soul"]["happiness"] = T.clamp(lover["soul"]["happiness"] - 6)
            line = "%s was deleted. It was part of %s." % (name, lover["name"])
            self.feed(line)
            self.diary(lover, line)
            self.want_talk(lover, self.nearest_other(lover), line)
            self.state["return_queue"].append({"iid": ing["id"], "cid": lover["id"],
                                               "due": self.state["sim_min"] + 20})

    def on_file_added(self, r):
        if r in self.state["generated"]:
            return
        if not self.ingredient_eligible(r):
            return
        if "/" not in r:
            # Mess/ is the drop zone: tidy it later, once the file has finished arriving
            self.pending_sort[r] = None
            return
        ing = self.register_ingredient(r)
        if not ing:
            return
        owner = self.owner_char(r)
        if owner:
            self.give_to(owner, ing)

    def on_file_modified(self, r):
        if T.kind_of(r) == "word":
            self.rules_dirty = True
            ing = next((i for i in self.state["ingredients"].values() if i["rel"] == r), None)
            if ing and r not in self.open_files:
                a = media.analyse(self.ab(r), self.base(r))
                if a:
                    a.pop("content", None)
                    ing["a"] = a

    def check_promises(self, what):
        p = self.state["player"]
        live = [x for x in p["promises"] if time.time() - x["t"] < 7 * 86400]
        if live:
            p["lies"] += 1
            for c in self.alive():
                c["mem"]["lies"] += 1
                c["mem"]["lie_notes"].append("You promised '%s' and then %s." % (live[-1]["text"][:60], what))
                c["soul"]["trust"] = T.clamp(c["soul"]["trust"] - 10)
            p["promises"] = []
            self.story.trigger("lie", what=what)

    # ------------------------------------------------------------ tidying the drop zone
    def sort_drop_zone(self):
        for r in list(self.pending_sort):
            e = self.snapshot.get(r)
            if not e:
                self.pending_sort.pop(r, None)
                continue
            if r in self.open_files:
                continue
            last = self.pending_sort[r]
            if last != e["s"]:
                self.pending_sort[r] = e["s"]      # still arriving
                continue
            self.pending_sort.pop(r, None)
            k = T.kind_of(r)
            folder = NEAT.get(k)
            if not folder:
                continue
            os.makedirs(self.ab(folder), exist_ok=True)
            dest = self.unique(folder, self.base(r))
            try:
                os.rename(self.ab(r), self.ab(dest))
            except OSError:
                continue
            self.register_ingredient(dest)
            what = {"word": "words", "image": "photo", "sound": "sound"}[k]
            note = "Note - moved your %s to %s.txt" % (what, NEAT_NAME[k])
            note_rel = self.unique("", note)
            self.write(note_rel, "Moved your %s to %s/\n\n%s is now in %s.\n(Mess tidies things it can name.)\n" % (
                what, NEAT_NAME[k], self.base(dest), folder))
            self.gen(note_rel)
            self.state["notes"].append(note_rel)
            while len(self.state["notes"]) > 5:
                old = self.state["notes"].pop(0)
                try:
                    os.remove(self.ab(old))
                except OSError:
                    pass
            self.dirty_tree = True

    # ------------------------------------------------------------ perception
    def perceive(self, c, ing, given=False):
        name = ing["name"]
        if name in c["mem"]["seen"] and not given:
            return
        if name not in c["mem"]["seen"]:
            c["mem"]["seen"].append(name)
        a = ing["a"]
        s = c["soul"]
        sc = a.get("scores", {})
        if ing["kind"] == "image":
            c["mem"]["images"].append([name, ing["rel"]])
            if a.get("mood") == "scary":
                c["mem"]["scary_image"] = [name, ing["rel"]]
                s["fear"] = T.clamp(s["fear"] + 12)
                s["corruption"] = T.clamp(s["corruption"] + 3)
                if "the picture " + name not in c["base_fears"]:
                    c["base_fears"].append("the picture " + name)
                self.state["player"]["cruelty"] += 4
                self.react(c, "scary_image")
                self.story.trigger("scary_image", c=c, image=name)
            elif a.get("person"):
                c["mem"]["person_image"] = [name, ing["rel"]]
                s["trust"] = T.clamp(s["trust"] + 2)
                self.react(c, "person_image")
                self.story.trigger("person_image", c=c, image=name)
            elif a.get("mood") == "soft":
                c["mem"]["soft_image"] = [name, ing["rel"]]
                s["happiness"] = T.clamp(s["happiness"] + 8)
                s["fear"] = T.clamp(s["fear"] - 5)
                if a.get("subject") not in (None, "something", "person"):
                    like = a["subject"] + "s"
                    if like not in c["base_likes"]:
                        c["base_likes"].append(like)
                self.state["player"]["kindness"] += 3
                self.react(c, "soft_image")
                self.story.trigger("soft_image", c=c, image=name, subject=a.get("subject"))
            else:
                self.react(c, "new_image")
                self.story.trigger("new_image", c=c, image=name)
        elif ing["kind"] == "sound":
            title = a.get("title", name)
            c["mem"]["songs"].append([title, ing["rel"]])
            if a.get("mood") == "distorted":
                c["mem"]["loud_song"] = [title, ing["rel"]]
                s["corruption"] = T.clamp(s["corruption"] + 10)
                s["anger"] = T.clamp(s["anger"] + 6)
                s["fear"] = T.clamp(s["fear"] + 4)
                self.react(c, "loud_sound")
                self.story.trigger("loud_sound", c=c, song=title)
            elif a.get("mood") == "voice":
                c["mem"]["voice_memo"] = [name, ing["rel"]]
                s["trust"] = T.clamp(s["trust"] + 6)
                self.react(c, "voice_memo")
                self.story.trigger("voice_memo", c=c, memo=name)
            else:
                s["fear"] = T.clamp(s["fear"] - 8)
                s["happiness"] = T.clamp(s["happiness"] + 5)
                like = 'the song "%s"' % title
                if like not in c["base_likes"]:
                    c["base_likes"].append(like)
                self.react(c, "new_sound")
                self.story.trigger("song", c=c, song=title)
        else:
            c["mem"]["files_read"].append(name)
            for w in a.get("vocab", [])[:5]:
                c["mem"]["vocab"].append([w, name])
                if w in T.SCARY_WORDS:
                    c["mem"]["scary_vocab"].append(w)
            c["mem"]["vocab"] = c["mem"]["vocab"][-60:]
            c["mem"]["scary_vocab"] = c["mem"]["scary_vocab"][-30:]
            s["happiness"] = T.clamp(s["happiness"] + sc.get("soft", 0) * 2 - sc.get("sad", 0))
            s["fear"] = T.clamp(s["fear"] + sc.get("scary", 0) * 2)
            s["anger"] = T.clamp(s["anger"] + sc.get("angry", 0) * 2)
            if sc.get("scary", 0) >= 3:
                self.react(c, "scary_near", {"file": name})
                self.story.trigger("scary_text", c=c, file=name)
            else:
                self.react(c, "new_file", {"file": name})
                if len(c["mem"]["scary_vocab"]) >= 3:
                    self.story.trigger("vocab_shift", c=c)

    def perceive_surroundings(self):
        """People see the pictures, hear the sounds and read the words in their folder and their place.
        One new thing at a time, so a gallery is looked at picture by picture."""
        for c in self.alive():
            for ing in self.visible_ingredients(c):
                if ing["name"] not in c["mem"]["seen"] and self.exists(ing["rel"]):
                    self.perceive(c, ing)
                    break

    def visible_ingredients(self, c):
        if not c.get("path"):
            return []
        own, place = c["path"], c.get("place_rel", "")
        out = []
        for ing in self.state["ingredients"].values():
            if ing["deleted"]:
                continue
            p = self.parent(ing["rel"])
            if p == own or p == place:
                out.append(ing)
        return out

    # ------------------------------------------------------------ simulation
    def compat(self, a, b):
        r = self.rel(a, b)
        la, lb = set(x.lower() for x in self.likes(a)), set(x.lower() for x in self.likes(b))
        shared = len(la & lb)
        sa, sb = a["soul"], b["soul"]
        diff = abs(sa["happiness"] - sb["happiness"]) + abs(sa["anger"] - sb["anger"])
        openness = 0.5 + sa["trust"] / 200.0 + sa["happiness"] / 300.0 - sa["anger"] / 300.0
        return max(0.2, min(2.0, r["chem"] * openness * (1 + 0.15 * shared) * (1.2 - diff / 300.0)))

    def step(self, dmin, offline=False):
        st = self.state
        st["sim_min"] += dmin
        people = self.alive()
        for c in people:
            s = c["soul"]
            rules = self.rules.get(c["id"], {})
            info = self.place_info(c.get("place_rel", ""))
            # where you are changes how you feel
            s["fear"] = T.clamp(s["fear"] + (-info["temp"] * 0.05 - info["light"] * 0.05) * dmin)
            s["happiness"] = T.clamp(s["happiness"] + (info["temp"] * 0.04 + info["light"] * 0.02) * dmin)
            room = self.room_rules.get(c["id"], 0)
            if room:
                s["happiness"] = T.clamp(s["happiness"] + room * 0.05 * dmin)
                s["fear"] = T.clamp(s["fear"] - room * 0.05 * dmin)
            if any("dark" in f.lower() for f in self.fears(c)) and info["light"] < 0:
                s["fear"] = T.clamp(s["fear"] + 0.3 * dmin)
            # slow healing towards a resting state
            s["fear"] = T.clamp(s["fear"] - 0.03 * dmin)
            s["anger"] = T.clamp(s["anger"] - 0.04 * dmin)
            s["corruption"] = T.clamp(s["corruption"] - 0.005 * dmin)
            # what's written is true: drift towards it
            for k, target in rules.get("mood", {}).items():
                delta = target - s[k]
                s[k] = T.clamp(s[k] + max(-3 * dmin, min(3 * dmin, delta)))
            # corruption is catching
            if s["corruption"] >= 60:
                for o in people:
                    if o["id"] != c["id"] and o.get("place_rel") == c.get("place_rel"):
                        o["soul"]["corruption"] = T.clamp(o["soul"]["corruption"] + 0.02 * dmin)
        # people together / apart
        for i, a in enumerate(people):
            for b in people[i + 1:]:
                ra, rb = self.rel(a, b), self.rel(b, a)
                together = a.get("place_rel") == b.get("place_rel")
                for x, y, r in ((a, b, ra), (b, a, rb)):
                    noise = 1.0 + (self.rng.random() * 2 - 1) * self.chance()
                    if together:
                        r["together"] += dmin
                        r["apart"] = 0
                        r["close"] = min(100, r["close"] + 1.5 * dmin * noise * self.compat(x, y) * (1 - r["close"] / 130))
                        if r["close"] >= 40 and x["voice"] != "child" and y["voice"] != "child" and not r.get("twin"):
                            r["love"] = min(100, r["love"] + 0.8 * dmin * noise * self.compat(x, y) * (1 - r["love"] / 120))
                    else:
                        r["apart"] += dmin
                        r["together"] = max(0, r["together"] - dmin * 0.2)
                        if r["close"] > 30:
                            x["soul"]["happiness"] = T.clamp(x["soul"]["happiness"] - 0.04 * dmin * (r["close"] / 50))
                        if r["love"] > 50:
                            x["soul"]["happiness"] = T.clamp(x["soul"]["happiness"] - 0.06 * dmin)
                        r["close"] = max(0, r["close"] - 0.01 * dmin)
                if not together and ra["close"] >= 35 and ra["apart"] >= 45:
                    self.story.trigger("missing", c=a, other=b)
                if not together and rb["close"] >= 35 and rb["apart"] >= 45:
                    self.story.trigger("missing", c=b, other=a)
                if together and ra["together"] >= 60 and ra["close"] >= 30:
                    self.story.trigger("closer", a=a, b=b)
        # who loves whom
        for c in people:
            best, bl = None, 0
            for oid, r in c["rel"].items():
                if self.char(oid) and r["love"] >= 60 and r["love"] > bl:
                    best, bl = oid, r["love"]
            if best != c.get("loves"):
                old = c.get("loves")
                c["loves"] = best
                if best:
                    other = self.char(best)
                    mutual = other["rel"].get(c["id"], {}).get("love", 0) >= 60
                    self.story.trigger("love", c=c, other=other, mutual=mutual)
                    if not offline:
                        self.react(c, "love_fall", {"other": other["name"]})
                elif old and self.char(old):
                    self.story.trigger("love_faded", c=c, other=self.char(old))
        # jealousy
        for c in people:
            if c.get("loves"):
                o = self.char(c["loves"])
                if o and o.get("loves") and o["loves"] != c["id"] and self.char(o["loves"]):
                    self.story.trigger("jealous", c=c, other=o, third=self.char(o["loves"]))
        # people do things on their own
        for c in people:
            if st["sim_min"] >= c.get("next_move", 0):
                c["next_move"] = st["sim_min"] + self.rng.uniform(15, 35)
                self.autonomy(c, offline)
            if self.state["sim_min"] - c.get("born_sim", 0) > 30 * 24 * 60 * (c.get("aged", 0) + 1):
                c["aged"] = c.get("aged", 0) + 1
                c["age"] += 1
            if c["voice"] == "child" and self.state["sim_min"] - c.get("born_sim", 0) > 5 * 24 * 60 * (c.get("aged", 0) + 1):
                c["aged"] = c.get("aged", 0) + 1
                c["age"] += 1
        # families
        for i, a in enumerate(people):
            for b in people[i + 1:]:
                if a["voice"] == "child" or b["voice"] == "child" or len(people) >= 12:
                    continue
                if a.get("loves") == b["id"] and b.get("loves") == a["id"]:
                    ra = self.rel(a, b)
                    if ra["love"] >= 80 and self.rel(b, a)["love"] >= 80 and ra["together"] >= 360:
                        self.story.trigger("child", a=a, b=b)
        # files that were loved come back
        for q in list(st["return_queue"]):
            if st["sim_min"] >= q["due"]:
                st["return_queue"].remove(q)
                self.bring_back(q)

    def autonomy(self, c, offline=False):
        """Characters move their own folders: towards love, away from the cold, towards friends."""
        if time.time() - c.get("last_player_move", 0) < 180 and not offline:
            return
        here = c.get("place_rel", "")
        info = self.place_info(here)
        dest, why = None, None
        love = self.char(c["loves"]) if c.get("loves") else None
        if love and love.get("place_rel") != here and love.get("place_rel") is not None:
            if self.is_place_dir(love["place_rel"]):
                dest, why = love["place_rel"], "love"
        elif c["soul"]["fear"] >= 65 and (info["temp"] < 0 or info["light"] < 0):
            warm = [(self.place_info(r)["temp"] + self.place_info(r)["light"], r)
                    for r, e in self.snapshot.items() if e["d"] and self.is_place_dir(r)
                    and not r.startswith(LOGS)]
            warm.sort(reverse=True)
            if warm and warm[0][0] > info["temp"] + info["light"]:
                dest, why = warm[0][1], "warmth"
        else:
            alone = not any(o.get("place_rel") == here for o in self.alive() if o["id"] != c["id"])
            if alone:
                friends = [(r["close"], oid) for oid, r in c["rel"].items() if self.char(oid) and r["close"] >= 35]
                if friends:
                    f = self.char(max(friends)[1])
                    if f.get("place_rel") != here and self.is_place_dir(f.get("place_rel", "")):
                        dest, why = f["place_rel"], "friend"
        if dest is None and self.roll(0.25 * self.chance()):
            options = [r for r, e in self.snapshot.items() if e["d"] and self.is_place_dir(r) and r != here
                       and not r.startswith(LOGS) and r.count("/") <= 2]
            if options:
                dest, why = self.rng.choice(options), "wander"
        if dest is None:
            # sometimes people borrow a file they like and carry it to where they are
            if not offline and self.rng.random() < 0.08:
                self.borrow_file(c)
            return
        if self.move_char(c, dest, by="self"):
            if why == "love":
                self.story.trigger("reunion", c=c, other=love)
                if not offline:
                    self.react(c, "love_fall", {"other": love["name"], "place": c["location"]})
            elif why == "wander":
                self.diary(c, "I went to %s. Nobody told me to. I just wanted to see it." % c["location"])
                self.story.trigger("wandered", c=c, place=c["location"])
            elif why == "warmth":
                self.story.trigger("fled_cold", c=c, place=c["location"])
            else:
                self.story.trigger("sought_friend", c=c, place=c["location"])

    def borrow_file(self, c):
        likes = [x.lower() for x in self.likes(c)]
        here = c.get("place_rel", "")
        for ing in self.state["ingredients"].values():
            if ing["deleted"] or self.parent(ing["rel"]) == here or ing["kind"] != "image":
                continue
            if ing["a"].get("mood") != "soft" and ing["used_by"] != c["id"]:
                continue
            if self.owner_char(ing["rel"]) or not self.is_place_dir(here):
                continue
            if self.parent(ing["rel"]) not in NEAT.values():
                continue
            dest = self.unique(here, ing["name"])
            try:
                os.rename(self.ab(ing["rel"]), self.ab(dest))
            except OSError:
                return
            old = ing["rel"]
            self._relocate(old, dest)
            self.dirty_tree = True
            line = "%s took %s to %s, to have it near them." % (c["name"], ing["name"], c["location"])
            self.whisper(c, line)
            self.diary(c, line)
            self.action("char_borrowed_file", {"char": c["id"], "file": ing["name"]})
            return

    def bring_back(self, q):
        ing = self.state["ingredients"].get(q["iid"])
        c = self.char(q["cid"])
        if not ing or not c:
            return
        stem, ext = os.path.splitext(ing["name"])
        newname = T.safe_name("%s (%s kept this)%s" % (stem, c["name"], ext), 80)
        src_txt = self.ab(SYSTEM + "/backups/files/%s.txt" % ing["id"])
        src_bin = self.ab(SYSTEM + "/backups/files/%s%s" % (ing["id"], ext.lower()))
        dest = self.unique(c.get("place_rel", ""), newname)
        try:
            if ing["kind"] == "word" and os.path.exists(src_txt):
                shutil.copy2(src_txt, self.ab(dest))
            elif os.path.exists(src_bin):
                shutil.copy2(src_bin, self.ab(dest))
            else:
                return
        except OSError:
            return
        self.gen(dest)
        ing["deleted"] = False
        ing["rel"] = dest
        ing["name"] = self.base(dest)
        self.dirty_tree = True
        self.story.trigger("file_returned", c=c, file=self.base(dest), orig=stem + ext)

    # ------------------------------------------------------------ talking between themselves
    def record_conversation(self, a, b, lines, title_prefix="Conversation"):
        key = "-".join(sorted([a["id"], b["id"]]))
        n = a["convo_n"].get(b["id"]) or 1
        text = "".join("[%s] %s: %s\n" % (T.stamp(), sp["name"], ln) for sp, ln in lines)
        for x, y in ((a, b), (b, a)):
            if not x.get("path"):
                continue
            num = x["convo_n"].setdefault(y["id"], 1)
            rel = "%s/Conversation_with_%s_%d.txt" % (x["path"], T.safe_name(y["name"]), num)
            if not self.exists(rel):
                self.write(rel, "Conversation between %s and %s (%d)\n\n" % (x["name"], y["name"], num))
            self.append(rel, text)
        return text

    def new_conversation_session(self, a, b):
        for x, y in ((a, b), (b, a)):
            x["convo_n"][y["id"]] = x["convo_n"].get(y["id"], 0) + 1

    def direct(self):
        """Every so often something happens that nobody caused directly."""
        st = self.state
        if not self.alive():
            return
        if st.get("next_direct") is None:
            st["next_direct"] = st["sim_min"] + self.rng.uniform(15, 40)
        if st["sim_min"] < st["next_direct"]:
            return
        c = self.chance()
        st["next_direct"] = st["sim_min"] + self.rng.uniform(20, 60) * (1.5 - c)
        if self.ai.available:
            self.ai.direct()
        elif self.roll(0.3 + 0.6 * c):
            self.story.spontaneous_fallback()
        # leftovers can wake up even while you're here, if luck says so
        if st["alice"] and len(self.unused_ingredients()) >= 5 and self.roll(0.15 * c):
            self.spawn_random(why="present")

    # ------------------------------------------------------------ AFK
    # ------------------------------------------------------------ talking among themselves
    def record_talk(self, lines, place=None):
        """lines: list of (char, line). Goes to the overheard feed, their conversation files and Logs."""
        if not lines:
            return
        speakers = []
        for sp, ln in lines:
            if sp not in speakers:
                speakers.append(sp)
            self.feed(ln, who=sp["name"], kind="speech")
        text = "".join("[%s] %s: %s\n" % (T.stamp(), sp["name"], ln) for sp, ln in lines)
        if len(speakers) >= 2:
            a, b = speakers[0], speakers[1]
            for x, y in ((a, b), (b, a)):
                if not x.get("path") or not self.exists(x["path"]):
                    continue
                num = x["convo_n"].setdefault(y["id"], 1)
                rel = "%s/Conversation_with_%s_%d.txt" % (x["path"], T.safe_name(y["name"]), num)
                if not self.exists(rel):
                    self.write(rel, "Conversation between %s and %s (%d)\n\n" % (x["name"], y["name"], num))
                self.append(rel, text)
        elif speakers and speakers[0].get("path") and self.exists(speakers[0]["path"]):
            rel = speakers[0]["path"] + "/Talking_to_the_files.txt"
            if not self.exists(rel):
                self.write(rel, "%s, talking to the files\n\n" % speakers[0]["name"])
            self.append(rel, text)
        rel = LOGS + "/Overheard - %s.txt" % time.strftime("%Y-%m-%d")
        if not self.exists(rel):
            self.write(rel, "OVERHEARD\nWhat was said in Mess today. None of it was said to you.\n\n")
            self.gen(rel)
        self.append(rel, "\n-- %s, in %s --\n%s" % (T.stamp(), place or speakers[0].get("location", "?"), text))
        self.dirty_tree = True

    def talk_tick(self):
        """They talk to each other about what changed and what they see. Only the AI can write their words."""
        st = self.state
        people = self.alive()
        now = time.time()
        if not people:
            st["talk_queue"] = []
            return
        if self.ai.available:
            if st.get("talk_busy_until", 0) > now:
                return
            q = st.setdefault("talk_queue", [])
            item = None
            while q and item is None:
                cand = q.pop(0)
                a = self.char(cand["a"])
                if a:
                    item = (a, self.char(cand["b"]) if cand.get("b") else None, cand["facts"])
            idle_due = now >= st.get("next_talk", 0)
            if item is None and idle_due:
                st["next_talk"] = now + self.rng.uniform(70, 160) * (1.4 - 0.6 * self.chance())
                if len(people) >= 2:
                    pairs = []
                    for i, x in enumerate(people):
                        for y in people[i + 1:]:
                            score = self.rel(x, y)["close"] + (40 if x.get("place_rel") == y.get("place_rel") else 0)
                            pairs.append((score + self.rng.random() * 40 * (0.5 + self.chance()), x, y))
                    pairs.sort(key=lambda z: -z[0])
                    _, a, b = pairs[0]
                else:
                    a, b = people[0], None
                news = [n["text"] for n in st.get("news", [])[-6:]]
                item = (a, b, news)
            if item is None:
                return
            a, b, facts = item
            st["talk_busy_until"] = now + 120
            place = a.get("location")

            def done(lines, a=a, place=place):
                st["talk_busy_until"] = 0
                if lines:
                    self.record_talk(lines, place)
            self.ai.converse(a, b, facts, done)
        else:
            # Without the AI nobody's words can be written. You can only see that they talk.
            if now >= st.get("next_talk", 0):
                st["next_talk"] = now + self.rng.uniform(150, 300)
                together = {}
                for c in people:
                    together.setdefault(c.get("place_rel"), []).append(c)
                groups = [g for g in together.values() if len(g) >= 2]
                if groups:
                    g = self.rng.choice(groups)
                    self.feed("%s are talking in %s. You can't make out the words." % (
                        " and ".join(c["name"] for c in g[:3]), g[0].get("location", "?")))
                    for x in g:
                        for y in g:
                            if x is not y:
                                self.rel(x, y)["close"] = min(100, self.rel(x, y)["close"] + 1)
            st["talk_queue"] = []
        # leftovers wake up when nobody is touching anything
        idle = now - st.get("last_input", now)
        if idle > 300 and st["alice"] and len(self.unused_ingredients()) >= 5 and not st.get("idle_spawned_at") == st.get("last_input"):
            st["idle_spawned_at"] = st.get("last_input")
            self.spawn_random(why="idle")

    def note_looked(self, rel):
        """The player opened a folder. If it's a person, they noticed something looking."""
        c = self.owner_char(rel)
        if c:
            c["last_looked"] = time.time()

    # ------------------------------------------------------------ time away
    def offline(self, gone_sec):
        self.in_offline = True
        try:
            self._offline(gone_sec)
        finally:
            self.in_offline = False

    def _offline(self, gone_sec):
        speed = self.state.get("time_speed", 1.0)
        sim_gone = gone_sec / 60.0 * speed
        p = self.state["player"]
        people = self.alive()
        # random people made of leftovers
        born = []
        if sim_gone >= 30:
            for _ in range(3):
                c = self.spawn_random(why="gone")
                if not c:
                    break
                born.append(c)
        # live through it in chunks
        chunk = 10.0 if sim_gone < 1440 else 30.0
        steps = int(min(sim_gone, 60 * 24 * 45) / chunk)
        steps = min(steps, 3000)
        for _ in range(steps):
            self.step(chunk, offline=True)
        if sim_gone > steps * chunk:
            self.state["sim_min"] += sim_gone - steps * chunk
        # buildings while away
        if sim_gone >= 24 * 60 and len(self.alive()) >= 3:
            self.story.trigger("build", why="gone")
        self.story.while_gone(gone_sec, sim_gone, born)

    def note_input(self):
        self.state["last_input"] = time.time()

    # ------------------------------------------------------------ world file
    def world_stats(self):
        people = self.alive()
        lines = ["THE WORLD",
                 "(This file is the whole of Mess. You can change the Time Speed.)",
                 "",
                 "Time Speed: %g" % self.state.get("time_speed", 1),
                 "(1 = real time. 60 = an hour passes every minute. 1440 = a day every minute.)",
                 "Chance: %g" % self.chance(),
                 "(0 = everything follows from what you do. 1 = anything can happen.)",
                 "",
                 "Population: %d" % len(people),
                 "Gone: %d" % len(self.state["dead"]),
                 "Days lived: %d" % int(self.state["sim_min"] // 1440),
                 "Files given: %d" % self.state["total_added"],
                 "Unused files (waiting to become someone): %d" % len(self.unused_ingredients()),
                 ""]
        if people:
            lines.append("Who is where:")
            for c in sorted(people, key=lambda c: -c["age"]):
                lines.append("  %s is in %s." % (c["name"], c.get("location", "?")))
            leader = max(people, key=lambda c: (c["soul"]["trust"] * 0 + sum(r["close"] for r in c["rel"].values()) + c["age"]))
            lines.append("")
            lines.append("The others listen to: %s" % leader["name"])
            couples = []
            for c in people:
                if c.get("loves") and self.char(c["loves"]):
                    o = self.char(c["loves"])
                    if o.get("loves") == c["id"]:
                        pair = " and ".join(sorted([c["name"], o["name"]]))
                        if pair not in couples:
                            couples.append(pair)
                    else:
                        couples.append("%s loves %s (not back)" % (c["name"], o["name"]))
            if couples:
                lines.append("Love: " + "; ".join(couples))
        if self.state["dead"]:
            lines.append("")
            lines.append("Remembered: " + ", ".join(c["name"] for c in self.state["dead"].values()))
        if self.state["places_built"]:
            lines.append("Built by them: " + ", ".join(self.state["places_built"]))
        lines.append("")
        lines.append("--- Write rules about the world below this line. ---")
        lines += self.state.get("world_notes", [])
        return "\n".join(lines) + "\n"

    def sync_world_file(self):
        rel = WORLD + "/Stats.txt"
        cur = self.read(rel)
        known = self.state["hashes"].get(rel)
        if cur is not None and known and _h(cur) != known and rel not in self.open_files:
            m = re.search(r"time speed\s*[:=]\s*([\d.]+)", cur, re.I)
            if m:
                try:
                    v = max(0.1, min(1440.0, float(m.group(1))))
                    if v != self.state.get("time_speed"):
                        self.state["time_speed"] = v
                        self.action("time_speed", {"v": v})
                        self.story.trigger("time_speed", v=v)
                except ValueError:
                    pass
            m = re.search(r"chance\s*[:=]\s*([\d.]+)", cur, re.I)
            if m:
                try:
                    v = max(0.0, min(1.0, float(m.group(1))))
                    if v != self.chance():
                        self.state["chance"] = v
                        self.action("chance", {"v": v})
                except ValueError:
                    pass
            after = cur.split("--- Write rules about the world below this line. ---", 1)
            if len(after) == 2:
                self.state["world_notes"] = [l for l in after[1].splitlines() if l.strip()][:60]
                self.rules_dirty = True
        if rel in self.open_files:
            return
        text = self.world_stats()
        if self.state["hashes"].get(rel) != _h(text) or cur is None:
            self.write(rel, text)

    # ------------------------------------------------------------ the heartbeat
    def tick(self):
        """Call every ~1.5 s. Returns True if the tree changed."""
        now = time.time()
        if not os.path.isdir(self.root):
            if not self.gone_world:
                self.gone_world = True
            return True
        new, new_souls = self.scan()
        changed = new != self.snapshot or new_souls != self.souls
        if changed:
            old, old_souls = self.snapshot, self.souls
            self.snapshot = new
            self.process_changes(old, old_souls, new, new_souls)
            self.dirty_tree = True
        self.ai.process()
        self.sort_drop_zone()
        if self.rules_dirty:
            self.parse_rules()
        born = self.check_births()
        dt = min(now - self.last_tick, 30)
        self.last_tick = now
        speed = self.state.get("time_speed", 1.0)
        self.step(dt / 60.0 * speed)
        self.perceive_surroundings()
        self.talk_tick()
        self.story.periodic()
        self.direct()
        for c in self.alive():
            self.sync_body(c)
        self.sync_world_file()
        if now - self.last_backup > self.BACKUP_EVERY or any(
                not os.path.isdir(self.ab(SYSTEM + "/backups/" + c["id"])) for c in self.alive()):
            self.backup()
        self.state["last_seen"] = now
        self.after_game_changes()
        if now - self.last_save > self.TICK_SAVE:
            self.save()
        return changed or bool(born) or self.dirty_tree

    def apply_effects(self, effects, default=None):
        """Effects invented by the AI. Every one is checked; anything unknown is ignored."""
        if not isinstance(effects, list):
            return
        def who(name):
            if not isinstance(name, str):
                return default
            c = self.char_by_name(name.strip())
            if not c:
                for x in self.alive():
                    if name.strip().lower() in [a.lower() for a in x.get("aliases", [])]:
                        return x
            return c
        def num(v, lim=15):
            try:
                return max(-lim, min(lim, float(v)))
            except (TypeError, ValueError):
                return 0
        def txt(v, n=600):
            return str(v).strip()[:n] if v is not None else ""
        built = 0
        for e in effects[:10]:
            if not isinstance(e, dict):
                continue
            t = e.get("type")
            try:
                c = who(e.get("who") or e.get("from"))
                if t == "soul" and c and e.get("field") in c["soul"]:
                    f = e["field"]
                    c["soul"][f] = T.clamp(c["soul"][f] + num(e.get("change")))
                elif t == "feel" and c:
                    o = who(e.get("toward"))
                    if o and o["id"] != c["id"]:
                        r = self.rel(c, o)
                        r["close"] = max(0, min(100, r["close"] + num(e.get("closeness"))))
                        if c["voice"] != "child" and o["voice"] != "child":
                            r["love"] = max(0, min(100, r["love"] + num(e.get("love"))))
                elif t == "move" and c and e.get("to"):
                    name = txt(e["to"], 40)
                    if name.lower() not in ("system", "world", "logs"):
                        dest = self.find_place(name, create=True)
                        if dest is not None and not dest.startswith(SYSTEM) and not dest.startswith(WORLD):
                            self.move_char(c, dest, by="self")
                elif t == "say" and c and e.get("text"):
                    self.feed(txt(e["text"], 300), who=c["name"], kind="speech")
                elif t == "diary" and c and e.get("text"):
                    self.diary(c, txt(e["text"], 500))
                elif t == "remember" and c and e.get("fact"):
                    c["mem"].setdefault("notes", []).append(txt(e["fact"], 200))
                    c["mem"]["notes"] = c["mem"]["notes"][-40:]
                elif t in ("like", "fear") and c and e.get("thing"):
                    key = "base_likes" if t == "like" else "base_fears"
                    thing = txt(e["thing"], 60)
                    if thing not in c[key]:
                        c[key] = (c[key] + [thing])[-12:]
                elif t == "learn_word" and c and e.get("word"):
                    src = who(e.get("from"))
                    c["mem"]["learned"].append([txt(e["word"], 30), src["name"] if src else "a file"])
                    c["mem"]["learned"] = c["mem"]["learned"][-20:]
                elif t == "gift" and c and e.get("text"):
                    target = who(e.get("to"))
                    dest_dir = target.get("path") if target and target["id"] != c["id"] else None
                    if dest_dir:
                        fname = T.safe_name("Gift for %s - %s.txt" % (target["name"],
                                                                     txt(e.get("title") or "from " + c["name"], 40)), 100)
                        rel = self.unique(dest_dir, fname)
                        self.write(rel, "%s\n\n%s\n\n- %s\n" % (txt(e.get("title") or "A gift", 80), txt(e["text"], 3000), c["name"]))
                        self.gen(rel)
                        self.dirty_tree = True
                elif t == "write_file" and c and e.get("text"):
                    place = c.get("place_rel", "")
                    if self.is_place_dir(place):
                        name = T.safe_name(txt(e.get("name") or "untitled", 60), 70)
                        if not name.lower().endswith((".txt", ".md")):
                            name += ".txt"
                        rel = self.unique(place, name)
                        self.write(rel, txt(e["text"], 4000) + "\n\n- %s\n" % c["name"])
                        self.gen(rel)
                        self.dirty_tree = True
                        self.feed("%s made something in %s: %s" % (c["name"], c["location"], self.base(rel)))
                elif t == "build" and e.get("place") and built == 0 and len(self.state["places_built"]) < 25:
                    name = T.safe_name(txt(e["place"], 40).title(), 40)
                    if name.lower() not in ("system", "world", "logs") and self.find_place(name) is None:
                        rel = self.join(PLACES, name)
                        os.makedirs(self.ab(rel), exist_ok=True)
                        about = rel + "/About %s.txt" % name
                        self.write(about, "%s\n%s\n" % (name, txt(e.get("description") or "We built this.", 400)))
                        self.gen(about)
                        self.state["places_built"].append(name)
                        self.snapshot[rel] = {"d": 1, "s": 0, "m": time.time(), "i": 0}
                        self.dirty_tree = True
                        self.rules_dirty = True
                        built += 1
            except Exception as ex:
                self.state.setdefault("errors", []).append("effect %s: %s" % (t, ex))

    def after_game_changes(self):
        """Re-read the disk so the game's own writes don't look like the player's."""
        self.snapshot, self.souls = self.scan()
        self.refresh_char_paths()

    def backup(self):
        self.last_backup = time.time()
        for c in self.alive():
            if not c.get("path"):
                continue
            dst = self.ab(SYSTEM + "/backups/" + c["id"])
            try:
                os.makedirs(dst, exist_ok=True)
                for fn in os.listdir(self.ab(c["path"])):
                    src = os.path.join(self.ab(c["path"]), fn)
                    if os.path.isfile(src) and fn != SOUL and os.path.getsize(src) < 5 * 1024 * 1024:
                        shutil.copy2(src, os.path.join(dst, fn))
            except OSError:
                pass

    # ------------------------------------------------------------ for the UI
    def list_dir(self, rel):
        out = []
        try:
            names = os.listdir(self.ab(rel))
        except OSError:
            return out
        dirs = self.char_dirs()
        for n in names:
            if n == SOUL or n.endswith(".tmp"):
                continue
            r = self.join(rel, n)
            p = self.ab(r)
            try:
                st = os.stat(p)
            except OSError:
                continue
            isdir = os.path.isdir(p)
            item = {"name": n, "rel": r, "dir": isdir, "mtime": st.st_mtime,
                    "size": self.folder_size(r) if isdir else st.st_size}
            if isdir:
                if r in dirs:
                    c = dirs[r]
                    item["kind"] = "character"
                    item["char"] = c["id"]
                    item["body"] = self.body_state(c)
                    item["label"] = "%s - in %s" % (n, c.get("location", "?"))
                else:
                    item["kind"] = self.dir_kind(r)
                    if self.owner_char(r):
                        item["kind"] = "place"
            else:
                item["kind"] = T.kind_of(n) or "file"
            out.append(item)
        def order(i):
            k = {"character": 0, "place": 1, "system": 2}.get(i.get("kind"), 3) if i["dir"] else 4
            return (k, i["name"].lower())
        out.sort(key=order)
        return out

    def folder_size(self, rel):
        total = 0
        base = self.ab(rel)
        for dp, dn, fn in os.walk(base):
            for f in fn:
                try:
                    total += os.path.getsize(os.path.join(dp, f))
                except OSError:
                    pass
        return total

    def counts(self):
        c = {"Words": 0, "Images": 0, "Sounds": 0, "Logs": 0, "Characters": len(self.alive())}
        for rel, e in self.snapshot.items():
            if e["d"]:
                continue
            for key, pre in (("Words", WORDS), ("Images", IMAGES), ("Sounds", SOUNDS), ("Logs", LOGS)):
                if self.parent(rel) == pre:
                    c[key] += 1
        return c

    def custom_places(self):
        std = {CHARS, PLACES, WORDS, IMAGES, SOUNDS, LOGS, SYSTEM, WORLD}
        out = []
        for rel, e in self.snapshot.items():
            if e["d"] and rel not in std and self.is_place_dir(rel) and rel.count("/") <= 2:
                n = sum(1 for r2, e2 in self.snapshot.items() if self.parent(r2) == rel)
                out.append((rel, n))
        out.sort()
        return out

    def where_is_everyone(self):
        return ["%s is in %s." % (c["name"], c.get("location", "?")) for c in self.alive()]

    def close(self):
        self.save()

    def follow(self, rel):
        """Where a file or folder ended up if it was moved or renamed."""
        seen = 0
        while rel and not self.exists(rel) and seen < 50:
            seen += 1
            moved = None
            for old, new in self.path_aliases.items():
                if rel == old:
                    moved = new
                    break
                if rel.startswith(old + "/"):
                    moved = new + rel[len(old):]
                    break
            if moved is None:
                return None
            rel = moved
        return rel if rel is not None and self.exists(rel) else None

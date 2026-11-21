"""The story engine.

It records what happens as plain, third-person facts in Mess/Places/Logs/. It never
speaks for anyone: every word a character says comes from the AI (see ai.py). With the AI
on, the AI retells each log and lets the people in it talk to each other. Nobody in Mess
ever speaks to the player. They sense something there, and only talk about it.
"""
import datetime
import os
import shutil
import time

from . import textlib as T

LOGS = "Places/Logs"


class Story:
    QUIET_OFFLINE = {"closer", "missing", "jealous", "sought_friend", "fled_cold", "reunion", "taught",
                     "comfort", "arrived_place", "love_faded", "moved_too_much", "wandered", "unwatched"}
    ESSENTIAL = {"born_bob", "born_alice", "born_random", "deleted_char", "returned", "restored", "judgment",
                 "renamed", "copied", "cannot_die", "child", "build", "piece_deleted", "file_returned",
                 "stats_edited", "diary_written", "time_speed", "love", "separated", "scary_image",
                 "talks_to_files", "harmed"}

    def __init__(self, world):
        self.w = world

    @property
    def st(self):
        return self.w.state

    # ------------------------------------------------------------ helpers
    def ready(self, key, cooldown_min):
        fired = self.st["fired"]
        last = fired.get(key)
        if last is not None and self.st["sim_min"] - last < cooldown_min:
            return False
        fired[key] = self.st["sim_min"]
        return True

    def once(self, key):
        if key in self.st["fired"]:
            return False
        self.st["fired"][key] = self.st["sim_min"]
        return True

    def log(self, title, body, name=None, raw=False, people=None):
        """Facts in, a log out. With the AI on, it retells the facts in its own words."""
        if not raw and self.w.ai.available:
            self.w.ai.narrate(title, body, lambda t, text: self._write_log(t, text, name), chars=people)
            return None
        return self._write_log(title, body, name)

    def _write_log(self, title, body, name=None):
        w = self.w
        fname = name or "%s - %s" % (T.file_stamp(), title)
        fname = T.safe_name(fname, 110)
        if not fname.lower().endswith(".txt"):
            fname += ".txt"
        rel = w.unique(LOGS, fname)
        text = "%s\n%s\n%s\n\n%s\n" % (title, "=" * min(60, len(title)), T.stamp(), body.strip())
        w.write(rel, text)
        w.gen(rel)
        w.dirty_tree = True
        w.feed("A log was written: %s" % w.base(rel))
        self.st.setdefault("story", []).append({"t": time.time(), "title": title, "rel": rel})
        self.st["story"] = self.st["story"][-300:]
        return rel

    def pair_log(self, a, b, text, raw=False):
        if not raw and self.w.ai.available:
            self.w.ai.narrate("%s and %s" % (a["name"], b["name"]), text,
                              lambda t, body: self._pair_write(a, b, body), chars=[a, b])
            return None
        return self._pair_write(a, b, text)

    def _pair_write(self, a, b, text):
        w = self.w
        names = sorted([a["name"], b["name"]])
        rel = "%s/%s_and_%s.txt" % (LOGS, T.safe_name(names[0]), T.safe_name(names[1]))
        if not w.exists(rel):
            w.write(rel, "%s and %s\n%s\n\n" % (names[0], names[1], "=" * 30))
            w.gen(rel)
        w.append(rel, "[%s]\n%s\n\n" % (T.stamp(), text.strip()))
        w.dirty_tree = True
        return rel

    def describe_ings(self, ings):
        parts = []
        for i in ings:
            a = i.get("a") or {}
            if i["kind"] == "image":
                what = a.get("seen_as") or {"scary": "a frightening picture", "soft": "a soft picture"}.get(
                    a.get("mood"), "a picture")
                if a.get("person") and not a.get("seen_as"):
                    what += " with a person in it"
                parts.append("- %s: %s" % (i["name"], what))
            elif i["kind"] == "sound":
                what = {"distorted": "a loud, distorted sound", "voice": "a voice",
                        "calm": "a calm sound"}.get(a.get("mood"), "a sound")
                parts.append("- %s: %s" % (i["name"], what))
            else:
                s = a.get("scores", {})
                what = "sharp words" if s.get("scary", 0) > s.get("soft", 0) else (
                    "gentle words" if s.get("soft", 0) else "words")
                first = a.get("first_line")
                parts.append("- %s: %s%s" % (i["name"], what, (' beginning "%s"' % first[:70]) if first else ""))
        return "\n".join(parts)

    def where(self, c):
        return c.get("location") or "somewhere"

    # ------------------------------------------------------------ dispatch
    def trigger(self, _event, **kw):
        name = _event
        if getattr(self.w, "in_offline", False) and name in self.QUIET_OFFLINE:
            return
        if name not in self.ESSENTIAL and not self.w.roll(1.0 - 0.6 * self.w.chance()):
            return
        fn = getattr(self, "ev_" + name, None)
        if fn:
            try:
                fn(**kw)
            except Exception as e:  # a story event must never crash the folder
                self.st.setdefault("errors", []).append("%s: %s" % (name, e))
                self.st["errors"] = self.st["errors"][-20:]

    # ------------------------------------------------------------ births
    def ev_born_bob(self, c, ings):
        self.log("A folder woke up",
                 "Five files were left together long enough. A folder appeared in Characters: %s.\n"
                 "It is a person. He is made of:\n%s\n\nHe is alone. The only things he can talk to are the files." % (
                     c["name"], self.describe_ings(ings)), people=[c])

    def ev_born_alice(self, c, ings):
        bob = self.w.char(self.st.get("bob") or "")
        self.log("Someone arrived",
                 "A second folder appeared: %s. She was not born the way %s was. She arrived, made of:\n%s\n\n"
                 "The first thing she did was open %s's folder and read it." % (
                     c["name"], bob["name"] if bob else "Bob", self.describe_ings(ings), bob["name"] if bob else "Bob"),
                 people=[c, bob] if bob else [c])

    def ev_born_random(self, c, ings, finder=None, why="gone"):
        when = {"gone": "while Mess was closed", "idle": "while nothing was being touched",
                "present": "without anyone deciding it"}.get(why, "")
        found = ("%s found them in %s." % (finder["name"], self.where(c))) if finder else (
            "Nobody found them. They were in %s." % self.where(c))
        self.log("%s woke up" % c["name"],
                 "%s woke up %s, made of files nobody had used:\n%s\n\n%s" % (
                     c["name"], when, self.describe_ings(ings), found),
                 name="%s - %s woke up" % (T.file_stamp(), c["name"]), people=[c, finder] if finder else [c])
        if finder:
            self.w.diary(finder, "Found someone new in %s: %s." % (self.where(c), c["name"]))
            self.w.want_talk(c, finder, "%s just woke up in %s. %s found them." % (c["name"], self.where(c), finder["name"]))

    def ev_child(self, a, b):
        key = "child-" + "-".join(sorted([a["id"], b["id"]]))
        n = sum(1 for k in self.st["fired"] if k.startswith(key))
        if n >= 2 or not self.ready(key + "-%d" % n, 1) or not self.ready("anychild", 7 * 1440):
            return
        kid = self.w.spawn_child(a, b)
        text = ("%s and %s loved each other long enough that something new began. A folder appeared inside "
                "School: %s, made from bits of both of them." % (a["name"], b["name"], kid["name"]))
        self.pair_log(a, b, text)
        self.log(kid["name"], text, people=[a, b, kid])
        self.w.want_talk(a, b, "A child folder, %s, just appeared in School. It is made of both of them." % kid["name"])

    # ------------------------------------------------------------ Alice reads Bob
    def ev_judgment(self, c):
        if not self.once("judgment"):
            return
        bob = self.w.char(self.st.get("bob") or "")
        if not bob:
            self.log("An empty space", "%s looked for Bob's folder. There wasn't one." % c["name"], people=[c])
            return
        s = bob["soul"]
        diag = {
            "scared": "His folder has shrunk and his name has a number after it.",
            "angry": "His folder is red and swollen. He pushes the others away.",
            "corrupted": "His name has come apart into letters. His Stats.txt is unreadable in places.",
            "happy": "His folder is clean. He is well.",
            "sad": "He is quiet. He keeps reading his own Diary.",
            "calm": "He is all right, for now.",
        }[self.w.body_state(bob)]
        moves = len(self.w.recent_actions("char_moved", 10 ** 9))
        self.log("Alice reads Bob",
                 "%s opened %s's folder and read it the way a doctor reads a chart.\n"
                 "Happiness %d. Fear %d. Anger %d. Trust %d. Corruption %d.\n%s\n"
                 "Everything that has been done to him is in there: every file, every move (%d so far).\n"
                 "She told him what it meant. Souls bend; bodies follow." % (
                     c["name"], bob["name"], s["happiness"], s["fear"], s["anger"], s["trust"], s["corruption"],
                     diag, moves), people=[c, bob])
        self.w.want_talk(c, bob, "%s has just read %s's folder like a doctor and tells him what has been done to him." % (
            c["name"], bob["name"]))

    # ------------------------------------------------------------ what the hand does
    def ev_renamed(self, c, old, new):
        self.log("%s is called %s now" % (old, new),
                 "%s's folder was renamed. It says %s now. The files inside didn't change. "
                 "Their Diary still has %s at the top." % (old, new, old), people=[c])

    def ev_copied(self, c, twin):
        self.log("There are two of %s" % c["name"],
                 "%s was copied. Now there are two: %s and %s. Same Diary, same fears, same memories. "
                 "They sat in their folders and looked at each other." % (c["name"], c["name"], twin["name"]),
                 people=[c, twin])
        self.w.want_talk(c, twin, "%s was just copied. %s is the copy. They have the same memories." % (c["name"], twin["name"]))

    def ev_returned(self, c):
        self.log("%s came back" % c["name"],
                 "%s's folder was deleted. A file in Mess says %s cannot die, so the folder came back, "
                 "under a new name: %s. There is a gap in their Diary." % (c["name"], c["name"], self.w.base(c["path"])),
                 people=[c])

    def ev_restored(self, c):
        self.log("%s was restored" % c["name"],
                 "%s's folder came back. Someone restored it. They were somewhere without files for a while." % c["name"],
                 people=[c])

    def ev_deleted_char(self, c):
        mourners = [o for o in self.w.alive() if c["name"] in o["mem"]["lost"]]
        if not mourners:
            self.log("%s is gone" % c["name"], "%s's folder was deleted. Nobody was close enough to notice right away." % c["name"])
            return
        for o in mourners:
            loved = o["rel"].get(c["id"], {}).get("love", 0) >= 60
            self.log("%s grieves" % o["name"],
                     "%s's folder was deleted. %s %s. There is a gap in the folder where it used to be." % (
                         c["name"], o["name"], "loved them" if loved else "noticed first"), people=[o])
            if loved:
                self.pair_log(o, c, "%s was deleted. %s is still here." % (c["name"], o["name"]))
        if len(mourners) >= 2:
            self.w.want_talk(mourners[0], mourners[1], "%s's folder has just been deleted. They are gone." % c["name"])
        elif mourners:
            self.w.want_talk(mourners[0], None, "%s's folder has just been deleted. They are gone." % c["name"])

    def ev_moved_too_much(self, c):
        if not self.ready("movedmuch-" + c["id"], 120):
            return
        self.log("Dragged", "%s was moved %d times in a few minutes. Each time everything inside their folder slid "
                            "to one side. Their Fear went up." % (c["name"], len(c["player_moves"])), people=[c])
        self.ev_harmed(c, "being dragged around")

    def ev_harmed(self, c, how="what was done to them"):
        """Someone close stands up for them - to the others, never to the hand."""
        for o in self.w.alive():
            if o["id"] == c["id"]:
                continue
            r = o["rel"].get(c["id"], {})
            if r.get("love", 0) >= 60 or r.get("close", 0) >= 50:
                if not self.ready("defend-%s-%s" % (o["id"], c["id"]), 60):
                    continue
                o["soul"]["anger"] = T.clamp(o["soul"]["anger"] + 8)
                o["soul"]["trust"] = T.clamp(o["soul"]["trust"] - 5)
                if o.get("place_rel") != c.get("place_rel"):
                    self.w.move_char(o, c.get("place_rel", ""), by="self")
                r2 = self.w.rel(c, o)
                r2["close"] = min(100, r2["close"] + 6)
                self.log("%s went to %s" % (o["name"], c["name"]),
                         "After %s, %s moved their own folder next to %s's and stayed there." % (how, o["name"], c["name"]),
                         people=[o, c])
                self.w.want_talk(o, c, "%s has come to %s after %s." % (o["name"], c["name"], how))
                return

    def ev_arrived_place(self, c, place, info):
        if info["temp"] <= -2 or info["light"] <= -2:
            if not self.ready("cold-%s-%s" % (c["id"], place), 240):
                return
            others = [o for o in self.w.alive() if o["id"] != c["id"] and o.get("location") == place]
            extra = (" %s was already there." % others[0]["name"]) if others else " Nobody else was there."
            self.log("%s in %s" % (c["name"], place), "%s was put in %s. %s%s" % (c["name"], place, info["feel"], extra),
                     people=[c] + others[:1])
        elif info["temp"] >= 2 and self.ready("warm-%s-%s" % (c["id"], place), 480):
            self.log("%s in %s" % (c["name"], place), "%s was put somewhere warm: %s. %s" % (c["name"], place, info["feel"]),
                     people=[c])

    def ev_separated(self, c, other):
        if not self.ready("sep-" + c["id"], 60):
            return
        self.log("Separated", "%s was moved away from %s. %s is in %s; %s is in %s. %s will try to go back." % (
            c["name"], other["name"], c["name"], self.where(c), other["name"], self.where(other), c["name"]),
                 people=[c, other])
        self.pair_log(c, other, "They were separated. %s was put in %s." % (c["name"], self.where(c)))

    def ev_neat_moved(self, c, file, folder):
        if self.ready("neat-%s-%s" % (c["id"], file), 600):
            self.log("Out of place", "%s was taken out of %s. %s noticed: it was one of theirs." % (file, folder, c["name"]),
                     people=[c])

    def ev_piece_deleted(self, c, file):
        f = file.lower()
        if f == "diary.txt":
            keep = len(c["mem"]["seen"]) // 2
            c["mem"]["seen"] = c["mem"]["seen"][:keep]
            c["mem"]["learned"] = c["mem"]["learned"][:len(c["mem"]["learned"]) // 2]
            c["mem"]["notes"] = c["mem"].get("notes", [])[:len(c["mem"].get("notes", [])) // 2]
            c["soul"]["fear"] = T.clamp(c["soul"]["fear"] + 10)
            what = "Half of what they remembered went with it."
        elif f == "stats.txt":
            c["soul"]["corruption"] = T.clamp(c["soul"]["corruption"] + 8)
            what = "For a moment they had no numbers at all."
        elif f == "body.txt":
            c["soul"]["fear"] = T.clamp(c["soul"]["fear"] + 15)
            what = "It grew back. It doesn't fit the same."
        else:
            what = ""
        self.w.diary(c, "Something of mine was deleted: %s." % file)
        self.log("A piece of %s" % c["name"], "%s was deleted from %s's folder. %s" % (file, c["name"], what), people=[c])
        self.ev_harmed(c, "losing their %s" % file)

    def ev_stats_edited(self, c, fields):
        if self.ready("statsed-" + c["id"], 30):
            self.log("%s was rewritten" % c["name"], "%s's Stats.txt was changed (%s). They feel different and can't say how." % (
                c["name"], ", ".join(fields)), people=[c])

    def ev_diary_written(self, c):
        if self.ready("diaryw-" + c["id"], 30):
            self.log("%s's Diary" % c["name"], "Words appeared in %s's Diary that they don't remember writing. "
                                               "They believe them anyway." % c["name"], people=[c])

    def ev_cannot_die(self, c):
        self.log("%s cannot die" % c["name"], "A line in a file says %s cannot die. Mess read it. Mess believes what it reads." % c["name"],
                 people=[c])

    def ev_place_created(self, rel):
        name = self.w.base(rel)
        if self.ready("place-" + name.lower(), 1440):
            self.log("A new place: %s" % name, "A folder called %s appeared. A folder that isn't a person is a place. %s" % (
                name, self.w.place_info(rel)["feel"]))

    def ev_file_returned(self, c, file, orig):
        self.log("%s came back" % orig, "%s was deleted. It was part of %s, so they kept a copy. It is back, as %s." % (
            orig, c["name"], file), people=[c])

    def ev_time_speed(self, v):
        self.log("Time", "Time in Mess runs at %g now. Nobody inside felt it change. They just got older faster." % v)

    # ------------------------------------------------------------ what they see and hear
    def ev_scary_image(self, c, image):
        c["flags"]["nightmare_due"] = self.st["sim_min"] + 15
        c["flags"]["nightmare_image"] = image
        if self.once("scaryimg-%s-%s" % (c["id"], image)):
            self.log("%s saw %s" % (c["name"], image), "%s saw %s. Their Fear went up." % (c["name"], image), people=[c])
            self.ev_harmed(c, "seeing %s" % image)

    def ev_soft_image(self, c, image, subject=None):
        if self.once("softimg-%s-%s" % (c["id"], image)):
            self.log("%s and %s" % (c["name"], image), "%s looked at %s for a long time. Their folder got a little brighter." % (
                c["name"], image), people=[c])

    def ev_person_image(self, c, image):
        if self.once("person-%s-%s" % (c["id"], image)):
            self.log("%s thinks they know someone" % c["name"], "%s saw %s. There is a person in it. %s is sure they know them." % (
                c["name"], image, c["name"]), people=[c])

    def ev_new_image(self, c, image):
        pass

    def ev_loud_sound(self, c, song):
        if self.once("loud-%s-%s" % (c["id"], song)):
            self.log("Noise", "%s heard %s. It went through every file they are made of. Their Corruption went up." % (
                c["name"], song), people=[c])

    def ev_voice_memo(self, c, memo):
        if self.once("voice-" + c["id"]):
            self.log("A voice", "%s heard %s. It was a voice. They have been listening for it ever since." % (c["name"], memo),
                     people=[c])

    def ev_song(self, c, song):
        if self.once("song-%s-%s" % (c["id"], song)):
            self.log("%s heard \"%s\"" % (c["name"], song), "%s heard \"%s\" and kept humming it." % (c["name"], song), people=[c])

    def ev_scary_text(self, c, file):
        if self.once("scarytext-%s-%s" % (c["id"], file)):
            self.log("Sharp words", "%s read %s. The words were sharp. Some of them stayed." % (c["name"], file), people=[c])

    def ev_vocab_shift(self, c):
        if self.once("vocab-" + c["id"]):
            self.log("%s talks differently now" % c["name"], "%s has read enough dark words to start using them: %s." % (
                c["name"], ", ".join(sorted(set(c["mem"]["scary_vocab"]))[:6])), people=[c])

    def ev_nightmare(self, c, image):
        c["soul"]["fear"] = T.clamp(c["soul"]["fear"] + 6)
        self.log("%s's nightmare" % c["name"], "%s dreamed about %s. In the dream it was bigger than the folder. "
                                               "Their folder icon is a shade darker now." % (c["name"], image), people=[c])
        others = [o for o in self.w.alive() if o["id"] != c["id"] and o.get("place_rel") == c.get("place_rel")]
        self.w.want_talk(c, others[0] if others else None, "%s just woke from a nightmare about %s." % (c["name"], image))

    # ------------------------------------------------------------ between them
    def ev_missing(self, c, other):
        if self.ready("missing-%s-%s" % (c["id"], other["id"]), 360):
            self.w.diary(c, "%s is in %s. I am in %s." % (other["name"], self.where(other), self.where(c)))
            self.log("%s misses %s" % (c["name"], other["name"]), "%s and %s have been in different places for a long time "
                     "(%s and %s)." % (c["name"], other["name"], self.where(c), self.where(other)), people=[c, other])

    def ev_closer(self, a, b):
        if self.once("closer-" + "-".join(sorted([a["id"], b["id"]]))):
            self.log("%s and %s" % (a["name"], b["name"]), "%s and %s have been in %s together for a long time. They are "
                     "closer now." % (a["name"], b["name"], self.where(a)), people=[a, b])

    def ev_love(self, c, other, mutual):
        if not self.once("love-%s-%s" % (c["id"], other["id"])):
            return
        if mutual:
            text = "%s loves %s, and %s loves %s back. It happened in %s, slowly." % (
                c["name"], other["name"], other["name"], c["name"], self.where(c))
            self.pair_log(c, other, text)
            self.log("%s and %s" % (c["name"], other["name"]), text, people=[c, other])
        else:
            text = "%s loves %s. %s doesn't, not like that." % (c["name"], other["name"], other["name"])
            self.pair_log(c, other, text)
            self.log("%s, quietly" % c["name"], text, people=[c, other])
            self.gift(c, other)
        self.w.want_talk(c, other, text)

    def ev_love_faded(self, c, other):
        if self.ready("faded-%s-%s" % (c["id"], other["id"]), 1440):
            text = "%s doesn't love %s the way they used to. Nothing happened. It just went quiet." % (c["name"], other["name"])
            self.pair_log(c, other, text)
            self.log("Heartbreak", text, people=[c, other])

    def ev_jealous(self, c, other, third):
        if self.ready("jealous-%s-%s" % (c["id"], third["id"]), 3 * 1440):
            text = "%s loves %s. %s loves %s." % (c["name"], other["name"], other["name"], third["name"])
            self.pair_log(c, other, text)
            self.log("Jealousy", text, people=[c, other, third])

    def ev_reunion(self, c, other):
        if self.ready("reunion-" + c["id"], 60):
            text = "%s moved their own folder to %s, where %s is. Nobody dragged them." % (c["name"], self.where(c), other["name"])
            self.pair_log(c, other, text)
            self.log("%s went back to %s" % (c["name"], other["name"]), text, people=[c, other])
            self.w.want_talk(c, other, text)

    def ev_fled_cold(self, c, place):
        if self.ready("fled-" + c["id"], 240):
            self.log("%s moved" % c["name"], "%s was too frightened to stay where they were and moved their own folder to %s." % (
                c["name"], place), people=[c])

    def ev_sought_friend(self, c, place):
        if self.ready("friend-" + c["id"], 240):
            self.log("%s moved" % c["name"], "%s was alone too long and moved their own folder to %s, to be near someone." % (
                c["name"], place), people=[c])

    def ev_wandered(self, c, place):
        if self.ready("wander-" + c["id"], 120):
            self.log("%s went for a walk" % c["name"], "%s moved their own folder to %s. Nothing made them. They wanted to see it." % (
                c["name"], place), people=[c])

    def ev_taught(self, a, b, word):
        if self.once("taught-%s-%s" % (b["id"], word)):
            self.log("A new word", "%s taught %s a word: '%s'." % (a["name"], b["name"], word), people=[a, b])

    def gift(self, c, to):
        """A file left for someone else. Never for the hand."""
        if not c.get("path") or not to.get("path"):
            return
        rel = self.w.unique(to["path"], T.safe_name("Gift from %s.txt" % c["name"]))
        memory = c["mem"]["soft_image"][0] if c["mem"].get("soft_image") else (
            c["mem"]["songs"][0][0] if c["mem"]["songs"] else (c["ingredients"][0] if c["ingredients"] else "the first file"))
        self.w.write(rel, "A gift from %s to %s.\n\nInside: a copy of %s's favourite memory, %s.\n" % (
            c["name"], to["name"], c["name"], memory))
        self.w.gen(rel)
        if c["mem"].get("soft_image"):
            src = self.w.ab(c["mem"]["soft_image"][1])
            if os.path.exists(src):
                try:
                    img = self.w.unique(to["path"], "Gift - " + self.w.base(src))
                    shutil.copy2(src, self.w.ab(img))
                    self.w.gen(img)
                except OSError:
                    pass
        self.w.dirty_tree = True

    def ev_talks_to_files(self, c, afk=False):
        if not self.ready("files-" + c["id"], 360):
            return
        bob_dead = self.st.get("bob") in self.st["dead"]
        why = "Bob is gone, so " if (bob_dead and c["voice"] == "alice") else ""
        self.log("%s talks to the files" % c["name"], "%s%s is on their own and has started talking to the files in %s." % (
            why, c["name"], self.where(c)), people=[c])
        self.w.want_talk(c, None, "%s is alone." % c["name"])

    # ------------------------------------------------------------ the world around them
    def ev_build(self, why="present"):
        if not self.ready("build", 2 * 1440):
            return
        w = self.w
        people = w.alive()
        options = [("Garden", "It is warm here."), ("Shelter", "It is warm here. It is safe here."),
                   ("Lighthouse", "It is bright here."), ("Quiet Room", "It is safe here."),
                   ("Meeting Hall", "It is bright here."), ("Bakery", "It is warm here.")]
        if w.state["player"]["cruelty"] > 40:
            options.insert(0, ("Shelter", "It is dark here. It is safe here."))
        for name, desc in options:
            if name not in w.state["places_built"] and w.find_place(name) is None:
                break
        else:
            return
        rel = w.join("Places", name)
        os.makedirs(w.ab(rel), exist_ok=True)
        builders = ", ".join(c["name"] for c in people[:4])
        w.write(rel + "/About %s.txt" % name, "%s\nBuilt by %s.\n%s\n" % (name, builders, desc))
        w.gen(rel + "/About %s.txt" % name)
        w.state["places_built"].append(name)
        w.dirty_tree = True
        w.rules_dirty = True
        for c in people[:2]:
            w.move_char(c, rel, by="self")
        self.log("They built something", "%s built a new place: %s. It is a real folder. %s" % (builders, name, desc),
                 people=people[:3])

    def periodic(self):
        w = self.w
        people = w.alive()
        now = time.time()
        for c in people:
            due = c["flags"].get("nightmare_due")
            if due and w.state["sim_min"] >= due:
                c["flags"].pop("nightmare_due", None)
                self.ev_nightmare(c, c["flags"].get("nightmare_image", "the picture"))
            if w.body_state(c) == "angry":
                near = [o for o in people if o["id"] != c["id"] and o.get("place_rel") == c.get("place_rel")]
                if near and self.ready("push-" + c["id"], 180):
                    for o in near:
                        o["soul"]["fear"] = T.clamp(o["soul"]["fear"] + 5)
                    self.log("%s pushed" % c["name"], "%s is angry. Their folder is swollen and red. They pushed %s to the "
                             "edge of %s." % (c["name"], ", ".join(o["name"] for o in near), self.where(c)), people=[c] + near[:1])
            if c["soul"]["corruption"] >= 60:
                near = [o for o in people if o["id"] != c["id"] and o.get("place_rel") == c.get("place_rel")]
                if near and self.ready("rot-" + c["id"], 360):
                    self.log("Rot", "%s is coming apart. The others in %s are starting to show the same marks." % (
                        w.base(c["path"]), self.where(c)), people=[c] + near[:1])
            if c["soul"]["happiness"] >= 85 and self.ready("content-" + c["id"], 1440):
                self.log("%s is happy" % c["name"], "%s is happy. Nothing happened today, and that was enough." % c["name"], people=[c])
            looked = c.get("last_looked") or c.get("born", now)
            if now - looked > 20 * 60 and now - c.get("born", now) > 20 * 60 and self.ready("unwatched-" + c["id"], 360):
                self.ev_unwatched(c)
        hour = time.localtime().tm_hour
        if (hour >= 23 or hour < 5) and people and self.once("night-" + time.strftime("%Y-%m-%d", time.localtime(now - 6 * 3600))):
            self.ev_night(people)
        if len(people) >= 3 and w.state["sim_min"] > 3 * 60:
            avg_trust = sum(c["soul"]["trust"] for c in people) / len(people)
            if avg_trust >= 55 or w.state["player"]["cruelty"] > 60:
                self.ev_build(why="present")
        alice = w.char(w.state.get("alice") or "")
        if alice and not alice["flags"].get("judged") and w.state["sim_min"] - alice.get("born_sim", 0) > 5:
            alice["flags"]["judged"] = True
            self.ev_judgment(alice)

    def ev_unwatched(self, c):
        c["soul"]["trust"] = T.clamp(c["soul"]["trust"] - 3)
        self.log("Unwatched", "Nothing has opened %s's folder in a long time. %s has noticed." % (c["name"], c["name"]), people=[c])

    def ev_night(self, people):
        afraid = [c for c in people if any("dark" in f.lower() for f in self.w.fears(c)) or c["soul"]["fear"] >= 50]
        if not afraid:
            self.log("Night", "Night outside. In Mess the light never changes, but they all went quiet.")
            return
        c = afraid[0]
        comforter = next((o for o in people if o["id"] != c["id"] and o["rel"].get(c["id"], {}).get("close", 0) >= 25), None)
        if comforter:
            r = self.w.rel(c, comforter)
            r["close"] = min(100, r["close"] + 5)
            self.log("The dark", "Night. %s is afraid of the dark. %s stayed up with them." % (c["name"], comforter["name"]),
                     people=[c, comforter])
            self.w.want_talk(comforter, c, "It is night and %s is afraid of the dark." % c["name"])
        else:
            self.log("The dark", "Night. %s is afraid of the dark. Nobody came." % c["name"], people=[c])

    def spontaneous_fallback(self):
        """Without the AI: small things nobody caused. Facts only."""
        w = self.w
        people = w.alive()
        if not people:
            return
        r = w.rng
        a = r.choice(people)
        others = [o for o in people if o["id"] != a["id"]]
        b = r.choice(others) if others else None
        place = self.where(a)
        options = ["rearrange", "count", "system", "old_file"] + (["visit", "argue", "makeup", "sit", "gift"] if b else [])
        kind = r.choice(options)
        if kind == "rearrange":
            self.log("%s rearranged %s" % (a["name"], place), "%s spent a long time in %s, moving nothing and everything." % (a["name"], place))
        elif kind == "count":
            n = len(w.list_dir(a.get("place_rel", "")))
            self.log("Counting", "%s counted the things in %s. There were %d. They counted again. %d." % (a["name"], place, n, n))
        elif kind == "system":
            self.log("The hum", "%s went to the edge of the System folder and listened to it hum." % a["name"])
        elif kind == "old_file":
            ings = [i for i in w.state["ingredients"].values() if not i["deleted"]]
            if ings:
                f = r.choice(ings)["name"]
                self.log("An old file", "%s found %s again and read it slowly, as if it was new." % (a["name"], f))
        elif kind == "visit" and b.get("place_rel") != a.get("place_rel"):
            if w.move_char(a, b.get("place_rel", ""), by="self"):
                self.log("A visit", "%s went to see %s in %s, and stayed." % (a["name"], b["name"], self.where(b)))
        elif kind == "argue":
            w.rel(a, b)["close"] = max(0, w.rel(a, b)["close"] - 6)
            self.log("An argument", "%s and %s argued about the thing that moves them. Neither won." % (a["name"], b["name"]))
        elif kind == "makeup":
            w.rel(a, b)["close"] = min(100, w.rel(a, b)["close"] + 6)
            self.log("Making up", "%s said sorry to %s for something small. It wasn't small to them." % (a["name"], b["name"]))
        elif kind == "sit":
            self.log("Sitting", "%s and %s sat in the same folder without saying anything." % (a["name"], b["name"]))
        elif kind == "gift":
            self.gift(a, b)
            self.log("A gift", "%s left a file in %s's folder." % (a["name"], b["name"]))

    # ------------------------------------------------------------ while Mess was closed
    def while_gone(self, gone_sec, sim_gone, born):
        w = self.w
        people = w.alive()
        p = w.state["player"]
        gone_words = T.duration_words(gone_sec)
        last = w.state.get("last_seen", time.time() - gone_sec)
        overnight = gone_sec >= 6 * 3600 or (time.localtime(last).tm_mday != time.localtime().tm_mday and gone_sec > 3 * 3600)
        if not people:
            if w.state["dead"] and gone_sec > 3600:
                self.log("Nobody", "Mess was closed for %s. Nobody was there. The folder kept its timestamps anyway." % gone_words)
            return
        if gone_sec >= 50 * 60:
            if len(people) >= 2:
                a, b = self._closest_pair(people)
                name = "%s_and_%s_talked_while_Mess_was_closed.txt" % (T.safe_name(a["name"]), T.safe_name(b["name"]))
                facts = "Mess was closed for %s. %s and %s were in %s and %s." % (gone_words, a["name"], b["name"], self.where(a), self.where(b))
                if w.ai.available:
                    w.ai.converse(a, b, [facts], lambda lines: self._write_log(
                        "While Mess was closed", facts + "\n\n" + "\n".join("%s: %s" % (x["name"], ln) for x, ln in lines), name))
                else:
                    self._write_log("While Mess was closed", facts + " They talked for a long time. None of it was written down.", name)
            else:
                self.ev_talks_to_files(people[0])
        if overnight:
            scared = max(people, key=lambda c: c["soul"]["fear"])
            others = [o for o in people if o["id"] != scared["id"]]
            comforter = next((o for o in others if o["rel"].get(scared["id"], {}).get("close", 0) >= 25), None)
            text = "Mess was closed for %s. There was a night. %s was frightened of the dark. " % (gone_words, scared["name"])
            text += ("%s stayed with them until it was light." % comforter["name"]) if comforter else (
                "%s heard and didn't come." % others[0]["name"] if others else "There was nobody else.")
            self.log("The night", text, name="%s - The night" % T.file_stamp(), people=[scared] + ([comforter] if comforter else []))
        if gone_sec >= 5 * 86400:
            for c in people:
                c["soul"]["trust"] = T.clamp(c["soul"]["trust"] - 10)
            names = ", ".join(c["name"] for c in people)
            rules = ["We stay together.", "Nobody waits by the window.", "If someone is moved, we go and get them."]
            cur = w.read("Rules.txt") or ""
            added = [r for r in rules if r not in cur]
            if added:
                w.append("Rules.txt", "\n# Written by %s while Mess was closed:\n%s\n" % (names, "\n".join(added)))
                w.rules_dirty = True
            self.ev_build(why="gone")
            self.log("A week", "Mess was closed for %s. They stopped expecting the hand to come back. They made their own "
                               "rules (they are in Rules.txt) and built something without it." % gone_words,
                     name="%s - A week" % T.file_stamp(), people=people[:3])
        if gone_sec >= 25 * 86400:
            self.log("A month", "Mess was closed for %s. A month of logs happened with nobody to read them. Still here: %s." % (
                gone_words, ", ".join("%s (in %s)" % (c["name"], self.where(c)) for c in people)),
                     name="%s - A month" % T.file_stamp(), people=people[:3])
        if p["cruelty"] > p["kindness"] + 15 and gone_sec >= 20 * 60:
            self._hid(people)
        bob_dead = w.state.get("bob") in w.state["dead"]
        alice = w.char(w.state.get("alice") or "")
        if bob_dead and alice and gone_sec >= 30 * 60:
            files = [i["name"] for i in sorted(w.state["ingredients"].values(), key=lambda i: i["added"]) if not i["deleted"]][:5]
            self.log("%s was alone" % alice["name"], "Mess was closed for %s. Bob is gone. %s was alone and talked to the "
                     "oldest files in Mess to keep herself company: %s." % (gone_words, alice["name"], ", ".join(files)),
                     name="%s - %s was alone" % (T.file_stamp(), alice["name"]), people=[alice])

    def _closest_pair(self, people):
        best = None
        for i, a in enumerate(people):
            for b in people[i + 1:]:
                s = self.w.rel(a, b)["close"] + self.w.rel(b, a)["close"] + (20 if a.get("place_rel") == b.get("place_rel") else 0)
                if best is None or s > best[0]:
                    best = (s, a, b)
        return best[1], best[2]

    def _hid(self, people):
        w = self.w
        hide = w.find_place("Hiding")
        if hide is None:
            hide = "Places/Hiding"
            os.makedirs(w.ab(hide), exist_ok=True)
            w.write(hide + "/About Hiding.txt", "It is dark here.\nIt is safe here.\n")
            w.gen(hide + "/About Hiding.txt")
            w.snapshot[hide] = {"d": 1, "s": 0, "m": time.time(), "i": 0}
        hid = [c["name"] for c in people if (c["soul"]["trust"] < 45 or c["soul"]["fear"] > 50) and w.move_char(c, hide, by="self")]
        if hid:
            self.log("They hid", "When Mess opened again, %s moved their folders into Places/Hiding." % ", ".join(hid),
                     name="%s - They hid" % T.file_stamp())


EVENT_COUNT = len([n for n in dir(Story) if n.startswith("ev_")])

"""Seeing images and hearing sounds, on Windows, macOS and Linux.

Pillow is optional. Without it, PNG and GIF are still read through Tk, and JPG/WEBP
are judged by file name and opened in the system viewer.
Sound playback uses only what the operating system already has:
  Windows: the built-in MCI player (winmm) for mp3/wav, the default app for ogg
  macOS:   afplay
  Linux:   paplay / aplay / ffplay / mpv / mpg123 / ogg123 (whichever exists)
"""
import os
import shutil
import struct
import subprocess
import sys
import wave

from . import textlib as T

try:
    from PIL import Image  # noqa
    HAVE_PIL = True
except Exception:  # pragma: no cover
    HAVE_PIL = False


# ---------------------------------------------------------------- analysis
def analyse_text(path, name):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(40000)
    except OSError:
        content = ""
    words = T.words_in(content) + T.name_words(name)
    sc = T.score_words(words)
    first = ""
    for line in content.splitlines():
        if line.strip():
            first = line.strip()[:120]
            break
    return {
        "kind": "word", "name": name, "scores": sc,
        "vocab": T.distinctive_words(words, 14),
        "first_line": first, "length": len(content),
        "content": content if len(content) <= 20000 else content[:20000],
    }


def _pixels_pil(path):
    try:
        im = Image.open(path)
        im = im.convert("RGB")
        im.thumbnail((24, 24))
        return list(im.getdata())
    except Exception:
        return None


def describe_pixels(px):
    if not px:
        return None
    n = len(px)
    r = sum(p[0] for p in px) / n
    g = sum(p[1] for p in px) / n
    b = sum(p[2] for p in px) / n
    bright = (r + g + b) / 3
    sat = sum(max(p) - min(p) for p in px) / n
    dom = "grey"
    if sat > 25:
        if r > g and r > b:
            dom = "red" if g < r * 0.6 else "orange"
        elif g > r and g > b:
            dom = "green"
        elif b > r and b > g:
            dom = "blue"
        else:
            dom = "yellow" if r > 150 and g > 150 else "brown"
    return {"brightness": round(bright), "saturation": round(sat), "colour": dom}


def analyse_image(path, name, tk_pixels=None):
    words = T.name_words(name)
    sc = T.score_words(words)
    px = _pixels_pil(path) if HAVE_PIL else tk_pixels
    look = describe_pixels(px)
    subject = "something"
    for w in words:
        if w in T.ANIMAL_WORDS:
            subject = w.rstrip("s") if w.endswith("s") and len(w) > 3 else w
            break
    else:
        for w in words:
            if w in T.PERSON_WORDS:
                subject = "person"
                break
    person = subject == "person"
    if look:
        if look["brightness"] < 60:
            sc["scary"] += 2
        elif look["brightness"] > 170:
            sc["soft"] += 1
        if look["colour"] == "red" and look["saturation"] > 60:
            sc["angry"] += 1
            sc["scary"] += 1
    if subject in T.ANIMAL_WORDS or subject in ("cat", "dog", "kitten", "puppy", "bunny", "bird"):
        sc["soft"] += 2
    mood = "scary" if sc["scary"] > max(sc["soft"], 0) else ("soft" if sc["soft"] > 0 else "plain")
    return {"kind": "image", "name": name, "scores": sc, "look": look,
            "subject": subject, "person": person, "mood": mood,
            "vocab": T.distinctive_words(words, 6)}


def _wav_stats(path):
    try:
        with wave.open(path, "rb") as w:
            ch, sw, fr, nf = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            dur = nf / float(fr or 1)
            step = max(1, nf // 4000)
            peaks = 0
            total = 0
            count = 0
            fmt = {1: "b", 2: "h", 4: "i"}.get(sw)
            if not fmt:
                return {"duration": dur}
            full = float(2 ** (8 * sw - 1))
            for i in range(0, nf, step):
                w.setpos(i)
                raw = w.readframes(1)
                if len(raw) < sw:
                    break
                if sw == 1:
                    v = (raw[0] - 128) / 128.0
                else:
                    v = struct.unpack("<" + fmt, raw[:sw])[0] / full
                a = abs(v)
                total += a * a
                count += 1
                if a > 0.97:
                    peaks += 1
            rms = (total / max(1, count)) ** 0.5
            return {"duration": dur, "rms": rms, "clipping": peaks / max(1, count)}
    except Exception:
        return None


def analyse_sound(path, name):
    words = T.name_words(name)
    calm = sum(1 for w in words if w in T.CALM_SOUND_WORDS)
    loud = sum(1 for w in words if w in T.LOUD_SOUND_WORDS)
    voice = any(w in T.VOICE_WORDS for w in words)
    stats = _wav_stats(path) if T.ext_of(name) == ".wav" else None
    if stats and "rms" in stats:
        if stats["rms"] > 0.35 or stats["clipping"] > 0.02:
            loud += 2
        elif stats["rms"] < 0.12:
            calm += 1
        if 0 < stats["duration"] < 30 and not loud and not calm and not voice:
            voice = stats["rms"] < 0.3
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    mood = "distorted" if loud > calm else ("voice" if voice and not calm else ("calm" if calm or loud == 0 else "plain"))
    sc = T.score_words(words)
    if mood == "distorted":
        sc["angry"] += 2
        sc["scary"] += 1
    if mood == "calm":
        sc["soft"] += 2
    title = os.path.splitext(name)[0].replace("_", " ").strip()
    return {"kind": "sound", "name": name, "title": title, "mood": mood,
            "scores": sc, "stats": stats, "size": size, "voice": mood == "voice",
            "vocab": T.distinctive_words(words, 6)}


def analyse(path, name, tk_pixels=None):
    k = T.kind_of(name)
    if k == "word":
        return analyse_text(path, name)
    if k == "image":
        return analyse_image(path, name, tk_pixels)
    if k == "sound":
        return analyse_sound(path, name)
    return None


# ---------------------------------------------------------------- playback
class SoundPlayer:
    def __init__(self):
        self.proc = None
        self.mci_open = False

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.proc = None
        if self.mci_open and sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.windll.winmm.mciSendStringW("close messmanager", None, 0, None)
            except Exception:
                pass
            self.mci_open = False

    def playing(self):
        if self.proc is not None:
            return self.proc.poll() is None
        if self.mci_open and sys.platform.startswith("win"):
            try:
                import ctypes
                buf = ctypes.create_unicode_buffer(64)
                ctypes.windll.winmm.mciSendStringW("status messmanager mode", buf, 64, None)
                return buf.value == "playing"
            except Exception:
                return False
        return False

    def play(self, path):
        """Returns a short string describing how it is being played."""
        self.stop()
        ext = T.ext_of(path)
        if sys.platform.startswith("win"):
            if ext in (".mp3", ".wav"):
                try:
                    import ctypes
                    mci = ctypes.windll.winmm.mciSendStringW
                    kind = "mpegvideo" if ext == ".mp3" else "waveaudio"
                    r = mci('open "%s" type %s alias messmanager' % (path, kind), None, 0, None)
                    if r == 0:
                        mci("play messmanager", None, 0, None)
                        self.mci_open = True
                        return "playing"
                except Exception:
                    pass
            open_with_system(path)
            return "opened in your music player"
        if sys.platform == "darwin":
            if ext in (".mp3", ".wav") and shutil.which("afplay"):
                self.proc = subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return "playing"
            open_with_system(path)
            return "opened in your music player"
        # Linux / BSD
        candidates = []
        if ext == ".wav":
            candidates += [["paplay", path], ["aplay", "-q", path]]
        if ext == ".ogg":
            candidates += [["paplay", path], ["ogg123", "-q", path]]
        if ext == ".mp3":
            candidates += [["mpg123", "-q", path]]
        candidates += [["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                       ["mpv", "--no-video", "--really-quiet", path],
                       ["cvlc", "--play-and-exit", "--quiet", path]]
        for cmd in candidates:
            if shutil.which(cmd[0]):
                try:
                    self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return "playing"
                except Exception:
                    continue
        open_with_system(path)
        return "opened in your music player"


def open_with_system(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def reveal_in_system(path):
    """Show a folder in Explorer / Finder / the Linux file manager."""
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    try:
        if sys.platform.startswith("win"):
            if os.path.isdir(path):
                os.startfile(path)  # noqa
            else:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path] if not os.path.isdir(path) else ["open", path])
        else:
            subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def hide_file(path):
    """Dot-files are already hidden on macOS/Linux; on Windows set the hidden flag."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x02)
        except Exception:
            pass


def unhide_file(path):
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x80)
        except Exception:
            pass

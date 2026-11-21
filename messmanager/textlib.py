"""Plain-English reading, word moods, glitching and time formatting.

Everything here is pure Python with no dependencies, so it works the same
on Windows, macOS and Linux.
"""
import random
import re
import time

TEXT_EXT = {".txt", ".md"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
SOUND_EXT = {".mp3", ".wav", ".ogg"}

SCARY_WORDS = {
    "dark", "blood", "dead", "death", "die", "dying", "knife", "scream", "screaming",
    "ghost", "monster", "fear", "afraid", "scared", "horror", "nightmare", "teeth",
    "skull", "bone", "bones", "grave", "corpse", "rot", "rotting", "hollow", "eyes",
    "watching", "behind", "alone", "night", "shadow", "shadows", "kill", "hurt",
    "pain", "cold", "basement", "spider", "spiders", "creepy", "scary", "evil",
    "demon", "hell", "burn", "burning", "cut", "wound", "drown", "drowning",
    "missing", "lost", "trapped", "cage", "chains", "void", "abyss", "face", "mask",
    "clown", "doll", "static", "whisper", "whispers", "funeral", "coffin",
}
SOFT_WORDS = {
    "cat", "cats", "kitten", "puppy", "dog", "dogs", "bunny", "rabbit", "flower",
    "flowers", "love", "loved", "warm", "soft", "gentle", "kind", "hug", "hugs",
    "sun", "sunny", "sunshine", "smile", "happy", "home", "safe", "friend",
    "friends", "bread", "tea", "cake", "garden", "rain", "blanket", "sleep",
    "dream", "dreams", "beach", "sea", "ocean", "sky", "cloud", "clouds", "star",
    "stars", "moon", "music", "song", "sing", "laugh", "laughing", "baby",
    "apple", "apples", "honey", "cozy", "cosy", "pretty", "beautiful", "bird",
    "birds", "butterfly", "spring", "summer", "light", "candle", "mother", "mum",
    "mom", "dad", "grandma", "grandad", "picnic", "puppies", "kittens", "heart",
}
ANGRY_WORDS = {
    "hate", "angry", "rage", "fight", "fighting", "punch", "smash", "break",
    "broken", "stupid", "idiot", "shut", "kill", "destroy", "war", "fire", "burn",
    "scream", "yell", "furious", "mad", "revenge", "enemy", "attack", "loud",
    "metal", "noise", "crash", "explode", "explosion", "gun", "bite", "riot",
}
SAD_WORDS = {
    "sad", "cry", "crying", "tears", "lonely", "alone", "miss", "missing", "gone",
    "goodbye", "lost", "sorry", "empty", "grey", "gray", "rain", "funeral",
    "forgot", "forget", "leave", "left", "nobody", "never", "hollow", "tired",
}
CALM_SOUND_WORDS = {
    "calm", "lullaby", "piano", "ambient", "rain", "sleep", "chill", "lofi",
    "lo-fi", "soft", "acoustic", "waves", "ocean", "forest", "birds", "relax",
    "relaxing", "meditation", "harp", "violin", "cello", "gentle", "quiet",
    "classical", "jazz", "slow", "song", "music",
}
LOUD_SOUND_WORDS = {
    "loud", "metal", "noise", "distort", "distorted", "distortion", "scream",
    "screaming", "static", "glitch", "crash", "bass", "drop", "dubstep",
    "industrial", "siren", "alarm", "horn", "harsh", "feedback", "earrape",
    "blast", "boom", "explosion", "drill", "chainsaw",
}
VOICE_WORDS = {
    "voice", "memo", "recording", "rec", "me", "talking",
    "message", "voicemail", "speech", "hello", "hi",
}
PERSON_WORDS = {
    "person", "man", "woman", "boy", "girl", "me", "selfie", "portrait", "face",
    "friend", "mum", "mom", "dad", "mother", "father", "sister", "brother",
    "grandma", "grandad", "family", "people", "baby", "kid", "child", "wife",
    "husband", "girlfriend", "boyfriend", "photo", "headshot", "profile",
}
ANIMAL_WORDS = {
    "cat", "cats", "kitten", "dog", "dogs", "puppy", "bird", "fish", "rabbit",
    "bunny", "horse", "fox", "owl", "bear", "frog", "mouse", "hamster", "duck",
    "cow", "sheep", "pig", "goat", "deer", "wolf", "lizard", "snake", "turtle",
}

KIND_PHRASES = [
    "love you", "i love", "you're good", "you are good", "good job", "well done",
    "proud of you", "i'm here", "im here", "i am here", "you're safe", "you are safe",
    "it's okay", "its okay", "it's ok", "its ok", "don't worry", "dont worry",
    "thank you", "thanks", "you're kind", "sweet", "i care", "i like you",
    "you're my friend", "you are my friend", "hug", "goodnight", "good night",
    "sleep well", "you matter", "beautiful", "i missed you", "missed you",
    "you're doing great", "brave", "it's alright", "its alright", "i'm sorry",
    "im sorry", "i am sorry", "sorry", "forgive", "i'll protect", "ill protect",
    "i will protect", "you're not alone", "you are not alone", "please",
    "how are you", "are you okay", "are you ok", "you're cute", "cute",
]
CRUEL_PHRASES = [
    "hate you", "shut up", "you're nothing", "you are nothing", "worthless",
    "stupid", "idiot", "die", "kill you", "delete you", "i'll delete", "ill delete",
    "i will delete", "you're just a file", "you are just a file", "just files",
    "not real", "you're not real", "you are not real", "nobody cares", "no one cares",
    "ugly", "pathetic", "disgusting", "useless", "go away", "leave me alone",
    "i don't care", "i dont care", "you're a mistake", "mistake", "freak",
    "dumb", "loser", "burn", "trash", "garbage", "rot", "be quiet",
]
LIE_DENIALS = [
    "i didn't", "i didnt", "i did not", "wasn't me", "wasnt me", "not me",
    "i never", "it was an accident", "i don't know what", "i dont know what",
]
PROMISES = [
    "i promise", "i won't delete", "i wont delete", "i will not delete",
    "i won't hurt", "i wont hurt", "i will never", "i'll never", "ill never",
    "i won't leave", "i wont leave", "i'll come back", "ill come back",
    "i will come back", "i won't move", "i wont move",
]

STOP_WORDS = set("""a an the and or but if of to in on at for with without from by is are was
were be been being am i you he she it we they me him her them my your his its our their this
that these those there here what which who whom whose when where why how not no yes so too very
just can will would should could do does did done have has had having than then also into out up
down over under again once all any some each few more most other such only own same s t don
now about as like get got go going went make made know think want really thing things one two
im ive dont cant wont isnt its youre theyre were lets ok okay oh hello hi""".split())

NAME_POOL = [
    "Milo", "June", "Ivy", "Theo", "Wren", "Nell", "Otto", "Mae", "Rue", "Ezra",
    "Hazel", "Juno", "Felix", "Iris", "Silas", "Pip", "Clara", "Arlo", "Tess",
    "Jude", "Ada", "Rowan", "Lark", "Fern", "Abel", "Vera", "Noor", "Elio",
    "Maple", "Sol", "Lumi", "Quinn", "Oona", "Remy", "Bea", "Cass", "Dov", "Lior",
    "Kit", "Poppy", "Sage", "Toby", "Willa", "Yara", "Zev", "Esme", "Hugo", "Nina",
]
CHILD_NAMES = ["Pebble", "Tuck", "Dot", "Bramble", "Lettie", "Sprout", "Moth",
               "Button", "Penny", "Robin", "Pim", "Clem", "Wick", "Fen", "Teddy"]

GLITCH = "▓▒░█▌▐■□▪◘◙╳"


def ext_of(name):
    i = name.rfind(".")
    return name[i:].lower() if i > 0 else ""


def kind_of(name):
    e = ext_of(name)
    if e in TEXT_EXT:
        return "word"
    if e in IMAGE_EXT:
        return "image"
    if e in SOUND_EXT:
        return "sound"
    return None


def words_in(text):
    return re.findall(r"[a-zA-Z][a-zA-Z'\-]*", text.lower())


def name_words(filename):
    base = filename.rsplit(".", 1)[0]
    return words_in(re.sub(r"[_\-\.\d]+", " ", base))


def score_words(words):
    s = {"scary": 0, "soft": 0, "angry": 0, "sad": 0}
    for w in words:
        if w in SCARY_WORDS:
            s["scary"] += 1
        if w in SOFT_WORDS:
            s["soft"] += 1
        if w in ANGRY_WORDS:
            s["angry"] += 1
        if w in SAD_WORDS:
            s["sad"] += 1
    return s


def distinctive_words(words, limit=12):
    seen = []
    for w in words:
        w = w.strip("'-")
        if len(w) < 4 or w in STOP_WORDS or w in seen:
            continue
        seen.append(w)
    # prefer emotionally loaded words first, then long ones
    loaded = [w for w in seen if w in SCARY_WORDS or w in SOFT_WORDS or w in ANGRY_WORDS or w in SAD_WORDS]
    rest = sorted([w for w in seen if w not in loaded], key=lambda x: -len(x))
    return (loaded + rest)[:limit]


def contains_any(text, phrases):
    t = " " + text.lower() + " "
    return [p for p in phrases if p in t]


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def glitch_text(text, amount):
    """amount 0..1: how much of the text rots."""
    if amount <= 0:
        return text
    rnd = random.Random(len(text))
    out = []
    for ch in text:
        if ch in "\r\n":
            out.append(ch)
            continue
        r = rnd.random()
        if r < amount * 0.25:
            out.append(rnd.choice(GLITCH))
        elif r < amount * 0.35:
            out.append(ch + "_")
        elif r < amount * 0.42:
            out.append(ch.upper() if ch.islower() else ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def light_glitch(line, amount):
    if amount < 0.35:
        return line
    return glitch_text(line, (amount - 0.3) * 0.6)


def ago(ts, now=None):
    now = now or time.time()
    d = max(0, now - ts)
    if d < 10:
        return "just now"
    if d < 60:
        return "%d seconds ago" % d
    m = d / 60
    if m < 60:
        n = int(m)
        return "1 minute ago" if n == 1 else "%d minutes ago" % n
    h = m / 60
    if h < 24:
        n = int(h)
        return "1 hour ago" if n == 1 else "%d hours ago" % n
    dd = h / 24
    if dd < 30:
        n = int(dd)
        return "yesterday" if n == 1 else "%d days ago" % n
    mo = dd / 30
    if mo < 12:
        n = int(mo)
        return "1 month ago" if n == 1 else "%d months ago" % n
    n = int(mo / 12)
    return "1 year ago" if n == 1 else "%d years ago" % n


def duration_words(seconds):
    m = seconds / 60
    if m < 60:
        return "%d minutes" % max(1, int(m))
    h = m / 60
    if h < 48:
        return "%d hours" % int(h)
    d = h / 24
    if d < 60:
        return "%d days" % int(d)
    return "%d months" % int(d / 30)


def human_size(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "bytes" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def stamp(ts=None):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts or time.time()))


def file_stamp(ts=None):
    # no colons: Windows forbids them in file names
    return time.strftime("%Y-%m-%d %H-%M", time.localtime(ts or time.time()))


def safe_name(s, limit=60):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s).strip().strip(".")
    return (s or "untitled")[:limit]


def clean_char_name(folder_name):
    """Turn whatever the folder is called on disk back into a person's name."""
    n = folder_name
    n = re.sub(r"\s*\(\d+\)$", "", n)            # Bob (1)
    n = re.sub(r"\s*\((again|returned|copy)\)$", "", n, flags=re.I)
    n = re.sub(r"\s*-\s*copy(\s*\(\d+\))?$", "", n, flags=re.I)
    n = re.sub(r"\s+copy(\s*\d+)?$", "", n, flags=re.I)
    if re.fullmatch(r"(\w_)+\w", n):              # B_o_b
        n = n.replace("_", "")
    n = n.strip() or folder_name
    return n[:40]


def pick(rnd, seq):
    return seq[rnd.randrange(len(seq))] if seq else None

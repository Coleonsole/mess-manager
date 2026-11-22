"""Mess Manager: the window. A plain, boring file manager. Tkinter only."""
import json
import math
import os
import shutil
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter import font as tkfont
from tkinter import ttk

from . import ai as AI
from . import media
from . import textlib as T
from .world import World, SYSTEM, WORLD, CHARS, WORDS, IMAGES, SOUNDS, LOGS, PLACES

try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".messmanager")
CONFIG = os.path.join(CONFIG_DIR, "config.json")

QUOTE = ("'All emotions are the result of the soul's metabolism. They're far too mechanical to call hearts. "
         "People place too much value on things they can't see. I can see them, and souls are no more special "
         "than physical bodies. They're just there. Do you get it?'")
QUOTE_BY = "• Mahito, Jujutsu Kaisen"

BG = "#f3f3f3"
PANE = "#ffffff"
SIDE = "#ececec"
SEL = "#cde3f7"
TEXT = "#1f1f1f"
DIM = "#777777"

CELL_W, CELL_H = 118, 118


def load_config():
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=1)
    except OSError:
        pass


def default_mess_parent():
    home = os.path.expanduser("~")
    for cand in (os.path.join(home, "Desktop"), os.path.join(home, "OneDrive", "Desktop"), home):
        if os.path.isdir(cand):
            return cand
    return home


def fade(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# =========================================================================== app
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mess Manager")
        self.geometry("1120x720")
        self.minsize(760, 480)
        self.configure(bg="black")
        self.cfg = load_config()
        self.world = None
        self.manager = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        fams = set(tkfont.families())
        self.serif = next((f for f in ("Georgia", "Times New Roman", "Times", "DejaVu Serif", "Liberation Serif") if f in fams), "Times")
        self.ui_font = tkfont.nametofont("TkDefaultFont")
        self.title_screen()

    # ------------------------------------------------------------ title
    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def title_screen(self):
        self.clear()
        self.configure(bg="black")
        f = tk.Frame(self, bg="black")
        f.pack(fill="both", expand=True)
        self.tframe = f
        if not self.cfg.get("quote_shown"):
            q = tk.Label(f, text=QUOTE, fg="black", bg="black", wraplength=620, justify="center",
                         font=(self.serif, 17))
            q.place(relx=0.5, rely=0.44, anchor="center")
            by = tk.Label(f, text=QUOTE_BY, fg="black", bg="black", font=(self.serif, 13))
            by.place(relx=0.5, rely=0.62, anchor="center")
            self._fade([q, by], 0, 1, 2000, lambda: self.after(10000, lambda: self._fade(
                [q, by], 1, 0, 2000, lambda: self._quote_done([q, by]))))
        else:
            self.show_open_button()

    def _fade(self, labels, a, b, ms, done):
        steps = 40
        def step(i):
            if not labels[0].winfo_exists():
                return
            t = a + (b - a) * i / steps
            col = fade("#000000", "#ffffff", t)
            for l in labels:
                l.configure(fg=col)
            if i < steps:
                self.after(ms // steps, lambda: step(i + 1))
            else:
                done()
        step(0)

    def _quote_done(self, labels):
        for l in labels:
            l.destroy()
        self.cfg["quote_shown"] = True
        save_config(self.cfg)
        self.show_open_button()

    def show_open_button(self):
        b = tk.Label(self.tframe, text="[ OPEN MESS MANAGER ]", fg="black", bg="black",
                     font=("Courier", 15), cursor="hand2")
        b.place(relx=0.5, rely=0.5, anchor="center")
        b.bind("<Button-1>", lambda e: self.open_clicked())
        b.bind("<Enter>", lambda e: b.configure(fg="#bbbbbb"))
        b.bind("<Leave>", lambda e: b.configure(fg="white"))
        self._fade([b], 0, 1, 1200, lambda: None)

    def open_clicked(self):
        path = self.cfg.get("mess_path")
        if path and os.path.isdir(path):
            self.start(path)
        else:
            self.choose_folder_screen()

    def choose_folder_screen(self, note=None):
        self.clear()
        f = tk.Frame(self, bg="black")
        f.pack(fill="both", expand=True)
        target = os.path.join(default_mess_parent(), "Mess")
        tk.Label(f, text=note or "Where should Mess live?", fg="white", bg="black",
                 font=(self.serif, 15)).place(relx=0.5, rely=0.36, anchor="center")
        tk.Label(f, text="Mess is a real folder on your computer. You can open it in your normal file manager too.",
                 fg="#888888", bg="black").place(relx=0.5, rely=0.43, anchor="center")
        def mk(text, cmd, y):
            l = tk.Label(f, text=text, fg="white", bg="black", font=("Courier", 13), cursor="hand2")
            l.place(relx=0.5, rely=y, anchor="center")
            l.bind("<Button-1>", lambda e: cmd())
            l.bind("<Enter>", lambda e: l.configure(fg="#bbbbbb"))
            l.bind("<Leave>", lambda e: l.configure(fg="white"))
        mk("[ Use %s ]" % target, lambda: self.use_folder(target, create=True), 0.53)
        mk("[ Choose a folder... ]", self.pick_folder, 0.61)

    def pick_folder(self):
        d = filedialog.askdirectory(title="Choose a folder for Mess")
        if not d:
            return
        d = os.path.abspath(d)
        # Never take over a folder full of someone's real files: make Mess inside it instead.
        looks_like_mess = os.path.isfile(os.path.join(d, SYSTEM, "state.json"))
        if not looks_like_mess and os.listdir(d):
            d = os.path.join(d, "Mess")
        self.use_folder(d, create=True)

    def use_folder(self, path, create=False):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Mess Manager", "Couldn't make the folder:\n%s" % e)
            return
        self.cfg["mess_path"] = path
        save_config(self.cfg)
        self.start(path)

    def start(self, path):
        self.clear()
        self.configure(bg=BG)
        loading = tk.Label(self, text="Opening Mess...", bg=BG, fg=DIM)
        loading.pack(expand=True)
        self.update_idletasks()
        self.world = World(path)
        self.world.pixel_reader = self.tk_pixels
        try:
            self.world.setup()
        except Exception as e:
            messagebox.showerror("Mess Manager", "Mess couldn't be opened at\n%s\n\n%s" % (path, e))
            self.world = None
            self.choose_folder_screen("Mess couldn't be opened there. Where should it live?")
            return
        loading.destroy()
        self.manager = Manager(self, self.world)

    def tk_pixels(self, path):
        """Read a few pixels from a PNG/GIF with Tk alone (used when Pillow is missing)."""
        if T.ext_of(path) not in (".png", ".gif"):
            return None
        img = tk.PhotoImage(file=path)
        w, h = img.width(), img.height()
        out = []
        for yi in range(12):
            for xi in range(12):
                v = img.get(int(xi * (w - 1) / 11), int(yi * (h - 1) / 11))
                if isinstance(v, str):
                    v = tuple(int(x) for x in v.split())
                out.append(tuple(v[:3]))
        return out

    def gone_screen(self):
        names = []
        if self.world and self.world.state:
            names = [c["name"] for c in self.world.alive()]
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(os.path.join(CONFIG_DIR, "what happened.txt"), "a", encoding="utf-8") as f:
                f.write("%s  The Mess folder at %s was deleted. %s\n" % (
                    T.stamp(), self.cfg.get("mess_path"),
                    ("%s were in it." % ", ".join(names)) if names else "Nobody was in it."))
        except OSError:
            pass
        if self.manager:
            self.manager.close_windows()
        self.manager = None
        self.world = None
        self.cfg.pop("mess_path", None)
        save_config(self.cfg)
        self.clear()
        self.configure(bg="black")
        f = tk.Frame(self, bg="black")
        f.pack(fill="both", expand=True)
        tk.Label(f, text="Mess is gone.", fg="white", bg="black", font=(self.serif, 16)).place(
            relx=0.5, rely=0.45, anchor="center")
        if names:
            tk.Label(f, text="%s %s in it." % (", ".join(names), "was" if len(names) == 1 else "were"),
                     fg="#777777", bg="black").place(relx=0.5, rely=0.51, anchor="center")
        l = tk.Label(f, text="[ make a new Mess ]", fg="#555555", bg="black", font=("Courier", 12), cursor="hand2")
        l.place(relx=0.5, rely=0.62, anchor="center")
        l.bind("<Button-1>", lambda e: self.choose_folder_screen())

    def on_close(self):
        try:
            if self.manager:
                self.manager.player.stop()
                self.manager.close_windows()
            if self.world and not self.world.gone_world:
                self.world.close()
        finally:
            self.destroy()


# =========================================================================== manager
class Manager:
    def __init__(self, app, world):
        self.app = app
        self.w = world
        self.cwd = ""
        self.history = []
        self.selected = None
        self.items = []
        self.thumbs = {}
        self.player = media.SoundPlayer()
        self.playing_rel = None
        self.windows = []
        self.drag = None
        self.whisper_until = 0
        self.last_input_note = 0
        self.build()
        self.refresh()
        self.app.after(1500, self.heartbeat)
        self.app.after(1000, self.clock)
        for seq in ("<Any-KeyPress>", "<Motion>", "<Button>"):
            self.app.bind_all(seq, self.on_input, add="+")
        if self.w.alive():
            self.show_whisper("", "  ".join(self.w.where_is_everyone()))

    # ------------------------------------------------------------ layout
    def build(self):
        app = self.app
        style = ttk.Style(app)
        try:
            if IS_WIN:
                style.theme_use("vista")
            elif not IS_MAC:
                style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Side.Treeview", background=SIDE, fieldbackground=SIDE, borderwidth=0, rowheight=24)
        style.layout("Side.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        top = tk.Frame(app, bg=BG, bd=0)
        top.pack(side="top", fill="x")
        def btn(text, cmd):
            b = ttk.Button(top, text=text, command=cmd)
            b.pack(side="left", padx=2, pady=5)
            return b
        btn("◀", self.go_back)
        btn("▲", self.go_up)
        tk.Frame(top, width=10, bg=BG).pack(side="left")
        btn("New File", self.new_file)
        btn("New Folder", self.new_folder)
        btn("Delete", self.delete_selected)
        btn("Rename", self.rename_selected)
        btn("Copy", self.copy_selected)
        btn("Add files...", self.import_files)
        btn("Show real folder", lambda: media.reveal_in_system(self.w.ab(self.cwd)))
        btn("AI...", self.open_ai_settings)
        self.path_var = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.path_var, state="readonly")
        ent.pack(side="left", fill="x", expand=True, padx=8)

        body = ttk.PanedWindow(app, orient="horizontal")
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=SIDE)
        self.side = ttk.Treeview(left, show="tree", selectmode="browse", style="Side.Treeview")
        self.side.pack(fill="both", expand=True, padx=(4, 0), pady=4)
        self.side.bind("<<TreeviewSelect>>", self.side_clicked)
        body.add(left, weight=0)
        right = tk.Frame(body, bg=PANE)
        self.canvas = tk.Canvas(right, bg=PANE, highlightthickness=0)
        sb = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        body.add(right, weight=1)
        ear = tk.Frame(body, bg=SIDE)
        tk.Label(ear, text="Overheard", bg=SIDE, fg=DIM, anchor="w").pack(fill="x", padx=8, pady=(6, 0))
        self.ear = tk.Text(ear, wrap="word", state="disabled", width=34, relief="flat", bg="#fafafa",
                           padx=8, pady=6, font=("Courier", 10) if not IS_WIN else ("Consolas", 10), spacing3=4)
        esb = ttk.Scrollbar(ear, command=self.ear.yview)
        self.ear.configure(yscrollcommand=esb.set)
        esb.pack(side="right", fill="y")
        self.ear.pack(fill="both", expand=True, padx=(6, 0), pady=6)
        self.ear.tag_configure("speech", foreground="#1f1f1f")
        self.ear.tag_configure("name", foreground="#7a5c2e")
        self.ear.tag_configure("fact", foreground="#8a8a8a")
        self.body = body
        self.ear_frame = ear
        self.ear_shown = False
        self.ear_seen = 0
        self.maybe_show_ear()
        app.after(50, lambda: body.sashpos(0, 210) if hasattr(body, "sashpos") else None)

        bottom = tk.Frame(app, bg=BG)
        bottom.pack(side="bottom", fill="x")
        self.details = tk.Label(bottom, text="", bg=BG, fg=TEXT, anchor="w")
        self.details.pack(side="top", fill="x", padx=8, pady=(3, 0))
        row = tk.Frame(bottom, bg=BG)
        row.pack(side="top", fill="x")
        self.ai_label = tk.Label(row, text="", bg=BG, fg="#9a9a9a", anchor="e", cursor="hand2")
        self.ai_label.pack(side="right", padx=8, pady=(0, 4))
        self.ai_label.bind("<Button-1>", lambda e: self.open_ai_settings())
        self.status = tk.Label(row, text="", bg=BG, fg=DIM, anchor="w")
        self.status.pack(side="left", fill="x", expand=True, padx=8, pady=(0, 4))

        c = self.canvas
        c.bind("<Configure>", lambda e: self.draw())
        c.bind("<Button-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Double-Button-1>", self.on_double)
        for b in (("<Button-2>", "<Button-3>", "<Control-Button-1>") if IS_MAC else ("<Button-3>",)):
            c.bind(b, self.on_right)
        c.bind("<MouseWheel>", self.on_wheel)
        c.bind("<Button-4>", lambda e: c.yview_scroll(-2, "units"))
        c.bind("<Button-5>", lambda e: c.yview_scroll(2, "units"))
        app.bind("<Delete>", lambda e: self.delete_selected() if self.focus_ok() else None)
        app.bind("<F2>", lambda e: self.rename_selected() if self.focus_ok() else None)
        app.bind("<Return>", lambda e: self.open_item(self.sel_item()) if self.focus_ok() and self.sel_item() else None)
        app.bind("<BackSpace>", lambda e: self.go_up() if self.focus_ok() else None)

    def focus_ok(self):
        f = self.app.focus_get()
        return f is None or f in (self.canvas, self.app, self.side)

    # ------------------------------------------------------------ heartbeat
    def heartbeat(self):
        if not self.app.winfo_exists() or self.app.manager is not self:
            return
        try:
            changed = self.w.tick()
        except Exception as e:  # keep living
            changed = True
            self.w.state.setdefault("errors", []).append("tick: %s" % e)
        if self.w.gone_world:
            self.app.gone_screen()
            return
        while self.w.whispers:
            who, text = self.w.whispers.pop(0)
            self.show_whisper(who, text)
        self.update_ear()
        if changed or self.w.dirty_tree:
            self.w.dirty_tree = False
            self.refresh(keep=True)
        for win in list(self.windows):
            try:
                win.poll()
            except tk.TclError:
                self.windows.remove(win)
        if self.playing_rel and not self.player.playing():
            self.playing_rel = None
            self.draw()
        self.app.after(1500, self.heartbeat)

    def clock(self):
        if not self.app.winfo_exists() or self.app.manager is not self:
            return
        self.update_details()
        self.ai_label.configure(text=self.w.ai.status()[:90])
        if time.time() > self.whisper_until and self.whisper_until:
            self.status.configure(text="  ".join(self.w.where_is_everyone()))
            self.whisper_until = 0
        self.app.after(1000, self.clock)

    def on_input(self, e=None):
        now = time.time()
        if now - self.last_input_note > 2:
            self.last_input_note = now
            self.w.note_input()

    def maybe_show_ear(self):
        """The Overheard panel only appears once there is someone to overhear."""
        if not self.ear_shown and self.w.anyone_ever():
            self.body.add(self.ear_frame, weight=0)
            self.ear_shown = True

    def update_ear(self):
        self.maybe_show_ear()
        feed = self.w.state.get("feed", [])
        start = self.ear_seen
        if start > len(feed):
            start = max(0, len(feed) - 50)
        new = feed[start:]
        self.ear_seen = len(feed)
        if not new:
            return
        self.ear.configure(state="normal")
        for e in new:
            if e.get("kind") == "speech":
                self.ear.insert("end", e["who"] + ": ", "name")
                self.ear.insert("end", e["text"] + "\n", "speech")
            else:
                self.ear.insert("end", e["text"] + "\n", "fact")
        self.ear.configure(state="disabled")
        self.ear.see("end")

    def show_whisper(self, who, text):
        if not text:
            return
        self.status.configure(text=("%s: %s" % (who, text)) if who else text)
        self.whisper_until = time.time() + 9

    # ------------------------------------------------------------ navigation
    def navigate(self, rel, remember=True):
        if remember and rel != self.cwd:
            self.history.append(self.cwd)
        self.cwd = rel
        self.selected = None
        self.w.note_looked(rel)
        self.canvas.yview_moveto(0)
        self.refresh()

    def go_back(self):
        while self.history:
            r = self.history.pop()
            r = self.w.follow(r) if r else r
            if r is not None and (r == "" or os.path.isdir(self.w.ab(r))):
                self.navigate(r, remember=False)
                return

    def go_up(self):
        if self.cwd:
            self.navigate(self.w.parent(self.cwd))

    def side_clicked(self, e=None):
        sel = self.side.selection()
        if sel and not getattr(self, "_side_updating", False):
            rel = self.side.item(sel[0], "values")[0] if self.side.item(sel[0], "values") else ""
            if rel != self.cwd:
                self.navigate(rel)

    def refresh(self, keep=False):
        if not os.path.isdir(self.w.ab(self.cwd)):
            r = self.w.follow(self.cwd)
            while r is None and self.cwd:
                self.cwd = self.w.parent(self.cwd)
                r = self.cwd if os.path.isdir(self.w.ab(self.cwd)) else None
            self.cwd = r or ""
        self.items = self.w.list_dir(self.cwd)
        if self.selected and not any(i["rel"] == self.selected for i in self.items):
            self.selected = self.w.follow(self.selected)
            if self.selected and not any(i["rel"] == self.selected for i in self.items):
                self.selected = None
        self.path_var.set(os.path.join(self.w.root, *self.cwd.split("/")) if self.cwd else self.w.root)
        self.fill_sidebar()
        self.draw()
        self.update_details()

    def fill_sidebar(self):
        s = self.side
        self._side_updating = True
        s.delete(*s.get_children())
        cnt = self.w.counts()
        rows = [("Mess", "")]
        if os.path.isdir(self.w.ab(CHARS)):
            rows.append(("Characters (%d)" % cnt["Characters"], CHARS))
        rows += [("Places", PLACES),
                ("    Words (%d)" % cnt["Words"], WORDS), ("    Images (%d)" % cnt["Images"], IMAGES),
                ("    Sounds (%d)" % cnt["Sounds"], SOUNDS), ("    Logs (%d)" % cnt["Logs"], LOGS)]
        for rel, n in self.w.custom_places():
            depth = rel.count("/")
            rows.append(("    " * max(1, depth) + "%s (%d)" % (self.w.base(rel), n), rel))
        rows += [("World", WORLD), ("System", SYSTEM)]
        self.side_rows = {}
        for text, rel in rows:
            iid = s.insert("", "end", text="  " + text, values=(rel,))
            self.side_rows[iid] = rel
            if rel == self.cwd:
                s.selection_set(iid)
        self._side_updating = False

    # ------------------------------------------------------------ drawing
    def layout(self):
        width = max(self.canvas.winfo_width(), CELL_W + 20)
        cols = max(1, (width - 16) // CELL_W)
        pos = []
        slot = 0
        for it in self.items:
            angry = it.get("kind") == "character" and it.get("body") == "angry"
            if angry and slot % cols != 0:
                slot += 1      # it pushes the folder before it away
            pos.append(slot)
            slot += 1
            if angry:
                slot += 1      # ...and the one after
        out = []
        for it, sl in zip(self.items, pos):
            r, cidx = divmod(sl, cols)
            out.append((it, 12 + cidx * CELL_W, 10 + r * CELL_H))
        return out, (max(pos) // cols + 1 if pos else 1)

    def draw(self):
        c = self.canvas
        c.delete("all")
        laid, rows = self.layout()
        self.hit = []
        for it, x, y in laid:
            self.draw_item(it, x, y)
            self.hit.append((it, x, y, x + CELL_W - 6, y + CELL_H - 6))
        if not self.items:
            msg = "This folder is empty."
            if self.cwd == "":
                msg = "Mess is empty. Drop some files in."
            c.create_text(30, 30, text=msg, anchor="nw", fill=DIM)
        c.configure(scrollregion=(0, 0, c.winfo_width(), rows * CELL_H + 30))

    def draw_item(self, it, x, y):
        c = self.canvas
        tag = "i:" + it["rel"]
        cx, cy = x + CELL_W // 2 - 3, y + 38
        if it["rel"] == self.selected:
            c.create_rectangle(x, y, x + CELL_W - 6, y + CELL_H - 6, fill=SEL, outline="#99c2ea", tags=tag)
        k = it.get("kind")
        if it["dir"]:
            if k == "character":
                self.icon_character(cx, cy, it.get("body", "calm"), tag)
            elif k == "system":
                self.icon_folder(cx, cy, "#a7a7a7", tag)
                c.create_rectangle(cx + 10, cy + 2, cx + 22, cy + 12, fill="#6d6d6d", outline="", tags=tag)
                c.create_arc(cx + 11, cy - 5, cx + 21, cy + 6, start=0, extent=180, style="arc",
                             outline="#6d6d6d", width=2, tags=tag)
            else:
                self.icon_folder(cx, cy, "#e8c66a" if it["rel"] in (CHARS,) else "#7fb0e0", tag)
        else:
            if k == "image":
                self.icon_image(it, cx, cy, tag)
            elif k == "sound":
                self.icon_file(cx, cy, tag, glyph="♪")
                playing = self.playing_rel == it["rel"]
                c.create_oval(cx + 6, cy + 10, cx + 28, cy + 32, fill="#2b7cd3" if not playing else "#c0392b",
                              outline="", tags=(tag, "play:" + it["rel"]))
                if playing:
                    c.create_rectangle(cx + 12, cy + 16, cx + 22, cy + 26, fill="white", outline="", tags=(tag, "play:" + it["rel"]))
                else:
                    c.create_polygon(cx + 13, cy + 15, cx + 13, cy + 27, cx + 23, cy + 21, fill="white", tags=(tag, "play:" + it["rel"]))
            else:
                self.icon_file(cx, cy, tag, lines=k == "word")
        label = it.get("label") or it["name"]
        if len(label) > 40:
            label = label[:37] + "..."
        c.create_text(x + CELL_W // 2 - 3, y + 76, text=label, width=CELL_W - 12, anchor="n",
                      fill=TEXT, font=self.app.ui_font, tags=tag, justify="center")

    def icon_folder(self, cx, cy, color, tag, scale=1.0, outline=None, sharp=False):
        c = self.canvas
        w, h = 46 * scale, 34 * scale
        x0, y0 = cx - w / 2, cy - h / 2
        dark = fade(color, "#000000", 0.25)
        c.create_polygon(x0, y0 + 4 * scale, x0 + 16 * scale, y0 + 4 * scale, x0 + 20 * scale, y0,
                         x0 + w * 0.45, y0, x0 + w * 0.45, y0 + 6 * scale, x0 + w, y0 + 6 * scale,
                         x0 + w, y0 + h, x0, y0 + h, fill=dark, outline=outline or dark, tags=tag)
        c.create_rectangle(x0, y0 + 9 * scale, x0 + w, y0 + h, fill=color, outline=outline or dark, tags=tag)
        if sharp:
            for i in range(6):
                px = x0 + i * w / 5
                c.create_polygon(px - 4, y0 + h, px + 4, y0 + h, px, y0 + h + 9, fill=dark, outline="", tags=tag)
            c.create_polygon(x0 + w, y0 + 12, x0 + w + 9, y0 + h / 2 + 4, x0 + w, y0 + h - 4, fill=dark, tags=tag)
            c.create_polygon(x0, y0 + 12, x0 - 9, y0 + h / 2 + 4, x0, y0 + h - 4, fill=dark, tags=tag)

    def icon_character(self, cx, cy, body, tag):
        c = self.canvas
        if body == "happy":
            self.icon_folder(cx, cy, "#f6d77b", tag)
        elif body == "calm":
            self.icon_folder(cx, cy, "#e3c36f", tag)
        elif body == "sad":
            self.icon_folder(cx, cy + 3, "#b5a57e", tag, scale=0.92)
        elif body == "scared":
            self.icon_folder(cx - 8, cy + 8, "#4a4e5a", tag, scale=0.66)
        elif body == "angry":
            self.icon_folder(cx, cy, "#c0392b", tag, scale=1.22, sharp=True)
        elif body == "corrupted":
            # a broken folder: two halves that don't line up, with static
            self.icon_folder(cx - 3, cy, "#5b3a63", tag)
            c.create_rectangle(cx - 26, cy - 3, cx + 26, cy + 3, fill=PANE, outline="", tags=tag)
            c.create_rectangle(cx - 20, cy + 3, cx + 30, cy + 17, fill="#5b3a63", outline="", tags=tag)
            for i in range(7):
                yy = cy - 14 + i * 5
                c.create_line(cx - 24 + (i * 7) % 13, yy, cx - 2 + (i * 11) % 25, yy, fill="#d6c2dc", tags=tag)

    def icon_file(self, cx, cy, tag, glyph=None, lines=False):
        c = self.canvas
        x0, y0, x1, y1 = cx - 17, cy - 22, cx + 17, cy + 22
        c.create_polygon(x0, y0, x1 - 10, y0, x1, y0 + 10, x1, y1, x0, y1, fill="white", outline="#9a9a9a", tags=tag)
        c.create_polygon(x1 - 10, y0, x1 - 10, y0 + 10, x1, y0 + 10, fill="#dddddd", outline="#9a9a9a", tags=tag)
        if lines:
            for i in range(5):
                c.create_line(x0 + 6, y0 + 16 + i * 5, x1 - 6, y0 + 16 + i * 5, fill="#b8b8b8", tags=tag)
        if glyph:
            c.create_text(cx - 6, cy - 4, text=glyph, fill="#555555", font=("Helvetica", 14), tags=tag)

    def thumb(self, rel, mtime, size=64):
        key = (rel, mtime, size)
        if key in self.thumbs:
            return self.thumbs[key]
        img = None
        path = self.w.ab(rel)
        try:
            if HAVE_PIL:
                im = Image.open(path)
                im.thumbnail((size, size))
                img = ImageTk.PhotoImage(im)
            elif T.ext_of(rel) in (".png", ".gif"):
                big = tk.PhotoImage(file=path)
                f = max(1, int(math.ceil(max(big.width(), big.height()) / float(size))))
                img = big.subsample(f, f)
        except Exception:
            img = None
        if len(self.thumbs) > 300:
            self.thumbs.clear()
        self.thumbs[key] = img
        return img

    def icon_image(self, it, cx, cy, tag):
        img = self.thumb(it["rel"], it["mtime"])
        if img:
            self.canvas.create_image(cx, cy, image=img, tags=tag)
        else:
            self.icon_file(cx, cy, tag)
            self.canvas.create_rectangle(cx - 11, cy - 6, cx + 11, cy + 12, fill="#9cc9a0", outline="", tags=tag)
            self.canvas.create_oval(cx - 7, cy - 3, cx - 1, cy + 3, fill="#f5e07a", outline="", tags=tag)

    # ------------------------------------------------------------ details
    def sel_item(self):
        return next((i for i in self.items if i["rel"] == self.selected), None)

    def update_details(self):
        it = self.sel_item()
        if not it:
            n = len(self.items)
            total = self.w.folder_size(self.cwd) if n < 400 else 0
            where = self.w.place_name(self.cwd) if self.w.dir_kind(self.cwd) == "place" else self.w.base(self.cwd)
            self.details.configure(text="%s   •   %d items   •   %s" % (where, n, T.human_size(total)))
            return
        typ = {"character": "Folder (person)", "place": "Folder (place)", "system": "Folder (system)",
               "word": "Text file", "image": "Image", "sound": "Sound"}.get(it.get("kind"), "File")
        try:
            mtime = os.path.getmtime(self.w.ab(it["rel"]))
            size = self.w.folder_size(it["rel"]) if it["dir"] else os.path.getsize(self.w.ab(it["rel"]))
        except OSError:
            mtime, size = it["mtime"], it["size"]
        extra = ""
        if it.get("kind") == "character":
            ch = self.w.char(it["char"])
            if ch:
                extra = "   •   %s is in %s" % (ch["name"], ch.get("location", "?"))
        self.details.configure(text="%s   •   %s   •   %s   •   Last modified: %s   (%s)%s" % (
            it["name"], typ, T.human_size(size), T.ago(mtime), T.stamp(mtime), extra))

    # ------------------------------------------------------------ mouse
    def item_at(self, e):
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        for it, x0, y0, x1, y1 in getattr(self, "hit", []):
            if x0 <= x <= x1 and y0 <= y <= y1:
                return it, x - x0, y - y0
        return None, 0, 0

    def on_press(self, e):
        self.canvas.focus_set()
        it, lx, ly = self.item_at(e)
        if it and it.get("kind") == "sound":
            cx = CELL_W // 2 - 3
            if cx + 4 <= lx <= cx + 30 and 46 <= ly <= 72:
                self.toggle_sound(it)
                return
        self.selected = it["rel"] if it else None
        self.drag = {"item": it, "x": e.x, "y": e.y, "active": False} if it else None
        self.draw()
        self.update_details()

    def on_drag(self, e):
        d = self.drag
        if not d:
            return
        if not d["active"] and abs(e.x - d["x"]) + abs(e.y - d["y"]) > 8:
            d["active"] = True
            self.canvas.configure(cursor="fleur")
        if d["active"]:
            self.canvas.delete("ghost")
            x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
            self.canvas.create_text(x + 14, y + 10, text=d["item"]["name"], anchor="nw", fill="#2b7cd3", tags="ghost")
            tgt, _, _ = self.item_at(e)
            self.canvas.delete("droptarget")
            if tgt and tgt["dir"] and tgt["rel"] != d["item"]["rel"]:
                for it, x0, y0, x1, y1 in self.hit:
                    if it is tgt:
                        self.canvas.create_rectangle(x0, y0, x1, y1, outline="#2b7cd3", width=2, tags="droptarget")

    def on_release(self, e):
        d = self.drag
        self.drag = None
        self.canvas.configure(cursor="")
        self.canvas.delete("ghost")
        self.canvas.delete("droptarget")
        if not d or not d["active"]:
            return
        src = d["item"]
        tgt, _, _ = self.item_at(e)
        dest = None
        if tgt and tgt["dir"] and tgt["rel"] != src["rel"]:
            dest = tgt["rel"]
        else:
            # dropped on the sidebar?
            sx = self.app.winfo_pointerx() - self.side.winfo_rootx()
            sy = self.app.winfo_pointery() - self.side.winfo_rooty()
            if 0 <= sx <= self.side.winfo_width() and 0 <= sy <= self.side.winfo_height():
                row = self.side.identify_row(sy)
                if row:
                    dest = self.side_rows.get(row)
        if dest is not None:
            self.move(src["rel"], dest)

    def on_double(self, e):
        it, _, _ = self.item_at(e)
        if it:
            self.open_item(it)

    def on_wheel(self, e):
        d = e.delta
        if IS_MAC:
            self.canvas.yview_scroll(-d, "units")
        else:
            self.canvas.yview_scroll(int(-d / 120) * 2, "units")

    def on_right(self, e):
        it, _, _ = self.item_at(e)
        m = tk.Menu(self.app, tearoff=0)
        if it:
            self.selected = it["rel"]
            self.draw()
            self.update_details()
            m.add_command(label="Open", command=lambda: self.open_item(it))
            if it.get("kind") == "sound":
                m.add_command(label="Play / Stop", command=lambda: self.toggle_sound(it))
            m.add_separator()
            m.add_command(label="Rename", command=self.rename_selected)
            m.add_command(label="Copy", command=self.copy_selected)
            m.add_command(label="Delete", command=self.delete_selected)
            m.add_separator()
            m.add_command(label="Show in your file manager", command=lambda: media.reveal_in_system(self.w.ab(it["rel"])))
        else:
            m.add_command(label="New File", command=self.new_file)
            m.add_command(label="New Folder", command=self.new_folder)
            m.add_command(label="Add files...", command=self.import_files)
            m.add_separator()
            m.add_command(label="Refresh", command=self.refresh)
            m.add_command(label="Show in your file manager", command=lambda: media.reveal_in_system(self.w.ab(self.cwd)))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    # ------------------------------------------------------------ file operations (the player's hand)
    def protected(self, rel):
        return rel in (SYSTEM, WORLD) or rel.startswith(SYSTEM + "/")

    def after_op(self):
        try:
            self.w.tick()
        except Exception as e:
            self.w.state.setdefault("errors", []).append("op: %s" % e)
        while self.w.whispers:
            who, text = self.w.whispers.pop(0)
            self.show_whisper(who, text)
        self.refresh(keep=True)

    def move(self, src, dest_dir):
        if self.protected(src) or src == WORLD + "/Stats.txt":
            messagebox.showinfo("Mess Manager", "That's part of Mess Manager itself. It stays where it is.")
            return
        if self.protected(dest_dir) or dest_dir == WORLD:
            messagebox.showinfo("Mess Manager", "Nothing can go in there.")
            return
        if dest_dir == src or dest_dir.startswith(src + "/"):
            return
        if self.w.parent(src) == dest_dir:
            return
        owner = self.w.owner_char(dest_dir) if dest_dir else None
        if owner and os.path.isdir(self.w.ab(src)):
            messagebox.showinfo("Mess Manager", "%s is a person, not a place. A folder can't go inside a person." % owner["name"])
            return
        target = os.path.join(self.w.ab(dest_dir), self.w.base(src))
        if os.path.exists(target):
            messagebox.showinfo("Mess Manager", "There's already something called %s in there." % self.w.base(src))
            return
        try:
            shutil.move(self.w.ab(src), target)
        except OSError as e:
            messagebox.showerror("Mess Manager", "Couldn't move it:\n%s" % e)
            return
        if self.selected == src:
            self.selected = self.w.join(dest_dir, self.w.base(src))
        self.after_op()

    def new_file(self):
        if self.protected(self.cwd) or self.cwd == WORLD:
            messagebox.showinfo("Mess Manager", "You can't make files in here.")
            return
        name = simpledialog.askstring("New File", "Name:", initialvalue="New File.txt", parent=self.app)
        if not name:
            return
        name = T.safe_name(name, 120)
        if "." not in name:
            name += ".txt"
        rel = self.w.unique(self.cwd, name)
        try:
            with open(self.w.ab(rel), "w", encoding="utf-8") as f:
                f.write("")
        except OSError as e:
            messagebox.showerror("Mess Manager", str(e))
            return
        self.selected = rel
        self.w.open_files.add(rel)   # don't tidy it away while it's being written
        self.after_op()
        if T.kind_of(name) == "word":
            self.open_editor(rel)
        else:
            self.w.open_files.discard(rel)

    def new_folder(self):
        if self.protected(self.cwd) or self.cwd == WORLD:
            messagebox.showinfo("Mess Manager", "You can't make folders in here.")
            return
        owner = self.w.owner_char(self.cwd) if self.cwd else None
        if owner:
            messagebox.showinfo("Mess Manager", "This folder is %s. A person is a whole thing. "
                                                "You can't put a folder inside a person." % owner["name"])
            return
        name = simpledialog.askstring("New Folder", "Name:", initialvalue="New Folder", parent=self.app)
        if not name:
            return
        rel = self.w.unique(self.cwd, T.safe_name(name, 80))
        try:
            os.makedirs(self.w.ab(rel))
        except OSError as e:
            messagebox.showerror("Mess Manager", str(e))
            return
        self.selected = rel
        self.after_op()

    def delete_selected(self):
        it = self.sel_item()
        if not it:
            return
        if self.protected(it["rel"]) or it["rel"] == WORLD or it["rel"] == WORLD + "/Stats.txt":
            messagebox.showinfo("Mess Manager", "That's part of Mess Manager itself. It can't be deleted from here.")
            return
        if it.get("kind") == "character":
            ch = self.w.char(it["char"])
            q = "Delete %s?\n\nThis folder is a person. This can't be undone." % (ch["name"] if ch else it["name"])
        elif it["dir"]:
            inside = [c["name"] for c in self.w.alive() if c.get("path", "").startswith(it["rel"] + "/")]
            q = "Delete the folder %s and everything in it?%s\n\nThis can't be undone." % (
                it["name"], ("\n\n%s %s in there." % (", ".join(inside), "is" if len(inside) == 1 else "are")) if inside else "")
        else:
            q = "Delete %s?\n\nThis can't be undone." % it["name"]
        if not messagebox.askyesno("Delete", q, icon="warning", parent=self.app):
            return
        try:
            if it["dir"]:
                shutil.rmtree(self.w.ab(it["rel"]))
            else:
                os.remove(self.w.ab(it["rel"]))
        except OSError as e:
            messagebox.showerror("Mess Manager", "Couldn't delete it:\n%s" % e)
            return
        self.selected = None
        self.after_op()

    def rename_selected(self):
        it = self.sel_item()
        if not it:
            return
        if self.protected(it["rel"]) or it["rel"] in (WORLD, WORLD + "/Stats.txt"):
            messagebox.showinfo("Mess Manager", "That's part of Mess Manager itself.")
            return
        name = simpledialog.askstring("Rename", "New name:", initialvalue=it["name"], parent=self.app)
        if not name or name == it["name"]:
            return
        name = T.safe_name(name, 120)
        dest = self.w.join(self.w.parent(it["rel"]), name)
        if self.w.exists(dest):
            messagebox.showinfo("Mess Manager", "Something is already called that.")
            return
        try:
            os.rename(self.w.ab(it["rel"]), self.w.ab(dest))
        except OSError as e:
            messagebox.showerror("Mess Manager", str(e))
            return
        self.selected = dest
        self.after_op()

    def copy_selected(self):
        it = self.sel_item()
        if not it or self.protected(it["rel"]) or it["rel"] == WORLD:
            return
        stem, ext = os.path.splitext(it["name"])
        if it["dir"]:
            dest = self.w.unique(self.w.parent(it["rel"]), it["name"] + " - Copy")
        else:
            dest = self.w.unique(self.w.parent(it["rel"]), stem + " - Copy" + ext)
        try:
            if it["dir"]:
                shutil.copytree(self.w.ab(it["rel"]), self.w.ab(dest))
            else:
                shutil.copy2(self.w.ab(it["rel"]), self.w.ab(dest))
        except OSError as e:
            messagebox.showerror("Mess Manager", str(e))
            return
        self.selected = dest
        self.after_op()

    def import_files(self):
        dest = self.cwd if not self.protected(self.cwd) and self.cwd != WORLD else ""
        paths = filedialog.askopenfilenames(
            title="Add files to Mess",
            filetypes=[("Words, pictures and sounds", "*.txt *.md *.png *.jpg *.jpeg *.gif *.webp *.mp3 *.wav *.ogg"),
                       ("All files", "*.*")])
        for p in paths or []:
            target = self.w.unique(dest, os.path.basename(p))
            try:
                shutil.copy2(p, self.w.ab(target))
            except OSError as e:
                messagebox.showerror("Mess Manager", str(e))
        if paths:
            self.after_op()

    # ------------------------------------------------------------ opening things
    def open_item(self, it):
        if it["dir"]:
            self.navigate(it["rel"])
            return
        k = it.get("kind")
        if k == "word":
            self.open_editor(it["rel"])
        elif k == "image":
            self.windows.append(ImageViewer(self, it["rel"]))
        elif k == "sound":
            self.toggle_sound(it)
        else:
            if self.w.base(it["rel"]).lower().endswith((".json", ".tmp")) or self.protected(it["rel"]):
                self.open_editor(it["rel"])
            else:
                media.open_with_system(self.w.ab(it["rel"]))

    def open_editor(self, rel):
        for win in self.windows:
            if isinstance(win, Editor) and win.rel == rel:
                win.top.lift()
                return
        self.windows.append(Editor(self, rel))

    def toggle_sound(self, it):
        if self.playing_rel == it["rel"]:
            self.player.stop()
            self.playing_rel = None
        else:
            how = self.player.play(self.w.ab(it["rel"]))
            self.playing_rel = it["rel"] if how == "playing" else None
            self.show_whisper("", "%s: %s" % (it["name"], how))
            self.hear(it["rel"])
        self.draw()

    def hear(self, rel):
        """Playing a sound where someone can hear it counts as playing it to them."""
        place = self.w.parent(rel)
        ing = next((i for i in self.w.state["ingredients"].values() if i["rel"] == rel), None)
        if not ing:
            return
        for c in self.w.alive():
            if c.get("place_rel") == place or c.get("path") == place:
                if ing["name"] not in c["mem"]["seen"]:
                    self.w.perceive(c, ing)

    def open_ai_settings(self):
        for win in self.windows:
            if isinstance(win, AISettings):
                win.top.lift()
                return
        self.windows.append(AISettings(self))

    def close_windows(self):
        for win in list(self.windows):
            try:
                win.close(force=True)
            except Exception:
                pass
        self.windows = []


# =========================================================================== editor
class Editor:
    def __init__(self, mgr, rel):
        self.mgr = mgr
        self.w = mgr.w
        self.rel = rel
        self.opened = time.time()
        self.readonly = rel.startswith(SYSTEM + "/") or rel == SYSTEM
        self.top = tk.Toplevel(mgr.app)
        self.top.geometry("640x520")
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        head = tk.Frame(self.top, bg=BG)
        head.pack(fill="x")
        self.info = tk.Label(head, text="", bg=BG, fg=DIM, anchor="w")
        self.info.pack(side="left", fill="x", expand=True, padx=8, pady=4)
        if not self.readonly:
            ttk.Button(head, text="Save", command=self.save).pack(side="right", padx=4, pady=3)
        frame = tk.Frame(self.top)
        frame.pack(fill="both", expand=True)
        self.text = tk.Text(frame, wrap="word", undo=True, font=("Courier", 11) if not IS_WIN else ("Consolas", 11),
                            padx=10, pady=8, relief="flat")
        sb = ttk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<Control-s>", lambda e: (self.save(), "break")[1])
        self.text.bind("<Command-s>" if IS_MAC else "<Control-S>", lambda e: (self.save(), "break")[1])
        self.text.bind("<<Modified>>", self.on_modified)
        self.w.open_files.add(rel)
        self.load()
        self.update_info()

    def load(self):
        content = self.w.read(self.rel) or ""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.edit_modified(False)
        self.dirty = False
        if self.readonly:
            self.text.configure(state="disabled")
        try:
            self.mtime = os.path.getmtime(self.w.ab(self.rel))
        except OSError:
            self.mtime = 0

    def on_modified(self, e=None):
        if self.text.edit_modified():
            self.dirty = True
            self.update_info()

    def update_info(self):
        try:
            m = os.path.getmtime(self.w.ab(self.rel))
            mod = T.ago(m)
        except OSError:
            mod = "gone"
        self.top.title(("* " if self.dirty else "") + self.w.base(self.rel) + " - Mess Manager")
        ro = "   •   read only" if self.readonly else ""
        self.info.configure(text="%s   •   Opened %s   •   Last modified: %s%s" % (
            self.rel or "Mess", T.ago(self.opened), mod, ro))

    def poll(self):
        if not self.top.winfo_exists():
            raise tk.TclError("closed")
        if not self.w.exists(self.rel):
            moved = self.w.follow(self.rel)
            if moved:
                self.w.open_files.discard(self.rel)
                self.rel = moved
                self.w.open_files.add(moved)
            else:
                self.info.configure(text="%s   •   This file isn't there any more." % self.w.base(self.rel))
                return
        try:
            m = os.path.getmtime(self.w.ab(self.rel))
        except OSError:
            return
        if m != self.mtime and not self.dirty:
            self.load()
        self.update_info()

    def save(self):
        if self.readonly:
            return
        content = self.text.get("1.0", "end-1c")
        try:
            with open(self.w.ab(self.rel), "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            messagebox.showerror("Mess Manager", str(e), parent=self.top)
            return
        self.text.edit_modified(False)
        self.dirty = False
        self.mtime = os.path.getmtime(self.w.ab(self.rel))
        self.w.rules_dirty = True
        self.mgr.after_op()
        self.update_info()

    def close(self, force=False):
        if self.dirty and not force:
            r = messagebox.askyesnocancel("Save?", "Save changes to %s?" % self.w.base(self.rel), parent=self.top)
            if r is None:
                return
            if r:
                self.save()
        self.w.open_files.discard(self.rel)
        if self in self.mgr.windows:
            self.mgr.windows.remove(self)
        self.top.destroy()


# =========================================================================== image viewer
class ImageViewer:
    def __init__(self, mgr, rel):
        self.mgr = mgr
        self.rel = rel
        self.top = tk.Toplevel(mgr.app)
        self.top.title(mgr.w.base(rel) + " - Mess Manager")
        self.top.configure(bg="#202020")
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        img = None
        path = mgr.w.ab(rel)
        try:
            if HAVE_PIL:
                im = Image.open(path)
                im.thumbnail((900, 650))
                img = ImageTk.PhotoImage(im)
            elif T.ext_of(rel) in (".png", ".gif"):
                big = tk.PhotoImage(file=path)
                f = max(1, int(math.ceil(max(big.width() / 900.0, big.height() / 650.0))))
                img = big.subsample(f, f)
        except Exception:
            img = None
        self.img = img
        if img:
            tk.Label(self.top, image=img, bg="#202020").pack(padx=10, pady=10)
        else:
            tk.Label(self.top, text="Mess Manager can't draw this kind of picture by itself.\n"
                                    "(Install Pillow to see JPG and WEBP here.)\nOpening it in your picture viewer...",
                     fg="white", bg="#202020", justify="center").pack(padx=30, pady=30)
            media.open_with_system(path)
        lookers = [c["name"] for c in mgr.w.alive() if any(x[0] == mgr.w.base(rel) for x in c["mem"]["images"])]
        if lookers:
            tk.Label(self.top, text="%s %s seen this." % (", ".join(lookers), "has" if len(lookers) == 1 else "have"),
                     fg="#999999", bg="#202020").pack(pady=(0, 8))

    def poll(self):
        if not self.top.winfo_exists():
            raise tk.TclError("closed")

    def close(self, force=False):
        if self in self.mgr.windows:
            self.mgr.windows.remove(self)
        self.top.destroy()



# =========================================================================== AI settings
class AISettings:
    LABELS = [AI.PROVIDER_NAMES[k] for k in ("none", "ollama", "claude", "openai")]

    def __init__(self, mgr):
        self.mgr = mgr
        self.w = mgr.w
        s = AI.load_settings()
        self.top = tk.Toplevel(mgr.app)
        self.top.title("AI - Mess Manager")
        self.top.geometry("560x560")
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        f = tk.Frame(self.top, padx=16, pady=12)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="AI", font=("Helvetica", 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(f, justify="left", anchor="w", wraplength=520, fg="#555555",
                 text="Mess Manager can use an AI running on this computer. Some things in Mess need it.").pack(fill="x", pady=(2, 10))

        def row(label):
            r = tk.Frame(f)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=label, width=20, anchor="w").pack(side="left")
            return r
        self.provider = tk.StringVar(value=AI.PROVIDER_NAMES[s["provider"]])
        cb = ttk.Combobox(row("Provider"), textvariable=self.provider, values=self.LABELS, state="readonly", width=30)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.hint())
        self.key = ttk.Entry(row("API key"), show="\u2022", width=40)
        self.key.pack(side="left")
        self.key.insert(0, s.get("key", ""))
        self.model = ttk.Entry(row("Model (optional)"), width=40)
        self.model.pack(side="left")
        self.model.insert(0, s.get("model", ""))
        self.address = ttk.Entry(row("Address (optional)"), width=40)
        self.address.pack(side="left")
        self.address.insert(0, s.get("address", ""))
        self.calls = ttk.Entry(row("Max AI calls per hour"), width=8)
        self.calls.pack(side="left")
        self.calls.insert(0, s.get("calls", "60"))
        self.pictures = tk.BooleanVar(value=not s.get("pictures", "yes").lower().startswith("n"))
        ttk.Checkbutton(f, text="Let the AI see the pictures you drop in", variable=self.pictures).pack(anchor="w", pady=(6, 0))
        tk.Label(f, text="Chance", anchor="w").pack(fill="x", pady=(12, 0))
        self.chance = tk.DoubleVar(value=self.w.chance())
        tk.Scale(f, from_=0.0, to=1.0, resolution=0.1, orient="horizontal", variable=self.chance,
                 showvalue=True, length=300).pack(anchor="w")
        tk.Label(f, text="0 = predictable.   1 = anything can happen.",
                 fg="#777777", anchor="w").pack(fill="x")
        self.hint_label = tk.Label(f, justify="left", anchor="w", wraplength=520, fg="#555555")
        self.hint_label.pack(fill="x", pady=(12, 0))
        self.result = tk.Label(f, text="", justify="left", anchor="w", wraplength=520)
        self.result.pack(fill="x", pady=(8, 0))
        b = tk.Frame(f)
        b.pack(fill="x", side="bottom", pady=(8, 0))
        ttk.Button(b, text="Save", command=self.save).pack(side="right")
        ttk.Button(b, text="Test", command=self.test).pack(side="right", padx=6)
        self.pull_btn = ttk.Button(b, text="Download model", command=self.pull)
        self.pull_btn.pack(side="right")
        ttk.Button(b, text="Close", command=self.close).pack(side="left")
        self.hint()

    def chosen(self):
        label = self.provider.get()
        for k, v in AI.PROVIDER_NAMES.items():
            if v == label:
                return k
        return "none"

    def hint(self):
        p = self.chosen()
        text = {
            "none": "Without an AI, some things in Mess stay quiet.",
            "claude": "Get a key at console.anthropic.com. Default model: %s. Each AI call costs a little; "
                      "the hourly limit keeps it small." % AI.DEFAULT_MODELS["claude"],
            "openai": "Get a key at platform.openai.com. Default model: %s. Each AI call costs a little; "
                      "the hourly limit keeps it small. Any OpenAI-compatible service works if you set its Address." % AI.DEFAULT_MODELS["openai"],
            "ollama": "Free and private. Install Ollama once from ollama.com (Mess Manager starts it for you). "
                      "Then press 'Download model' (default %s, a few GB, only once). No key needed. "
                      "For it to see pictures, type llava as the Model and download that." % AI.DEFAULT_MODELS["ollama"],
        }[p]
        if p in ("claude", "openai"):
            text += ("\n\nPrivacy: to write the story, what happens in Mess is sent to that company: "
                     "file names, the words in your text files, and (if ticked) your pictures. "
                     "Your key is kept in %s, outside Mess." % AI.SETTINGS_PATH)
        self.hint_label.configure(text=text)

    def gather(self):
        return {"provider": self.chosen(), "key": self.key.get().strip(), "model": self.model.get().strip(),
                "address": self.address.get().strip(), "calls": self.calls.get().strip() or "60",
                "pictures": "yes" if self.pictures.get() else "no"}

    def save(self, quiet=False):
        try:
            AI.save_settings(self.gather())
        except OSError as e:
            messagebox.showerror("Mess Manager", str(e), parent=self.top)
            return False
        self.w.state["chance"] = round(float(self.chance.get()), 2)
        self.w.ai.reload()
        if not quiet:
            self.result.configure(text="Saved. " + self.w.ai.status(), fg="#2b7a3d")
        return True

    def test(self):
        if not self.save(quiet=True):
            return
        if not self.w.ai.enabled:
            self.result.configure(text=self.w.ai.status(), fg="#a33")
            return
        self.result.configure(text="Asking...", fg="#555555")

        def done(data):
            try:
                if not self.top.winfo_exists():
                    return
            except tk.TclError:
                return
            if data:
                line = data.get("line") or "It answered."
                self.result.configure(text="It works.", fg="#2b7a3d")
            else:
                err = (self.w.state.get("ai_errors") or ["no answer"])[-1]
                self.result.configure(text="It didn't work: %s" % err, fg="#a33")
        self.w.ai.test(done)

    def pull(self):
        if not self.save(quiet=True):
            return
        if self.chosen() != "ollama":
            self.result.configure(text="'Download model' is for Ollama.", fg="#a33")
            return
        self.w.ai.pull_model()
        self.result.configure(text=self.w.ai.pull_status, fg="#555555")

    def poll(self):
        if not self.top.winfo_exists():
            raise tk.TclError("closed")
        if self.w.ai.pull_status:
            self.result.configure(text=self.w.ai.pull_status,
                                  fg="#a33" if "failed" in self.w.ai.pull_status else "#555555")

    def close(self, force=False):
        if self in self.mgr.windows:
            self.mgr.windows.remove(self)
        self.top.destroy()


def main():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = App()
    app.mainloop()

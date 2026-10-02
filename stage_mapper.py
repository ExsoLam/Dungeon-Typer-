#!/usr/bin/env python3
"""Stage mapper for Typing of the Dungeon.

Lay out a stage on its background photo and save it as JSON:
attack line (yend, hend, lanes), vanishing x (xc), spawn zones with waypoints,
foreground masks, light effects, and the wave. The preview uses the game's own
stagePos() math, so the ghosts are the size and position the game will draw.

Requires Python 3 with tkinter and Pillow:  pip install pillow
Run:  python stage_mapper.py [image-or-stage.json]

Mouse: left = place / drag handles, right or middle drag = pan, wheel = zoom.
Keys:  Delete = remove selected, Ctrl+Z = undo, Ctrl+S = save,
       Enter = close the mask polygon being drawn, Esc = cancel it,
       1-6 = modes (Move, Zone, Waypoint, Mask, Glow, Flame).
"""
import base64, copy, io, json, math, os, re, sys

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    sys.exit("Pillow is required:  pip install pillow")

FORMAT = "dungeon-typer-stage/1"
# enemy types the wave queue accepts (game TYPES keys -> display name); bats spawn on their own
TYPES = [("rat", "Zombie"), ("zombie", "Zombie (alt)"), ("skel", "Rotter"), ("orc", "Brute"), ("wraith", "Husk"),
         ("armor", "Armored"), ("thrower", "Axeman"), ("prisoner", "Prisoner"), ("boss", "Boss")]
TYPE_KEYS = [t[0] for t in TYPES]
PALETTE = ["#ff6a3d", "#3dc7ff", "#b7ff3d", "#ff3dd2", "#ffd23d", "#3dffa8", "#a03dff", "#ff3d6a"]
MODES = ["Move", "Zone", "Waypoint", "Mask", "Glow", "Flame"]
HINTS = {
    "Move": "Drag any handle. Click a handle to select it.",
    "Zone": "Click to place a spawn point (feet). Drag the square above it to set the enemy height.",
    "Waypoint": "Click to add a waypoint to the selected zone (max 2).",
    "Mask": "Click to add polygon points. Enter or click the first point closes it, Esc cancels.",
    "Glow": "Click to place a light glow. Drag the ring handle to set its radius.",
    "Flame": "Click to place a flame. Drag its top handle to set its size.",
}


# ---------------------------------------------------------------- model / geometry

def new_stage(iw, ih, image=""):
    return {"format": FORMAT, "name": "NEW STAGE", "image": image, "iw": iw, "ih": ih,
            "xc": round(iw / 2), "yend": round(ih * 0.8), "hend": round(ih * 0.37),
            "lanes": [round(iw * 0.35), round(iw * 0.5), round(iw * 0.65)],
            "boss": "", "cap": 0, "music": "", "zones": {}, "w": {}, "masks": [],
            "fx": {"glows": [], "flames": [], "fog": None},
            "wave": {"queue": "", "gap": 2.6, "max": 3}}


def zone_params(S, z):
    """(A, yh) for a zone, or None if degenerate. Height h = A * (feet_y - yh)."""
    dy = S["yend"] - z["y"]
    if dy <= 0 or S["hend"] <= z["h"] or z["h"] <= 0:
        return None
    A = (S["hend"] - z["h"]) / dy
    return A, z["y"] - z["h"] / A


def stage_pos(S, z, lane, u):
    """Port of the game's stagePos() in image pixels: (feet x, feet y, height) at progress u in [0, 1]."""
    p = zone_params(S, z)
    if p is None:
        return None
    A, yh = p
    xe = S["lanes"][lane] if 0 <= lane < len(S["lanes"]) else S["lanes"][1]
    pts = [[z["x"], z["y"]]] + list(z.get("wp") or []) + [[xe, S["yend"]]]
    n = len(pts) - 1
    sp = [1] if n == 1 else [0.4, 0.6] if n == 2 else [0.25, 0.3, 0.45]
    t, sg, acc = u, 0, 0.0
    while sg < n - 1 and t > acc + sp[sg]:
        acc += sp[sg]; sg += 1
    t = min(1.0, (t - acc) / sp[sg])
    a, b = pts[sg], pts[sg + 1]
    xc = S["xc"]
    k0, k1 = max(1.0, a[1] - yh), max(1.0, b[1] - yh)
    Z = 1 / k0 + (1 / k1 - 1 / k0) * t
    k = 1 / Z
    X = (a[0] - xc) / k0 + ((b[0] - xc) / k1 - (a[0] - xc) / k0) * t
    return xc + X * k, yh + k, A * k


def check(S):
    """List of warning strings."""
    out = []
    if not S["name"].strip():
        out.append("Stage has no name.")
    for i, x in enumerate(S["lanes"]):
        if not 0 <= x <= S["iw"]:
            out.append(f"Lane {i} is outside the image.")
    if not S["zones"]:
        out.append("No spawn zones.")
    yhs = []
    for name, z in S["zones"].items():
        p = zone_params(S, z)
        if p is None:
            out.append(f"Zone '{name}': feet must be above the attack line and height below hend ({S['hend']}); it cannot spawn.")
            continue
        yhs.append((name, p[1]))
        pref = z.get("pref") or []
        if not pref or any(l not in (0, 1, 2) for l in pref):
            out.append(f"Zone '{name}': lane preference must list lanes 0-2.")
        if len(z.get("wp") or []) > 2:
            out.append(f"Zone '{name}': more than 2 waypoints (the game supports 2).")
    if len(yhs) > 1:
        lo, hi = min(yhs, key=lambda q: q[1]), max(yhs, key=lambda q: q[1])
        if hi[1] - lo[1] > 0.05 * S["ih"]:
            out.append(f"Horizons disagree by {hi[1] - lo[1]:.0f}px ('{lo[0]}' {lo[1]:.0f} vs '{hi[0]}' {hi[1]:.0f}); "
                       "enemies from those zones will shrink and grow at different rates.")
    if sum(S["w"].get(n, 0) for n in S["zones"]) <= 0 and S["zones"]:
        out.append("All zone weights are 0; nothing can spawn.")
    q = S["wave"]["queue"].split()
    if not q:
        out.append("Wave queue is empty.")
    if "boss" in q and S["boss"] not in S["zones"]:
        out.append("Queue has a boss but no boss zone is set.")
    bad = [t for t in q if t not in TYPE_KEYS]
    if bad:
        out.append("Unknown enemy types in queue: " + ", ".join(sorted(set(bad))))
    for i, m in enumerate(S["masks"]):
        if len(m["poly"]) < 3:
            out.append(f"Mask {i + 1} has fewer than 3 points.")
    return out


def export_dict(S):
    """Clean JSON-ready copy with rounded numbers."""
    r = lambda v: int(round(v))
    D = copy.deepcopy(S)
    for k in ("xc", "yend", "hend", "iw", "ih", "cap"):
        D[k] = r(D[k])
    D["lanes"] = [r(x) for x in D["lanes"]]
    for z in D["zones"].values():
        z["x"], z["y"], z["h"] = r(z["x"]), r(z["y"]), r(z["h"])
        if z.get("wp"):
            z["wp"] = [[r(p[0]), r(p[1])] for p in z["wp"]]
        else:
            z.pop("wp", None)
    D["w"] = {n: D["w"].get(n, 1) for n in D["zones"]}
    D["masks"] = [{"y": r(m["y"]), "poly": [[r(p[0]), r(p[1])] for p in m["poly"]]} for m in D["masks"]]
    if isinstance(D["fx"], dict):
        f = D["fx"]
        f["glows"] = [[r(g[0]), r(g[1]), r(g[2]), round(g[3], 3)] for g in f.get("glows", [])]
        f["flames"] = [[r(g[0]), r(g[1]), r(g[2])] for g in f.get("flames", [])]
        if f.get("fog"):
            f["fog"] = [r(f["fog"][0]), round(f["fog"][1], 3), r(f["fog"][2])]
    D["wave"]["queue"] = " ".join(D["wave"]["queue"].split())
    D["format"] = FORMAT
    return D


def js_literal_to_json(txt):
    txt = re.sub(r"//[^\n]*", "", txt)
    txt = re.sub(r"([{,]\s*)([A-Za-z_]\w*)\s*:", r'\1"\2":', txt)
    return json.loads(txt)


def import_html(path):
    """[(stage dict, image bytes or None)] for every stage in a game HTML file."""
    src = open(path, encoding="utf-8").read()
    m = re.search(r"const STAGES = (\[.*?\n\]);", src, re.S)
    w = re.search(r"const SEGS = (\[.*?\n\]);", src, re.S)
    if not m:
        raise ValueError("No STAGES table found in that file.")
    stages = js_literal_to_json(m.group(1))
    segs = js_literal_to_json(w.group(1)) if w else []
    imgmap = {}
    im = re.search(r"const STIMG = (\{[^}]*\})", src)
    if im:
        for key, const in re.findall(r"(\w+)\s*:\s*(\w+)", im.group(1)):
            d = re.search(r"const " + const + r" = [^\n]*?src: \"data:image/\w+;base64,([A-Za-z0-9+/=]+)\"", src)
            if d:
                imgmap[key] = base64.b64decode(d.group(1))
    out = []
    for i, st in enumerate(stages):
        S = new_stage(st["iw"], st["ih"])
        for k in ("name", "xc", "yend", "hend", "lanes", "boss", "cap", "music", "masks"):
            if k in st:
                S[k] = st[k]
        S["zones"] = {n: {"x": z["x"], "y": z["y"], "h": z["h"], "pref": z.get("pref", [1]), **({"wp": z["wp"]} if z.get("wp") else {})}
                      for n, z in st["zones"].items()}
        S["w"] = {n: st.get("w", {}).get(n, 0) for n in S["zones"]}
        S["fx"] = st.get("fx", S["fx"])
        if i < len(segs):
            S["wave"] = {"queue": segs[i].get("queue", ""), "gap": segs[i].get("gap", 2.6), "max": segs[i].get("max", 3)}
        S["image"] = ""
        out.append((S, imgmap.get(st.get("img"))))
    return out


# ---------------------------------------------------------------- rendering

def ghost(draw, x, y, h, col, alpha):
    """Simple standing silhouette, feet at (x, y)."""
    c = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5)) + (alpha,)
    hw = h * 0.16
    hr = h * 0.085
    draw.ellipse([x - hr, y - h, x + hr, y - h + 2 * hr], fill=c)
    draw.polygon([(x - hw, y - h + 2.2 * hr), (x + hw, y - h + 2.2 * hr), (x + hw * 0.7, y - h * 0.45),
                  (x + hw * 0.6, y), (x - hw * 0.6, y), (x - hw * 0.7, y - h * 0.45)], fill=c)


class Renderer:
    """Photo + ghosts, depth-sorted against mask cutouts exactly like the game's actorOrder()."""

    def __init__(self):
        self.photo = None
        self.cuts = {}

    def set_photo(self, img):
        self.photo = img.convert("RGBA")
        self.cuts = {}

    def cut(self, poly):
        key = tuple(map(tuple, poly))
        if key not in self.cuts:
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            box = (max(0, int(min(xs))), max(0, int(min(ys))), min(self.photo.width, int(max(xs)) + 1), min(self.photo.height, int(max(ys)) + 1))
            if box[2] <= box[0] or box[3] <= box[1]:
                self.cuts[key] = None
            else:
                crop = self.photo.crop(box)
                m = Image.new("L", crop.size, 0)
                ImageDraw.Draw(m).polygon([(p[0] - box[0], p[1] - box[1]) for p in poly], fill=255)
                crop.putalpha(m)
                self.cuts[key] = (crop, box[:2])
        return self.cuts[key]

    def render(self, S, ghosts, shade):
        """ghosts: [(x, y, h, color, alpha)]. Returns RGBA image at photo size."""
        base = self.photo.copy() if self.photo else Image.new("RGBA", (S["iw"], S["ih"]), (40, 40, 40, 255))
        items = [(g[1], 0, g) for g in ghosts] + [(m["y"], 1, m) for m in S["masks"] if len(m["poly"]) >= 3]
        items.sort(key=lambda q: q[0])
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        dr = ImageDraw.Draw(layer)
        dirty = False
        for _, kind, it in items:
            if kind == 0:
                ghost(dr, *it); dirty = True
            elif self.photo:
                if dirty:
                    base.alpha_composite(layer); layer = Image.new("RGBA", base.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(layer); dirty = False
                c = self.cut(it["poly"])
                if c:
                    base.alpha_composite(c[0], c[1])
        if dirty:
            base.alpha_composite(layer)
        if shade and S["masks"]:
            tint = Image.new("RGBA", base.size, (0, 0, 0, 0))
            td = ImageDraw.Draw(tint)
            for m in S["masks"]:
                if len(m["poly"]) >= 3:
                    td.polygon([tuple(p) for p in m["poly"]], fill=(60, 140, 255, 46))
            base.alpha_composite(tint)
        return base


# ---------------------------------------------------------------- UI

def run_app(initial=None, block=True):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Stage Mapper - Typing of the Dungeon")
            self.geometry("1500x900")
            self.S = None
            self.path = None            # JSON path
            self.image_path = None      # absolute path of the photo
            self.image_bytes = None     # photo bytes imported from the game HTML (written out on save)
            self.R = Renderer()
            self.undo = []
            self.mode = tk.StringVar(value="Move")
            self.sel = None             # ("zone", name) | ("mask", i) | ("glow", i) | ("flame", i)
            self.sel_vertex = None      # (mask index, vertex index)
            self.drawing = []           # mask polygon in progress
            self.drag = None
            self.pan = None
            self.scale, self.ox, self.oy = 1.0, 0.0, 0.0
            self.comp = None
            self.comp_job = None
            self.walk_t = None
            self.hmap = {}
            self.opt_ghosts = tk.BooleanVar(value=True)
            self.opt_horizon = tk.BooleanVar(value=True)
            self.opt_shade = tk.BooleanVar(value=True)
            self.opt_steps = tk.IntVar(value=8)
            self.fields = []
            self.build()
            self.bind_all("<Control-z>", lambda e: self.do_undo())
            self.bind_all("<Control-s>", lambda e: self.save())
            self.bind("<Delete>", self.on_delete)
            self.bind("<Return>", self.on_enter)
            self.bind("<Escape>", lambda e: self.cancel_drawing())
            for i, m in enumerate(MODES):
                self.bind(str(i + 1), lambda e, m=m: self.set_mode(m))
            self.protocol("WM_DELETE_WINDOW", self.destroy)
            self.after(100, lambda: self.load_initial(initial))

        # ---------------- layout
        def build(self):
            mb = tk.Menu(self)
            fm = tk.Menu(mb, tearoff=0)
            fm.add_command(label="New stage from image...", command=self.new_from_image)
            fm.add_command(label="Open stage JSON...", command=self.open_json)
            fm.add_command(label="Import stage from game HTML...", command=self.import_from_html)
            fm.add_separator()
            fm.add_command(label="Change image...", command=self.change_image)
            fm.add_separator()
            fm.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
            fm.add_command(label="Save as...", command=lambda: self.save(True))
            fm.add_separator()
            fm.add_command(label="Quit", command=self.destroy)
            mb.add_cascade(label="File", menu=fm)
            self.config(menu=mb)

            top = ttk.Frame(self); top.pack(side="top", fill="x")
            for i, m in enumerate(MODES):
                ttk.Radiobutton(top, text=f"{i + 1} {m}", value=m, variable=self.mode, command=lambda m=m: self.set_mode(m)).pack(side="left", padx=4, pady=3)
            ttk.Button(top, text="Fit view", command=self.fit).pack(side="left", padx=12)
            self.walk_btn = ttk.Button(top, text="Walk", command=self.toggle_walk); self.walk_btn.pack(side="left")
            self.hint = ttk.Label(top, text=HINTS["Move"]); self.hint.pack(side="left", padx=12)

            body = ttk.PanedWindow(self, orient="horizontal"); body.pack(fill="both", expand=True)
            self.cv = tk.Canvas(body, bg="#1a1a1a", highlightthickness=0, cursor="crosshair")
            body.add(self.cv, weight=4)
            side = ttk.Frame(body, width=380); body.add(side, weight=0)
            self.status = ttk.Label(self, text="File > New stage from image... to start", anchor="w"); self.status.pack(side="bottom", fill="x")

            self.cv.bind("<Configure>", lambda e: self.redraw_view())
            self.cv.bind("<ButtonPress-1>", self.on_press)
            self.cv.bind("<B1-Motion>", self.on_motion)
            self.cv.bind("<ButtonRelease-1>", self.on_release)
            self.cv.bind("<Double-Button-1>", lambda e: self.finish_mask())
            for b in ("2", "3"):
                self.cv.bind(f"<ButtonPress-{b}>", self.pan_start)
                self.cv.bind(f"<B{b}-Motion>", self.pan_move)
            self.cv.bind("<MouseWheel>", lambda e: self.zoom(e.x, e.y, 1.15 if e.delta > 0 else 1 / 1.15))
            self.cv.bind("<Button-4>", lambda e: self.zoom(e.x, e.y, 1.15))
            self.cv.bind("<Button-5>", lambda e: self.zoom(e.x, e.y, 1 / 1.15))
            self.cv.bind("<Motion>", self.on_hover)

            nb = ttk.Notebook(side); nb.pack(fill="both", expand=True)
            self.tab_stage(nb); self.tab_zones(nb); self.tab_masks(nb); self.tab_lights(nb); self.tab_wave(nb); self.tab_check(nb)

        def field(self, parent, label, get, set_, row, width=10, col=0):
            ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            e = ttk.Entry(parent, textvariable=v, width=width)
            e.grid(row=row, column=col + 1, sticky="we", padx=4, pady=2)

            def apply(_=None):
                if self.S is None or get() is None:
                    return
                try:
                    old = get()
                    if str(old) == v.get():
                        return
                    self.push_undo(); set_(v.get()); self.changed()
                except (ValueError, KeyError, IndexError) as ex:
                    messagebox.showerror("Invalid value", str(ex)); self.refresh_fields()
            e.bind("<Return>", apply); e.bind("<FocusOut>", apply)
            self.fields.append((v, e, get))
            return e

        def tab_stage(self, nb):
            f = ttk.Frame(nb); nb.add(f, text="Stage")
            S = lambda: self.S
            def num(key, cast=float):
                return (lambda: None if S() is None else fmt(S()[key]), lambda s: S().__setitem__(key, cast(s)))
            def fmt(v):
                return str(int(round(v))) if isinstance(v, (int, float)) and float(v).is_integer() or isinstance(v, int) else (f"{v:.0f}" if isinstance(v, float) else str(v))
            self.field(f, "Name", lambda: None if S() is None else S()["name"], lambda s: S().__setitem__("name", s.strip().upper()), 0, 28)
            self.field(f, "Music file (SOUNDS)", lambda: None if S() is None else S()["music"], lambda s: S().__setitem__("music", s.strip()), 1, 28)
            ttk.Label(f, text="blank = \"STAGE <n>\"").grid(row=2, column=1, sticky="w", padx=4)
            self.field(f, "Word-tier minimum (cap)", *num("cap", int), 3)
            ttk.Separator(f).grid(row=4, column=0, columnspan=2, sticky="we", pady=6)
            self.field(f, "Attack line y (yend)", *num("yend"), 5)
            self.field(f, "Height at attack line (hend)", *num("hend"), 6)
            self.field(f, "Vanishing x (xc)", *num("xc"), 7)
            for i in range(3):
                self.field(f, f"Lane {i} x", lambda i=i: None if S() is None else fmt(S()["lanes"][i]), lambda s, i=i: S()["lanes"].__setitem__(i, float(s)), 8 + i)
            self.img_label = ttk.Label(f, text="", wraplength=340, justify="left")
            self.img_label.grid(row=12, column=0, columnspan=2, sticky="w", padx=4, pady=8)
            ttk.Label(f, wraplength=340, justify="left", text=(
                "Attack line: where enemies stop and hit you. Drag the yellow line, the three lane "
                "dots on it, the height handle above the middle lane, and the dashed vanishing line.")).grid(row=13, column=0, columnspan=2, sticky="w", padx=4)
            f.columnconfigure(1, weight=1)

        def tab_zones(self, nb):
            f = ttk.Frame(nb); nb.add(f, text="Zones")
            self.zlist = tk.Listbox(f, height=8, exportselection=False); self.zlist.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
            self.zlist.bind("<<ListboxSelect>>", lambda e: self.pick_list(self.zlist, "zone"))
            Z = lambda: self.S["zones"].get(self.sel[1]) if self.S and self.sel and self.sel[0] == "zone" else None
            def zget(k):
                return lambda: None if Z() is None else (str(int(round(Z()[k]))) if k in "xyh" else str(Z()[k]))
            def zset(k):
                return lambda s: Z().__setitem__(k, float(s))
            self.field(f, "Name", lambda: None if Z() is None else self.sel[1], self.rename_zone, 1, 18)
            self.field(f, "Feet x", zget("x"), zset("x"), 2)
            self.field(f, "Feet y", zget("y"), zset("y"), 3)
            self.field(f, "Height h", zget("h"), zset("h"), 4)
            self.field(f, "Lane preference", lambda: None if Z() is None else ",".join(map(str, Z()["pref"])),
                       lambda s: Z().__setitem__("pref", [int(x) for x in re.split(r"[ ,]+", s.strip()) if x != ""]), 5, 18)
            self.field(f, "Spawn weight", lambda: None if Z() is None else str(self.S["w"].get(self.sel[1], 1)),
                       lambda s: self.S["w"].__setitem__(self.sel[1], float(s) if "." in s else int(s)), 6)
            self.boss_var = tk.BooleanVar()
            ttk.Checkbutton(f, text="Boss spawns here", variable=self.boss_var, command=self.toggle_boss).grid(row=7, column=0, columnspan=2, sticky="w", padx=4)
            bf = ttk.Frame(f); bf.grid(row=8, column=0, columnspan=2, sticky="w", pady=4)
            ttk.Button(bf, text="Clear waypoints", command=self.clear_wp).pack(side="left", padx=4)
            ttk.Button(bf, text="Delete zone", command=lambda: self.delete_sel()).pack(side="left", padx=4)
            ttk.Label(f, wraplength=340, justify="left", text=(
                "Lane preference: lanes tried in order, 0 = left, 1 = middle, 2 = right. An enemy takes the first free one. "
                "Weight: relative chance this zone is picked. Ghosts show each zone walking to each preferred lane, "
                "at the size the game draws a normal enemy. Dashed lines are each zone's horizon; they should agree.")).grid(row=9, column=0, columnspan=2, sticky="w", padx=4)
            f.columnconfigure(1, weight=1); f.rowconfigure(0, weight=1)

        def tab_masks(self, nb):
            f = ttk.Frame(nb); nb.add(f, text="Masks")
            self.mlist = tk.Listbox(f, height=8, exportselection=False); self.mlist.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
            self.mlist.bind("<<ListboxSelect>>", lambda e: self.pick_list(self.mlist, "mask"))
            M = lambda: self.S["masks"][self.sel[1]] if self.S and self.sel and self.sel[0] == "mask" and self.sel[1] < len(self.S["masks"]) else None
            self.field(f, "Depth y", lambda: None if M() is None else str(int(round(M()["y"]))), lambda s: M().__setitem__("y", float(s)), 1)
            bf = ttk.Frame(f); bf.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
            ttk.Button(bf, text="Delete mask", command=lambda: self.delete_sel()).pack(side="left", padx=4)
            ttk.Button(bf, text="Close polygon", command=self.finish_mask).pack(side="left", padx=4)
            ttk.Label(f, wraplength=340, justify="left", text=(
                "A mask is a foreground object cut out of the photo. Enemies whose feet are above its depth line "
                "(smaller y) are drawn behind it. Drag the depth handle (the bar with the square at its right end). "
                "Click a vertex and press Delete to remove it.")).grid(row=3, column=0, columnspan=2, sticky="w", padx=4)
            f.columnconfigure(1, weight=1); f.rowconfigure(0, weight=1)

        def tab_lights(self, nb):
            f = ttk.Frame(nb); nb.add(f, text="Lights")
            self.llist = tk.Listbox(f, height=8, exportselection=False); self.llist.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
            self.llist.bind("<<ListboxSelect>>", self.pick_light)
            L = lambda: (self.S["fx"]["glows"][self.sel[1]] if self.sel[0] == "glow" else self.S["fx"]["flames"][self.sel[1]]) \
                if self.S and isinstance(self.S["fx"], dict) and self.sel and self.sel[0] in ("glow", "flame") else None
            self.field(f, "Radius / size", lambda: None if L() is None else str(int(round(L()[2]))), lambda s: L().__setitem__(2, float(s)), 1)
            self.field(f, "Glow strength (0-1)", lambda: None if L() is None or self.sel[0] != "glow" else f"{L()[3]:.2f}", lambda s: L().__setitem__(3, float(s)), 2)
            ttk.Button(f, text="Delete light", command=lambda: self.delete_sel()).grid(row=3, column=0, sticky="w", padx=4, pady=4)
            ttk.Separator(f).grid(row=4, column=0, columnspan=2, sticky="we", pady=6)
            self.fog_var = tk.BooleanVar()
            ttk.Checkbutton(f, text="Drifting fog", variable=self.fog_var, command=self.toggle_fog).grid(row=5, column=0, columnspan=2, sticky="w", padx=4)
            F = lambda: self.S["fx"]["fog"] if self.S and isinstance(self.S["fx"], dict) and self.S["fx"].get("fog") else None
            self.field(f, "Fog y", lambda: None if F() is None else str(int(F()[0])), lambda s: F().__setitem__(0, float(s)), 6)
            self.field(f, "Fog strength (0-1)", lambda: None if F() is None else f"{F()[1]:.3f}", lambda s: F().__setitem__(1, float(s)), 7)
            self.fx_note = ttk.Label(f, wraplength=340, justify="left", text="")
            self.fx_note.grid(row=8, column=0, columnspan=2, sticky="w", padx=4, pady=6)
            ttk.Label(f, wraplength=340, justify="left", text=(
                "Glows and flames flicker in the game. They are not drawn in this preview; the circles mark their position and reach.")).grid(row=9, column=0, columnspan=2, sticky="w", padx=4)
            f.columnconfigure(1, weight=1); f.rowconfigure(0, weight=1)

        def tab_wave(self, nb):
            f = ttk.Frame(nb); nb.add(f, text="Wave")
            self.qlist = tk.Listbox(f, height=14, exportselection=False); self.qlist.grid(row=0, column=0, rowspan=6, sticky="nsew", padx=4, pady=4)
            bf = ttk.Frame(f); bf.grid(row=0, column=1, sticky="n", padx=4, pady=4)
            ttk.Label(bf, text="Append:").pack(anchor="w")
            for k, name in TYPES:
                ttk.Button(bf, text=name, command=lambda k=k: self.q_add(k)).pack(fill="x")
            ef = ttk.Frame(f); ef.grid(row=6, column=0, columnspan=2, sticky="w")
            for txt, fn in (("Up", lambda: self.q_move(-1)), ("Down", lambda: self.q_move(1)), ("Remove", self.q_remove), ("Clear", self.q_clear)):
                ttk.Button(ef, text=txt, command=fn).pack(side="left", padx=3, pady=3)
            g = ttk.Frame(f); g.grid(row=7, column=0, columnspan=2, sticky="we")
            W = lambda: None if self.S is None else self.S["wave"]
            self.field(g, "Seconds between spawns (gap)", lambda: None if W() is None else str(W()["gap"]), lambda s: W().__setitem__("gap", float(s)), 0)
            self.field(g, "Max enemies at once", lambda: None if W() is None else str(W()["max"]), lambda s: W().__setitem__("max", int(s)), 1)
            self.q_summary = ttk.Label(f, text="", wraplength=340, justify="left"); self.q_summary.grid(row=8, column=0, columnspan=2, sticky="w", padx=4)
            f.columnconfigure(0, weight=1); f.rowconfigure(5, weight=1)

        def tab_check(self, nb):
            f = ttk.Frame(nb); nb.add(f, text="Check")
            ttk.Checkbutton(f, text="Ghost enemies along paths", variable=self.opt_ghosts, command=self.schedule).pack(anchor="w", padx=4)
            r = ttk.Frame(f); r.pack(anchor="w", padx=20)
            ttk.Label(r, text="ghosts per path").pack(side="left")
            ttk.Spinbox(r, from_=2, to=20, width=4, textvariable=self.opt_steps, command=self.schedule).pack(side="left", padx=4)
            ttk.Checkbutton(f, text="Zone horizons", variable=self.opt_horizon, command=self.redraw_handles).pack(anchor="w", padx=4)
            ttk.Checkbutton(f, text="Shade masks", variable=self.opt_shade, command=self.schedule).pack(anchor="w", padx=4)
            ttk.Label(f, text="Warnings:").pack(anchor="w", padx=4, pady=(10, 0))
            self.warn = tk.Text(f, height=18, wrap="word", width=44); self.warn.pack(fill="both", expand=True, padx=4, pady=4)

        # ---------------- file handling
        def load_initial(self, p):
            if not p:
                return
            if p.lower().endswith(".json"):
                self.open_json(p)
            else:
                self.new_from_image(p)

        def set_image(self, img, path=None, data=None):
            self.R.set_photo(img)
            self.image_path, self.image_bytes = path, data

        def new_from_image(self, p=None):
            p = p or filedialog.askopenfilename(title="Background image", filetypes=[("Images", "*.jpg *.jpeg *.png *.webp"), ("All", "*.*")])
            if not p:
                return
            img = Image.open(p)
            self.S = new_stage(img.width, img.height, os.path.basename(p))
            self.set_image(img, os.path.abspath(p))
            self.path = None; self.undo = []; self.sel = None; self.drawing = []
            self.fit(); self.changed()

        def change_image(self):
            if not self.S:
                return
            p = filedialog.askopenfilename(title="Background image", filetypes=[("Images", "*.jpg *.jpeg *.png *.webp"), ("All", "*.*")])
            if not p:
                return
            img = Image.open(p)
            if (img.width, img.height) != (self.S["iw"], self.S["ih"]):
                if not messagebox.askyesno("Different size", f"The new image is {img.width}x{img.height}, the stage was mapped on "
                                           f"{self.S['iw']}x{self.S['ih']}. Scale all coordinates to the new size?"):
                    return
                self.push_undo(); self.rescale(img.width / self.S["iw"], img.height / self.S["ih"])
            self.S["iw"], self.S["ih"], self.S["image"] = img.width, img.height, os.path.basename(p)
            self.set_image(img, os.path.abspath(p)); self.fit(); self.changed()

        def rescale(self, fx, fy):
            S = self.S
            S["xc"] *= fx; S["yend"] *= fy; S["hend"] *= fy; S["lanes"] = [x * fx for x in S["lanes"]]
            for z in S["zones"].values():
                z["x"] *= fx; z["y"] *= fy; z["h"] *= fy
                if z.get("wp"):
                    z["wp"] = [[p[0] * fx, p[1] * fy] for p in z["wp"]]
            for m in S["masks"]:
                m["y"] *= fy; m["poly"] = [[p[0] * fx, p[1] * fy] for p in m["poly"]]
            if isinstance(S["fx"], dict):
                S["fx"]["glows"] = [[g[0] * fx, g[1] * fy, g[2] * fy, g[3]] for g in S["fx"]["glows"]]
                S["fx"]["flames"] = [[g[0] * fx, g[1] * fy, g[2] * fy] for g in S["fx"]["flames"]]
                if S["fx"].get("fog"):
                    S["fx"]["fog"] = [S["fx"]["fog"][0] * fy, S["fx"]["fog"][1], S["fx"]["fog"][2] * fx]

        def open_json(self, p=None):
            p = p or filedialog.askopenfilename(title="Stage JSON", filetypes=[("Stage JSON", "*.json"), ("All", "*.*")])
            if not p:
                return
            S = json.load(open(p, encoding="utf-8"))
            base = new_stage(S["iw"], S["ih"]); base.update(S); S = base
            S["w"] = {n: S["w"].get(n, 1) for n in S["zones"]}
            if isinstance(S["fx"], dict):
                S["fx"].setdefault("glows", []); S["fx"].setdefault("flames", []); S["fx"].setdefault("fog", None)
            img = None
            for cand in (S.get("image_path"), os.path.join(os.path.dirname(p), S.get("image") or "")):
                if cand and os.path.isfile(cand):
                    img = Image.open(cand); ipath = os.path.abspath(cand); break
            if img is None:
                messagebox.showwarning("Image not found", f"Could not find '{S.get('image')}'. Pick it.")
                q = filedialog.askopenfilename(title="Background image")
                if not q:
                    return
                img = Image.open(q); ipath = os.path.abspath(q); S["image"] = os.path.basename(q)
            S.pop("image_path", None)
            self.S, self.path = S, p
            self.set_image(img, ipath)
            self.undo = []; self.sel = None; self.drawing = []
            self.fit(); self.changed()

        def import_from_html(self):
            p = filedialog.askopenfilename(title="Game HTML", filetypes=[("HTML", "*.html *.htm")])
            if not p:
                return
            try:
                st = import_html(p)
            except Exception as ex:
                messagebox.showerror("Import failed", str(ex)); return
            names = [f"{i + 1}  {s['name']}" for i, (s, _) in enumerate(st)]
            ans = simpledialog.askinteger("Import stage", "Which stage?\n\n" + "\n".join(names), minvalue=1, maxvalue=len(st), parent=self)
            if not ans:
                return
            S, data = st[ans - 1]
            if data:
                img = Image.open(io.BytesIO(data)); ext = ".png" if data[:4] == b"\x89PNG" else ".jpg"
                S["image"] = re.sub(r"[^a-z0-9]+", "_", S["name"].lower()).strip("_") + ext
                self.set_image(img, None, data)
            else:
                self.set_image(Image.new("RGB", (S["iw"], S["ih"]), (40, 40, 40)))
            self.S, self.path = S, None
            self.undo = []; self.sel = None; self.drawing = []
            self.fit(); self.changed()

        def save(self, ask=False):
            if not self.S:
                return
            if ask or not self.path:
                slug = re.sub(r"[^a-z0-9]+", "_", self.S["name"].lower()).strip("_") or "stage"
                p = filedialog.asksaveasfilename(title="Save stage JSON", defaultextension=".json", initialfile=f"stage_{slug}.json",
                                                 filetypes=[("Stage JSON", "*.json")])
                if not p:
                    return
                self.path = p
            D = export_dict(self.S)
            d = os.path.dirname(self.path)
            if self.image_bytes is not None:     # imported from the game: write the photo next to the JSON
                ip = os.path.join(d, D["image"])
                open(ip, "wb").write(self.image_bytes)
                self.image_path, self.image_bytes = ip, None
            if self.image_path:
                D["image_path"] = self.image_path
            json.dump(D, open(self.path, "w", encoding="utf-8"), indent=1)
            self.status.config(text=f"Saved {self.path}")

        # ---------------- model changes
        def push_undo(self):
            if self.S:
                self.undo.append(copy.deepcopy(self.S))
                del self.undo[:-200]

        def do_undo(self):
            if self.undo:
                self.S = self.undo.pop()
                if self.sel and ((self.sel[0] == "zone" and self.sel[1] not in self.S["zones"]) or (self.sel[0] == "mask" and self.sel[1] >= len(self.S["masks"]))):
                    self.sel = None
                self.changed()

        def changed(self):
            self.refresh_fields(); self.refresh_lists(); self.redraw_handles(); self.schedule(); self.refresh_warnings()

        def refresh_fields(self):
            foc = self.focus_get()
            for v, e, get in self.fields:
                if e is foc:
                    continue
                try:
                    val = get()
                except Exception:
                    val = None
                v.set("" if val is None else val)
                e.state(["disabled"] if val is None else ["!disabled"])
            if self.S:
                fxs = self.S["fx"]
                self.fog_var.set(isinstance(fxs, dict) and bool(fxs.get("fog")))
                self.boss_var.set(bool(self.sel and self.sel[0] == "zone" and self.S["boss"] == self.sel[1]))
                self.fx_note.config(text=f"This stage uses the game's built-in effect '{fxs}'. Adding a light or fog replaces it with these settings."
                                    if isinstance(fxs, str) else "")
                self.img_label.config(text=f"Image: {self.S['image']}  ({self.S['iw']} x {self.S['ih']})")

        def refresh_lists(self):
            if not self.S:
                return
            S = self.S
            self.zlist.delete(0, "end")
            for n, z in S["zones"].items():
                self.zlist.insert("end", f"{n}{'  [boss]' if S['boss'] == n else ''}   w={S['w'].get(n, 1)}  lanes {','.join(map(str, z['pref']))}")
            if self.sel and self.sel[0] == "zone" and self.sel[1] in S["zones"]:
                self.zlist.selection_set(list(S["zones"]).index(self.sel[1]))
            self.mlist.delete(0, "end")
            for i, m in enumerate(S["masks"]):
                self.mlist.insert("end", f"Mask {i + 1}   {len(m['poly'])} points   depth y={m['y']:.0f}")
            if self.sel and self.sel[0] == "mask" and self.sel[1] < len(S["masks"]):
                self.mlist.selection_set(self.sel[1])
            self.llist.delete(0, "end"); self.lrows = []
            if isinstance(S["fx"], dict):
                for i, g in enumerate(S["fx"]["glows"]):
                    self.llist.insert("end", f"Glow   ({g[0]:.0f}, {g[1]:.0f})  r={g[2]:.0f}  strength {g[3]:.2f}"); self.lrows.append(("glow", i))
                for i, g in enumerate(S["fx"]["flames"]):
                    self.llist.insert("end", f"Flame  ({g[0]:.0f}, {g[1]:.0f})  size {g[2]:.0f}"); self.lrows.append(("flame", i))
                if self.sel in self.lrows:
                    self.llist.selection_set(self.lrows.index(self.sel))
            q = S["wave"]["queue"].split()
            cur = self.qlist.curselection()
            self.qlist.delete(0, "end")
            names = dict(TYPES)
            for i, t in enumerate(q):
                self.qlist.insert("end", f"{i + 1:2d}  {names.get(t, t + ' (?)')}")
            if cur and cur[0] < len(q):
                self.qlist.selection_set(cur[0])
            counts = {}
            for t in q:
                counts[names.get(t, t)] = counts.get(names.get(t, t), 0) + 1
            self.q_summary.config(text=f"{len(q)} enemies: " + ", ".join(f"{k} x{v}" for k, v in counts.items()))

        def refresh_warnings(self):
            self.warn.delete("1.0", "end")
            if self.S:
                w = check(self.S)
                self.warn.insert("end", "\n\n".join(w) if w else "No problems found.")

        # ---------------- list / panel actions
        def pick_list(self, lb, kind):
            s = lb.curselection()
            if not s or not self.S:
                return
            self.sel = ("zone", list(self.S["zones"])[s[0]]) if kind == "zone" else ("mask", s[0])
            self.refresh_fields(); self.redraw_handles()

        def pick_light(self, _):
            s = self.llist.curselection()
            if s:
                self.sel = self.lrows[s[0]]; self.refresh_fields(); self.redraw_handles()

        def rename_zone(self, new):
            new = re.sub(r"\W+", "", new)
            old = self.sel[1]
            if not new or new == old:
                return
            if new in self.S["zones"]:
                raise ValueError(f"A zone named '{new}' already exists.")
            self.S["zones"] = {(new if k == old else k): v for k, v in self.S["zones"].items()}
            self.S["w"] = {(new if k == old else k): v for k, v in self.S["w"].items()}
            if self.S["boss"] == old:
                self.S["boss"] = new
            self.sel = ("zone", new)

        def toggle_boss(self):
            if self.S and self.sel and self.sel[0] == "zone":
                self.push_undo(); self.S["boss"] = self.sel[1] if self.boss_var.get() else ""; self.changed()

        def clear_wp(self):
            if self.S and self.sel and self.sel[0] == "zone":
                self.push_undo(); self.S["zones"][self.sel[1]].pop("wp", None); self.changed()

        def ensure_fx_dict(self):
            if not isinstance(self.S["fx"], dict):
                if not messagebox.askyesno("Replace built-in effect", f"This stage uses the game's built-in effect '{self.S['fx']}'. "
                                           "Replace it with your own lights?"):
                    return False
                self.S["fx"] = {"glows": [], "flames": [], "fog": None}
            return True

        def toggle_fog(self):
            if not self.S:
                return
            if not self.ensure_fx_dict():
                self.fog_var.set(False); return
            self.push_undo()
            self.S["fx"]["fog"] = [round(self.S["yend"] - 20), 0.06, self.S["iw"] + 500] if self.fog_var.get() else None
            self.changed()

        def q_add(self, k):
            if self.S:
                self.push_undo(); self.S["wave"]["queue"] = (self.S["wave"]["queue"] + " " + k).strip(); self.changed()
                self.qlist.selection_clear(0, "end"); self.qlist.selection_set("end"); self.qlist.see("end")

        def q_move(self, d):
            s = self.qlist.curselection()
            if not self.S or not s:
                return
            q = self.S["wave"]["queue"].split(); i = s[0]; j = i + d
            if 0 <= j < len(q):
                self.push_undo(); q[i], q[j] = q[j], q[i]; self.S["wave"]["queue"] = " ".join(q); self.changed()
                self.qlist.selection_clear(0, "end"); self.qlist.selection_set(j)

        def q_remove(self):
            s = self.qlist.curselection()
            if self.S and s:
                q = self.S["wave"]["queue"].split(); self.push_undo(); del q[s[0]]; self.S["wave"]["queue"] = " ".join(q); self.changed()

        def q_clear(self):
            if self.S and self.S["wave"]["queue"] and messagebox.askyesno("Clear", "Clear the whole wave queue?"):
                self.push_undo(); self.S["wave"]["queue"] = ""; self.changed()

        def delete_sel(self):
            if not self.S:
                return
            if self.sel_vertex:
                mi, vi = self.sel_vertex
                if mi < len(self.S["masks"]) and len(self.S["masks"][mi]["poly"]) > 3:
                    self.push_undo(); del self.S["masks"][mi]["poly"][vi]; self.sel_vertex = None; self.changed()
                return
            if not self.sel:
                return
            k, i = self.sel
            self.push_undo()
            if k == "zone":
                self.S["zones"].pop(i, None); self.S["w"].pop(i, None)
                if self.S["boss"] == i:
                    self.S["boss"] = ""
            elif k == "mask":
                del self.S["masks"][i]
            elif k == "glow":
                del self.S["fx"]["glows"][i]
            elif k == "flame":
                del self.S["fx"]["flames"][i]
            self.sel = None; self.changed()

        def on_delete(self, e):
            if isinstance(self.focus_get(), (tk.Entry, ttk.Entry, ttk.Spinbox)):
                return
            self.delete_sel()

        def on_enter(self, e):
            if self.drawing:
                self.finish_mask()

        # ---------------- view transform
        def to_img(self, x, y):
            return (x - self.ox) / self.scale, (y - self.oy) / self.scale

        def to_view(self, x, y):
            return x * self.scale + self.ox, y * self.scale + self.oy

        def fit(self):
            if not self.S:
                return
            self.update_idletasks()
            cw, ch = max(100, self.cv.winfo_width()), max(100, self.cv.winfo_height())
            self.scale = min(cw / self.S["iw"], ch / self.S["ih"]) * 0.97
            self.ox = (cw - self.S["iw"] * self.scale) / 2; self.oy = (ch - self.S["ih"] * self.scale) / 2
            self.redraw_view()

        def zoom(self, x, y, f):
            if not self.S:
                return
            ns = min(8.0, max(0.1, self.scale * f)); f = ns / self.scale
            self.ox = x - (x - self.ox) * f; self.oy = y - (y - self.oy) * f; self.scale = ns
            self.redraw_view()

        def pan_start(self, e):
            self.pan = (e.x, e.y, self.ox, self.oy)

        def pan_move(self, e):
            if self.pan:
                self.ox = self.pan[2] + e.x - self.pan[0]; self.oy = self.pan[3] + e.y - self.pan[1]; self.redraw_view()

        # ---------------- composite
        def ghosts(self):
            S = self.S; out = []
            if self.walk_t is not None:
                for zi, (n, z) in enumerate(S["zones"].items()):
                    for li, lane in enumerate(z["pref"]):
                        p = stage_pos(S, z, lane, ((self.walk_t / 3.5) + li * 0.33) % 1.0)
                        if p:
                            out.append((p[0], p[1], p[2], PALETTE[zi % len(PALETTE)], 210))
                return out
            if not self.opt_ghosts.get():
                return out
            steps = max(2, int(self.opt_steps.get() or 8))
            for zi, (n, z) in enumerate(S["zones"].items()):
                for lane in z["pref"]:
                    for s in range(steps):
                        p = stage_pos(S, z, lane, s / (steps - 1))
                        if p:
                            out.append((p[0], p[1], p[2], PALETTE[zi % len(PALETTE)], 120))
            return out

        def schedule(self):
            if self.comp_job:
                self.after_cancel(self.comp_job)
            self.comp_job = self.after(60, self.rebuild)

        def rebuild(self):
            self.comp_job = None
            if not self.S:
                return
            self.comp = self.R.render(self.S, self.ghosts(), self.opt_shade.get())
            self.redraw_view()

        def redraw_view(self):
            self.cv.delete("img")
            if self.comp is not None:
                cw, ch = self.cv.winfo_width(), self.cv.winfo_height()
                x0, y0 = self.to_img(0, 0); x1, y1 = self.to_img(cw, ch)
                x0, y0 = max(0, int(x0)), max(0, int(y0)); x1, y1 = min(self.comp.width, int(x1) + 1), min(self.comp.height, int(y1) + 1)
                if x1 > x0 and y1 > y0:
                    crop = self.comp.crop((x0, y0, x1, y1))
                    w, h = max(1, round((x1 - x0) * self.scale)), max(1, round((y1 - y0) * self.scale))
                    crop = crop.resize((w, h), Image.BILINEAR if self.scale < 2 else Image.NEAREST)
                    self.tkimg = ImageTk.PhotoImage(crop)
                    vx, vy = self.to_view(x0, y0)
                    self.cv.create_image(vx, vy, anchor="nw", image=self.tkimg, tags="img")
                    self.cv.tag_lower("img")
            self.redraw_handles()

        # ---------------- handles
        def H(self, item, *kind):
            self.hmap[item] = kind
            return item

        def dot(self, x, y, r, fill, kind, outline="black", shape="oval"):
            vx, vy = self.to_view(x, y)
            f = self.cv.create_oval if shape == "oval" else self.cv.create_rectangle
            return self.H(f(vx - r, vy - r, vx + r, vy + r, fill=fill, outline=outline, width=1.5, tags="ov"), *kind)

        def redraw_handles(self):
            cv = self.cv; cv.delete("ov"); self.hmap = {}
            if not self.S:
                return
            S = self.S; V = self.to_view
            # vanishing x
            x, _ = V(S["xc"], 0)
            cv.create_line(x, V(0, 0)[1], x, V(0, S["ih"])[1], fill="#9a9a9a", dash=(6, 5), tags="ov")
            self.dot(S["xc"], 18 / self.scale, 6, "#cfcfcf", ("xc",), shape="rect")
            # zone horizons
            if self.opt_horizon.get():
                for zi, (n, z) in enumerate(S["zones"].items()):
                    p = zone_params(S, z)
                    if p:
                        y = V(0, p[1])[1]
                        cv.create_line(V(0, 0)[0], y, V(S["iw"], 0)[0], y, fill=PALETTE[zi % len(PALETTE)], dash=(2, 6), tags="ov")
            # attack line, lanes, hend
            y = V(0, S["yend"])[1]
            cv.create_line(V(0, 0)[0], y, V(S["iw"], 0)[0], y, fill="#ffd23d", width=2, tags="ov")
            self.dot(S["iw"] - 14 / self.scale, S["yend"], 6, "#ffd23d", ("yend",), shape="rect")
            for i, lx in enumerate(S["lanes"]):
                self.dot(lx, S["yend"], 7, "#ffd23d", ("lane", i))
                vx, vy = V(lx, S["yend"]); cv.create_text(vx, vy + 14, text=str(i), fill="#ffd23d", tags="ov")
            mx = S["lanes"][1]
            a, b = V(mx, S["yend"]), V(mx, S["yend"] - S["hend"])
            cv.create_line(a[0] + 12, a[1], b[0] + 12, b[1], fill="#ffd23d", width=2, arrow="both", tags="ov")
            self.dot(mx + 12 / self.scale, S["yend"] - S["hend"], 6, "#ffd23d", ("hend",), shape="rect")
            # zones
            for zi, (n, z) in enumerate(S["zones"].items()):
                col = PALETTE[zi % len(PALETTE)]; selz = self.sel == ("zone", n)
                pts = [(z["x"], z["y"])] + [tuple(p) for p in (z.get("wp") or [])]
                for lane in z["pref"]:
                    if 0 <= lane < 3:
                        chain = pts + [(S["lanes"][lane], S["yend"])]
                        cv.create_line(*[c for p in chain for c in V(*p)], fill=col, width=2 if selz else 1, dash=() if selz else (4, 3), tags="ov")
                hx, hy = V(z["x"], z["y"] - z["h"]); fx_, fy_ = V(z["x"], z["y"])
                cv.create_line(fx_, fy_, hx, hy, fill=col, width=3 if selz else 1, tags="ov")
                self.dot(z["x"], z["y"], 8 if selz else 6, col, ("zfeet", n), outline="white" if selz else "black")
                self.dot(z["x"], z["y"] - z["h"], 5, col, ("zhead", n), shape="rect")
                for j, p in enumerate(z.get("wp") or []):
                    self.dot(p[0], p[1], 5, col, ("wp", n, j), outline="white")
                cv.create_text(fx_ + 10, fy_ + 10, text=n + ("  [boss]" if S["boss"] == n else ""), fill=col, anchor="nw",
                               font=("TkDefaultFont", 10, "bold"), tags="ov")
            # masks
            for mi, m in enumerate(S["masks"]):
                selm = self.sel == ("mask", mi)
                if len(m["poly"]) >= 2:
                    cv.create_polygon(*[c for p in m["poly"] for c in V(*p)], outline="#3d9bff", fill="", width=2.5 if selm else 1.2, tags="ov")
                for vi, p in enumerate(m["poly"]):
                    hot = self.sel_vertex == (mi, vi)
                    self.dot(p[0], p[1], 5 if selm or hot else 3.5, "#ff3d3d" if hot else "#3d9bff", ("mv", mi, vi), outline="white" if selm else "black")
                xs = [p[0] for p in m["poly"]] or [0]
                a, b = V(min(xs), m["y"]), V(max(xs), m["y"])
                cv.create_line(a[0], a[1], b[0], b[1], fill="#3d9bff", width=2, dash=(8, 3), tags="ov")
                self.dot(max(xs) + 10 / self.scale, m["y"], 6, "#3d9bff", ("mdepth", mi), shape="rect")
            if self.drawing:
                pts = [c for p in self.drawing for c in V(*p)]
                if len(self.drawing) >= 2:
                    cv.create_line(*pts, fill="#ff9a3d", width=2, tags="ov")
                for i, p in enumerate(self.drawing):
                    self.dot(p[0], p[1], 6 if i == 0 else 4, "#ff9a3d", ("draw", i))
            # lights
            if isinstance(S["fx"], dict):
                for i, g in enumerate(S["fx"]["glows"]):
                    sl = self.sel == ("glow", i)
                    a, b = V(g[0] - g[2], g[1] - g[2]), V(g[0] + g[2], g[1] + g[2])
                    cv.create_oval(a[0], a[1], b[0], b[1], outline="#ffb060", dash=() if sl else (3, 4), width=2 if sl else 1, tags="ov")
                    self.dot(g[0], g[1], 6, "#ffb060", ("glow", i), outline="white" if sl else "black")
                    self.dot(g[0] + g[2], g[1], 4, "#ffb060", ("glowr", i), shape="rect")
                for i, g in enumerate(S["fx"]["flames"]):
                    sl = self.sel == ("flame", i)
                    a, b = V(g[0], g[1]), V(g[0], g[1] - g[2])
                    cv.create_line(a[0], a[1], b[0], b[1], fill="#ff7a20", width=3 if sl else 2, tags="ov")
                    self.dot(g[0], g[1], 6, "#ff7a20", ("flame", i), outline="white" if sl else "black")
                    self.dot(g[0], g[1] - g[2], 4, "#ff7a20", ("flames", i), shape="rect")
                fog = S["fx"].get("fog")
                if fog:
                    y = V(0, fog[0])[1]
                    cv.create_line(V(0, 0)[0], y, V(S["iw"], 0)[0], y, fill="#a0c8b8", width=1.5, dash=(10, 4), tags="ov")
                    self.dot(30 / self.scale, fog[0], 6, "#a0c8b8", ("fog",), shape="rect")

        def hit(self, x, y):
            for it in reversed(self.cv.find_overlapping(x - 7, y - 7, x + 7, y + 7)):
                if it in self.hmap:
                    return self.hmap[it]
            return None

        # ---------------- mouse
        def set_mode(self, m):
            self.mode.set(m); self.hint.config(text=HINTS[m])
            if m != "Mask":
                self.cancel_drawing()

        def on_hover(self, e):
            if self.S:
                x, y = self.to_img(e.x, e.y)
                self.status.config(text=f"x {x:.0f}   y {y:.0f}      zoom {self.scale * 100:.0f}%      {self.path or 'unsaved'}")

        def on_press(self, e):
            if not self.S:
                return
            self.cv.focus_set()
            x, y = self.to_img(e.x, e.y); h = self.hit(e.x, e.y); m = self.mode.get()
            if m == "Mask" and (self.drawing or not h or h[0] not in ("mv", "mdepth")):
                if self.drawing and h and h[0] == "draw" and h[1] == 0 and len(self.drawing) >= 3:
                    self.finish_mask(); return
                self.drawing.append([x, y]); self.redraw_handles(); return
            if h and h[0] != "draw":
                self.push_undo(); self.drag = h; self.sel_vertex = None
                k = h[0]
                if k in ("zfeet", "zhead", "wp"):
                    self.sel = ("zone", h[1])
                elif k in ("mv", "mdepth"):
                    self.sel = ("mask", h[1])
                    if k == "mv":
                        self.sel_vertex = (h[1], h[2])
                elif k in ("glow", "glowr"):
                    self.sel = ("glow", h[1])
                elif k in ("flame", "flames"):
                    self.sel = ("flame", h[1])
                self.refresh_fields(); self.refresh_lists(); self.redraw_handles(); return
            # empty space
            if m == "Zone":
                self.push_undo()
                n = 1
                while f"zone{n}" in self.S["zones"]:
                    n += 1
                name = f"zone{n}"
                self.S["zones"][name] = {"x": x, "y": y, "h": self.guess_h(y), "pref": [self.nearest_lane(x)]}
                self.S["w"][name] = 1
                self.sel = ("zone", name); self.changed()
            elif m == "Waypoint":
                if not (self.sel and self.sel[0] == "zone"):
                    self.status.config(text="Select a zone first (click its feet dot).") ; return
                z = self.S["zones"][self.sel[1]]
                if len(z.get("wp") or []) >= 2:
                    self.status.config(text="That zone already has 2 waypoints (the game's limit)."); return
                self.push_undo(); z.setdefault("wp", []).append([x, y]); self.changed()
            elif m in ("Glow", "Flame"):
                if not self.ensure_fx_dict():
                    return
                self.push_undo()
                if m == "Glow":
                    self.S["fx"]["glows"].append([x, y, 85, 0.28]); self.sel = ("glow", len(self.S["fx"]["glows"]) - 1)
                else:
                    self.S["fx"]["flames"].append([x, y, 12]); self.sel = ("flame", len(self.S["fx"]["flames"]) - 1)
                self.changed()
            else:
                self.sel = None; self.sel_vertex = None; self.refresh_fields(); self.refresh_lists(); self.redraw_handles()

        def on_motion(self, e):
            if not self.drag or not self.S:
                return
            x, y = self.to_img(e.x, e.y); S = self.S; d = self.drag; k = d[0]
            x = max(0, min(S["iw"], x)); y = max(0, min(S["ih"], y))
            if k == "yend":
                S["yend"] = y
            elif k == "lane":
                S["lanes"][d[1]] = x
            elif k == "hend":
                S["hend"] = max(10, S["yend"] - y)
            elif k == "xc":
                S["xc"] = x
            elif k == "zfeet":
                z = S["zones"][d[1]]; z["x"], z["y"] = x, y
            elif k == "zhead":
                z = S["zones"][d[1]]; z["h"] = max(4, z["y"] - y)
            elif k == "wp":
                S["zones"][d[1]]["wp"][d[2]] = [x, y]
            elif k == "mv":
                S["masks"][d[1]]["poly"][d[2]] = [x, y]
            elif k == "mdepth":
                S["masks"][d[1]]["y"] = y
            elif k == "glow":
                g = S["fx"]["glows"][d[1]]; g[0], g[1] = x, y
            elif k == "glowr":
                g = S["fx"]["glows"][d[1]]; g[2] = max(5, math.hypot(x - g[0], y - g[1]))
            elif k == "flame":
                g = S["fx"]["flames"][d[1]]; g[0], g[1] = x, y
            elif k == "flames":
                g = S["fx"]["flames"][d[1]]; g[2] = max(3, g[1] - y)
            elif k == "fog":
                S["fx"]["fog"][0] = y
            self.redraw_handles(); self.refresh_fields(); self.schedule()

        def on_release(self, e):
            if self.drag:
                self.drag = None; self.changed()

        def finish_mask(self):
            if len(self.drawing) >= 3:
                self.push_undo()
                self.S["masks"].append({"y": max(p[1] for p in self.drawing), "poly": self.drawing})
                self.sel = ("mask", len(self.S["masks"]) - 1)
                self.drawing = []; self.changed()

        def cancel_drawing(self):
            if self.drawing:
                self.drawing = []; self.redraw_handles()

        def nearest_lane(self, x):
            return min(range(3), key=lambda i: abs(self.S["lanes"][i] - x))

        def guess_h(self, y):
            """Height consistent with the other zones' average horizon, so new zones start in perspective."""
            S = self.S
            yhs = [p[1] for p in (zone_params(S, z) for z in S["zones"].values()) if p]
            if not yhs:
                return S["hend"] * 0.3
            yh = sum(yhs) / len(yhs)
            if y <= yh + 1 or y >= S["yend"]:
                return S["hend"] * 0.3
            return S["hend"] * (y - yh) / (S["yend"] - yh)

        # ---------------- walk animation
        def toggle_walk(self):
            if self.walk_t is None:
                self.walk_t = 0.0; self.walk_btn.config(text="Stop"); self.walk_step()
            else:
                self.walk_t = None; self.walk_btn.config(text="Walk"); self.schedule()

        def walk_step(self):
            if self.walk_t is None or not self.S:
                return
            self.walk_t += 0.05
            self.comp = self.R.render(self.S, self.ghosts(), self.opt_shade.get())
            self.redraw_view()
            self.after(50, self.walk_step)

    app = App()
    if block:
        app.mainloop()
    return app


if __name__ == "__main__":
    run_app(sys.argv[1] if len(sys.argv) > 1 else None)

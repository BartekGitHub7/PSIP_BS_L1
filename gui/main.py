"""PSIP: natywny interfejs Tkinter, kafelki wektorowe MVT z PostGIS.
Siatki: id + geom + przejezdnosc. BDOT: id + geom. Bez serwera HTTP i bez pobierania całych warstw.
"""
import math
import argparse
import sys
from pathlib import Path as FilePath
import queue
import re
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import tkinter as tk
from tkinter import ttk, messagebox
import psycopg
from psycopg import sql
import mapbox_vector_tile
from PIL import Image, ImageTk, ImageDraw
from shapely.geometry import shape
from shapely.geometry.polygon import orient
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import PathCollection, LineCollection
from matplotlib.path import Path
from matplotlib.colors import to_rgb, to_hex

COLORS = ["#70a9d1", "#e49b55", "#86b875", "#b28bc4", "#df7777"]
HALF_WORLD = 20037508.342789244
WORLD = 2 * HALF_WORLD
TILE_SIZE = 256
EXTENT = 4096
BUFFER = 64
CACHE_LIMIT = 192  # około 48 MiB obrazów RGBA
NO_DATA_COLOR = "#bdbdbd"
RAMP = ("#d73027", "#fee08b", "#1a9850")
RENDER_LOCK = threading.Lock()  # Matplotlib nie jest bezpieczny wielowątkowo


THEME = dict(bg="#0b1120", panel="#111c2e", surface="#19283e",
             hover="#243952", border="#2a3b52", text="#e6edf7",
             muted="#94a3b8", accent="#38bdf8", map="#0f172a")


def application_icon():
    """Ikona generowana z geometrii, bez zewnętrznych zasobów."""
    image = Image.new("RGBA",(256,256),(0,0,0,0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4,4,252,252),radius=54,fill=THEME["bg"])
    for cx,cy,color in [(87,88,"#164e63"),(163,88,"#0c4a6e"),(125,155,"#0891b2")]:
        points=[(cx+47*math.cos(math.radians(a)),cy+47*math.sin(math.radians(a)))
                for a in (30,90,150,210,270,330)]
        draw.polygon(points,fill=color)
        draw.line(points+[points[0]],fill=THEME["accent"],width=5,joint="curve")
    return image


def apply_dark_theme(root):
    root.configure(background=THEME["bg"])
    root.option_add("*Font", "{Segoe UI} 10")
    root.option_add("*Menu.background",THEME["panel"])
    root.option_add("*Menu.foreground",THEME["text"])
    root.option_add("*Menu.activeBackground",THEME["surface"])
    root.option_add("*Menu.activeForeground",THEME["accent"])
    root.option_add("*Menu.borderWidth",0)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".",background=THEME["panel"],foreground=THEME["text"],
                    font=("Segoe UI",10),bordercolor=THEME["border"],
                    lightcolor=THEME["border"],darkcolor=THEME["border"])
    style.configure("TFrame",background=THEME["panel"])
    style.configure("Header.TFrame",background=THEME["bg"])
    style.configure("TLabel",background=THEME["panel"],foreground=THEME["text"])
    style.configure("Muted.TLabel",foreground=THEME["muted"])
    style.configure("Brand.TLabel",background=THEME["bg"],font=("Segoe UI",22,"bold"))
    style.configure("BrandSub.TLabel",background=THEME["bg"],foreground=THEME["muted"],font=("Segoe UI",10))
    style.configure("Badge.TLabel",background=THEME["surface"],foreground=THEME["accent"],padding=(12,6),font=("Segoe UI",9,"bold"))
    style.configure("Title.TLabel",font=("Segoe UI",11,"bold"))
    style.configure("TButton",padding=(12,9),background=THEME["surface"],
                    foreground=THEME["text"],borderwidth=0,focusthickness=1,
                    focuscolor=THEME["accent"],font=("Segoe UI",10))
    style.map("TButton",background=[("disabled",THEME["panel"]),("pressed",THEME["border"]),("active",THEME["hover"])],
              foreground=[("disabled","#66758b")])
    style.configure("Primary.TButton",background=THEME["accent"],foreground=THEME["bg"],font=("Segoe UI",10,"bold"))
    style.map("Primary.TButton",background=[("disabled",THEME["surface"]),("pressed","#0284c7"),("active","#7dd3fc")],
              foreground=[("disabled",THEME["muted"]),("!disabled",THEME["bg"])])
    style.configure("Danger.TButton",foreground="#fda4af")
    style.map("Danger.TButton",background=[("active","#4c2435")])
    style.configure("TEntry",fieldbackground=THEME["bg"],foreground=THEME["text"],
                    insertcolor=THEME["accent"],padding=7,borderwidth=1)
    style.map("TEntry",bordercolor=[("focus",THEME["accent"])])
    style.configure("Treeview",background=THEME["bg"],fieldbackground=THEME["bg"],
                    foreground=THEME["text"],rowheight=32,borderwidth=0)
    style.map("Treeview",background=[("selected","#164e63")],foreground=[("selected","#f0f9ff")])
    style.configure("Treeview.Heading",background=THEME["surface"],foreground=THEME["muted"],
                    padding=(8,9),font=("Segoe UI",9,"bold"),relief="flat")
    style.map("Treeview.Heading",background=[("active",THEME["hover"])])
    style.configure("TScrollbar",background=THEME["surface"],troughcolor=THEME["bg"],
                    arrowcolor=THEME["muted"],borderwidth=0)
    style.configure("TPanedwindow",background=THEME["border"])
    style.configure("TLabelframe",background=THEME["panel"],bordercolor=THEME["border"],borderwidth=1)
    style.configure("TLabelframe.Label",background=THEME["panel"],foreground=THEME["muted"],font=("Segoe UI",9,"bold"))
    style.configure("Status.TLabel",background=THEME["bg"],foreground=THEME["muted"],padding=(14,8),font=("Segoe UI",9))
    root._app_icon = ImageTk.PhotoImage(application_icon(),master=root)
    root.iconphoto(True,root._app_icon)
    if sys.platform == "win32":
        root.after(100,lambda:dark_titlebar(root))


def dark_titlebar(window):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        enabled = ctypes.c_int(1)
        for attribute in (20,19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,attribute,ctypes.byref(enabled),ctypes.sizeof(enabled))
            if result == 0:
                break
    except (AttributeError,OSError):
        pass


def passability_color(value):
    """Stała skala 0–1; NULL/NaN/dane poza zakresem nie udają wyniku."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return NO_DATA_COLOR
    if not math.isfinite(value) or not 0 <= value <= 1:
        return NO_DATA_COLOR
    a, b = (RAMP[0], RAMP[1]) if value <= 0.5 else (RAMP[1], RAMP[2])
    fraction = value * 2 if value <= 0.5 else (value - 0.5) * 2
    return to_hex(tuple(x+(y-x)*fraction for x,y in zip(to_rgb(a),to_rgb(b))))


def describe_layer(connection, row, settings):
    schema, table, geom, srid = row
    srid = int(srid)
    if srid <= 0:
        raise ValueError(f"{schema}.{table}: nieznany SRID")
    display_name = f"{schema}.{table}"
    # Te konkretne widoki utworzono wcześniej jako aliasy naszych tabel H3.
    match = re.fullmatch(r"h3_r([678])_(2180|3857)", table)
    if schema == "grid" and match:
        source = f"h3_r{match.group(1)}"
        source_row = connection.execute(
            "SELECT f_geometry_column, srid FROM public.geometry_columns "
            "WHERE f_table_schema=%s AND f_table_name=%s", (schema, source)
        ).fetchone()
        if source_row:
            table, (geom, srid) = source, source_row
            srid = int(srid)
    columns = {r[0] for r in connection.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s", (schema, table)
    )}
    identity = next((c for c in ("h3_id", "ogc_fid", "fid", "id") if c in columns), None)
    if identity is None:
        raise ValueError(f"{display_name}: brak kolumny ID (h3_id / ogc_fid / fid / id)")
    q = sql.SQL("""
        WITH e AS (
            SELECT ST_Envelope(ST_Transform(ST_SetSRID(ST_Extent({geom})::geometry,
                   %s),3857)) AS g FROM {table}
        )
        SELECT ST_XMin(g), ST_YMin(g), ST_XMax(g), ST_YMax(g) FROM e
    """).format(geom=sql.Identifier(geom), table=sql.Identifier(schema, table))
    bounds = connection.execute(q, (srid,)).fetchone()
    return dict(name=display_name, schema=schema, table=table, geom=geom,
                srid=srid, identity=identity, settings=dict(settings),
                is_grid=(schema == "grid" and bool(re.fullmatch(r"h3_r[678]",table))),
                has_passability=("przejezdnosc" in columns),
                bounds=None if bounds[0] is None else tuple(map(float, bounds)))


def tile_query(layer):
    # Indeksowana kolumna po LEWEJ stronie && pozostaje bez transformacji.
    # Transformujemy bufor kafelka do SRID tabeli. Geometrię wybranych
    # obiektów transformujemy do 3857 dopiero do kodowania MVT.
    return sql.SQL("""
        WITH bounds AS (
            SELECT ST_TileEnvelope(%s,%s,%s) AS tile,
                   ST_Transform(ST_Segmentize(
                       ST_TileEnvelope(%s,%s,%s, margin => 64.0/4096),
                       %s), %s) AS search
        ), features AS (
            SELECT {id}::text AS id{value},
                   ST_AsMVTGeom(ST_Transform(ST_Force2D(t.{geom}),3857),
                                b.tile,4096,64,true) AS geom
            FROM {table} t CROSS JOIN bounds b
            WHERE t.{geom} && b.search AND t.{geom} IS NOT NULL
        )
        SELECT ST_AsMVT(f,'features',4096,'geom')
        FROM features f WHERE f.geom IS NOT NULL
    """).format(id=sql.Identifier("t",layer["identity"]),
                 value=(sql.SQL(', t."przejezdnosc"::double precision AS przejezdnosc')
                        if layer.get("has_passability") else
                        sql.SQL(', NULL::double precision AS przejezdnosc'))
                        if layer.get("is_grid") else sql.SQL(""),
                 geom=sql.Identifier(layer["geom"]),
                 table=sql.Identifier(layer["schema"],layer["table"]))


def fetch_tile(layer, z, x, y):
    # Kilkanaście odcinków na bok: bezpieczniejsza transformacja obwiedni
    # z Mercatora do lokalnego układu niż transformacja samych narożników.
    segment = WORLD / (2**z) / 16
    with psycopg.connect(**layer["settings"]) as connection:
        blob = connection.execute(tile_query(layer),
            (z,x,y,z,x,y,segment,layer["srid"])).fetchone()[0]
    blob = bytes(blob) if blob else b""
    features = [] if not blob else mapbox_vector_tile.decode(blob)["features"]["features"]
    return paint_tile(features, layer["color"], layer.get("is_grid",False)), len(blob), len(features)


def polygon_patch(polygon):
    polygon = orient(polygon, sign=1.0)
    vertices = []
    codes = []

    for ring in [polygon.exterior, *polygon.interiors]:
        coordinates = list(ring.coords)
        vertices.extend((x, y) for x, y, *_ in coordinates)
        codes.extend(
            [Path.MOVETO]
            + [Path.LINETO] * (len(coordinates) - 2)
            + [Path.CLOSEPOLY]
        )

    return Path(vertices, codes)


def collect_parts(geometry, polygons, lines, points):
    if geometry is None or geometry.is_empty:
        return

    kind = geometry.geom_type

    if kind == "Polygon":
        polygons.append(polygon_patch(geometry))
    elif kind in ("LineString", "LinearRing"):
        lines.append([(x, y) for x, y, *_ in geometry.coords])
    elif kind == "Point":
        points.append((geometry.x, geometry.y))
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            collect_parts(part, polygons, lines, points)


def paint_tile(features, color, thematic=False):
    polygons, lines, points = [], [], []
    polygon_colors, line_colors, point_colors = [], [], []
    # Dekoder domyślnie zwraca oś Y skierowaną w górę.
    for feature in features:
        np,nl,nt = len(polygons),len(lines),len(points)
        feature_color = (passability_color(feature.get("properties",{}).get("przejezdnosc"))
                         if thematic else color)
        collect_parts(shape(feature["geometry"]), polygons, lines, points)
        polygon_colors.extend([feature_color]*(len(polygons)-np))
        line_colors.extend([feature_color]*(len(lines)-nl))
        point_colors.extend([feature_color]*(len(points)-nt))
    with RENDER_LOCK:
        fig = Figure(figsize=(TILE_SIZE/100, TILE_SIZE/100), dpi=100)
        fig.patch.set_alpha(0)
        ax = fig.add_axes([0,0,1,1])
        ax.set_axis_off()
        ax.patch.set_alpha(0)
        ax.set_xlim(0,EXTENT)
        ax.set_ylim(0,EXTENT)
        if polygons:
            ax.add_collection(PathCollection(polygons, facecolors=polygon_colors,
                edgecolors="#64748b", linewidths=0.35, antialiaseds=False), autolim=False)
        if lines:
            ax.add_collection(LineCollection(lines, colors=line_colors,
                linewidths=0.85, antialiaseds=False), autolim=False)
        if points:
            ax.scatter([p[0] for p in points], [p[1] for p in points],
                       s=8, c=point_colors, edgecolors="#64748b", linewidths=0.3)
        ax.set_xlim(0,EXTENT)
        ax.set_ylim(0,EXTENT)
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        image = Image.frombuffer("RGBA", (TILE_SIZE,TILE_SIZE),
                                 canvas.buffer_rgba(), "raw", "RGBA", 0, 1).copy()
        fig.clear()
        return image


class GISApp(tk.Tk):
    def __init__(self):
        super().__init__()
        apply_dark_theme(self)
        self.title("PSIP Map — analiza terenu")
        self.geometry("1360x860")
        self.minsize(1080,700)
        self.layers = []
        self.last_settings = {}
        self.events = queue.Queue()
        self.tile_events = queue.Queue()
        self.pool = ThreadPoolExecutor(max_workers=3)
        self.pending = set()
        self.cache = OrderedDict()
        self.photos = []
        self.visible_keys = set()
        self.serial = 0
        self.busy = False
        self.closing = False
        self.zoom_level = 9
        self.center = (21.0/360+0.5, 0.33)
        self.drag = None
        self.timer = None
        self.error_keys = set()
        self.tile_errors = 0
        self.last_error = ""
        self.bytes_received = 0
        self.status = tk.StringVar(value="Gotowe | MVT | mapa EPSG:3857")
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        header = ttk.Frame(self,style="Header.TFrame",padding=(20,14))
        header.pack(fill="x")
        ttk.Label(header,text="PSIP MAP",style="Brand.TLabel").pack(side="left")
        ttk.Label(header,text="Analiza terenu  /  powiat radomszczański",style="BrandSub.TLabel").pack(side="left",padx=20)
        ttk.Label(header,text="POSTGIS  ·  MVT",style="Badge.TLabel").pack(side="right")
        toolbar = ttk.Frame(self,padding=(16,10))
        toolbar.pack(fill="x",pady=(0,1))
        self.add_button = ttk.Button(toolbar,text="＋  Dodaj dane",style="Primary.TButton",command=self.open_database)
        self.add_button.pack(side="left")
        ttk.Button(toolbar,text="Dopasuj widok",command=self.fit_layers).pack(side="left",padx=(10,4))
        ttk.Button(toolbar,text="Odśwież mapę",command=self.clear_cache).pack(side="left",padx=4)
        ttk.Button(toolbar,text="＋",width=3,command=lambda:self.change_zoom(1)).pack(side="left",padx=(16,4))
        ttk.Button(toolbar,text="−",width=3,command=lambda:self.change_zoom(-1)).pack(side="left")
        ttk.Label(toolbar,text="Przesuwanie: lewy przycisk   ·   Zoom: kółko",style="Muted.TLabel").pack(side="right",padx=8)
        layout = ttk.Panedwindow(self,orient="horizontal")
        layout.pack(fill="both",expand=True)
        sidebar = ttk.Frame(layout,padding=(14,14),width=320)
        layout.add(sidebar,weight=0)
        ttk.Label(sidebar,text="WARSTWY",style="Title.TLabel").pack(anchor="w")
        ttk.Label(sidebar,text="Kliknij warstwę, aby ją wybrać.\n☑/☐ przełącza widoczność. Górna warstwa\njest rysowana na wierzchu.",
                  wraplength=290,style="Muted.TLabel").pack(anchor="w",pady=(8,12))
        layer_box = ttk.Frame(sidebar)
        layer_box.pack(fill="both",expand=True)
        self.layer_tree = ttk.Treeview(layer_box,columns=("show","name"),show="headings",
                                      selectmode="browse",height=8)
        self.layer_tree.heading("show",text="✓")
        self.layer_tree.heading("name",text="Warstwa")
        self.layer_tree.column("show",width=35,stretch=False,anchor="center")
        self.layer_tree.column("name",width=255)
        scroll = ttk.Scrollbar(layer_box,orient="vertical",command=self.layer_tree.yview)
        self.layer_tree.configure(yscrollcommand=scroll.set)
        self.layer_tree.pack(side="left",fill="both",expand=True)
        scroll.pack(side="right",fill="y")
        self.layer_tree.bind("<ButtonRelease-1>",self.layer_clicked)
        self.layer_tree.bind("<<TreeviewSelect>>",lambda e:self.update_layer_info())
        self.layer_tree.bind("<Delete>",lambda e:self.remove_selected())
        self.layer_tree.bind("<Button-3>",self.layer_menu)
        controls = ttk.Frame(sidebar)
        controls.pack(fill="x",pady=(12,6))
        controls.columnconfigure(0,weight=1)
        controls.columnconfigure(1,weight=1)
        ttk.Button(controls,text="↑  Wyżej",command=lambda:self.move_selected(1)).grid(row=0,column=0,sticky="ew",padx=(0,3),pady=3)
        ttk.Button(controls,text="↓  Niżej",command=lambda:self.move_selected(-1)).grid(row=0,column=1,sticky="ew",padx=(3,0),pady=3)
        ttk.Button(controls,text="Pokaż / ukryj",command=self.toggle_selected).grid(row=1,column=0,sticky="ew",padx=(0,3),pady=3)
        ttk.Button(controls,text="Przybliż",command=self.fit_selected).grid(row=1,column=1,sticky="ew",padx=(3,0),pady=3)
        ttk.Button(controls,text="Usuń warstwę",style="Danger.TButton",command=self.remove_selected).grid(row=2,column=0,columnspan=2,sticky="ew",pady=(3,0))
        ttk.Button(sidebar,text="Otwórz tabelę danych",command=self.show_attributes).pack(fill="x",pady=(0,4))
        self.layer_info = tk.StringVar(value="Wybierz siatkę H3, aby zobaczyć przejezdność.")
        ttk.Label(sidebar,textvariable=self.layer_info,wraplength=290,style="Muted.TLabel").pack(anchor="w",pady=8)
        legend = ttk.LabelFrame(sidebar,text="PRZEJEZDNOŚĆ · SKALA ROBOCZA",padding=12)
        legend.pack(fill="x",pady=6)
        bar = tk.Canvas(legend,width=240,height=16,bg=THEME["panel"],highlightthickness=0)
        bar.pack(fill="x")
        for x in range(240):
            bar.create_line(x,0,x,16,fill=passability_color(x/239))
        ttk.Label(legend,text="0 — nieprzejezdne          1 — przejezdne").pack(anchor="w")
        empty = ttk.Frame(legend)
        empty.pack(anchor="w",pady=(6,0))
        tk.Label(empty,bg=NO_DATA_COLOR,width=3,relief="flat").pack(side="left",padx=(0,5))
        ttk.Label(empty,text="Brak danych (NULL)").pack(side="left")
        ttk.Label(legend,text="Kolory komórek, nie gęstość punktów.\nWartości musi dostarczyć analiza.",
                  wraplength=265,style="Muted.TLabel").pack(anchor="w",pady=(6,0))
        map_panel = ttk.Frame(layout)
        layout.add(map_panel,weight=1)
        map_heading = ttk.Frame(map_panel,padding=(14,10))
        map_heading.pack(fill="x")
        ttk.Label(map_heading,text="MAPA",style="Title.TLabel").pack(side="left")
        ttk.Label(map_heading,text="EPSG:3857",style="Muted.TLabel").pack(side="right")
        self.map = tk.Canvas(map_panel,bg=THEME["map"],highlightthickness=0)
        self.map.pack(fill="both",expand=True)
        self.map.bind("<Configure>",lambda e:self.schedule_draw())
        self.map.bind("<ButtonPress-1>",self.pan_start)
        self.map.bind("<B1-Motion>",self.pan_move)
        self.map.bind("<ButtonRelease-1>",self.pan_end)
        self.map.bind("<MouseWheel>",self.wheel)
        self.map.bind("<Button-4>",lambda e:self.change_zoom(1,e.x,e.y))
        self.map.bind("<Button-5>",lambda e:self.change_zoom(-1,e.x,e.y))
        ttk.Label(self,textvariable=self.status,style="Status.TLabel").pack(fill="x")
        self.schedule_draw()
        self.after(100,self.process_events)
        self.after(50,self.process_tiles)

    def run_background(self, work, finished, failed=None):
        if self.busy:
            messagebox.showinfo("Trwa operacja", "Poczekaj na jej zakończenie.")
            return

        self.busy = True
        self.add_button.configure(state="disabled")

        def worker():
            try:
                result = work()
                self.events.put((finished, result, None, failed))
            except Exception as error:
                self.events.put((finished, None, str(error), failed))

        threading.Thread(target=worker, daemon=True).start()

    def process_events(self):
        try:
            while True:
                callback, result, error, failed = self.events.get_nowait()
                self.busy = False
                self.add_button.configure(state="normal")

                if error:
                    self.status.set("Operacja zakończona błędem")
                    messagebox.showerror("Błąd", error)
                    if failed:
                        failed()
                else:
                    callback(result)
        except queue.Empty:
            pass

        self.after(100, self.process_events)

    def open_database(self):
        dialog = tk.Toplevel(self)
        dialog.configure(background=THEME["panel"])
        dialog.after(100,lambda:dark_titlebar(dialog))
        dialog.title("Dodaj dane z PostgreSQL / PostGIS")
        dialog.geometry("840x640")
        dialog.minsize(760,580)
        dialog.transient(self)
        dialog.grab_set()

        form = ttk.Frame(dialog, padding=10)
        form.pack(fill="x")

        defaults = [
            ("Host", "localhost"),
            ("Port", "5444"),
            ("Baza", "psip"),
            ("Użytkownik", "psip"),
            ("Hasło", ""),
        ]
        fields = {}

        for row, (label, default) in enumerate(defaults):
            ttk.Label(form, text=label).grid(
                row=row, column=0, sticky="w", pady=3
            )
            value = tk.StringVar(value=self.last_settings.get(label, default))
            fields[label] = value
            ttk.Entry(
                form,
                textvariable=value,
                show="*" if label == "Hasło" else "",
                width=35,
            ).grid(row=row, column=1, sticky="w", padx=10)

        tree = ttk.Treeview(
            dialog,
            columns=("schema", "table", "geometry", "srid"),
            show="headings",
            selectmode="extended",
        )

        for name, title, width in [
            ("schema", "Schemat", 100),
            ("table", "Warstwa", 260),
            ("geometry", "Geometria", 130),
            ("srid", "EPSG", 70),
        ]:
            tree.heading(name, text=title)
            tree.column(name, width=width)

        tree.pack(fill="both", expand=True, padx=10, pady=10)

        info = ttk.Label(
            dialog, text="Połącz się. Ctrl pozwala zaznaczyć kilka warstw."
        )
        info.pack(anchor="w", padx=10)

        buttons = ttk.Frame(dialog, padding=10)
        buttons.pack(fill="x")
        connection_settings = {}

        def connect():
            try:
                settings = {
                    "host": fields["Host"].get().strip(),
                    "port": int(fields["Port"].get()),
                    "dbname": fields["Baza"].get().strip(),
                    "user": fields["Użytkownik"].get().strip(),
                    "password": fields["Hasło"].get(),
                    "connect_timeout": 8,
                    "options": (
                        "-c default_transaction_read_only=on "
                        "-c statement_timeout=60000"
                    ),
                }
            except ValueError:
                messagebox.showerror("Błąd", "Port musi być liczbą.")
                return

            def work():
                with psycopg.connect(**settings) as connection:
                    return connection.execute(
                        """
                        SELECT f_table_schema, f_table_name,
                               f_geometry_column, srid
                        FROM public.geometry_columns
                        WHERE f_table_schema IN ('grid', 'bdot', 'public')
                        ORDER BY f_table_schema, f_table_name,
                                 f_geometry_column
                        """
                    ).fetchall()

            def finished(rows):
                if not dialog.winfo_exists():
                    return

                self.last_settings = {
                    label: value.get() for label, value in fields.items()
                    if label != "Hasło"
                }
                connection_settings.clear()
                connection_settings.update(settings)

                for item in tree.get_children():
                    tree.delete(item)

                for row in rows:
                    tree.insert("", "end", values=row)

                info.configure(text=f"Połączono. Dostępne warstwy: {len(rows)}")
                self.status.set("Połączono z bazą")

            self.status.set("Łączenie z PostgreSQL…")
            self.run_background(work, finished)

        def add_selected():
            selected = [
                tree.item(item, "values") for item in tree.selection()
            ]
            if not selected or not connection_settings:
                messagebox.showinfo("Wybór warstw", "Połącz się i wybierz warstwę.")
                return

            settings = dict(connection_settings)

            def work():
                with psycopg.connect(**settings) as connection:
                    return [describe_layer(connection, row, settings) for row in selected]

            def finished(loaded):
                for layer in loaded:
                    self.add_layer(layer)
                if dialog.winfo_exists():
                    dialog.destroy()
                self.fit_layers()

            self.status.set("Odczyt metadanych i zasięgu — bez pobierania całej warstwy…")
            self.run_background(work, finished)

        ttk.Button(
            buttons, text="Połącz", command=connect
        ).pack(side="left")

        ttk.Button(
            buttons, text="Dodaj zaznaczone", style="Primary.TButton", command=add_selected
        ).pack(side="right")

    def add_layer(self, layer):
        # Ta sama warstwa z tego samego połączenia nie jest dodawana drugi raz.
        for previous in self.layers:
            if (previous["name"]==layer["name"] and
                all(previous["settings"].get(k)==layer["settings"].get(k)
                    for k in ("host","port","dbname","user"))):
                previous["visible"].set(True)
                self.refresh_layer_tree(previous["key"])
                self.schedule_draw()
                return
        self.serial += 1
        layer.update(key=self.serial, color=COLORS[(self.serial-1)%len(COLORS)],
                     visible=tk.BooleanVar(value=True))
        self.layers.append(layer)
        self.refresh_layer_tree(layer["key"])

    def selected_layer(self):
        selection = self.layer_tree.selection()
        return next((l for l in self.layers if selection and str(l["key"])==selection[0]),None)

    def refresh_layer_tree(self, selected=None):
        if selected is None:
            layer = self.selected_layer()
            selected = layer["key"] if layer else None
        for item in self.layer_tree.get_children():
            self.layer_tree.delete(item)
        for layer in reversed(self.layers):
            self.layer_tree.insert("","end",iid=str(layer["key"]),
                values=("☑" if layer["visible"].get() else "☐",layer["name"]))
        if selected is not None and self.layer_tree.exists(str(selected)):
            self.layer_tree.selection_set(str(selected))
            self.layer_tree.focus(str(selected))
        self.update_layer_info()

    def update_layer_info(self):
        layer = self.selected_layer()
        if layer is None:
            self.layer_info.set("Wybierz warstwę.")
        elif layer.get("is_grid"):
            missing = "\nBrak kolumny — uruchom add_passability.sql." if not layer["has_passability"] else ""
            self.layer_info.set("Siatka: ID + geometria + przejezdnosc.\n"
                                "NULL = szary. Skala stała: 0–1."+missing)
        else:
            self.layer_info.set("Warstwa pomocnicza: ID + geometria.\nMapa: EPSG:3857.")

    def layer_clicked(self,event):
        item = self.layer_tree.identify_row(event.y)
        if item and self.layer_tree.identify_column(event.x)=="#1":
            self.layer_tree.selection_set(item)
            self.toggle_selected()

    def toggle_selected(self):
        layer = self.selected_layer()
        if layer:
            layer["visible"].set(not layer["visible"].get())
            self.refresh_layer_tree(layer["key"])
            self.schedule_draw()

    def remove_selected(self):
        layer = self.selected_layer()
        if layer is None:
            return
        key = layer["key"]
        self.layers.remove(layer)  # Tylko z mapy. Bez DELETE/DROP w bazie.
        self.cache = OrderedDict((k,v) for k,v in self.cache.items() if k[0]!=key)
        self.error_keys = {k for k in self.error_keys if k[0]!=key}
        self.visible_keys = {k for k in self.visible_keys if k[0]!=key}
        self.refresh_layer_tree(self.layers[-1]["key"] if self.layers else None)
        self.schedule_draw()

    def move_selected(self,direction):
        layer = self.selected_layer()
        if layer is None:
            return
        i = self.layers.index(layer)
        j = i+direction
        if 0<=j<len(self.layers):
            self.layers[i],self.layers[j] = self.layers[j],self.layers[i]
            self.refresh_layer_tree(layer["key"])
            self.schedule_draw()

    def layer_menu(self,event):
        item = self.layer_tree.identify_row(event.y)
        if not item:
            return
        self.layer_tree.selection_set(item)
        menu = tk.Menu(self,tearoff=False)
        for label,command in [("Pokaż/ukryj",self.toggle_selected),
                              ("Przybliż do warstwy",self.fit_selected),
                              ("Tabela danych",self.show_attributes),
                              ("Wyżej",lambda:self.move_selected(1)),
                              ("Niżej",lambda:self.move_selected(-1)),
                              ("Usuń z mapy",self.remove_selected)]:
            menu.add_command(label=label,command=command)
        try:
            menu.tk_popup(event.x_root,event.y_root)
        finally:
            menu.grab_release()

    def fit_selected(self):
        layer = self.selected_layer()
        if layer:
            layer["visible"].set(True)
            self.refresh_layer_tree(layer["key"])
            self.fit_bounds([layer["bounds"]] if layer["bounds"] else [])

    def fit_layers(self):
        self.fit_bounds([l["bounds"] for l in self.layers if l["visible"].get() and l["bounds"]])

    def fit_bounds(self,bounds):
        if not bounds:
            return
        xmin,ymin = min(b[0] for b in bounds),min(b[1] for b in bounds)
        xmax,ymax = max(b[2] for b in bounds),max(b[3] for b in bounds)
        self.center = ((xmin+xmax)/2/WORLD+0.5, 0.5-(ymin+ymax)/2/WORLD)
        w,h = max(256,self.map.winfo_width()),max(256,self.map.winfo_height())
        fraction = max((xmax-xmin)/WORLD/w,(ymax-ymin)/WORLD/h,1e-10)
        self.zoom_level = max(0,min(20,math.floor(math.log2(1/(fraction*TILE_SIZE*1.1)))))
        self.schedule_draw()

    def show_attributes(self):
        if self.busy:
            messagebox.showinfo("Tabela", "Poczekaj na zakończenie bieżącej operacji.")
            return
        layer = self.selected_layer()
        if not layer:
            return
        dialog = tk.Toplevel(self)
        dialog.configure(background=THEME["panel"])
        dialog.after(100,lambda:dark_titlebar(dialog))
        dialog.title("Tabela — "+layer["name"])
        dialog.geometry("1000x470")
        columns = ("id","geom","przejezdnosc") if layer.get("is_grid") else ("id","geom")
        table = ttk.Treeview(dialog,columns=columns,show="headings")
        for col in columns:
            table.heading(col,text=col)
            table.column(col,width=600 if col=="geom" else 170,stretch=True)
        scroll = ttk.Scrollbar(dialog,command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right",fill="y")
        table.pack(fill="both",expand=True,padx=8,pady=8)
        info = ttk.Label(dialog,text="Geometria jako WKT w układzie tabeli źródłowej (skrócona w widoku).")
        info.pack(anchor="w",padx=8)
        nav = ttk.Frame(dialog,padding=8)
        nav.pack(fill="x")
        page = [0]
        loading = [False]
        def load(delta=0):
            if self.busy or loading[0] or not dialog.winfo_exists():
                return
            offset = max(0,page[0]+delta)
            loading[0] = True
            prev.configure(state="disabled")
            nxt.configure(state="disabled")
            def work():
                value = (sql.SQL(', "przejezdnosc"::double precision') if layer["has_passability"]
                         else sql.SQL(', NULL::double precision')) if layer.get("is_grid") else sql.SQL("")
                query = sql.SQL("SELECT {id}::text, ST_AsText({geom}){value} FROM {table} "
                                "ORDER BY {id} LIMIT 101 OFFSET %s").format(
                    id=sql.Identifier(layer["identity"]),geom=sql.Identifier(layer["geom"]),
                    value=value,table=sql.Identifier(layer["schema"],layer["table"]))
                with psycopg.connect(**layer["settings"]) as connection:
                    return connection.execute(query,(offset*100,)).fetchall()
            def finished(rows):
                loading[0] = False
                if not dialog.winfo_exists():
                    return
                page[0] = offset
                table.delete(*table.get_children()) if table.get_children() else None
                for row in rows[:100]:
                    values = [str(row[0]), (row[1] or "NULL")[:200]]
                    if layer.get("is_grid"):
                        values.append("NULL — brak danych" if row[2] is None else f"{row[2]:.4f}")
                    table.insert("","end",values=values)
                info.configure(text=f"Strona {offset+1} | {len(rows[:100])} rekordów | WKT skrócony do 200 znaków | "
                                    f"EPSG:{layer['srid']} | NULL = brak wyniku")
                prev.configure(state="normal" if offset else "disabled")
                nxt.configure(state="normal" if len(rows)>100 else "disabled")
            def failed():
                loading[0] = False
                if dialog.winfo_exists():
                    prev.configure(state="normal" if page[0] else "disabled")
                    nxt.configure(state="normal")
                    info.configure(text="Błąd odczytu. Kliknij Odśwież tabelę, aby spróbować ponownie.")
            self.run_background(work,finished,failed)
        prev = ttk.Button(nav,text="← Poprzednie 100",command=lambda:load(-1))
        prev.pack(side="left")
        nxt = ttk.Button(nav,text="Następne 100 →",command=lambda:load(1))
        nxt.pack(side="left",padx=8)
        ttk.Button(nav,text="Odśwież tabelę",command=load).pack(side="right")
        load()

    def schedule_draw(self):
        if self.closing:
            return
        if self.timer:
            self.after_cancel(self.timer)
        self.timer = self.after(70,self.draw_tiles)

    def visible_tiles(self):
        z = self.zoom_level
        n = 2**z
        size = TILE_SIZE*n
        w,h = self.map.winfo_width(),self.map.winfo_height()
        left,top = self.center[0]*size-w/2,self.center[1]*size-h/2
        for y in range(max(0,math.floor(top/TILE_SIZE)),min(n-1,math.floor((top+h)/TILE_SIZE))+1):
            for x in range(max(0,math.floor(left/TILE_SIZE)),min(n-1,math.floor((left+w)/TILE_SIZE))+1):
                yield z,x,y,round(x*TILE_SIZE-left),round(y*TILE_SIZE-top)

    def draw_tiles(self):
        self.timer = None
        if self.closing or self.drag:
            return
        tiles = list(self.visible_tiles())
        wanted = []
        self.visible_keys = set()
        self.map.delete("tile")
        self.map.delete("empty")
        if not any(layer["visible"].get() for layer in self.layers):
            cx,cy = self.map.winfo_width()/2,self.map.winfo_height()/2
            title = "Dodaj pierwszą warstwę" if not self.layers else "Warstwy są ukryte"
            subtitle = "Kliknij ＋ Dodaj dane i wybierz siatkę H3 lub BDOT z PostGIS." if not self.layers else "Włącz widoczność wybranej warstwy w panelu po lewej."
            self.map.create_text(cx,cy-16,text=title,fill=THEME["text"],font=("Segoe UI",20,"bold"),tags="empty")
            self.map.create_text(cx,cy+24,text=subtitle,fill=THEME["muted"],font=("Segoe UI",10),width=max(200,self.map.winfo_width()-80),tags="empty")
        self.photos.clear()
        cached = 0
        for layer in self.layers:
            if not layer["visible"].get():
                continue
            for z,x,y,px,py in tiles:
                # Nie pytamy o kafelki poza zasięgiem warstwy (z buforem).
                if layer["bounds"]:
                    span = WORLD/(2**z)
                    xmin,ymin,xmax,ymax = layer["bounds"]
                    margin = span*BUFFER/EXTENT
                    tx,ty = x*span-HALF_WORLD,HALF_WORLD-y*span
                    if tx> xmax+margin or tx+span<xmin-margin or ty<ymin-margin or ty-span>ymax+margin:
                        continue
                key = (layer["key"],z,x,y)
                self.visible_keys.add(key)
                if key in self.cache:
                    image = self.cache.pop(key)
                    self.cache[key] = image
                    photo = ImageTk.PhotoImage(image,master=self)
                    self.photos.append(photo)
                    self.map.create_image(px,py,anchor="nw",image=photo,tags="tile")
                    cached += 1
                elif key not in self.pending and key not in self.error_keys:
                    wanted.append((abs(px-self.map.winfo_width()/2)+abs(py-self.map.winfo_height()/2),
                                   layer,key,z,x,y))
        wanted.sort(key=lambda item:item[0])
        # Kolejka nie rośnie przy szybkim zoomie. Maksymalnie trzy aktywne kafelki.
        for _,layer,key,z,x,y in wanted[:max(0,3-len(self.pending))]:
            self.pending.add(key)
            future = self.pool.submit(fetch_tile,layer,z,x,y)
            future.add_done_callback(lambda f,k=key:self.tile_done(k,f))
        self.status.set(f"MVT | EPSG:3857 | zoom {self.zoom_level} | widoczne kafelki: {cached} | "
                        f"pobieranie: {len(self.pending)} | transfer: {self.bytes_received/1024:.0f} KiB"
                        + (f" | Błędy: {self.tile_errors} — {self.last_error[:140]}" if self.tile_errors else ""))

    def tile_done(self,key,future):
        try:
            self.tile_events.put((key,future.result(),None))
        except Exception as error:
            self.tile_events.put((key,None,str(error)))

    def process_tiles(self):
        changed = False
        try:
            while True:
                key,result,error = self.tile_events.get_nowait()
                self.pending.discard(key)
                if not any(l["key"]==key[0] for l in self.layers):
                    changed = True
                    continue
                if error:
                    self.error_keys.add(key)
                    self.tile_errors += 1
                    self.last_error = error
                    if self.tile_errors == 1:
                        messagebox.showerror("Błąd pobierania MVT",error)
                else:
                    image,nbytes,count = result
                    self.bytes_received += nbytes
                    self.cache[key] = image
                    # Bieżący widok pozostaje w pamięci; limit dotyczy także
                    # rezerwy kafelków poza ekranem. Bez pętli pobierz/usuń
                    # przy wielu jednocześnie włączonych warstwach.
                    limit = max(CACHE_LIMIT,len(self.visible_keys)+32)
                    for old_key in list(self.cache):
                        if len(self.cache)<=limit:
                            break
                        if old_key not in self.visible_keys:
                            del self.cache[old_key]
                changed = True
        except queue.Empty:
            pass
        if changed and not self.drag:
            self.schedule_draw()
        if not self.closing:
            self.after(50,self.process_tiles)

    def pan_start(self,event):
        self.drag = (event.x,event.y)
        self.map.configure(cursor="fleur")

    def pan_move(self,event):
        if not self.drag:
            return
        dx,dy = event.x-self.drag[0],event.y-self.drag[1]
        size = TILE_SIZE*2**self.zoom_level
        self.center = (self.center[0]-dx/size,self.center[1]-dy/size)
        self.map.move("tile",dx,dy)
        self.drag = (event.x,event.y)

    def pan_end(self,event):
        self.drag = None
        self.map.configure(cursor="")
        self.schedule_draw()

    def wheel(self,event):
        if event.delta:
            self.change_zoom(1 if event.delta>0 else -1,event.x,event.y)

    def change_zoom(self,delta,x=None,y=None):
        z = max(0,min(20,self.zoom_level+delta))
        if z == self.zoom_level:
            return
        w,h = self.map.winfo_width(),self.map.winfo_height()
        x,y = w/2 if x is None else x,h/2 if y is None else y
        old_size,new_size = TILE_SIZE*2**self.zoom_level,TILE_SIZE*2**z
        self.center = (self.center[0]+(x-w/2)/old_size-(x-w/2)/new_size,
                       self.center[1]+(y-h/2)/old_size-(y-h/2)/new_size)
        self.zoom_level = z
        self.schedule_draw()

    def clear_cache(self):
        if self.pending:
            messagebox.showinfo("Odświeżanie", "Poczekaj na zakończenie pobierania kafelków.")
            return
        self.cache.clear()
        self.error_keys.clear()
        self.tile_errors = 0
        self.last_error = ""
        self.schedule_draw()

    def close_app(self):
        self.closing = True
        self.pool.shutdown(wait=False,cancel_futures=True)
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description="PSIP Map — przeglądarka PostGIS")
    parser.add_argument("--write-icon",metavar="PATH",help="Zapisz ikonę ICO bez otwierania GUI")
    parser.add_argument("--smoke-test",action="store_true",help="Sprawdź inicjalizację okna bez połączenia z bazą")
    args = parser.parse_args()
    if args.write_icon:
        target = FilePath(args.write_icon)
        target.parent.mkdir(parents=True,exist_ok=True)
        application_icon().save(target,format="ICO",sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
        return
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError,OSError):
            pass
    app = GISApp()
    if args.smoke_test:
        app.after(600,app.close_app)
    app.mainloop()


if __name__ == "__main__":
    main()

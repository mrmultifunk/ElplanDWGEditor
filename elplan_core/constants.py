"""Fælles, Qt-uafhængige konstanter for Elplan DWG Editor."""

APP_NAME = "Elplan DWG Editor"
APP_VERSION = "0.59.85"
ODA_DOWNLOAD_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"

# Programmet bruger separate lag til forskellige typer el-installationer.
# EL-SYMBOLER beholdes kun som navn af hensyn til ældre eksporter, men nye
# symboler placeres på de mere specifikke lag nedenfor.
ELECTRICAL_LAYER = "EL-SYMBOLER"
LEGACY_SWITCH_LAYER = "EL-KONTAKTER"
SWITCH_LAYER = "EL-AFBRYDERE"
COMBO_LAYER = "EL-KOMBI"
SOCKET_LAYER = "EL-STIKKONTAKTER"
DATA_LAYER = "EL-TELE-DATA"
LIGHT_OUTLET_LAYER = "EL-LYSUDTAG"
LIGHTING_LAYER = "EL-BELYSNING"
APPLIANCE_LAYER = "EL-BRUGSGENSTANDE"
SOLAR_LAYER = "EL-SOLCELLER"
BOARD_LAYER = "EL-TAVLER"
EARTHING_LAYER = "EL-JORDING"
DETECTOR_LAYER = "EL-DETEKTORER"
MISC_LAYER = "EL-DIVERSE"
CABLE_LAYER = "EL-KABLER"
PATCH_CABLE_LAYER = "EL-PATCHKABLER"
WIRE_LAYER = "EL-LEDNINGER"
META_LAYER = "EL-TEKST"
FREE_TEXT_LAYER = "EL-FRITEKST"
ROOM_LAYER = "EL-RUM"

GENERATED_LAYER_COLORS = {
    SWITCH_LAYER: 1,
    COMBO_LAYER: 1,
    SOCKET_LAYER: 1,
    DATA_LAYER: 1,
    LIGHT_OUTLET_LAYER: 1,
    LIGHTING_LAYER: 1,
    APPLIANCE_LAYER: 1,
    SOLAR_LAYER: 3,
    BOARD_LAYER: 1,
    EARTHING_LAYER: 3,
    DETECTOR_LAYER: 1,
    MISC_LAYER: 1,
    CABLE_LAYER: 1,
    PATCH_CABLE_LAYER: 5,
    WIRE_LAYER: 1,
    META_LAYER: 3,
    FREE_TEXT_LAYER: 7,
    ROOM_LAYER: 4,
}

CABLE_TYPES = {
    "Kabel": CABLE_LAYER,
    "Patchkabel": PATCH_CABLE_LAYER,
    "Ledning": WIRE_LAYER,
}

# Almindelige installationskabler. Feltet er frit redigerbart i GUI'en, så
# andre betegnelser kan stadig anvendes.
CABLE_SPEC_PRESETS = (
    "1G2,5", "1G6", "1G10",
    "3G1,5", "3G2,5", "5G1,5", "5G2,5", "5G4", "5G6", "7G1,5",
    "4X10", "4x1,5",
)

# Kabelvisning gemmes pr. kabel. Interne værdier holdes stabile, mens GUI'en
# kan vise danske navne. De samme værdier bruges af Qt, PDF/print og DXF.
CABLE_LINE_STYLES = {
    "solid": "Fuldt optrukket",
    "dash": "Stiplet",
    "dot": "Prikket",
    "dashdot": "Streg-prik",
}
DEFAULT_CABLE_COLOR = "#d00000"
DEFAULT_CABLE_LINE_STYLE = "solid"

# 0.50.19: kabelkategorier er egentlige visuelle underlag/lag. Kablets
# ``layer`` beskriver stadig den tekniske type (kabel, patchkabel, ledning),
# mens ``cable_category`` beskriver anvendelsen. Den kombinerede kategori-layer
# bruges til lagvisning og DXF-output, uden at eksisterende BOM-nøgler brydes.
DEFAULT_CABLE_CATEGORY = "other"
DEFAULT_CABLE_CATEGORIES = (
    {"id":"sockets", "name":"Stikkontakter", "description":"Kabel til indendørs stikkontakter.", "color":"#d00000", "line_style":"solid"},
    {"id":"outdoor_sockets", "name":"Udendørs stikkontakter", "description":"Kabel til udendørs stikkontakter.", "color":"#b45309", "line_style":"dash"},
    {"id":"outdoor_lighting", "name":"Udendørs lys", "description":"Kabel til udendørs belysning.", "color":"#15803d", "line_style":"dashdot"},
    {"id":"light_points", "name":"Lampesteder", "description":"Forsynings- og installationskabel til lampesteder.", "color":"#2563eb", "line_style":"solid"},
    {"id":"interconnect", "name":"Mellemkabel", "description":"Kabel mellem lampesteder på forskellige grupper.", "color":"#0e7490", "line_style":"dash"},
    {"id":"switch_cable", "name":"Tændkabel", "description":"Kabel fra afbryder til lampested.", "color":"#ea580c", "line_style":"dashdot"},
    {"id":"spots", "name":"Spots", "description":"Kabel til spots og downlights.", "color":"#7c3aed", "line_style":"dot"},
    {"id":"ev_charger", "name":"Ladeboks", "description":"Kabel til ladeboks.", "color":"#0f766e", "line_style":"dash"},
    {"id":"appliances", "name":"Hvidevarer / faste forbrugere", "description":"Kabel til hvidevarer og andre faste elektriske forbrugere.", "color":"#be123c", "line_style":"dashdot"},
    {"id":"data", "name":"Data / netværk", "description":"Kabel til data- og netværksinstallationer.", "color":"#0369a1", "line_style":"dot"},
    {"id":"earthing_bonding", "name":"Udligning / beskyttelsesleder", "description":"Beskyttelsesleder og potentialudligning, herunder hovedjordforbindelse.", "color":"#16a34a", "line_style":"solid"},
    {"id":"service_main", "name":"Stikledning / hovedledning", "description":"Forsyningskabel mellem tilslutningspunkt, måler- og fordelingstavle.", "color":"#7f1d1d", "line_style":"solid"},
    {"id":"other", "name":"Øvrige", "description":"Kabler som ikke passer i en af de øvrige kategorier.", "color":"#d00000", "line_style":"solid"},
)

DEFAULT_SYMBOL_COLOR = "#d00000"
SNAP_TOLERANCE_PX = 18
# Snap skal føles som screen-space magnetisme og derfor være uafhængigt af CAD-enheder/zoom.
SNAP_WALL_TOLERANCE_PX = 36
SNAP_SYMBOL_PORT_TOLERANCE_PX = 34
SNAP_SYMBOL_BODY_PAD_PX = 12
SNAP_DEVICE_TOLERANCE_PX = 28
# Alignment bruges kun som visuel hjælpelinje - ikke som fysisk snapmål.
SNAP_ALIGN_TOLERANCE_PX = 6
GENERATED_LAYERS = set(GENERATED_LAYER_COLORS) | {ELECTRICAL_LAYER, LEGACY_SWITCH_LAYER}

ANNOTATION_STYLES = ("Kompakt", "Detaljeret")
DEFAULT_ANNOTATION_STYLE = "Kompakt"
DEFAULT_ANNOTATION_FONT_SIZE = 8
PRINT_SCOPES = ("Aktuel visning", "Hele tegningen")
DEFAULT_PRINT_SCOPE = "Aktuel visning"
PRINT_MARGIN_MM = 5.0
# Qt-editoren bruger 96 DPI som reference for skærmbaserede labels. PDF-output
# arbejder i points (72/inch), så denne faktor bruges til at oversætte den
# fysiske PDF-skala til samme semantiske zoomniveau som editoren.
OUTPUT_SCREEN_DPI = 96.0

THEME_MODES = ("Lys",)
DEFAULT_THEME = "Lys"
THEMES = {
    "Lys": {
        "root": "#eef1f5", "panel": "#f7f9fb", "surface": "#ffffff", "surface_alt": "#eef2f7",
        "canvas": "#ffffff", "cad": "#17191c", "text": "#1f2937", "muted": "#667085",
        "border": "#c7cfdb", "button": "#e7ecf3", "button_hover": "#dce7f8", "button_pressed": "#d1def2",
        "accent": "#2563eb", "accent_soft": "#eaf1ff",
        "success": "#1d7a45", "annotation_bg": "#ffffff", "annotation_text": "#176b3a",
        "association": "#285d9b", "snap": "#008b8b", "snap_text": "#176b6b",
        "preview_bg": "#dfe3e8", "page_border": "#9aa0a6", "shadow": "#aeb4bc",
    },
}
AUTOSAVE_INTERVAL_MS = 90_000
MAX_RECENT_PROJECTS = 6
SYMBOL_CLIPBOARD_PREFIX = "ELPLAN_SYMBOL_V1\n"
SYMBOLS_CLIPBOARD_PREFIX = "ELPLAN_SYMBOLS_V1\n"
CUSTOM_COMBO_PREFIX = "custom_combo|"
CUSTOM_COMBO_MAX_MODULES = 6
CUSTOM_SWITCH_TYPES = {
    "1-polet afbryder": "switch_1",
    "Korrespondanceafbryder": "switch_2way",
    "Kroneafbryder": "switch_crown",
    "Krydsningsafbryder": "switch_cross",
    "Dobbelt korrespondanceafbryder": "switch_double_2way",
    "Trykkontakt": "pushbutton",
    "Trykkontakt med indikeringslampe": "pushbutton_indicator",
}
CUSTOM_SOCKET_TYPES = {
    "Ingen stikkontakt": "none",
    "Stikkontakt": "socket",
    "Stikkontakt med jordtilslutning": "socket_earth",
}
CUSTOM_SWITCH_SHORT = {
    "switch_1": "1P", "switch_2way": "Korr.", "switch_crown": "Krone",
    "switch_cross": "Kryds", "switch_double_2way": "Dobb. korr.",
    "pushbutton": "Tryk", "pushbutton_indicator": "Tryk+lampe",
}

# Symbolnavne og geometri er genskabt som vektorer med Cubus' oversigt over
# installationstegningssymboler som visuel reference. Bitmapfilerne distribueres
# ikke med programmet.
SYMBOL_GROUPS = {
    "Afbrydere": {
        "Enpolet afbryder": "switch_1",
        "Kroneafbryder": "switch_crown",
        "Korrespondanceafbryder": "switch_2way",
        "Krydsningsafbryder": "switch_cross",
        "Dobbelt korrespondanceafbryder": "switch_double_2way",
        "Trykkontakt": "pushbutton",
        "Trykkontakt med indikeringslampe": "pushbutton_indicator",
        "4 trykkontakter": "pushbutton_4",
    },
    "Kombi": {
        "1-polet afbryder + stikkontakt": "combo_switch_1_socket",
        "Korrespondance + stikkontakt": "combo_switch_2way_socket",
        "Kroneafbryder + stikkontakt": "combo_switch_crown_socket",
        "Krydsningsafbryder + stikkontakt": "combo_switch_cross_socket",
        "Dobbelt korrespondanceafbryder + stikkontakt": "combo_switch_double_2way_socket",
        "Trykkontakt + stikkontakt": "combo_pushbutton_socket",
        "Trykkontakt med indikeringslampe + stikkontakt": "combo_pushbutton_indicator_socket",
        "1-polet + 1-polet + stikkontakt": "combo_row_2x1_socket",
        "1-polet + korrespondance + stikkontakt": "combo_row_1_2way_socket",
        "Korrespondance + korrespondance + stikkontakt": "combo_row_2way_2way_socket",
        "Kroneafbryder + 1-polet + stikkontakt": "combo_row_crown_1_socket",
        "1-polet + 1-polet + 1-polet + stikkontakt": "combo_row_3x1_socket",
        "1-polet + 1-polet + korrespondance + stikkontakt": "combo_row_2x1_2way_socket",
        "Kroneafbryder + 1-polet + 1-polet + stikkontakt": "combo_row_crown_2x1_socket",
    },
    "Stikkontakter": {
        "Stikkontakt": "socket",
        "Stikkontakt med jordtilslutning": "socket_earth",
        "Pillesikker stikkontakt": "socket_childsafe",
        "Stikkontakt med enpolet afbryder": "socket_switch",
        "Stikkontakt 3F+N+PE": "socket_3fn",
        "Shaverstikkontakt / skilletransformer": "socket_shaver",
        "2 stikkontakter i samme dåse (forenklet)": "socket_double_box",
        "3 stikkontakter i samme dåse (forenklet)": "socket_triple_box",
        "2 stikkontakter med jordtilslutning i samme dåse (forenklet)": "socket_double_box_earth",
        "3 stikkontakter med jordtilslutning i samme dåse (forenklet)": "socket_triple_box_earth",
        "2 stikkontakter": "socket_double",
        "3 stikkontakter": "socket_triple",
        "2 stikkontakter med jordtilslutning": "socket_double_earth",
        "3 stikkontakter med jordtilslutning": "socket_triple_earth",
    },
    "Data / netværk": {
        "Tele/Data-stik": "socket_tele",
        "Patchpanel / datacentral (12 porte)": "patch_panel",
    },
    "Belysning": {
        "Tilslutningssted for belysning": "light_connection",
        "Lampeudtag på væg (alm. dåse)": "wall_light_outlet",
        "Belysningsarmatur": "light_fixture",
        "Armatur for lysstofrør": "fluorescent",
        "Lysstofarmatur med fast tilslutning": "fluorescent_fixed",
        "Nød-/panikbelysning": "emergency_light",
        "Spot / downlight": "spot",
    },
    "Brugsgenstande": {
        "Vandvarmer": "water_heater",
        "Varmeapparat / elradiator": "heater",
        "Ventilator": "fan",
        "Elbilslader / ladeboks": "ev_charger",
    },
    "Solceller / energi": {
        "Solcellepanel(er)": "solar_panel",
        "Solcelleinverter": "solar_inverter",
        "Solcellebatteri": "solar_battery",
    },
    "Tavler / forsyning": {
        "Fordelingsanlæg / tavle": "distribution_board",
        "Gruppetavle": "group_board",
        "Målertavle": "meter_board",
        "Hovedjordforbindelse": "main_earthing_connection",
    },
    "Diverse": {
        "Elektrisk lås": "electric_lock",
        "Tilslutningssted, ikke belysning": "connection",
        "Bevægelsesdetektor / PIR": "pir",
        "Røgdetektor": "smoke",
    },
}
SYMBOLS = {name: code for group in SYMBOL_GROUPS.values() for name, code in group.items()}
SYMBOL_NAMES_BY_CODE = {code: name for name, code in SYMBOLS.items()}

SWITCH_ASSOCIATION_SYMBOLS = (
    {code for code in SYMBOL_GROUPS["Afbrydere"].values()}
    | {code for code in SYMBOL_GROUPS["Kombi"].values()}
)
LIGHT_ASSOCIATION_SYMBOLS = {
    "light_connection", "wall_light_outlet", "light_fixture", "fluorescent",
    "fluorescent_fixed", "emergency_light", "spot",
}

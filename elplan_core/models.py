"""Qt-uafhængige datamodeller for projekter og CAD-data."""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid

from elplan_core.constants import (
    CABLE_LAYER,
    DEFAULT_CABLE_CATEGORY,
    DEFAULT_CABLE_COLOR,
    DEFAULT_CABLE_LINE_STYLE,
    DEFAULT_SYMBOL_COLOR,
)


@dataclass
class Placement:
    symbol: str
    x: float
    y: float
    rotation: float = 0.0
    size: float = 500.0
    label: str = ""
    group: str = ""
    # Kombisymboler kan enten bruge den fælles mærkning ovenfor eller separate
    # felter for afbryder- og stikkontaktdelen. Felterne er harmløse for andre symboler.
    label_mode: str = "Fælles"
    switch_label: str = ""
    switch_group: str = ""
    socket_label: str = ""
    socket_group: str = ""
    # Fysisk linjetykkelse ved PDF/DXF/DWG-eksport, angivet i mm.
    line_width: float = 0.25
    # Individuel symbolfarve som #RRGGBB.
    color: str = DEFAULT_SYMBOL_COLOR
    # Visuelle tilhørsforhold mellem kontakter og lys. Afbrydere kan have ét
    # bogstav pr. kanal; et lampested har højst ét bogstav.
    associations: list[str] = field(default_factory=list)
    # For afbrydere gemmes den fysiske kanal -> tilhørsbogstav separat.
    # Det er vigtigt for kombisymboler, fordi alfabetisk sorterede bogstaver ikke
    # nødvendigvis følger modulrækkefølgen (fx 1P=b, 1P=c, korrespondance=a).
    # Tom streng betyder, at den pågældende betjening endnu ikke er tilknyttet.
    association_channels: list[str] = field(default_factory=list)
    # Ét fysisk lampeudtag kan have flere uafhængige tændte udgange. Hver
    # udgang har stabilt id, navn og højst ét tilhørsbogstav. PL-dåse, position
    # og BOM tilhører fortsat det ene fysiske Placement-objekt.
    light_outputs: list[dict] = field(default_factory=list)
    # Låste symboler kan stadig vælges/kopieres, men kan ikke flyttes, roteres,
    # slettes eller redigeres før de låses op igen.
    locked: bool = False
    # Montage- og indkøbskontekst gemmes pr. fysisk symbolforekomst. Profilen
    # bruges til robust gruppering, mens den præcise højde og materialefarven
    # gør Excel/BOM egnet som indkøbsgrundlag uden at ændre symboltypen.
    mounting_zone: str = ""
    mounting_height_mm: float | None = None
    material_color: str = ""
    already_purchased: bool = False
    # Spots kan samles i en vedvarende logisk gruppe. Gruppen er uafhængig af
    # gruppe/kreds-feltet og bruges til samlet valg, redigering og kobling til
    # et lampested. Et tomt id betyder, at spottet ikke er grupperet.
    spot_group_id: str = ""
    spot_group_name: str = ""
    # Spots kan knyttes logisk til et lampested. Når lampestedet senere får
    # tilhørsbogstav fra en afbryder, synkroniseres bogstavet til spottene.
    parent_light_uid: str = ""
    # Et spot følger en bestemt logisk udgang på et flerudgangs-lampested.
    parent_light_output_id: str = ""
    # PL-loftdåser ved lampesteder kan dokumenteres med seks fysiske
    # kabelindføringer. Nøglerne er "1".."6" og værdierne peger på et
    # bestemt kabelben (kabel-id + side ved lampestedet).
    pl_box_entries: dict[str, dict] = field(default_factory=dict)
    # Lederplanen gemmer funktion/samling pr. fysisk leder på hvert kabelben.
    # Referencerne følger samme kabelben som PL-indføringerne og overlever derfor
    # flytning af selve indføringen mellem port 1..6.
    pl_box_wiring: list[dict] = field(default_factory=list)
    # Manuelle Wago-samlinger i PL-dåsen. Hver samling gemmer funktion og de
    # konkrete ledere, som samles før en kort bro går videre til lampeudtaget.
    pl_box_splices: list[dict] = field(default_factory=list)
    # Fysisk orientering af selve PL-dåsen relativt til plantegningens top.
    # Indføringernes numre roteres med dåsen; kabeltilknytningerne ændres ikke.
    pl_box_orientation: int = 0
    # 0.50.12: den grafiske ledereditor kan vise terminalerne som et generisk
    # PL-punkt, et klassisk LK-lampeudtag eller et Wiser/dæmpbart udtag.
    lamp_outlet_type: str = "generic"
    # Read-only feltdokumentation importeret fra PL-dåse-PWA'en. Posten
    # indeholder kun fysisk indføring, kabeltekst, noter og fotoreferencer.
    # Lederfunktioner og Wago-data ligger fortsat udelukkende i felterne ovenfor.
    pl_field_record: dict = field(default_factory=dict)
    # Stabilt id bruges til egentlige kabeltilslutninger, også efter gem/åbn.
    uid: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class CablePlacement:
    points: list[tuple[float, float]]
    layer: str = CABLE_LAYER
    line_width: float = 0.35
    # Visuel kabelstil. Farve/linjetype påvirker visning og output, men ikke
    # kabelgeometri, længde eller artikel/BOM-data.
    color: str = DEFAULT_CABLE_COLOR
    line_style: str = DEFAULT_CABLE_LINE_STYLE
    # Anvendelseskategori styrer visuel stil og et separat lag-niveau.
    cable_category: str = DEFAULT_CABLE_CATEGORY
    # Manuel ekstra tekst. Den automatiske mærkning bygges af cable_id + cable_spec.
    label: str = ""
    cable_spec: str = ""
    cable_id: str = ""
    # Gruppe/kreds er den logiske elektriske sammenhæng. Flere selvstændige
    # fysiske kabler kan høre til samme gruppe uden at blive ét kabelobjekt.
    circuit_id: str = ""
    # Kabler der blev tegnet i samme sammenhængende arbejdsgang deler dette id.
    # Feltet er kun metadata til navigation/markering; BOM arbejder altid pr. kabel-UID.
    route_chain_uid: str = ""
    auto_label: bool = False
    start_symbol_uid: str = ""
    end_symbol_uid: str = ""
    # Portindeks gør forbindelsen stabil på symboler med flere tilslutningspunkter.
    # Ældre projekter mangler felterne og får derfor automatisk port 0.
    start_symbol_port: int = 0
    end_symbol_port: int = 0
    orthogonal: bool = False
    # Valgfri ruteførings-overrides mellem to nabotilslutninger på samme kabel.
    # Kabellets ``orthogonal``-flag er stadig standarden for hele ruten, mens
    # poster her gør det muligt fx kun at føre strækket mellem to lampesteder
    # frit/diagonalt. Identiteten ligger på symbol-uid/port og er derfor stabil,
    # selv når polyline-punkter indsættes eller remappes.
    route_section_modes: list[dict] = field(default_factory=list)
    # Valgfri kabeltype pr. fysisk afsnit mellem to nabotilslutninger.
    # ``cable_spec`` er stadig kabellets globale/default type, mens poster her
    # gør det muligt fx at gå fra 3G1,5 til 5G1,5 kun mellem to lampesteder.
    # Identiteten ligger på symbol-uid/port og er derfor robust over for
    # indsatte/fjernede knækpunkter i selve polyline-geometrien.
    spec_section_overrides: list[dict] = field(default_factory=list)
    # Alle fysiske tilslutningssteder langs samme kabel. Hvert element peger på
    # et punkt i polyline-ruten: {point_index, symbol_uid, symbol_port}. Start-/
    # slutfelterne ovenfor beholdes som kompatibilitet med ældre projekter.
    symbol_connections: list[dict] = field(default_factory=list)
    # Stabilt id gør det muligt at tilknytte BOM-artikler til ét bestemt kabelstræk.
    uid: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class TextPlacement:
    text: str
    x: float
    y: float
    height: float = 250.0
    rotation: float = 0.0
    color: str = "#202020"
    uid: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class RoomPlacement:
    """Brugerdefineret rumområde oven på plantegningen.

    Polygonen gemmes i CAD-koordinater. Rumteksten har sin egen position, så
    brugeren frit kan flytte den væk fra symboler uden at ændre selve rummet.
    """
    name: str
    points: list[tuple[float, float]]
    code: str = ""
    label_x: float = 0.0
    label_y: float = 0.0
    color: str = "#0f766e"
    uid: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class CADPrimitive:
    kind: str
    layer: str
    data: tuple

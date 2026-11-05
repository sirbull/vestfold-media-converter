from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

KINDS = {"video": "Video", "audio": "Lyd", "subtitle": "Undertekst", "data": "Data", "attachment": "Vedlegg"}
TAG_NAMES = {
    "title": "Tittel",
    "artist": "Artist",
    "album_artist": "Albumartist",
    "album": "Album",
    "genre": "Sjanger",
    "date": "Dato",
    "creation_time": "Opprettet",
    "comment": "Kommentar",
    "description": "Beskrivelse",
    "copyright": "Opphavsrett",
    "encoder": "Koder",
    "encoded_by": "Kodet av",
    "handler_name": "Behandler",
    "vendor_id": "Leverandør",
    "major_brand": "Hovedmerke",
    "minor_version": "Mindre versjon",
    "compatible_brands": "Kompatible merker",
    "timecode": "Tidskode",
    "track": "Spor",
    "language": "Språk",
}
CHANNELS = {1: "Mono", 2: "Stereo", 6: "5.1", 8: "7.1"}


def duration_text(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"


def size_text(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _known(value):
    return "" if value in (None, "", 0, "unknown", "und", "N/A") else str(value)


def _bitrate(value):
    return f"{value / 1000:,.0f} kb/s".replace(",", " ") if value else ""


def _codec(stream):
    name = stream.codec.upper()
    extra = " · ".join(part for part in (stream.codec_long, _known(stream.profile)) if part)
    return f"{name} ({extra})" if extra else name


def _scan(field_order):
    if field_order == "progressive":
        return "Progressiv"
    if field_order in {"tt", "tb"}:
        return "Linjesprang, øvre felt først"
    if field_order in {"bb", "bt"}:
        return "Linjesprang, nedre felt først"
    return ""


def _tag_rows(tags, skip=()):
    return [(TAG_NAMES.get(key.lower(), key), value) for key, value in tags if key.lower() not in skip]


def _stream_section(stream):
    kind = "Omslagsbilde" if stream.attached_pic else KINDS.get(stream.kind, stream.kind.capitalize())
    rows = [("Kodek", _codec(stream))]
    if stream.kind == "video":
        rows += [
            ("Oppløsning", f"{stream.width} × {stream.height}" if stream.width else ""),
            ("Visningsforhold", _known(stream.display_aspect)),
            (
                "Bildefrekvens",
                f"{stream.frame_rate:.3f}".rstrip("0").rstrip(".") + " bilder/s"
                if stream.frame_rate and not stream.attached_pic
                else "",
            ),
            ("Skanning", _scan(stream.field_order)),
            ("Pikselformat", stream.pixel_format),
            ("Bitdybde", f"{stream.bit_depth} bit" if stream.bit_depth else ""),
            ("Bitrate", _bitrate(stream.bit_rate)),
            ("Fargerom", _known(stream.color_space)),
            ("Overføring", _known(stream.color_transfer)),
            ("Primærfarger", _known(stream.color_primaries)),
            ("Fargeområde", _known(stream.color_range)),
            ("HDR", "Ja" if stream.hdr else ""),
        ]
    elif stream.kind == "audio":
        layout = _known(stream.channel_layout)
        channels = CHANNELS.get(stream.channels, f"{stream.channels} kanaler") if stream.channels else ""
        rows += [
            ("Samplingsfrekvens", f"{stream.sample_rate / 1000:g} kHz" if stream.sample_rate else ""),
            (
                "Kanaler",
                f"{channels} ({layout})" if layout and layout.lower() != channels.lower() else channels,
            ),
            ("Bitdybde", f"{stream.bit_depth} bit" if stream.bit_depth else ""),
            ("Bitrate", _bitrate(stream.bit_rate)),
        ]
    rows += [
        ("Språk", _known(stream.language)),
        ("Tittel", stream.title),
        ("Standardspor", "Ja" if stream.default else ""),
        *_tag_rows(stream.tags, skip={"language", "title"}),
    ]
    return f"{kind} – strøm {stream.index}", rows


def _export_section(settings):
    video = settings.video_codec
    quality = (
        f"CRF {settings.quality}"
        if settings.quality_mode == "quality"
        else _bitrate(settings.video_bitrate * 1000)
    )
    return "Eksport", [
        ("Profil", settings.name),
        ("Filformat", settings.container.upper()),
        ("Videokodek", video or ("Ingen video" if video is None else "")),
        ("Videokvalitet", quality if video and video != "copy" else ""),
        ("Hastighet", settings.preset if video and video not in {"copy", "prores_ks"} else ""),
        ("Oppløsning", f"{settings.width} × {settings.height}" if settings.width and settings.height else ""),
        ("Bildefrekvens", settings.fps),
        ("Lydkodek", settings.audio_codec),
        (
            "Lydbitrate",
            f"{settings.audio_bitrate} kb/s"
            if settings.audio_codec != "copy" and not settings.audio_codec.startswith(("pcm", "flac"))
            else "",
        ),
        (
            "Samplingsfrekvens",
            f"{settings.sample_rate / 1000:g} kHz" if settings.sample_rate else "Som kilden",
        ),
        (
            "Kanaler",
            CHANNELS.get(settings.channels, str(settings.channels)) if settings.channels else "Som kilden",
        ),
    ]


def item_sections(item):
    """Samler alt vi vet om en fil som (tittel, [(felt, verdi)]), tomme felt utelatt."""
    info = item.info
    sections = [
        (
            "Fil",
            [
                ("Navn", item.path.name),
                ("Mappe", str(item.path.parent)),
                ("Status", item.status),
                ("Feil", item.error),
                ("Resultat", str(item.output) if item.output else ""),
            ],
        )
    ]
    if info:
        sections.append(
            (
                "Format",
                [
                    ("Type", info.kind),
                    ("Filformat", info.format_long or info.format_name),
                    ("Varighet", duration_text(info.duration)),
                    ("Størrelse", f"{size_text(info.size)} ({info.size:,} byte)".replace(",", " ")),
                    ("Samlet bitrate", _bitrate(info.bit_rate)),
                    ("Strømmer", str(len(info.streams))),
                ],
            )
        )
        sections += [_stream_section(stream) for stream in info.streams]
        if info.tags:
            sections.append(("Metadata", _tag_rows(info.tags)))
    if item.settings:
        sections.append(_export_section(item.settings))
    return [(title, [(key, value) for key, value in rows if value]) for title, rows in sections]


def details_text(items):
    blocks = []
    for item in items:
        for title, rows in item_sections(item):
            blocks.append("\n".join([title.upper(), *(f"  {key}: {value}" for key, value in rows)]))
    return "\n\n".join(blocks)


class FileDetailsDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items
        self.setObjectName("fileDetails")
        self.setWindowTitle("Fildetaljer" if len(items) == 1 else f"Fildetaljer – {len(items)} filer")
        self.setMinimumSize(520, 420)
        self.resize(660, 760)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)
        scroll = QScrollArea()
        scroll.setObjectName("detailsScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("detailsContent")
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 6, 0)
        body.setSpacing(12)
        for item in items:
            body.addLayout(self._file_header(item))
            for title, rows in item_sections(item):
                if rows:
                    body.addWidget(self._card(title, rows))
            body.addSpacing(12)
        body.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        buttons = QHBoxLayout()
        self.copy_button = QPushButton("Kopier alt")
        self.copy_button.setObjectName("softButton")
        self.copy_button.setAccessibleName("Kopier alle fildetaljer til utklippstavlen")
        self.copy_button.clicked.connect(self.copy_all)
        close = QPushButton("Lukk")
        close.setObjectName("filledButton")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(self.copy_button)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _file_header(self, item):
        header = QVBoxLayout()
        header.setSpacing(2)
        name = QLabel(item.path.name)
        name.setObjectName("sectionTitle")
        name.setWordWrap(True)
        name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.addWidget(name)
        info = item.info
        summary = QLabel(
            f"{info.kind}  ·  {duration_text(info.duration)}  ·  {size_text(info.size)}  ·  {item.status}"
            if info
            else item.status
        )
        summary.setObjectName("muted")
        header.addWidget(summary)
        return header

    def _card(self, title, rows):
        card = QFrame()
        card.setObjectName("detailCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(8)
        heading = QLabel(title.upper())
        heading.setObjectName("eyebrow")
        layout.addWidget(heading)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        for row, (key, value) in enumerate(rows):
            label = QLabel(key)
            label.setObjectName("detailKey")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            # Usynlige bruddpunkter lar lange stier brytes i stedet for å gjøre dialogen bredere.
            text = QLabel(value.replace("\\", "\\\u200b").replace("/", "/\u200b"))
            text.setObjectName("detailError" if key == "Feil" else "detailValue")
            text.setWordWrap(True)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(label, row, 0)
            grid.addWidget(text, row, 1)
        layout.addLayout(grid)
        return card

    def copy_all(self):
        QApplication.clipboard().setText(details_text(self.items))
        self.copy_button.setText("Kopiert")

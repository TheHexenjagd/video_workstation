"""Shared constants, codec sets, GPU presets, and subtitle language mappings."""

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".ts", ".m4v")

BITMAP_SUB_CODECS = {
    "hdmv_pgs_subtitle",
    "dvd_subtitle",
    "dvb_subtitle",
    "xsub",
    "dvb_teletext",
    "eia_608",
    "cea_708",
    "teletext",
    "arib_caption",
    "subviewer",
    "pjs",
    "vplayer",
}

INCOMPATIBLE_MP4_AUDIO_CODECS = {
    "dca",
    "dts",
    "flac",
    "pcm_s16le",
    "pcm_s24le",
    "pcm_s32le",
    "pcm_s8",
    "pcm_u8",
    "pcm_bluray",
    "pcm_dvd",
    "pcm_alaw",
    "pcm_mulaw",
    "truehd",
    "mlp",
    "vorbis",
    "opus",
}

STRIP_METADATA_ARGS = (
    "-map_metadata",
    "-1",
    "-map_metadata:s",
    "-1",
    "-map_chapters",
    "-1",
    "-fflags",
    "+bitexact",
)

PRESETS_NVIDIA = {
    "lossless": {"nombre": "Lossless", "descripcion": "Sin perdida", "velocidad": "⚡☆☆", "calidad": "★★★★★"},
    "hq": {"nombre": "HQ", "descripcion": "Prioriza calidad", "velocidad": "⚡☆☆", "calidad": "★★★★☆"},
    "slow": {"nombre": "Slow (HQ)", "descripcion": "Mejor calidad, menor velocidad", "velocidad": "⚡☆☆", "calidad": "★★★★"},
    "bd": {"nombre": "BD", "descripcion": "Compatibilidad Blu-ray", "velocidad": "⚡☆☆", "calidad": "★★★★"},
    "default": {"nombre": "Default", "descripcion": "Balance entre calidad y velocidad", "velocidad": "⚡⚡☆", "calidad": "★★★☆"},
    "medium": {"nombre": "Medium", "descripcion": "Calidad intermedia", "velocidad": "⚡⚡☆", "calidad": "★★★☆"},
    "llhq": {"nombre": "LLHQ", "descripcion": "Baja latencia + calidad", "velocidad": "⚡⚡☆", "calidad": "★★★☆"},
    "fast": {"nombre": "Fast", "descripcion": "Mas rapido, algo menos eficiente", "velocidad": "⚡⚡⚡", "calidad": "★★☆☆"},
    "ll": {"nombre": "LL", "descripcion": "Baja latencia", "velocidad": "⚡⚡⚡", "calidad": "★★☆☆"},
    "llhp": {"nombre": "LLHP", "descripcion": "Baja latencia + rendimiento", "velocidad": "⚡⚡⚡", "calidad": "★★☆☆"},
    "hp": {"nombre": "HP", "descripcion": "Prioriza velocidad", "velocidad": "⚡⚡⚡⚡", "calidad": "★★☆☆"},
}

PRESETS_QSV = {
    "veryslow": {"nombre": "Very Slow", "descripcion": "Maxima calidad", "velocidad": "⚡☆☆", "calidad": "★★★★★"},
    "slow": {"nombre": "Slow", "descripcion": "Mejor calidad", "velocidad": "⚡☆☆", "calidad": "★★★★"},
    "medium": {"nombre": "Medium", "descripcion": "Calidad mejor, algo mas lento", "velocidad": "⚡⚡☆", "calidad": "★★★☆"},
    "fast": {"nombre": "Fast", "descripcion": "Balance velocidad/calidad", "velocidad": "⚡⚡⚡", "calidad": "★★★☆"},
    "faster": {"nombre": "Faster", "descripcion": "Rapido", "velocidad": "⚡⚡⚡", "calidad": "★★☆☆"},
    "veryfast": {"nombre": "Very Fast", "descripcion": "Maxima velocidad", "velocidad": "⚡⚡⚡⚡", "calidad": "★★☆☆"},
}

PRESETS_AMD = {
    "quality": {"nombre": "Quality", "descripcion": "Prioriza calidad", "velocidad": "⚡☆☆", "calidad": "★★★★★"},
    "balanced": {"nombre": "Balanced", "descripcion": "Balance entre velocidad y calidad", "velocidad": "⚡⚡☆", "calidad": "★★★☆"},
    "speed": {"nombre": "Speed", "descripcion": "Prioriza velocidad", "velocidad": "⚡⚡⚡⚡", "calidad": "★★☆☆"},
}

SUBTITLE_LANGUAGE_MAP = {
    "es": ("spa", "Español"),
    "spa": ("spa", "Español"),
    "esp": ("spa", "Español"),
    "spanish": ("spa", "Español"),
    "castellano": ("spa", "Español (Castellano)"),
    "lat": ("spa", "Español (Latino)"),
    "latino": ("spa", "Español (Latino)"),
    "en": ("eng", "Inglés"),
    "eng": ("eng", "Inglés"),
    "english": ("eng", "Inglés"),
    "ingles": ("eng", "Inglés"),
    "fr": ("fra", "Francés"),
    "fra": ("fra", "Francés"),
    "fre": ("fra", "Francés"),
    "french": ("fra", "Francés"),
    "frances": ("fra", "Francés"),
    "de": ("deu", "Alemán"),
    "deu": ("deu", "Alemán"),
    "ger": ("deu", "Alemán"),
    "german": ("deu", "Alemán"),
    "aleman": ("deu", "Alemán"),
    "it": ("ita", "Italiano"),
    "ita": ("ita", "Italiano"),
    "italian": ("ita", "Italiano"),
    "italiano": ("ita", "Italiano"),
    "pt": ("por", "Portugués"),
    "por": ("por", "Portugués"),
    "portuguese": ("por", "Portugués"),
    "portugues": ("por", "Portugués"),
    "ja": ("jpn", "Japonés"),
    "jpn": ("jpn", "Japonés"),
    "japanese": ("jpn", "Japonés"),
    "japones": ("jpn", "Japonés"),
    "ru": ("rus", "Ruso"),
    "rus": ("rus", "Ruso"),
    "zh": ("chi", "Chino"),
    "chi": ("chi", "Chino"),
    "zho": ("chi", "Chino"),
    "ko": ("kor", "Coreano"),
    "kor": ("kor", "Coreano"),
}

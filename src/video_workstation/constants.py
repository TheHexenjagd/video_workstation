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
    "p7": {"nombre": "P7 - Máxima calidad", "descripcion": "Codificación más lenta con la mejor compresión y fidelidad visual.", "velocidad": 1, "calidad": 5},
    "p6": {"nombre": "P6 - Muy alta calidad", "descripcion": "Prioriza la calidad de imagen con un tiempo de codificación alto.", "velocidad": 2, "calidad": 4},
    "p5": {"nombre": "P5 - Alta calidad", "descripcion": "Buena mejora de calidad respecto al modo estándar.", "velocidad": 2, "calidad": 4},
    "p4": {"nombre": "P4 - Equilibrado (Recomendado)", "descripcion": "Balance óptimo entre velocidad y calidad (valor por defecto de NVENC).", "velocidad": 3, "calidad": 3},
    "p3": {"nombre": "P3 - Rápido", "descripcion": "Mayor velocidad manteniendo una calidad sólida.", "velocidad": 4, "calidad": 3},
    "p2": {"nombre": "P2 - Muy rápido", "descripcion": "Prioriza la velocidad con menor eficiencia de compresión.", "velocidad": 4, "calidad": 2},
    "p1": {"nombre": "P1 - Máxima velocidad", "descripcion": "Codificación ultrarrápida con calidad básica.", "velocidad": 5, "calidad": 2},
}

PRESETS_QSV = {
    "veryslow": {"nombre": "Very Slow", "descripcion": "Máxima calidad y compresión, codificación más lenta.", "velocidad": 1, "calidad": 5},
    "slower": {"nombre": "Slower", "descripcion": "Muy alta calidad con mayor tiempo de procesamiento.", "velocidad": 2, "calidad": 4},
    "slow": {"nombre": "Slow", "descripcion": "Prioriza la calidad sobre la velocidad.", "velocidad": 2, "calidad": 4},
    "medium": {"nombre": "Medium (Recomendado)", "descripcion": "Balance estándar entre velocidad y calidad.", "velocidad": 3, "calidad": 3},
    "fast": {"nombre": "Fast", "descripcion": "Más rápido que Medium con ligera pérdida de eficiencia.", "velocidad": 4, "calidad": 3},
    "faster": {"nombre": "Faster", "descripcion": "Codificación rápida orientada a productividad.", "velocidad": 4, "calidad": 2},
    "veryfast": {"nombre": "Very Fast", "descripcion": "Máxima velocidad con calidad básica.", "velocidad": 5, "calidad": 2},
}

PRESETS_AMD = {
    "quality": {"nombre": "Quality", "descripcion": "Prioriza la calidad visual en AMD AMF.", "velocidad": 2, "calidad": 5},
    "balanced": {"nombre": "Balanced (Recomendado)", "descripcion": "Balance entre velocidad y calidad.", "velocidad": 3, "calidad": 3},
    "speed": {"nombre": "Speed", "descripcion": "Prioriza la máxima velocidad de codificación.", "velocidad": 5, "calidad": 2},
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

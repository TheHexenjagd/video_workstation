"""Unit tests for GPU preset normalization."""

import unittest

from video_workstation.media.presets import get_default_preset, get_valid_preset
from video_workstation.media.processor import MediaProcessorMixin


class _FakeVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class _FakeCombo:
    def __init__(self):
        self._values = []
        self._current = ""

    def config(self, **kwargs):
        if "values" in kwargs:
            self._values = list(kwargs["values"])

    def set(self, value):
        self._current = value

    def get(self):
        return self._current

    def __getitem__(self, key):
        if key == "values":
            return self._values
        raise KeyError(key)


class _DummyProcessor(MediaProcessorMixin):
    def __init__(self, gpu, preset, gpus_status):
        self.gpu_acel_var = _FakeVar(gpu)
        self.preset_var = _FakeVar(preset)
        self.gpus_status = gpus_status
        self.gpu_availability = {}
        self.gpu_map_display_to_val = {}
        self.cb_gpu = _FakeCombo()


class TestPresets(unittest.TestCase):
    def test_nvidia_preset_mapping(self):
        self.assertEqual(get_valid_preset("p4", "nvidia"), "p4")
        self.assertEqual(get_valid_preset("medium", "nvidia"), "p4")
        self.assertEqual(get_valid_preset("veryfast", "nvidia"), "p1")
        self.assertEqual(get_valid_preset("unknown", "nvidia"), "p4")

    def test_intel_and_amd_preset_mapping(self):
        self.assertEqual(get_valid_preset("hq", "intel"), "slow")
        self.assertEqual(get_valid_preset("p6", "intel"), "slower")
        self.assertEqual(get_valid_preset("medium", "amd"), "balanced")
        self.assertEqual(get_valid_preset("p5", "amd"), "quality")
        self.assertEqual(get_valid_preset("unknown", "amd"), "balanced")

    def test_default_preset_per_gpu(self):
        self.assertEqual(get_default_preset("nvidia"), "p4")
        self.assertEqual(get_default_preset("intel"), "medium")
        self.assertEqual(get_default_preset("amd"), "balanced")
        self.assertEqual(get_default_preset("other"), "medium")

    def test_gpu_detection_registers_medium_preset_and_preserves_custom(self):
        proc = _DummyProcessor(
            "nvidia",
            "medium",
            {"nvidia": (True, "OK"), "intel": (True, "OK"), "amd": (False, "No")},
        )
        proc._update_gpu_selector_ui()
        self.assertEqual(proc.gpu_acel_var.get(), "nvidia")
        self.assertEqual(proc.preset_var.get(), "p4")

        # Custom preset on the active GPU is preserved on startup
        proc_custom = _DummyProcessor(
            "nvidia",
            "p6",
            {"nvidia": (True, "OK"), "intel": (True, "OK"), "amd": (False, "No")},
        )
        proc_custom._update_gpu_selector_ui()
        self.assertEqual(proc_custom.gpu_acel_var.get(), "nvidia")
        self.assertEqual(proc_custom.preset_var.get(), "p6")

    def test_gpu_fallback_and_manual_change_reset_to_medium_preset(self):
        # NVIDIA unavailable -> falls back to Intel (medium)
        proc = _DummyProcessor(
            "nvidia",
            "p6",
            {"nvidia": (False, "No"), "intel": (True, "OK"), "amd": (True, "OK")},
        )
        proc._update_gpu_selector_ui()
        self.assertEqual(proc.gpu_acel_var.get(), "intel")
        self.assertEqual(proc.preset_var.get(), "medium")

        # Manual switch to AMD -> resets to AMD medium (balanced)
        proc.cb_gpu.set("AMD (AMF)")
        proc._on_gpu_selected()
        self.assertEqual(proc.gpu_acel_var.get(), "amd")
        self.assertEqual(proc.preset_var.get(), "balanced")

        # Re-selecting same GPU keeps custom preset
        proc.preset_var.set("quality")
        proc._on_gpu_selected()
        self.assertEqual(proc.preset_var.get(), "quality")

    def test_hardware_decoder_fallback_to_software(self):
        import subprocess

        class _ProcWithFallback(_DummyProcessor):
            def __init__(self):
                super().__init__("nvidia", "p4", {"nvidia": (True, "OK")})
                self.decod_hw_var = _FakeVar("D3D11VA")
                self.var_subcarpeta = _FakeVar(False)
                self.var_eliminar_metadatos = _FakeVar(False)
                self.cancelar_procesamiento = False
                self.ffmpeg_path = "ffmpeg"
                self.commands_run = []
                self.logged_messages = []
                self.recorded_activities = []

            def _invalidate_file_cache(self, p):
                pass

            def _log_message(self, msg):
                self.logged_messages.append(msg)

            def _record_activity(self, estado, video, accion, detalle="", item_key=None, log_extra=None):
                self.recorded_activities.append((estado, video, accion, detalle, log_extra))

            def _run_subprocess_cancellable(self, cmd):
                self.commands_run.append(list(cmd))
                if "-hwaccel" in cmd:
                    return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="Error: d3d11va decoder device failed")
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        proc = _ProcWithFallback()
        info = {
            "streams": [
                {"index": 0, "codec_type": "video", "codec_name": "h264"},
                {"index": 1, "codec_type": "audio", "codec_name": "aac", "tags": {"language": "spa"}},
            ]
        }
        combos = [
            {
                "audio_indices": [1],
                "sub_indices": [],
                "label": "DUAL",
                "hardsub": True,
            }
        ]
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_out:
            errores = []
            proc._build_combinations("sample_video.mkv", tmp_out, info, combos, errores)

            self.assertEqual(len(errores), 0)
            self.assertEqual(len(proc.commands_run), 2)
            self.assertIn("-hwaccel", proc.commands_run[0])
            self.assertNotIn("-hwaccel", proc.commands_run[1])
            self.assertTrue(any("Fallo en decodificador D3D11VA" in m for m in proc.logged_messages))

            success_acts = [a for a in proc.recorded_activities if a[0] == "exito"]
            self.assertEqual(len(success_acts), 1)
            detalle = success_acts[0][3]
            log_extra = success_acts[0][4]
            self.assertIn("[Fallback Software (D3D11VA)]", detalle)
            self.assertIn("Software (Fallback", log_extra["Decodificador"])


if __name__ == "__main__":
    unittest.main()

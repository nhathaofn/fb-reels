import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from unittest.mock import MagicMock, patch
from src.core.whisper_manager import WhisperModelManager, get_whisper_manager


class TestWhisperManager(unittest.TestCase):

    def setUp(self):
        self.manager = get_whisper_manager()
        self.manager.unload_model()

    def tearDown(self):
        self.manager.unload_model()

    def test_singleton(self):
        m1 = get_whisper_manager()
        m2 = WhisperModelManager()
        self.assertIs(m1, m2)

    @patch("faster_whisper.WhisperModel")
    @patch("ctranslate2.get_cuda_device_count", return_value=1)
    def test_preload_and_reuse_on_cuda(self, mock_cuda_count, mock_whisper_cls):
        mock_instance = MagicMock()
        mock_whisper_cls.return_value = mock_instance

        # Lần 1: Nạp
        ok = self.manager.preload_model("large-v3-turbo", device="cuda")
        self.assertTrue(ok)
        self.assertTrue(self.manager.is_loaded())
        mock_whisper_cls.assert_called_once_with("large-v3-turbo", device="cuda", compute_type="float16")

        # Lần 2: get_model trả về instance đã nạp mà không khởi tạo lại
        model = self.manager.get_model("large-v3-turbo")
        self.assertIs(model, mock_instance)
        self.assertEqual(mock_whisper_cls.call_count, 1)

        # Lần 3: Unload
        self.manager.unload_model()
        self.assertFalse(self.manager.is_loaded())

"""Module Quản lý Vòng đời Model Whisper (Whisper Model Manager).

Cơ chế:
1. Nạp trước (Preload) model Whisper (mặc định 'large-v3-turbo') lên GPU (CUDA NVIDIA) khi bắt đầu cào dự án.
2. Giữ nguyên instance model trong VRAM GPU để tái sử dụng xuyên suốt toàn bộ tiến trình render/transcribe,
   tránh việc tự nạp tự tắt gây tốn tài nguyên và thời gian mỗi lần xử lý video.
3. Giải phóng (Unload) model sạch sẽ khỏi VRAM/RAM khi hoàn thành toàn bộ tác vụ hoặc người dùng hủy cào.
"""

import gc
import os
from pathlib import Path
from typing import Optional

from src.utils.logger import logger


def setup_cuda_environment():
    """Tự động thêm đường dẫn thư viện CUDA DLL (cublas, cudnn) vào search path của Windows."""
    import site
    try:
        site_dirs = site.getsitepackages() if hasattr(site, "getsitepackages") else []
        try:
            import site as user_site
            if hasattr(user_site, "getusersitepackages"):
                site_dirs.append(user_site.getusersitepackages())
        except Exception:
            pass

        for s_dir in site_dirs:
            nv_dir = Path(s_dir) / "nvidia"
            if nv_dir.exists():
                for sub in nv_dir.iterdir():
                    bin_dir = sub / "bin"
                    if bin_dir.exists():
                        try:
                            os.add_dll_directory(str(bin_dir))
                        except Exception:
                            pass
                        cur_path = os.environ.get("PATH", "")
                        if str(bin_dir) not in cur_path:
                            os.environ["PATH"] = str(bin_dir) + os.pathsep + cur_path
    except Exception as e:
        logger.debug(f"Không thể cấu hình tự động CUDA DLL: {e}")


class WhisperModelManager:
    """Singleton quản lý vòng đời model Whisper trên GPU CUDA."""
    _instance: Optional["WhisperModelManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
            cls._instance._loaded_model_name = ""
            cls._instance._device = ""
            cls._instance._compute_type = ""
        return cls._instance

    def is_loaded(self) -> bool:
        """Kiểm tra model hiện tại đã được nạp sẵn trong bộ nhớ hay chưa."""
        return self._model is not None

    def get_loaded_info(self) -> dict:
        return {
            "is_loaded": self._model is not None,
            "model_name": self._loaded_model_name,
            "device": self._device,
            "compute_type": self._compute_type
        }

    def preload_model(
        self,
        model_name: str = "large-v3-turbo",
        device: str = "cuda"
    ) -> bool:
        """Nạp model Whisper lên GPU (CUDA) một lần duy nhất lúc khởi động cào dự án."""
        # Nếu model đã được nạp và đúng tên -> tái sử dụng ngay lập tức
        if self._model is not None and self._loaded_model_name == model_name:
            logger.info(f"⚡ Model whisper '{model_name}' đã sẵn sàng trên {self._device} (giữ nguyên VRAM).")
            return True

        setup_cuda_environment()

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            logger.warning("Thư viện 'faster-whisper' chưa được cài đặt. Không thể nạp model Whisper.")
            return False

        has_cuda = False
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                has_cuda = True
        except Exception:
            pass

        target_device = "cuda" if (device == "cuda" and has_cuda) else "cpu"
        target_compute_type = "float16" if target_device == "cuda" else "int8"

        logger.info(
            f"🚀 Đang khởi tạo và nạp model Whisper '{model_name}' trên "
            f"{'GPU (CUDA NVIDIA)' if target_device == 'cuda' else 'CPU'} "
            f"cho phiên làm việc này..."
        )

        try:
            if target_device == "cuda":
                model = WhisperModel(model_name, device="cuda", compute_type="float16")
                logger.info(f"⚡ ĐÃ NẠP THÀNH CÔNG model whisper '{model_name}' trên GPU (CUDA NVIDIA)!")
            else:
                num_threads = min(8, max(2, (os.cpu_count() or 4) - 1))
                model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=num_threads)
                logger.info(f"Đã nạp model whisper '{model_name}' trên CPU ({num_threads} threads).")

            self._model = model
            self._loaded_model_name = model_name
            self._device = target_device
            self._compute_type = target_compute_type
            return True
        except Exception as e:
            logger.warning(f"Lỗi khi nạp model whisper '{model_name}' trên {target_device}: {e}")
            if target_device == "cuda":
                logger.info(f"Thử nạp dự phòng model whisper '{model_name}' trên CPU...")
                try:
                    num_threads = min(8, max(2, (os.cpu_count() or 4) - 1))
                    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=num_threads)
                    self._model = model
                    self._loaded_model_name = model_name
                    self._device = "cpu"
                    self._compute_type = "int8"
                    logger.info(f"Đã nạp model whisper '{model_name}' trên CPU thành công.")
                    return True
                except Exception as ce:
                    logger.error(f"Không thể nạp model whisper trên CPU: {ce}")
            return False

    def get_model(self, model_name: str = "large-v3-turbo"):
        """Lấy instance model đã nạp sẵn. Nếu chưa nạp, tự động nạp."""
        if self._model is not None and self._loaded_model_name == model_name:
            return self._model

        # Nếu model chưa nạp hoặc khác tên, tiến hành nạp
        success = self.preload_model(model_name=model_name)
        if success:
            return self._model
        return None

    def unload_model(self):
        """Giải phóng hoàn toàn model khỏi VRAM/RAM khi hoàn tất toàn bộ tiến trình cào."""
        if self._model is not None:
            model_name = self._loaded_model_name
            dev = self._device
            self._model = None
            self._loaded_model_name = ""
            self._device = ""
            self._compute_type = ""

            # Dọn dẹp bộ nhớ Python và CUDA
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

            logger.info(f"🛑 Đã tắt và giải phóng model whisper '{model_name}' khỏi {dev.upper()}!")


# Instance toàn cục thuận tiện truy xuất
whisper_manager = WhisperModelManager()


def get_whisper_manager() -> WhisperModelManager:
    return whisper_manager

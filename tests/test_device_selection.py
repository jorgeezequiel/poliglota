"""Tests for device selection and fallback behavior in gpu.py and cli.py."""

from unittest.mock import patch

import pytest

from poliglota import gpu
from poliglota.cli import _resolve_device_name


class TestDetectDeviceStrictMode:
    """Test detect_device() with strict mode enforcement."""

    def test_detect_device_auto_cuda_available(self) -> None:
        """Auto mode selects CUDA when available."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = True
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=False):
                device = gpu.detect_device("auto", strict=False)
                assert device == "cuda"

    def test_detect_device_auto_mps_fallback(self) -> None:
        """Auto mode falls back to MPS when CUDA unavailable."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=True):
                device = gpu.detect_device("auto", strict=False)
                assert device == "mps"

    def test_detect_device_auto_cpu_fallback(self) -> None:
        """Auto mode falls back to CPU when no accelerator available."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=False):
                device = gpu.detect_device("auto", strict=False)
                assert device == "cpu"

    def test_detect_device_cpu_explicit_never_fallback(self) -> None:
        """CPU explicit request never falls back."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = True
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=True):
                device = gpu.detect_device("cpu", strict=False)
                assert device == "cpu"

    def test_detect_device_cpu_explicit_strict_mode(self) -> None:
        """CPU explicit request succeeds in strict mode."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=False):
                device = gpu.detect_device("cpu", strict=True)
                assert device == "cpu"

    def test_detect_device_cuda_available_permissive(self) -> None:
        """CUDA explicit request succeeds when available (permissive mode)."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = True
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=False):
                device = gpu.detect_device("cuda", strict=False)
                assert device == "cuda"

    def test_detect_device_cuda_unavailable_permissive_fallback(self) -> None:
        """CUDA explicit request falls back to CPU when unavailable (permissive mode)."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=False):
                device = gpu.detect_device("cuda", strict=False)
                assert device == "cpu"

    def test_detect_device_cuda_unavailable_strict_raises(self) -> None:
        """CUDA explicit request raises when unavailable (strict mode)."""
        with (
            patch("poliglota.gpu._require_torch") as mock_torch,
            patch("poliglota.gpu._is_mps_available", return_value=False),
        ):
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with pytest.raises(ValueError, match=r"CUDA requested but not available"):
                gpu.detect_device("cuda", strict=True)

    def test_detect_device_mps_available_permissive(self) -> None:
        """MPS explicit request succeeds when available (permissive mode)."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=True):
                device = gpu.detect_device("mps", strict=False)
                assert device == "mps"

    def test_detect_device_mps_unavailable_permissive_fallback(self) -> None:
        """MPS explicit request falls back to CPU when unavailable (permissive mode)."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=False):
                device = gpu.detect_device("mps", strict=False)
                assert device == "cpu"

    def test_detect_device_mps_unavailable_strict_raises(self) -> None:
        """MPS explicit request raises when unavailable (strict mode)."""
        with (
            patch("poliglota.gpu._require_torch") as mock_torch,
            patch("poliglota.gpu._is_mps_available", return_value=False),
        ):
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with pytest.raises(ValueError, match=r"MPS.*not available"):
                gpu.detect_device("mps", strict=True)

    def test_detect_device_gpu_alias_cuda_priority(self) -> None:
        """GPU alias prioritizes CUDA over MPS."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = True
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=True):
                device = gpu.detect_device("gpu", strict=False)
                assert device == "cuda"

    def test_detect_device_gpu_alias_mps_fallback(self) -> None:
        """GPU alias falls back to MPS when CUDA unavailable."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=True):
                device = gpu.detect_device("gpu", strict=False)
                assert device == "mps"

    def test_detect_device_gpu_alias_no_device_fallback(self) -> None:
        """GPU alias falls back to CPU when no accelerator available."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=False):
                device = gpu.detect_device("gpu", strict=False)
                assert device == "cpu"

    def test_detect_device_invalid_device_permissive_defaults_auto(self) -> None:
        """Invalid device in permissive mode defaults to auto."""
        with patch("poliglota.gpu._require_torch") as mock_torch:
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with patch("poliglota.gpu._is_mps_available", return_value=False):
                device = gpu.detect_device("npu", strict=False)
                assert device == "cpu"

    def test_detect_device_invalid_device_strict_raises(self) -> None:
        """Invalid device in strict mode raises ValueError."""
        with (
            patch("poliglota.gpu._require_torch") as mock_torch,
            patch("poliglota.gpu._is_mps_available", return_value=False),
        ):
            mock_torch.return_value.cuda.is_available.return_value = False
            mock_torch.return_value.version.__version__ = "2.0.0"
            with pytest.raises(ValueError, match=r"Invalid device 'npu'"):
                gpu.detect_device("npu", strict=True)


class TestResolveDeviceName:
    """Test _resolve_device_name() CLI validation."""

    def test_resolve_device_name_auto_uses_permissive(self) -> None:
        """_resolve_device_name('auto') uses permissive detect_device."""
        with patch("poliglota.gpu.detect_device", return_value="cuda") as mock_detect:
            device = _resolve_device_name("auto")
            assert device == "cuda"
            mock_detect.assert_called_once_with("auto", strict=False)

    def test_resolve_device_name_explicit_uses_strict_cuda(self) -> None:
        """_resolve_device_name('cuda') uses strict detect_device."""
        with patch("poliglota.gpu.detect_device", return_value="cuda") as mock_detect:
            device = _resolve_device_name("cuda")
            assert device == "cuda"
            mock_detect.assert_called_once_with("cuda", strict=True)

    def test_resolve_device_name_explicit_uses_strict_cpu(self) -> None:
        """_resolve_device_name('cpu') uses strict detect_device."""
        with patch("poliglota.gpu.detect_device", return_value="cpu") as mock_detect:
            device = _resolve_device_name("cpu")
            assert device == "cpu"
            mock_detect.assert_called_once_with("cpu", strict=True)

    def test_resolve_device_name_explicit_uses_strict_mps(self) -> None:
        """_resolve_device_name('mps') uses strict detect_device."""
        with patch("poliglota.gpu.detect_device", return_value="mps") as mock_detect:
            device = _resolve_device_name("mps")
            assert device == "mps"
            mock_detect.assert_called_once_with("mps", strict=True)

    def test_resolve_device_name_gpu_alias_uses_strict(self) -> None:
        """_resolve_device_name('gpu') uses strict detect_device."""
        with patch("poliglota.gpu.detect_device", return_value="cuda") as mock_detect:
            device = _resolve_device_name("gpu")
            assert device == "cuda"
            mock_detect.assert_called_once_with("gpu", strict=True)

    def test_resolve_device_name_invalid_raises(self) -> None:
        """_resolve_device_name rejects invalid devices."""
        with pytest.raises(ValueError, match="Unsupported device 'npu'"):
            _resolve_device_name("npu")

    def test_resolve_device_name_none_defaults_auto(self) -> None:
        """_resolve_device_name(None) defaults to 'auto'."""
        with patch("poliglota.gpu.detect_device", return_value="cpu") as mock_detect:
            device = _resolve_device_name(None)
            assert device == "cpu"
            mock_detect.assert_called_once_with("auto", strict=False)

    def test_resolve_device_name_whitespace_normalization(self) -> None:
        """_resolve_device_name normalizes whitespace."""
        with patch("poliglota.gpu.detect_device", return_value="cuda") as mock_detect:
            device = _resolve_device_name("  CUDA  ")
            assert device == "cuda"
            mock_detect.assert_called_once_with("cuda", strict=True)

    def test_resolve_device_name_strict_propagates_error(self) -> None:
        """_resolve_device_name propagates strict mode errors."""
        with (
            patch(
                "poliglota.gpu.detect_device",
                side_effect=ValueError("CUDA requested but not available on this system."),
            ),
            pytest.raises(ValueError, match="CUDA requested but not available"),
        ):
            _resolve_device_name("cuda")

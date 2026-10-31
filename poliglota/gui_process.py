"""Process-tree lifetime management for the GUI's CLI subprocesses.

The GUI runs the CLI in a child process. On Windows, terminating that child does
not necessarily stop the worker processes it started, so the GUI puts the child
inside a *job object* configured with ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``:
closing the job — or terminating it explicitly — takes the whole tree down.

Everything here degrades to a no-op outside Windows or when the Win32 calls are
unavailable, so the GUI keeps working exactly as before on other platforms.
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import sys
from typing import Self

logger = logging.getLogger(__name__)

#: Win32 constant: kill every process in the job when the last handle closes.
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
#: Win32 constant: ``JobObjectExtendedLimitInformation`` information class.
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = (
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    )


class _IoCounters(ctypes.Structure):
    _fields_ = (
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    )


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = (
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    )


def _kernel32() -> object | None:
    """Return a configured ``kernel32`` handle, or ``None`` when unavailable."""
    if sys.platform != "win32":
        return None

    loader = getattr(ctypes, "WinDLL", None)
    if loader is None:  # pragma: no cover - non-Windows ctypes build
        return None

    try:
        kernel32 = loader("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        kernel32.CreateJobObjectW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p)
        kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        kernel32.AssignProcessToJobObject.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
        kernel32.SetInformationJobObject.restype = ctypes.c_int
        kernel32.SetInformationJobObject.argtypes = (
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        )
        kernel32.TerminateJobObject.restype = ctypes.c_int
        kernel32.TerminateJobObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        kernel32.CloseHandle.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    except (AttributeError, OSError):
        return None
    return kernel32


class WindowsJob:
    """Keeps a CLI process tree together so it can be terminated as a unit."""

    def __init__(self, kernel32: object | None = None) -> None:
        """Create a job; ``kernel32`` is injectable for tests."""
        self._kernel32 = kernel32 if kernel32 is not None else _kernel32()
        self._handle: int | None = None

    @property
    def available(self) -> bool:
        """Whether the job object API can be used on this machine."""
        return self._kernel32 is not None

    @property
    def active(self) -> bool:
        """Whether a process has already been assigned to this job."""
        return self._handle is not None

    def attach(self, process: object) -> bool:
        """Assign ``process`` — and everything it spawns — to the job."""
        if self._handle is not None or self._kernel32 is None:
            return False

        handle = self._create()
        if handle is None:
            return False

        process_handle = getattr(process, "_handle", None)
        if process_handle is None:
            self._close_handle(handle)
            return False

        try:
            assigned = bool(
                self._kernel32.AssignProcessToJobObject(handle, int(process_handle)),  # type: ignore[attr-defined]
            )
        except (AttributeError, OSError, TypeError, ValueError):
            assigned = False

        if not assigned:
            logger.debug("Could not assign the CLI process to the job object")
            self._close_handle(handle)
            return False

        self._handle = handle
        return True

    def _create(self) -> int | None:
        kernel32 = self._kernel32
        if kernel32 is None:
            return None

        try:
            handle = kernel32.CreateJobObjectW(None, None)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            return None
        if not handle:
            return None

        info = _ExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        try:
            configured = bool(
                kernel32.SetInformationJobObject(  # type: ignore[attr-defined]
                    handle,
                    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                ),
            )
        except (AttributeError, OSError, TypeError):
            configured = False

        if not configured:
            self._close_handle(handle)
            return None

        return int(handle)

    def terminate(self) -> bool:
        """Terminate every process currently assigned to the job."""
        if self._handle is None or self._kernel32 is None:
            return False
        try:
            return bool(self._kernel32.TerminateJobObject(self._handle, 1))  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            return False

    def close(self) -> None:
        """Close the job handle, which also kills any surviving process."""
        handle = self._handle
        self._handle = None
        if handle is not None:
            self._close_handle(handle)

    def _close_handle(self, handle: int) -> None:
        if self._kernel32 is None:
            return
        with contextlib.suppress(AttributeError, OSError):
            self._kernel32.CloseHandle(handle)  # type: ignore[attr-defined]

    def __enter__(self) -> Self:
        """Enter the job context."""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Close the job when the context ends."""
        self.close()

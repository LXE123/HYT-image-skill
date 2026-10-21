"""Resolve the cross-platform desktop product-package location."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path


WORKSPACE_NAME = "ProductVisualWorkspace"
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def safe_segment(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} 不能为空，也不能以空格开头或结尾")
    if value in {".", ".."} or any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} 包含无效字符")
    if any(character in '<>:"/\\|?*' for character in value) or value.endswith((".", " ")):
        raise ValueError(f"{label} 包含 Windows 或 macOS 路径不支持的字符")
    if value.split(".", 1)[0].upper() in WINDOWS_RESERVED:
        raise ValueError(f"{label} 是 Windows 保留名称")
    if len(value) > 120:
        raise ValueError(f"{label} 不能超过 120 个字符")
    return value


def _windows_desktop() -> Path:
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    desktop_id = GUID.from_buffer_copy(uuid.UUID("b4bfcc3a-db2c-424c-b029-7fe99a87c641").bytes_le)
    pointer = ctypes.c_wchar_p()
    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.c_long
    shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None
    init_result = ole32.CoInitializeEx(None, 0x2)
    init_code = init_result & 0xFFFFFFFF
    if init_code not in {0, 1, 0x80010106}:
        raise OSError(f"无法初始化 Windows COM（HRESULT=0x{init_code:08X}）")
    must_uninitialize = init_code in {0, 1}
    try:
        result = shell32.SHGetKnownFolderPath(ctypes.byref(desktop_id), 0, None, ctypes.byref(pointer))
        if result == 0 and pointer.value:
            return Path(pointer.value)
        profile = os.environ.get("USERPROFILE")
        if profile:
            return Path(profile) / "Desktop"
        raise OSError(f"无法读取 Windows Desktop Known Folder（HRESULT=0x{result & 0xFFFFFFFF:08X}）")
    finally:
        if pointer:
            ole32.CoTaskMemFree(ctypes.cast(pointer, ctypes.c_void_p))
        if must_uninitialize:
            ole32.CoUninitialize()


def desktop_root() -> Path:
    if sys.platform == "win32":
        return _windows_desktop()
    if sys.platform == "darwin":
        return Path.home() / "Desktop"
    configured = os.environ.get("XDG_DESKTOP_DIR")
    return Path(configured).expanduser() if configured else Path.home() / "Desktop"


def product_package_path(product_id: str, version: str, desktop_override: Path | None = None) -> Path:
    product_id = safe_segment(product_id, "product-id")
    version = safe_segment(version, "version")
    desktop = desktop_override.expanduser().resolve() if desktop_override else desktop_root().resolve()
    return desktop / WORKSPACE_NAME / "products" / product_id / version

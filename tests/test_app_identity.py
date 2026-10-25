from __future__ import annotations

import ctypes
import sys
import tkinter as tk
import unittest
from unittest import mock

from semi_auto_probe.ui import app_identity


class AppIdentityTests(unittest.TestCase):
    def test_non_windows_does_not_call_windows_api(self):
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(
            ctypes, "windll", create=True
        ) as windll:
            app_identity.set_windows_app_identity()
        windll.shell32.SetCurrentProcessExplicitAppUserModelID.assert_not_called()

    def test_windows_sets_stable_unicode_identity(self):
        with mock.patch.object(sys, "platform", "win32"), mock.patch.object(
            ctypes, "windll", create=True
        ) as windll:
            setter = windll.shell32.SetCurrentProcessExplicitAppUserModelID
            setter.return_value = 0
            app_identity.set_windows_app_identity()
        setter.assert_called_once_with(app_identity.WINDOWS_APP_ID)
        self.assertEqual(setter.argtypes, [ctypes.c_wchar_p])

    def test_failed_hresult_logs_without_preventing_startup(self):
        with mock.patch.object(sys, "platform", "win32"), mock.patch.object(
            ctypes, "windll", create=True
        ) as windll, self.assertLogs(app_identity.logger, level="WARNING"):
            windll.shell32.SetCurrentProcessExplicitAppUserModelID.return_value = -2147467259
            app_identity.set_windows_app_identity()

    @unittest.skipUnless(sys.platform == "win32", "Requires Windows shell APIs")
    def test_native_windows_identity_and_window_icons(self):
        from semi_auto_probe.app import ProbeApp

        original_init = tk.Tk.__init__
        # Exercise SAP's initialization order and icon loading without connecting
        # to instruments, cameras, or the application's background services.
        def create_window_only(window):
            get_id = ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID
            get_id.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]
            get_id.restype = ctypes.c_long
            app_id = ctypes.c_wchar_p()
            self.assertEqual(get_id(ctypes.byref(app_id)), 0)
            try:
                self.assertEqual(app_id.value, app_identity.WINDOWS_APP_ID)
            finally:
                free = ctypes.windll.ole32.CoTaskMemFree
                free.argtypes = [ctypes.c_void_p]
                free(app_id)
            original_init(window)
            window.withdraw()
            window._set_window_icon()
            window.deiconify()
            window.update()
            self.assertIsNotNone(window.window_icon)
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [ctypes.c_void_p]
            user32.GetParent.restype = ctypes.c_void_p
            user32.GetClassLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.GetClassLongPtrW.restype = ctypes.c_size_t
            handle = user32.GetParent(window.winfo_id())
            # iconphoto(default=True) installs Tk's shared window class icons.
            for icon_kind in (-14, -34):  # GCLP_HICON and GCLP_HICONSM
                self.assertTrue(user32.GetClassLongPtrW(handle, icon_kind))
            raise StopIteration

        window = ProbeApp.__new__(ProbeApp)
        try:
            # Check identity at the exact boundary before the native Tk window.
            with mock.patch.object(tk.Tk, "__init__", autospec=True, side_effect=create_window_only):
                with self.assertRaises(StopIteration):
                    ProbeApp.__init__(window)
        finally:
            if "tk" in window.__dict__:
                tk.Tk.destroy(window)


if __name__ == "__main__":
    unittest.main()

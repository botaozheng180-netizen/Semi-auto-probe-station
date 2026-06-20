import unittest
from unittest import mock

from semi_auto_probe.app import ProbeApp


class SimpleVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class ExistingClient:
    def __init__(self, port: str, is_open: bool = True) -> None:
        self.port = port
        self._is_open = is_open
        self.closed = False

    @property
    def is_open(self) -> bool:
        return self._is_open

    def close(self) -> None:
        self.closed = True
        self._is_open = False


class AppSerialConnectionTest(unittest.TestCase):
    def make_app(self, port: str):
        app = ProbeApp.__new__(ProbeApp)
        app.port_var = SimpleVar(port)
        app.status_var = SimpleVar("")
        app.admin_mode_enabled = False
        app.serial_client = None
        app._update_serial_port_style = lambda: None
        return app

    def test_connect_failure_clears_stale_serial_client(self) -> None:
        app = self.make_app("COM7")

        class FailingClient:
            def __init__(self, port: str) -> None:
                self.port = port

            def set_admin_mode_enabled(self, enabled: bool) -> None:
                return None

            def open(self) -> None:
                raise FileNotFoundError("COM7")

        with mock.patch("semi_auto_probe.app.ControllerSerialClient", FailingClient), mock.patch("semi_auto_probe.app.threading.Thread") as thread:
            thread.return_value.start.return_value = None

            self.assertFalse(ProbeApp.connect_serial(app))

        self.assertIsNone(app.serial_client)

    def test_connect_closes_old_client_when_selected_port_changes(self) -> None:
        app = self.make_app("COM8")
        old_client = ExistingClient("COM7")
        app.serial_client = old_client

        class WorkingClient:
            def __init__(self, port: str) -> None:
                self.port = port
                self._is_open = False

            @property
            def is_open(self) -> bool:
                return self._is_open

            def close(self) -> None:
                self._is_open = False

            def set_admin_mode_enabled(self, enabled: bool) -> None:
                return None

            def open(self) -> None:
                self._is_open = True

        with mock.patch("semi_auto_probe.app.ControllerSerialClient", WorkingClient):
            self.assertTrue(ProbeApp.connect_serial(app))

        self.assertTrue(old_client.closed)
        self.assertEqual(app.serial_client.port, "COM8")


if __name__ == "__main__":
    unittest.main()

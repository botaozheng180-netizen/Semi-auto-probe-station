import sys
import types
import unittest
from unittest import mock

from semi_auto_probe.protocol import FRAME_TAIL, RESPONSE_HEAD, Axis, build_clear_position_command, build_read_motion_parameters_command, checksum
from semi_auto_probe.serial_client import ControllerSerialClient, list_serial_ports


class FakeSerial:
    is_open = True

    def __init__(self, payload: bytes) -> None:
        self.payload = bytearray(payload)
        self.written = bytearray()
        self.reset_count = 0

    def read(self, size: int = 1) -> bytes:
        if not self.payload:
            return b""
        chunk = bytes(self.payload[:size])
        del self.payload[:size]
        return chunk

    def reset_input_buffer(self) -> None:
        self.reset_count += 1

    def write(self, data: bytes) -> int:
        self.written.extend(data)
        return len(data)

    def flush(self) -> None:
        return None


def position_response(axis: Axis, position: int) -> bytes:
    data = bytes((0x00, 0x00, 0x00, 0x00)) + position.to_bytes(2, "big")
    first_nine = bytes((RESPONSE_HEAD, 0xCB, axis)) + data
    return first_nine + bytes((checksum(first_nine),)) + FRAME_TAIL


def reached_response(axis: Axis) -> bytes:
    first_nine = bytes((RESPONSE_HEAD, 0xB5, axis)) + bytes(6)
    return first_nine + bytes((checksum(first_nine),)) + FRAME_TAIL


def multi_axis_completed_response() -> bytes:
    first_nine = bytes((RESPONSE_HEAD, 0xBE, 0x00)) + bytes(6)
    return first_nine + bytes((checksum(first_nine),)) + FRAME_TAIL


def motion_parameters_response(axis: Axis, minimum_speed: int, work_speed: int, acceleration: int) -> bytes:
    data = (
        minimum_speed.to_bytes(2, "big")
        + work_speed.to_bytes(2, "big")
        + acceleration.to_bytes(2, "big")
    )
    first_nine = bytes((RESPONSE_HEAD, 0xB4, axis)) + data
    return first_nine + bytes((checksum(first_nine),)) + FRAME_TAIL


class FakePort:
    def __init__(
        self,
        device: str,
        description: str = "",
        manufacturer: str = "",
        hwid: str = "",
    ) -> None:
        self.device = device
        self.description = description
        self.manufacturer = manufacturer
        self.hwid = hwid


class FakeSerialException(Exception):
    pass


class OpenedSerial:
    is_open = True

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True
        self.is_open = False


def patch_comports(ports: list[FakePort]):
    serial_module = types.ModuleType("serial")
    tools_module = types.ModuleType("serial.tools")
    list_ports_module = types.ModuleType("serial.tools.list_ports")
    list_ports_module.comports = lambda: ports
    tools_module.list_ports = list_ports_module
    serial_module.tools = tools_module
    return mock.patch.dict(
        sys.modules,
        {
            "serial": serial_module,
            "serial.tools": tools_module,
            "serial.tools.list_ports": list_ports_module,
        },
    )


def fake_serial_module(serial_factory):
    serial_module = types.ModuleType("serial")
    serial_module.Serial = serial_factory
    serial_module.SerialException = FakeSerialException
    serial_module.EIGHTBITS = 8
    serial_module.PARITY_NONE = "N"
    serial_module.STOPBITS_ONE = 1
    return serial_module


class SerialClientTest(unittest.TestCase):
    def test_list_serial_ports_prefers_usb_serial_adapter_over_bluetooth(self) -> None:
        with patch_comports(
            [
                FakePort("COM3", description="Standard Serial over Bluetooth link", hwid="BTHENUM\\0000"),
                FakePort("COM4", description="Standard Serial over Bluetooth link", hwid="BTHENUM\\0001"),
                FakePort("COM8", description="USB-SERIAL CH340", manufacturer="wch.cn", hwid="USB\\VID_1A86&PID_7523"),
            ]
        ):
            self.assertEqual(list_serial_ports(), ["COM8", "COM3", "COM4"])

    def test_list_serial_ports_sorts_plain_com_ports_numerically(self) -> None:
        with patch_comports(
            [
                FakePort("COM12", description="Communications Port"),
                FakePort("COM2", description="Communications Port"),
                FakePort("LPT1", description="Printer Port"),
            ]
        ):
            self.assertEqual(list_serial_ports(), ["COM2", "COM12"])

    def test_open_retries_ch340_configure_failure_with_warmup_and_rtscts(self) -> None:
        calls = []

        def serial_factory(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise FakeSerialException(
                    "Cannot configure port, something went wrong. Original message: "
                    "PermissionError(13, 'A device attached to the system is not functioning.', None, 31)"
                )
            return OpenedSerial()

        client = ControllerSerialClient("COM8", timeout=1.0)
        with mock.patch.dict(sys.modules, {"serial": fake_serial_module(serial_factory)}), mock.patch("semi_auto_probe.serial_client.time.sleep") as sleep:
            client.open()

        self.assertTrue(client.is_open)
        self.assertEqual([call["baudrate"] for call in calls], [115200, 9600, 115200])
        self.assertEqual([call.get("rtscts") for call in calls], [False, False, True])
        sleep.assert_called_once_with(0.2)

    def test_open_does_not_retry_unrelated_serial_exception(self) -> None:
        calls = []

        def serial_factory(**kwargs):
            calls.append(kwargs)
            raise FakeSerialException("Access is denied")

        client = ControllerSerialClient("COM8", timeout=1.0)
        with mock.patch.dict(sys.modules, {"serial": fake_serial_module(serial_factory)}):
            with self.assertRaises(FakeSerialException):
                client.open()

        self.assertEqual(len(calls), 1)

    def test_position_reader_resynchronizes_after_fragment(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        expected = position_response(Axis.Y, 20)
        client._serial = FakeSerial(bytes.fromhex("0A 7A 0D 0A") + expected)

        self.assertEqual(client._read_position_response(Axis.Y), expected)

    def test_reached_reader_waits_for_axis_b5(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        expected = reached_response(Axis.Z)
        client._serial = FakeSerial(position_response(Axis.X, 10) + expected)

        self.assertEqual(client._read_axis_reached_response(Axis.Z, timeout=0.05), expected)

    def test_multi_axis_reader_waits_for_a5_completion(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        client._serial = FakeSerial(bytes.fromhex("00 FF A5"))

        self.assertEqual(client._read_multi_axis_completed_response(timeout=0.05), b"\xA5")

    def test_multi_axis_reader_ignores_a5_ack_when_axes_are_expected(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        expected = reached_response(Axis.X)
        client._serial = FakeSerial(b"\xA5" + expected)

        completed = client._read_multi_axis_completed_response(timeout=0.05, moving_axes={Axis.X})

        self.assertEqual(completed, expected)

    def test_multi_axis_reader_accepts_b5_for_all_moving_axes(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        expected = reached_response(Axis.X) + reached_response(Axis.Y)
        client._serial = FakeSerial(expected)

        completed = client._read_multi_axis_completed_response(timeout=0.05, moving_axes={Axis.X, Axis.Y})

        self.assertEqual(completed, expected)

    def test_multi_axis_reader_accepts_b5_axis_mask(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        first_nine = bytes((RESPONSE_HEAD, 0xB5, int(Axis.X) | int(Axis.Y))) + bytes(6)
        expected = first_nine + bytes((checksum(first_nine),)) + FRAME_TAIL
        client._serial = FakeSerial(expected)

        completed = client._read_multi_axis_completed_response(timeout=0.05, moving_axes={Axis.X, Axis.Y})

        self.assertEqual(completed, expected)

    def test_multi_axis_reader_accepts_be_completion_frame(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        expected = multi_axis_completed_response()
        client._serial = FakeSerial(expected)

        completed = client._read_multi_axis_completed_response(timeout=0.05, moving_axes={Axis.X, Axis.Y})

        self.assertEqual(completed, expected)

    def test_multi_axis_move_resets_input_writes_and_waits(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        fake = FakeSerial(multi_axis_completed_response())
        client._serial = fake

        command, completed = client.move_multi_axis_relative_and_wait({Axis.X: (False, 10, 100, 0)}, timeout=0.05)

        self.assertEqual(completed, multi_axis_completed_response())
        self.assertEqual(bytes(fake.written), command)
        self.assertEqual(fake.reset_count, 1)

    def test_read_motion_parameters_writes_d5_and_parses_response(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        fake = FakeSerial(position_response(Axis.Y, 20) + motion_parameters_response(Axis.X, 0, 10, 0))
        client._serial = fake

        command, response, parameters = client.read_motion_parameters(Axis.X)

        self.assertEqual(command, build_read_motion_parameters_command(Axis.X))
        self.assertEqual(bytes(fake.written), command)
        self.assertEqual(response, motion_parameters_response(Axis.X, 0, 10, 0))
        self.assertEqual(parameters.axis, Axis.X)
        self.assertEqual(parameters.minimum_speed, 0)
        self.assertEqual(parameters.work_speed, 10)
        self.assertEqual(parameters.acceleration, 0)
        self.assertEqual(fake.reset_count, 1)

    def test_read_xyz_motion_parameters_reads_each_axis(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        fake = FakeSerial(
            motion_parameters_response(Axis.X, 5, 100, 10)
            + motion_parameters_response(Axis.Y, 6, 90, 11)
            + motion_parameters_response(Axis.Z, 7, 80, 12)
        )
        client._serial = fake

        entries = client.read_xyz_motion_parameters()

        self.assertEqual([entry[2].axis for entry in entries], [Axis.X, Axis.Y, Axis.Z])
        self.assertEqual([entry[2].minimum_speed for entry in entries], [5, 6, 7])
        self.assertEqual(bytes(fake.written), b"".join(build_read_motion_parameters_command(axis) for axis in (Axis.X, Axis.Y, Axis.Z)))
        self.assertEqual(fake.reset_count, 3)

    def test_clear_position_is_blocked_without_admin_mode(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        client._serial = FakeSerial(b"")

        with self.assertRaises(PermissionError):
            client.clear_position(Axis.Z)
        with self.assertRaises(PermissionError):
            client.send_raw(build_clear_position_command(Axis.ALL), read_length=0)

    def test_clear_position_is_allowed_with_admin_mode(self) -> None:
        client = ControllerSerialClient("COM_TEST", timeout=0.05)
        fake = FakeSerial(b"")
        client._serial = fake
        client.set_admin_mode_enabled(True)

        command = client.clear_position(Axis.Z)

        self.assertEqual(command, build_clear_position_command(Axis.Z))
        self.assertEqual(bytes(fake.written), command)


if __name__ == "__main__":
    unittest.main()

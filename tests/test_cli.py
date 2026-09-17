import pytest

from andopt import adb, cli


def test_devices_command_lists_devices(monkeypatch, capsys):
    monkeypatch.setattr(
        adb, "list_devices", lambda: [adb.Device("ABC123", "device")]
    )
    assert cli.main(["devices"]) == 0
    assert "ABC123\tdevice" in capsys.readouterr().out


def test_adb_error_returns_exit_code_1(monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise adb.AdbError("연결된 기기가 없습니다.")

    monkeypatch.setattr(adb, "resolve_device", boom)
    assert cli.main(["report"]) == 1
    assert "오류:" in capsys.readouterr().err


def test_clean_is_cancelled_without_confirmation(monkeypatch, capsys):
    monkeypatch.setattr(adb, "resolve_device", lambda s: adb.Device("X", "device"))
    monkeypatch.setattr(cli, "_confirm", lambda *_: False)
    assert cli.main(["clean"]) == 0
    assert "취소" in capsys.readouterr().out


def test_unknown_command_exits():
    with pytest.raises(SystemExit):
        cli.main(["nope"])

from groundstop.cli import main
from groundstop.i18n import set_lang


def test_commands_run(tmp_path, capsys):
    try:
        main(["nights"])
        main(["show", "p1"])
        main(["show", "s1"])
        main(["--lang", "en", "replay", "p1", "--out", str(tmp_path)])
        out = capsys.readouterr().out
        assert "Rehoused by 06:00" in out and "Salidas de esta noche" in out
        assert (tmp_path / "traffic.log").exists() and (tmp_path / "scoreboard.json").exists()
        assert "LOST" in (tmp_path / "traffic.log").read_text()
    finally:
        set_lang("es")

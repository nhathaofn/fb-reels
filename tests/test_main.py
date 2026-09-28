import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main


def test_main_entrypoint():
    with patch("main.DesktopApp") as mock_desktop_app:
        instance = MagicMock()
        mock_desktop_app.return_value = instance

        main.main()

        mock_desktop_app.assert_called_once()
        instance.mainloop.assert_called_once()

import subprocess
import sys


def test_main_module_entrypoint():
    """Vérifie que le module src.main s'exécute sans erreur en tant que script."""
    result = subprocess.run(
        [sys.executable, "-m", "src.main", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()

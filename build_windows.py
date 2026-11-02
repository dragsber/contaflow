from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main():
    if sys.platform != "win32":
        raise SystemExit(
            "ContaFlow Windows si compila solo da Windows; cross-compilazione non supportata."
        )
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", "ContaFlow",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "pyinstaller"),
        str(ROOT / "run_contaflow.py"),
    ], cwd=ROOT)


if __name__ == "__main__":
    main()

"""Require actual installed scanners; never report a source grep as vulnerability scanning."""
import shutil
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if not shutil.which('gitleaks') or not shutil.which('pip-audit'):
    raise SystemExit('BLOCKED: install reviewed gitleaks and pip-audit in the verification environment; scan full history and resolved requirements. No scanner result exists yet.')
subprocess.run(['gitleaks','git','--redact',str(root)],check=True)
subprocess.run(['pip-audit','-r',str(root/'requirements-reference.txt')],check=True)

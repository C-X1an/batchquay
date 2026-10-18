"""Inspect local prerequisites; never auto-install or silently change the host."""
import importlib.metadata
import json
import shutil
import sys

required=['cmake','ninja','g++','git']
missing=[tool for tool in required if shutil.which(tool) is None]
versions={}
for name in ['numpy','torch','transformers','safetensors','tokenizers']:
    try: versions[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: versions[name]='NOT INSTALLED'
print(json.dumps(dict(python=sys.version,tools={k:shutil.which(k) for k in required},packages=versions,
    note='Core fixture/demo require no Python packages. Differential needs NumPy. Reference pins need Python >=3.12 and a network-capable clean venv; this command does not install them.'),indent=2))
if sys.version_info<(3,11) or missing:
    raise SystemExit('Missing core prerequisites: '+','.join(missing))

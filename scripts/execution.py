"""Bounded verification environment; inherited recipe overrides are not evidence."""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path

MAKE_PROGRAMS={'make','make.exe','gmake','gmake.exe','mingw32-make.exe'}
PYTHON_PROGRAMS={'python','python3','python.exe','python3.exe','python3.12','python3.12.exe'}
RECIPE_VARIABLES={'PYTHON','CMAKE','BUILD'}


def valid_assignment(name: str, value: str) -> bool:
    if name=='PYTHON': return value in PYTHON_PROGRAMS
    if name=='CMAKE': return value=='cmake'
    if name=='BUILD': return re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*',value) is not None
    return False


def bound_command(command: list[str]) -> list[str]:
    if Path(command[0].replace('\\','/')).name.lower() not in MAKE_PROGRAMS:
        return list(command)
    present=set()
    for argument in command[1:]:
        if '=' not in argument or argument.startswith('-'):continue
        name,value=argument.split('=',1)
        if name in present or not valid_assignment(name,value):
            raise ValueError('unsupported or repeated verification recipe assignment')
        present.add(name)
    defaults={'PYTHON':Path(sys.executable).name,'CMAKE':'cmake','BUILD':'build'}
    if defaults['PYTHON'] not in PYTHON_PROGRAMS:raise ValueError('unsupported verification interpreter name')
    return [command[0],*(f'{name}={value}' for name,value in defaults.items() if name not in present),*command[1:]]


def environment(base: dict | None = None) -> dict:
    result=dict(os.environ if base is None else base)
    blocked=RECIPE_VARIABLES|{'SHELL','.SHELLFLAGS','MAKE','MAKEFLAGS','GNUMAKEFLAGS','MFLAGS',
        'MAKEFILES','MAKEOVERRIDES','MAKELEVEL','CC','CXX','CPP','CPPFLAGS','CFLAGS','CXXFLAGS',
        'LDFLAGS','BASH_ENV','ENV','CDPATH','PYTHONPATH','PYTHONHOME','PYTHONSTARTUP','PYTHONINSPECT',
        'ASAN_OPTIONS','UBSAN_OPTIONS','LSAN_OPTIONS'}
    for name in list(result):
        if name.upper() in blocked or name.upper().startswith(('CMAKE_','PYTHON')):
            result.pop(name)
    result.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONNOUSERSITE='1',
                  ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    return result

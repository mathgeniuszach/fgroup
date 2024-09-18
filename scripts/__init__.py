from pathlib import Path

import os
import re
import sys
import subprocess
import shutil
import fgroup

VERSION = re.compile(r'^(version\s+=\s+"\d+\.\d+\.\d+)(\.\d+)?(")', re.MULTILINE)

PROJECT_DIR = Path(__file__).parent.parent
PROJECT = PROJECT_DIR / "pyproject.toml"

def delete(*paths: str):
    for path in paths:
        if not os.path.exists(path): continue
        try: os.unlink(path)
        except IsADirectoryError: shutil.rmtree(path)

def clean():
    if os.name == "nt": return
    delete("dist", "__pycache__", ".pytest_cache", "fgroup/__pycache__", "scripts/__pycache__", ".coverage")

def run():
    fgroup.run()
    clean()

def test():
    subprocess.call(["pytest", *sys.argv[1:]])
    clean()

def cover():
    subprocess.call(["coverage", "run", "--source", "fgroup", "-m", "pytest"])
    subprocess.call(["coverage", "report", "-m"])
    clean()

def resetbuild():
    with open(PROJECT, "r") as file:
        data = VERSION.sub(lambda m: f'{m[1]}{m[3]}', file.read())
    with open(PROJECT, "w") as file:
        file.write(data)

def incbuild():
    with open(PROJECT, "r") as file:
        data = VERSION.sub(lambda m: f'{m[1]}.{int(m[2][1:])+1 if m[2] else 1}{m[3]}', file.read())
    with open(PROJECT, "w") as file:
        file.write(data)

def build():
    clean()
    subprocess.call(["poetry", "build"])

def upload():
    with open(Path(__file__).parent / "auth", "r") as file:
        p = file.read()
    subprocess.call(["poetry", "publish", "-u", "__token__", "-p", p])
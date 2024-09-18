from typing import TYPE_CHECKING
if TYPE_CHECKING: # pragma: no cover
    from typing import NoReturn, Generator

import os
import shutil
import glob


PROG = "fgroup"

DEFAULT_GROUP = "unknown"
"The default group used when a node was not given a group."

CLEAR = "\33[2K"
"The clear line escape code used for printing over an existing line."

MAX_TERMINAL_COLUMNS = shutil.get_terminal_size()[0]
"The maximum number of columns the terminal currently supports."

TERMINAL_COLUMNS = MAX_TERMINAL_COLUMNS if MAX_TERMINAL_COLUMNS < 80 else 80
"The number of columns which will be available for printing."

RESERVED_COLUMNS = len("  -o, --override [G:N ...]  ")
"The number of reserved columns for any arguments/options for printing."

DEFAULT_TOP = 10
"The default number of entries to list with --top."

DEFAULT_INDENT = 4
"The default indent width with --indent."


# Cross-platform functions for handling paths and path separators.
if os.path.altsep is None: # pragma: cover-if-win
    # Unix specific methods!
    SEP = os.path.sep
    SEPS = SEP
    DEFAULT_PATH = SEP

    def split_path(path: str) -> 'list[str]':
        return path.split(SEP)
    def strip_path(path: str) -> str:
        return path.strip(SEPS)
    def join_path(spath: str, *paths: str) -> str:
        return os.path.join(spath, *(path.strip(SEPS) for path in paths))
    def abs_path(cwd: str, path: str) -> str:
        if path == "": return ""
        resolved = os.path.join(cwd if cwd == "" else os.path.normpath(cwd), path)
        if resolved == "": return ""
        return SEP + os.path.normpath(resolved).strip(SEPS)
    def list_path(path: str) -> 'list[str]':
        if path == "": return []
        try: return os.listdir(path)
        except (OSError, FileNotFoundError, PermissionError, ValueError): return []

else: # pragma: cover-if-unix
    # Windows specific methods!
    SEP = os.path.sep
    ALT_SEP = os.path.altsep
    SEPS = SEP+ALT_SEP+"?"
    DEFAULT_PATH = "\\\\?\\" + os.path.abspath(SEP)

    def split_path(path: str) -> 'list[str]':
        drive, subpath = os.path.splitdrive(path.replace(ALT_SEP, SEP))
        if drive: return [drive.strip(SEPS), *subpath.strip(SEPS).split(SEP)]
        else: return subpath.strip(SEPS).split(SEP)
    def strip_path(path: str) -> str:
        return path.replace(ALT_SEP, SEP).strip(SEPS)
    def join_path(spath: str, *paths: str) -> str:
        if spath == "": return os.path.join(*(path.strip(SEPS) for path in paths))
        return os.path.join(spath, *(path.strip(SEPS) for path in paths))
    def abs_path(cwd: str, path: str) -> str:
        if path == "": return ""
        if cwd == "":
            resolved = os.path.abspath(path) if path[0] in "\\/" else path
        else:
            resolved = os.path.normpath(os.path.join(cwd, path))
        drive, subpath = os.path.splitdrive("\\\\?\\" + resolved.strip(SEPS))
        # Drives need to end in a path separator to do anything with them
        return drive + subpath if subpath else drive + SEP if drive[-1] != SEP else drive
    def list_path(path: str) -> 'list[str]':
        if path == "": return []
        try: return os.listdir(path)
        except (OSError, FileNotFoundError, PermissionError, ValueError): return []


def glob_root(root: str, rglob: str, dirs_only: bool = False) -> 'Generator[str]':
    "Cross-platform glob relative to the root path. Root may be empty."
    # No glob means no files
    if rglob == "": return

    # Cleanup the glob
    nglob = strip_path(rglob)

    # If no root path is given, do some checks to find out where true root is.
    nroot = root
    if root == "":
        # A glob with only slashes on empty root is filesystem root.
        # Filesystem root always exists.
        if nglob == "": yield DEFAULT_PATH; return

        if os.name == "nt": # pragma: cover-if-unix
            # On windows systems at blank root, take the drive path from the glob and use as root
            drive, subpath = os.path.splitdrive("\\\\?\\" + nglob)
            nroot = drive + SEP
            nglob = strip_path(subpath)
            # If rglob is empty - return back root directory as this was part of a glob originally
            if nglob == "": yield root; return
        else: # pragma: cover-if-win
            # On non-windows systems, blank root is filesystem root.
            nroot = DEFAULT_PATH

    # After root has been determined, no glob still means no files.
    if nglob == "": return

    # Ensure root path ends in path separator (Mainly for drives on windows).
    if nroot[-1] != SEP: nroot += SEP

    # Glob relative to the true root path
    if dirs_only:
        gen = (path[:-1] for path in glob.iglob(nglob + os.path.sep, root_dir=nroot, recursive=True, include_hidden=True))
    else:
        gen = glob.iglob(nglob, root_dir=nroot, recursive=True, include_hidden=True)

    # Add back drive prefix on windows at empty root
    if os.name == "nt" and root == "": # pragma: cover-if-unix
        yield from (nroot + path for path in gen)
    else:
        yield from gen

def critical_err(msg: str) -> 'NoReturn':
    "Throws a critical TypeError to be printed."
    raise TypeError(f'{PROG}: error: {msg}')

from typing import TYPE_CHECKING
if TYPE_CHECKING: # pragma: no cover
    from typing import Optional, TypeAlias, cast
    StrTree: TypeAlias = 'dict[str, str | StrTree]'

    from .grouper import FileGrouper

import yaml
import os

from .util import critical_err, abs_path
from .grouper import group


def check_file_tree(tree: 'dict', path: str):
    "Type checks the tree, printing an error and exiting if it doesn't match."
    # Loop over items
    for k, v in tree.items():
        # Non-string keys are illegal
        if not isinstance(k, str): critical_err(f"invalid config: found \"{type(k).__name__}\" key in {path}")
        # Empty parts of string keys are also not okay
        if k == "" or not all(k.split(", ")): critical_err(f"invalid config: found empty glob at {path} -> {k}")
        # Values must be dictionaries or strings
        if isinstance(v, str): continue
        # Values that are not strings must be dictionaries, or error
        if not isinstance(v, dict): critical_err(f"invalid config: value is not str or dict for key {path} -> {k}")
        # Recurse into dictionary
        check_file_tree(v, path + " -> " + k)

def group_from(
    config_path: 'Optional[str]',
    root: 'Optional[str]' = None,
    absolute: 'bool' = False,
    distinct: 'bool' = False,
    extra_globs: 'list[tuple[str, str]]' = [],
    overrides: 'dict[str, str]' = {}
) -> 'FileGrouper':
    "Reads the config at config_path and calls group() with collected data."
    # Create override copy for merging
    noverrides = {}

    if not config_path:
        # Throw a little extra error to prevent people from overriding the config if they forget -c.
        if not extra_globs: critical_err("no globs given, provide some with -m or supply a config with -c.")
        files = {}
        if root is None: root = "."
    else:
        try:
            with open(config_path) as file:
                config = yaml.safe_load(file)
        except yaml.parser.ParserError: # pyright: ignore [reportAttributeAccessIssue]
            critical_err("invalid config: config is not a valid yaml file")
        except FileNotFoundError:
            critical_err(f"config file \"{config_path}\" not found")

        # If config is not a dictionary, error.
        if not isinstance(config, dict): critical_err(f"invalid config: must be a dictionary, parsed \"{type(config).__name__}\" instead")

        # Check for weird keys in the dictionary
        keys = set(config.keys())
        for key in ["overrides", "root", "files", "config_relative_root"]:
            keys.discard(key)
        if keys: critical_err(f"invalid config: unknown keys: {', '.join(repr(key) for key in keys)}")

        # Get overrides if they exist and add to list
        ooverrides = config.get("overrides")
        if ooverrides is not None:
            over_msg = "invalid config: overrides must be a dictionary of string: string pairs"
            if not isinstance(ooverrides, dict): critical_err(over_msg)
            for k, v in ooverrides.items():
                if not isinstance(k, str) or not isinstance(v, str): critical_err(over_msg)
                noverrides[k] = v

        # Get root if it exist
        if root is None:
            root = config.get("root", ".")
            if not isinstance(root, str): critical_err("invalid config: root filepath must be a string")

            config_relative_root = config.get("config_relative_root", False)
            if not isinstance(config_relative_root, bool): critical_err("invalid config: config_relative_root must be true or false")
            if config_relative_root:
                # Resolve root relative to config parent if desired
                root = abs_path(os.path.dirname(abs_path(os.getcwd(), config_path)), root)

        # Get files if it exists and type check it
        files = config.get("files")
        if files is None:
            files = {}
        else:
            if not isinstance(files, dict): critical_err("invalid config: files must be a dictionary")
            check_file_tree(files, "files")
            if TYPE_CHECKING: files = cast('StrTree', files)

    # Merge overrides on top of any file overrides
    noverrides.update(overrides)

    # resolve root if it hasn't been resolved yet.
    root = abs_path(os.getcwd(), root)
    if root != "" and not os.path.exists(root): critical_err(f"root filepath \"{root}\" not found")

    # Load extra globs into file tree
    if extra_globs:
        nfiles = {}
        for ex_glob, ex_group in extra_globs:
            nfiles[ex_glob] = ex_group
        for r_glob, r_data in files.items():
            if r_glob not in nfiles: nfiles[r_glob] = r_data
    else:
        nfiles = files

    return group(root, nfiles, absolute, distinct, noverrides)
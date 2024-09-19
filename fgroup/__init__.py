#!/usr/bin/env python3

__all__ = [
    "main", "group", "group_from", "FileGrouper",
    "PROG", "DEFAULT_GROUP", "DEFAULT_TOP", "DEFAULT_INDENT",
    "split_path", "strip_path", "join_path", "abs_path", "list_path",
    "glob_root"
]

from typing import TYPE_CHECKING
if TYPE_CHECKING: # pragma: no cover
    from typing import Optional, TypeAlias, Literal, cast
    StrTree: TypeAlias = 'dict[str, str | StrTree]'

import importlib.util
import traceback
import argparse

import os
import sys
import yaml
import json

from .util import PROG, DEFAULT_GROUP, DEFAULT_TOP, DEFAULT_INDENT
from .util import split_path, strip_path, join_path, abs_path, list_path
from .util import critical_err, glob_root
from .file import group_from
from .grouper import FileGrouper, group
from .formatter import Formatter, wrap_full, wrap

def main(*sys_argv: str) -> int:
    """Main method for fgroup. Handles parsing arguments from sys.argv and exeuting the program.

    Use `group()` or `group_from()` if you want the raw FileGrouper group data for yourself.
    """

    parser = argparse.ArgumentParser(
        prog="fgroup",
        description=wrap_full(
            "A helpful cross-platorm utility for grouping files across many locations.",
            "",
            "Groups paths based on the globs given through the -m option and the \"config\" file (-c) if provided. "
            "Outputs the result to the given \"output\" path. If a file is not matched, it is placed into the "
            "default group (\"unknown\"). For an example config file, see the git repo.",
            "",
            "By default, if a parent directory is grouped, none of it's children can be. To allow "
            "them to be grouped separately, use the -d option."
        ),
        formatter_class=Formatter,
        add_help=False, # Help option is manually added because it doesn't capitalize the message and so tests work
        epilog=wrap_full(
            "Output is given in four different formats. \"text\" is a long header-separated format, "
            "\"json\" and \"yaml\" output as dictionaries with the keys as groups and the values lists "
            "of paths in those groups, and \"folder\" creates a directory at the given output and places "
            "one file per group into it (group.txt)",
            "",
            "If -t is set, output will be in the form of a table with the first column being the weight "
            "(right aligned) and the second column being the path. \"text\" is a simple-text table, "
            "\"json\" and \"yaml\" are 2-list deep tables (with the weight and filepath indexes switched), "
            "and \"folder\" is unsupported.",
            "",
            "If -g is set, only a single list is printed, with \"text\" being one path per line, \"json\" "
            "and \"yaml\" being lists in those formats, and \"folder\" only outputs to one sub-file.",
            "",
            "The weight metric generally represents how much work a given path has taken to glob through, "
            "and it is good for finding paths that are taking too long to process and might need to be "
            "given a manual override in the config. Currently, the number is equal to the number of "
            "times any given path has been globbed on directly or indirectly through recursive globs, plus "
            "the number of times a descendant node has been created.",
            "",
            "The script given by -s will be loaded through an import statement. "
            "Any function with the name \"run_action_(group)\" will be called with "
            "the list for that group. The function \"run_actions()\" will be called "
            "with the full dictionary of all groups. Groups without functions "
            "will be ignored."
        )
    )

    # NOTE: If you make an option/argument name too long, you need to update the "RESERVED_COLUMNS" global
    # NOTE: Changing info might require updating other parts of the help message. Keep this in mind.
    parser.add_argument("output", nargs='?', help=wrap("Path to output to. If blank, stdout is used."))

    parser.add_argument("-h", "--help", action="store_true", help=wrap("Show this help message and exit."))
    parser.add_argument("-a", "--absolute", action="store_true", help=wrap("Output paths as absolute paths instead of paths relative to the root path."))
    parser.add_argument("-d", "--distinct", action="store_true", help=wrap(
        "If set, a parent folder and it's descendants can be given distinct groups. "
        "Consequently, unmatched paths will not be placed in the default group."
    ))
    parser.add_argument("-c", "--config", help=wrap("A config file used to group various files/folders."))
    parser.add_argument("-m", "--manual", metavar="P:G", nargs="*", help=wrap(
        "File globs (P) executed on the root path. Matching paths will be given group (G). "
        "These have higher priority than the globs in the config file."
    ))
    parser.add_argument("-r", "--root", metavar="ROOT", nargs="?", default=False, help=wrap(
        "Changes the root path where files/folders are grouped from. "
        "This setting has higher priority than the root set in the config. "
        "(default: \".\", default with option: \"\")"
    ))
    parser.add_argument("-f", "--format", choices=["text", "json", "yaml", "folder"], metavar="TYPE",
        help=wrap("Change the output format used to print out results.", "Options are \"text\", \"json\", \"yaml\", and \"folder\".")
    )
    parser.add_argument("-t", "--top", metavar='N', nargs="?", type=int, default=False, # Must be False, because using -t without an argument stores None
        help=wrap(
            f"Output top N path weights (all: 0, default: {DEFAULT_TOP}).",
            "Paths that glob more have a higher weight.",
            "See below for more info on this metric.",
            "Not compatible with -g."
        )
    )
    parser.add_argument("-g", "--group", help=wrap("If set, outputs only the paths in the given group.", "Not compatible with -t."))
    parser.add_argument("-i", "--indent", metavar="N", nargs="?", type=int, default=False, # Must be False, because using -t without an argument stores None
        help=wrap(f"For formats \"json\" and \"yaml\", indents and nicely formats output. (default: {DEFAULT_INDENT})")
    )
    parser.add_argument("-o", "--override", metavar="G:N", nargs="*", help=wrap(
        "A list of group overrides, one per argument.",
        "Using group G directly will instead use group N."
    ))
    parser.add_argument("-s", "--script", metavar="SCRIPT", help=wrap(
        "A python script to load and execute with all groups. "
        "Using this argument will prevent output to the given output path."
        "See below for more info. Not compatible with -f, -t, -g, or -i."
    ))
    parser.add_argument("-A", "--args", metavar="ARG", nargs="*", help=wrap(
        "Additional arguments to pass on to the -s script as strings. "
        "Each argument is only given to the script's run_actions() function."
    ))


    # Type checking for pyright
    class Namespace(argparse.Namespace):
        def __init__(self): # pragma: no cover
            self.output: 'Optional[str]'
            self.help: 'bool'
            self.absolute: 'bool'
            self.distinct: 'bool'
            self.config: 'Optional[str]'
            self.manual: 'Optional[list[str]]'
            self.root: 'Optional[Literal[False] | str]'
            self.format: 'Optional[Literal["text", "json", "yaml", "folder"]]'
            self.top: 'Optional[Literal[False] | int]'
            self.group: 'Optional[str]'
            self.indent: 'Optional[Literal[False] | int]'
            self.override: 'Optional[list[str]]'
            self.script: 'Optional[str]'
            self.args: 'Optional[list[str]]'

    file = None
    try:
        args = parser.parse_args(sys_argv)
        if TYPE_CHECKING: args = cast('Namespace', args)

        assert args.output is None or isinstance(args.output, str)
        assert isinstance(args.help, bool)
        assert isinstance(args.absolute, bool)
        assert isinstance(args.distinct, bool)
        assert hasattr(args, "config")
        assert args.config is None or isinstance(args.config, str)
        assert args.manual is None or (isinstance(args.manual, list) and (isinstance(arg, str) for arg in args.manual))
        assert args.root is False or args.root is None or isinstance(args.root, str)
        assert args.format in [None, "text", "json", "yaml", "folder"]
        assert args.top is False or args.top is None or isinstance(args.top, int)
        assert args.group is None or isinstance(args.group, str)
        assert args.indent is False or args.indent is None or isinstance(args.indent, int)
        assert args.override is None or (isinstance(args.override, list) and (isinstance(arg, str) for arg in args.override))
        assert args.script is None or isinstance(args.script, str)
        assert args.args is None or (isinstance(args.args, list) and (isinstance(arg, str) for arg in args.args))

        if args.help:
            parser.print_help()
            return 0

        # Split overrides
        overrides: 'dict[str, str]' = {}
        if args.override is not None:
            if len(args.override) <= 0: critical_err(f"need at least one \"G:N\" argument for override")
            for over in args.override:
                if ":" not in over: critical_err(f"invalid override \"{over}\"")
                loc = over.rindex(":")
                overrides[over[:loc]] = over[loc+1:]

        # Split manuals
        extra_globs: 'list[tuple[str, str]]' = []
        if args.manual is not None:
            if len(args.manual) <= 0: critical_err(f"need at least one \"P:G\" argument for manual")
            for manual in args.manual:
                if ":" not in manual: critical_err(f"invalid manual \"{manual}\"")
                loc = manual.rindex(":")
                extra_globs.append((manual[:loc], manual[loc+1:]))

        # Execute grouper on config
        root: 'Optional[str]' = None if args.root is False else "" if args.root is None else args.root
        grouper: 'FileGrouper' = group_from(args.config, root, args.absolute, args.distinct, extra_globs, overrides)

        # Execute script
        if args.script is not None:
            if args.format or args.top is not False or args.group or args.indent is not False:
                critical_err("-s is not compatible with -f, -t, -g, or -i")
            if not os.path.isfile(args.script):
                critical_err(f"cannot find script \"{args.script}\"")

            try:
                spec = importlib.util.spec_from_file_location("userscript", args.script)
                # This shouldn't ever really happen, but it throws an error regardless so there's nothing to test
                if spec is None: critical_err(f"cannot get spec of \"{args.script}\"") # pragma: nocover
                userscript = importlib.util.module_from_spec(spec)
                sys.modules["userscript"] = userscript
                # This also shouldn't ever really happen, but it also throws an error regardless so there's nothing to test
                if spec.loader is None: critical_err(f"spec loader not found") # pragma: nocover
                spec.loader.exec_module(userscript)

                for group, files in grouper.groups.items():
                    func = "run_action_"+group
                    if hasattr(userscript, func):
                        getattr(userscript, func)(files)

                if hasattr(userscript, "run_actions"):
                    getattr(userscript, "run_actions")(grouper.groups, *(args.args or []))
            except Exception as e:
                traceback.print_exc()
                critical_err(f"failed to run script \"{args.script}\"; see error above")

            return 0

        # Get output format
        def get_format(format: 'Optional[str]', output: 'Optional[str]'):
            if format: return format
            if not output: return "text"
            if os.path.isdir(output): return "folder"
            if output.endswith(".json"): return "json"
            if output.endswith(".yaml"): return "yaml"
            return "text"

        form = get_format(args.format, args.output)

        # Create output file.
        if form == "folder":
            file = None
            if args.output is None: critical_err("output format \"folder\" requires an output path")
        elif args.output is None:
            file = sys.stdout
        else:
            file = open(args.output, "w")

        # Indentation
        indent: 'Optional[int]' = None if args.indent is False else (DEFAULT_INDENT if args.indent is None else args.indent)

        # Output data in some kind of format.
        if args.top is not False:
            # Output top N file weights.
            if args.group is not None: critical_err("options -t and -g are not compatible with each other")
            if file is None: critical_err("option -t does not support output format \"folder\"")

            # Determine N top weight files.
            top: int = DEFAULT_TOP if args.top is None else args.top
            # -0 means all.
            if top <= 0: top = len(grouper.weights)
            common = sorted(grouper.weights.most_common(len(grouper.weights)), key=lambda d: (-d[1], *split_path(d[0])))[:top]

            if form == "text":
                max_len = len(str(common[0][1]))
                for path, count in common:
                    print(f"{count:>{max_len}}  {path}", file=file)
            elif form == "json":
                json.dump(common, file, indent=indent, sort_keys=False)
            elif form == "yaml":
                yaml.safe_dump(common, file, indent=indent, sort_keys=False)
        else:
            if args.group is not None:
                # Output data only for a single group.
                paths = grouper.groups.get(args.group)
                if paths is None: critical_err(f"no paths were given the group \"{args.group}\"")

                if file is None:
                    assert args.output is not None # For pyright. The check is done above with "file is None and args.output is None"
                    if not os.path.exists(args.output): os.mkdir(args.output)
                    with open(join_path(args.output, args.group + ".txt"), "w") as nfile:
                        for path in paths: print(path, file=nfile)
                elif form == "text":
                    for path in paths: print(path, file=file)
                elif form == "json":
                    json.dump(paths, file, indent=indent, sort_keys=False)
                elif form == "yaml":
                    yaml.safe_dump(paths, file, indent=indent, sort_keys=False)
            else:
                # Output data for all groups.
                if file is None:
                    assert args.output is not None # For pyright. The check is done above with "file is None and args.output is None"
                    if not os.path.exists(args.output): os.mkdir(args.output)
                    for group, paths in grouper.groups.items():
                        with open(join_path(args.output, group + ".txt"), "w") as nfile:
                            for path in paths: print(path, file=nfile)
                elif form == "text":
                    for group, paths in sorted(grouper.groups.items(), key=lambda s: s[0]):
                        print(f"{group}", file=file)
                        for path in paths: print(path, file=file)
                        print(file=file)
                elif form == "json":
                    json.dump(grouper.groups, file, indent=indent, sort_keys=True)
                elif form == "yaml":
                    yaml.safe_dump(grouper.groups, file, indent=indent, sort_keys=True)
    except (TypeError, FileNotFoundError, FileExistsError, PermissionError, NotADirectoryError, OSError) as e:
        parser.print_usage(sys.stderr)
        print(str(e), file=sys.stderr)
        return 1
    except SystemExit:
        return 1
    finally:
        if file and file != sys.stdout: file.close()

    return 0

# This function simply calls main(), and all tests test main() directly, so there's nothing really to test here.
def run(): # pragma: nocover
    "Wrapper around main() that uses sys_argv. Called when this script is executed directly."
    quit(main(*sys.argv[1:]))

if __name__ == "__main__": run()

# fgroup
A helpful cross-platorm utility for grouping files across many locations.

fgroup is a tool designed to help keep track of and organize files on your entire system, for doing things like backing up certain files, cleaning up junk files created by various programs, or organizing the files on your desktop based on their extension. Ungrouped files will be automatically sent to the "unknown" group so you always know what you missed. Before getting started, I recommend reading the pitfalls section below.

All functionality is thoroughly tested via pytest. If you do still find any issues or want to request a feature, feel free to do so!

You can install the script and run it via your tool of choice through PyPI (`pip install fgroup`).

# License
The license (MIT) is available in the repo. If you are doing anything sensitive with this program - please always make a backup first.

# Contact
Contact me on [Discord](https://discord.gg/pBFqEcXvW5) and support me on [Ko-Fi](https://ko-fi.com/mathgeniuszach)!

# Pitfalls
- Files that cannot be found regularly or via permission errors will not be placed into a group.
- In fgroup globs, the characters "\*?[]" and the string ", " have special meaning. E.g. multiple globs on one line are separated by a comma followed by exactly one space. If you need to escape any of these characters, put it in a character group by itself: "\[\*\]" or "\[\[\]"
- By default, if a parent directory is placed into a group first, none of it's children files/folders can be placed into one. This is intentional - it wouldn't make sense to say, "backup this entire folder which includes this file", then to say, "also, delete this file.". To get around this, place the subfile into a group _first_, then the parent directory (or the rest of it's children with "*") into a group.
- As an extension of the previous point, "*" will re-match any folders that have not had all of their children placed into a group yet. This rule does not apply if -d is set. For more info, see the second example below.
- The -d flag overrides this behavior to allow paths to be in distinct groups. As a consequence, for performance reasons, ungrouped files will not be placed into the unknown group by default. The result of any operations on the grouped files (say, backing up files and deleting others) may be different depending on the order they are performed in.
- Use -a to output absolute paths when using a custom root. By default, paths are given relative to the root directory.
- On Windows, all paths are made absolute and evaluated relative to `\\?\`, so there's no need to worry about path limits. However, this also means you should not use `\\?\` in any glob or the root path. You can use `UNC\system\drive` with a blank "" root to mean `\\?\UNC\system\drive`.
- YAML files have some strange features that may cause the file to not function how you expect it to (e.g., "*" characters have special meaning), so if a string doesn't do what you expect and gives an error to fgroup, put keys and values in quotes like so: `"Some File, Another File": "backup"`. You MAY NOT, however, do this: `"Some File", "Another File": "backup"`. You can also just use a JSON file instead if you would prefer.

# Examples
You can provide a list of globs directly to fgroup on the command-line to tell it how to group files:
```console
$ ls
script.py  update.py  random.txt  important.txt  letters.txt
$ fgroup -m "*.py:python" "important*:important" "*.txt:text"
important
important.txt

python
script.py
update.py

text
letters.txt
random.txt
```
Or you can provide a yaml/json config with a tree-like structure to fgroup instead:
```yaml
# config.yaml
root: /home/mgz
files:
    Desktop, Downloads: sync
    Music, Videos, Public: sync
    Pictures, Templates: backup

    # Define dotfiles to include in backup or similar
    .config:
        GIMP: backup
        obs-studio: backup
    .local/share: sync
    .ssh: backup

    # Remove other dotfiles because they clutter up space
    "*": delete

    # Note that "*" here will include .local/state and similar,
    # because .local was not fully defined, only .local/share was.
    # It will not match .config/* though, as ".config" is fully defined.
    # Prefer to expand out paths (like .config above) instead because of this.

    # Or just... don't delete files by default.
```
```console
$ fgroup output.json -c config.yaml -i -a
$ cat output.json
{
    "backup": [
        "/home/mgz/.config/GIMP",
        "/home/mgz/.config/obs-studio",
        "/home/mgz/.ssh",
        "/home/mgz/Pictures",
        "/home/mgz/Templates"
    ],
    "delete": [
        "/home/mgz/.cache",
        "/home/mgz/.local/state",
        "/home/mgz/.npm",
        "/home/mgz/.pki",
        ...
    ],
    "sync": [
        "/home/mgz/.local/share",
        "/home/mgz/Desktop",
        "/home/mgz/Downloads",
        "/home/mgz/Music",
        "/home/mgz/Videos"
    ],
    "unknown": [
        "/home/mgz/.config/QDirStat",
        "/home/mgz/.config/VSCodium",
        "/home/mgz/.config/qalculate",
        ...
    ]
}
```
Detailed help is available on the command line with -h or in the documentation text below.

# Automation
Grouped paths can be outputed to stdout, a txt/json/yaml file, or a bunch of text files in a folder.

Choose the format you want and send any outputted files to another utility:
```console
$ fgroup groups -f folder -c config.yaml
$ restic -r backups-repo backup --files-from-verbatim groups/backup.txt
```
Or create a python script to execute with the collected files:
```python
# script.py
def run_action_backup(file_list: list[str]):
    print(f"Group backup has {len(file_list)} files")
def run_actions(groups: dict[str, list[str]]):
    print(f"{len(groups)} groups total")
```
```console
$ fgroup -c config.yaml -s script.py
Group backup has 5 files
4 groups total
```

fgroup can also be used as a normal python library:
```python
import fgroup
grouper = fgroup.group(".", {"*": "here"}, absolute=True)
print(grouper.groups)
```

# Documentation
```
usage: fgroup [-h] [-a] [-d] [-c CONFIG] [-m [P:G ...]] [-r [ROOT]] [-f TYPE]
              [-t [N]] [-g GROUP] [-i [N]] [-o [G:N ...]] [-s SCRIPT]
              [output]

A helpful cross-platorm utility for grouping files across many locations.

Groups paths based on the globs given through the -m option and the "config"
file (-c) if provided. Outputs the result to the given "output" path. If a file
is not matched, it is placed into the default group ("unknown"). For an example
config file, see the git repo.

By default, if a parent directory is grouped, none of it's children can be. To
allow them to be grouped separately, use the -d option.

positional arguments:
  output                    Path to output to. If blank, stdout is used.

options:
  -h, --help                Show this help message and exit.
  -a, --absolute            Output paths as absolute paths instead of paths
                            relative to the root path.
  -d, --distinct            If set, a parent folder and it's descendants can be
                            given distinct groups. Consequently, unmatched paths
                            will not be placed in the default group.
  -c, --config CONFIG       A config file used to group various files/folders.
  -m, --manual [P:G ...]    File globs (P) executed on the root path. Matching
                            paths will be given group (G). These have higher
                            priority than the globs in the config file.
  -r, --root [ROOT]         Changes the root path where files/folders are
                            grouped from. This setting has higher priority than
                            the root set in the config. (default: ".", default
                            with option: "")
  -f, --format TYPE         Change the output format used to print out results.
                            Options are "text", "json", "yaml", and "folder".
  -t, --top [N]             Output top N path weights (all: 0, default: 10).
                            Paths that glob more have a higher weight.
                            See below for more info on this metric.
                            Not compatible with -g.
  -g, --group GROUP         If set, outputs only the paths in the given group.
                            Not compatible with -t.
  -i, --indent [N]          For formats "json" and "yaml", indents and nicely
                            formats output. (default: 4)
  -o, --override [G:N ...]  A list of group overrides, one per argument.
                            Using group G directly will instead use group N.
  -s, --script SCRIPT       A python script to load and execute with all groups.
                            Using this argument will prevent output to the given
                            output path.See below for more info. Not compatible
                            with -f, -t, -g, or -i.

Output is given in four different formats. "text" is a long header-separated
format, "json" and "yaml" output as dictionaries with the keys as groups and the
values lists of paths in those groups, and "folder" creates a directory at the
given output and places one file per group into it (group.txt)

If -t is set, output will be in the form of a table with the first column being
the weight (right aligned) and the second column being the path. "text" is a
simple-text table, "json" and "yaml" are 2-list deep tables (with the weight and
filepath indexes switched), and "folder" is unsupported.

If -g is set, only a single list is printed, with "text" being one path per
line, "json" and "yaml" being lists in those formats, and "folder" only outputs
to one sub-file.

The weight metric generally represents how much work a given path has taken to
glob through, and it is good for finding paths that are taking too long to
process and might need to be given a manual override in the config. Currently,
the number is equal to the number of times any given path has been globbed on
directly or indirectly through recursive globs, plus the number of times a
descendant node has been created.

The script given by -s will be loaded through an import statement. Any function
with the name "run_action_(group)" will be called with the list for that group.
The function "run_actions()" will be called with the full dictionary of all
groups. Groups without functions will be ignored.
```
from typing import TYPE_CHECKING
if TYPE_CHECKING: # pragma: no cover
    from typing import Optional, TypeAlias
    StrTree: TypeAlias = 'dict[str, str | StrTree]'

from collections import Counter

import os

from .util import DEFAULT_GROUP, split_path
from .filetree import FileTreeNode


class DistinctFileTreeNode(FileTreeNode):
    "A version of file tree nodes that does not get visited"
    def __init__(self, *args, grouper: 'FileGrouper', **kwargs):
        self.grouper: 'FileGrouper' = grouper
        super().__init__(*args, **kwargs)

    def get_child(self, name: str, group: 'Optional[str]' = None, quasi: 'Optional[bool]' = None) -> 'FileTreeNode':
        "Gets the given child node, creating it if it doesn't exist."
        # Also, quasi state on to subnodes if not given.
        if name in self.children:
            return self.children[name]
        else:
            return DistinctFileTreeNode(self, name, group, self.quasi if quasi is None else quasi, grouper=self.grouper)

    def visit(self, group: 'Optional[str]' = None):
        "Visits this node by setting its own group only."
        self.observe()
        self.collapse()

        if self.group is not None: return
        self.group = group or DEFAULT_GROUP
        self.grouper.add_to_group(self.group, self.path)

class FileGrouper(object):
    "Groups files from a root directory with the given config."
    def __init__(
        self,
        root: str,
        config: 'StrTree',
        absolute: bool = False,
        distinct: bool = False,
        overrides: 'dict[str, str]' = {}
    ):
        self.tree = DistinctFileTreeNode(None, root, grouper=self) if distinct else FileTreeNode(None, root)
        "The main file tree where marked files are stored"
        self.absolute = absolute
        "If True, paths are outputted as absolute paths instead of relative to the root."
        self.groups: 'dict[str, list[str]]' = {}
        "Lists of paths, each distinguished by their group."
        self.weights: 'Counter[str]' = Counter()
        "The access count of every file path in the tree."
        self.overrides: 'dict[str, str]' = overrides
        "Group overrides, which replace one froup with another when found."
        self.overrides[DEFAULT_GROUP] = DEFAULT_GROUP

        # Load the config into a tree
        self.load(self.tree, config)
        # Catch stragglers if not in distinct mode
        if not distinct:
            self.tree.visit()
            # Organize the tree into group lists.
            self.walk(self.tree)
        # Organize groups.
        for group in self.groups.values(): group.sort(key=lambda p: split_path(p))

    def add_to_group(self, group: str, path: str):
        "Adds the given path to the given group, creating the group if it doesn't exist."
        # If path is not absolute, make it relative
        if self.tree.path and not self.absolute: path = os.path.relpath(path, self.tree.path)

        # Add path to group
        if group in self.groups:
            self.groups[group].append(path)
        else:
            self.groups[group] = [path]

    def load(self, parent: FileTreeNode, config: 'StrTree'):
        "Uses the current config and parent folder to mark files recursively."
        # Loop over all entries in config
        for glob_key, data in config.items():
            if isinstance(data, str):
                # If path data is a string, then it's a group. Mark nodes with group
                for child in parent.glob_children(glob_key):
                    # Also apply override if available.
                    child.visit(self.overrides.get(data, data))
            else:
                # Otherwise, recurse into data as a new config
                # Only match directories though - they're the only things that can have subpaths.
                for child in parent.glob_children(glob_key, dirs_only=True):
                    self.load(child, data)
                    # Visit folder nodes matched by glob so "*" on same level doesn't re-visit them.
                    child.visit(DEFAULT_GROUP)

    def walk(self, node: FileTreeNode):
        "Walks through the file tree and collects nodes into group lists."
        # Store access count.
        path: str = os.path.relpath(node.path, self.tree.path) if self.tree.path and not self.absolute else node.path
        self.weights[path] = node.weight

        if node.group is None:
            # If node has no group, then it's a folder and one of it's descendents does.
            for child in node.children.values():
                self.walk(child)
        else:
            # Otherwise, add child's path to group
            self.add_to_group(node.group, node.path)

def group(
    root: str,
    files: 'StrTree',
    absolute: bool = False,
    distinct: bool = False,
    overrides: 'dict[str, str]' = {}
) -> FileGrouper:
    "Shorthand for instantiating a FileGrouper instance. Groups files with the given data."
    return FileGrouper(root, files, absolute, distinct, overrides)
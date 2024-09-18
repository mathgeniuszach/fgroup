from typing import TYPE_CHECKING
if TYPE_CHECKING: # pragma: no cover
    from typing import Optional, Generator

import os

from .util import DEFAULT_GROUP, abs_path, split_path, list_path, glob_root


class FileTreeNode(object):
    "A node in the FileTree class."
    def __init__(self, parent: 'Optional[FileTreeNode]', name: str, group: 'Optional[str]' = None, quasi: bool = False):
        self.parent: 'Optional[FileTreeNode]' = parent
        "The parent node of this node."
        self.name = name
        "The base name of the node."
        # abs_path(name if not parent or parent.path == "" else join_path(parent.path, name))
        self.path: str = abs_path(parent.path, name) if parent else abs_path(os.getcwd(), name)
        "The full absolute path of the node including the root."
        self.group: 'Optional[str]' = group
        "The group of the node as given by the config."
        self.visited: bool = group is not None
        "A node is visited if it or all of its children have been found and given a group."
        self.expanded: bool = group is not None
        "A node is expanded if it or all of its children have been found."
        self.collapsed: bool = True
        "A node is collapsed if it and none of its children have been expanded."
        self.quasi: bool = quasi
        "A quasi node is an unvisited node inserted only for caching purposes."
        self.prune_guard: int = 0
        "If >0, this node will not be able to be pruned, regardless of other factors."
        self.children: 'dict[str, FileTreeNode]' = {}
        "For folder nodes, each subfolder/file in the folder that has been marked."
        self.weight: int = 0
        "A metric which represents how much work a node has done. Useful for finding paths to manually override."

        # Add node to parent
        if parent: parent.children[name] = self

        for parent in self.ancestors():
            self.weight += 1

    def __repr__(self): # pragma: no cover
        return f'FileTreeNode(path={self.path!r})'

    def prune(self):
        "Deletes this node and all unvisited parent nodes without children."
        if self.prune_guard > 0 or self.children or self.visited or self.parent is None: return

        # Record weight into parent to remember how much work was done on this node.
        self.parent.weight += self.weight
        if self.name in self.parent.children:
            del self.parent.children[self.name]
            self.parent.prune()

    def locate(self, path: 'list[str]') -> 'Optional[FileTreeNode]':
        "Locates the given decendant with the given path, creating it if it doesn't exist."
        # Use parts to acquire the cursor node
        cursor: FileTreeNode = self
        for part in path:
            cursor = cursor.get_child(part)
            # If a node is already visited, skip this path
            if cursor.visited: return None

        # If path is not visited, return it
        return cursor

    def get_child(self, name: str, group: 'Optional[str]' = None, quasi: 'Optional[bool]' = None) -> 'FileTreeNode':
        "Gets the given child node, creating it if it doesn't exist."
        # Also, quasi state on to subnodes if not given.
        return self.children[name] if name in self.children else FileTreeNode(self, name, group, self.quasi if quasi is None else quasi)

    def glob_nodes(self, rglob: str, dirs_only: bool = False) -> 'Generator[FileTreeNode]':
        "Globs up child nodes with glob_root(), creating them if they don't exist. "
        for path in glob_root(self.path, rglob, dirs_only):
            node = self.locate(split_path(path))
            if node is not None: yield node

    def glob_children(self, rglob: str, dirs_only: bool = False) -> 'Generator[FileTreeNode]':
        "Gets all child nodes that match the glob, creating them if they don't exist."
        self.weight += 1
        # TODO: Conditional sub-globbing.

        # Keep track of how long
        for glob_part in rglob.split(", "):
            parts: 'list[str]' = [i for i in split_path(glob_part) if i != "."]
            # If no parts are available, we stripped out all the ".". Therefore, yield self.
            if not parts:
                yield self
                return

            # Make .. function in globs by moving up directories
            if ".." in parts:
                pi = parts.index("..")

                # Handle pre-".." part if it exists
                # NOTE: list() call is necessary here - we want to resolve ALL nodes before potentially going back on them and doing weird things to them.
                sub_nodes = [self] if pi == 0 else list(self.glob_children(os.path.sep.join(parts[:pi])))

                # Count number of successive ".."
                n = 1
                pi += 1
                while pi < len(parts) and parts[pi] == "..":
                    pi += 1
                    n += 1

                # Collect all unique parent elements
                parents = set(node.ancestor(n) for node in sub_nodes)
                # Sort parent elements by path, so parents come before children
                parents = sorted(parents, key=lambda p: split_path(p.path))

                for parent in parents: parent.prune_guard += 1
                for node in sub_nodes: node.prune()
                for parent in parents: parent.prune_guard -= 1

                # Handle leftover
                leftover = os.path.sep.join(parts[pi:])
                if leftover:
                    for pnode in parents: yield from pnode.glob_children(leftover, dirs_only)
                else:
                    yield from parents

                # Don't perform default functionality if ".." exists.
                return

            # Split into recursive and non-recursive paths.
            if "**" in parts:
                # Recursive paths are slow, so it's a good idea to work through them in memory to cache them.
                # Split glob into parts to find pre-recursive part
                pi = parts.index("**")

                # Handle pre-recursive part if it exists
                sub_nodes = [self] if pi == 0 else self.glob_nodes(os.path.sep.join(parts[:pi]))

                leftover = os.path.sep.join(parts[pi+1:])
                if leftover:
                    # Any leftover part of the glob must be used on matched children.
                    for node in sub_nodes:
                        node.expand()
                        # Iterate over all descendants, globbing them too.
                        # For each descendant, perform the leftover glob normally
                        for descendant in node.descendants():
                            yield from descendant.glob_children(leftover, dirs_only)
                else:
                    # Without a leftover part of the glob, we can simply use the paths directly.
                    for node in sub_nodes:
                        node.expand()
                        # Make sure to exclude leaf nodes if undesired.
                        yield from node.descendants(dirs_only)

                # Don't perform non-recursive functionality if recursive glob exists.
                return

            # Non-recursive paths are fast enough to just glob as is
            yield from self.glob_nodes(glob_part, dirs_only)


    def visit(self, group: 'Optional[str]' = None):
        "Visits this node, filling in its own group or its descendants' groups."
        # If this node has already been visited, no need to visit it again
        if self.visited: return

        # In order to visit the node without a bunch of random paths in the way, remove quasi nodes.
        self.observe()
        self.collapse()

        group = group or self.group or DEFAULT_GROUP

        # Nodes without children do not need to recurse.
        if len(self.children) <= 0:
            self.visited = True
            self.group = group
            return

        # Visit all children in folder, including those not listed
        items = list_path(self.path)
        if items:
            for name in items: self.get_child(name, group).visit(group)
        else:
            for child in self.children.values(): child.visit(group)

        # Mark node as visited
        self.visited = True
        self.expanded = True
        self.collapsed = True
        self.group = None

    def observe(self):
        "Observes a quasi-node, making it and all it's parents not quasi."
        # No need to observe a non-quasi-node.
        if not self.quasi: return

        # Make self no longer quasi
        self.quasi = False
        # Make parents no longer quasi
        for parent in self.ancestors():
            if not parent.quasi: break
            parent.quasi = False

    def collapse(self):
        "Removes all quasi-node descendants recursively."
        # No need to collapse on nodes which have been visited or collapsed.
        if self.collapsed or self.visited: return

        # Loop over all children and collapse or delete quasi nodes.
        for name, child in list(self.children.items()):
            if child.quasi:
                # Record the child's weight to remember how much work was done on this node.
                self.weight += child.weight
                del self.children[name]
            elif not child.collapsed:
                child.collapse()

        # Mark as collapsed.
        self.expanded = False
        self.collapsed = True

    def descendants(self, exclude_leaves: bool = False) -> 'Generator[FileTreeNode]':
        "Yields all unvisited descendant nodes (including self). Expand first for best results."
        if self.visited: return

        # Yield self first, because parents take priority over children when marking
        if not exclude_leaves or self.children: yield self
        for child in self.children.values():
            if not child.visited: yield from child.descendants(exclude_leaves)

    def ancestors(self) -> 'Generator[FileTreeNode]':
        "Yields all ancestor nodes."
        cursor = self.parent
        while cursor:
            yield cursor
            cursor = cursor.parent

    def ancestor(self, n: int) -> 'FileTreeNode':
        "Gets the nth ancestor if it exists, or the closest ancestor if not."
        if n == 1: return self.parent or self

        cursor = self
        for _ in range(n):
            cursor = cursor.parent or cursor
            if cursor is self: return self

        return cursor

    def expand(self):
        "Adds all undiscovered descendants as quasi nodes."
        # No need to re-expand or expand visited nodes.
        if self.expanded or self.visited: return

        # Loop over children and expand them too.
        isdir: bool = os.path.isdir(self.path)
        if isdir:
            for name in list_path(self.path):
                self.get_child(name, quasi=True).expand()

        # Mark as expanded
        self.expanded = True

        # Mark self and all parents as not collapsed
        if isdir and self.collapsed:
            self.collapsed = False
            for parent in self.ancestors():
                parent.collapsed = False

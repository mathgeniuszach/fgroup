#!/usr/bin/env python3
from typing import TYPE_CHECKING
if TYPE_CHECKING: # pragma: nocover
    from typing import TypeVar, Generator
    from pytest import CaptureFixture
    T = TypeVar("T")

from tempfile import TemporaryDirectory

import contextlib
import os
import sys

import json
import yaml
import fgroup


# Helper funcs to quickly create a temporary file tree
def _make_tree(path: str, tree: 'dict | list | str'):
    if isinstance(tree, list):
        # Lists are folders with only files in them
        if path and not os.path.exists(path): os.mkdir(path)
        for name in tree:
            if not name or not isinstance(name, str): continue
            _make_tree(os.path.join(path, name), "")
    elif isinstance(tree, dict):
        # Dictionaries are folders with files and folders in them
        if path and not os.path.exists(path): os.mkdir(path)
        for name, data in tree.items():
            if not isinstance(name, str): continue
            _make_tree(os.path.join(path, name), data)
    else:
        # Anything else is a file
        open(path, "w").close()

@contextlib.contextmanager
def file_tree(tree: 'dict | list | str'):
    with TemporaryDirectory() as tmpdir:
        try:
            owd = os.getcwd()
            os.chdir(tmpdir)
            _make_tree("", tree)
            yield fgroup.abs_path(os.getcwd(), tmpdir)
        finally:
            os.chdir(owd)

@contextlib.contextmanager
def file_config(data: dict):
    with TemporaryDirectory() as tmpdir:
        path = fgroup.abs_path(os.getcwd(), os.path.join(tmpdir, "config.yaml"))
        with open(path, "w") as file:
            yaml.safe_dump(data, file, sort_keys=False)
        yield path

ALT_SEP = os.path.altsep or os.path.sep
SEP = os.path.sep

# Helper func to transform path separators in output data
if os.name == "nt": # pragma: cover-if-unix
    # pyright seems to have a lot of random issues with this function for no good reason
    def ntify(data: 'T') -> 'T': # pyright: ignore [reportRedeclaration]
        if isinstance(data, str):
            return data.replace(ALT_SEP, SEP)
        elif isinstance(data, list):
            return [ntify(item) for item in data] # pyright: ignore [reportReturnType]
        elif isinstance(data, dict):
            return {k: ntify(v) for k, v in data.items()} # pyright: ignore [reportReturnType]
        else:
            return data
else: # pragma: cover-if-win
    def ntify(data: 'T') -> 'T':
        return data

# Helper func to flatten array
def flatten(data: 'list') -> 'Generator':
    for item in data:
        if isinstance(item, list): yield from flatten(item)
        else: yield item

def assert_json_equal(path: str, data: 'str | dict | list'):
    with open(path) as file:
        assert json.load(file) == data
def assert_file_equal(path: str, data: str):
    with open(path) as file:
        assert file.read() == data



# Tests the file tree helper
def test_file_tree_helper():
    with file_tree({
        "folder": {
            "subfolder": {
                "subfile": 0,
                "": ["subfiles", "subfiles 2"]
            },
            "sublist": ["a", "b"],
            "inside file": 0,
        },
        "file": 0,
        "": ["", "file2", "file 3"]
    }):
        assert os.path.isdir ("folder")
        assert os.path.isdir ("folder/subfolder")
        assert os.path.isfile("folder/subfolder/subfile")
        assert os.path.isfile("folder/subfolder/subfiles")
        assert os.path.isfile("folder/subfolder/subfiles 2")
        assert os.path.isdir ("folder/sublist")
        assert os.path.isfile("folder/sublist/a")
        assert os.path.isfile("folder/sublist/b")
        assert os.path.isfile("folder/inside file")
        assert os.path.isfile("file")
        assert os.path.isfile("file2")
        assert os.path.isfile("file 3")

# Test help message
def test_help_message():
    assert fgroup.main("-h") == 0

# Test invalid arguments
def test_invalid_args():
    with file_tree({}):
        with open("nonyamlfile", "w") as file: file.write("[")
        with open("blankfile", "w") as file: pass

        assert fgroup.main("blankfile") == 1 # no globs means... the user probably forgot -c
        assert fgroup.main("-c") == 1
        assert fgroup.main("-c", "nonexistantfile") == 1
        assert fgroup.main("-c", "nonyamlfile") == 1
        assert fgroup.main("-m") == 1
        assert fgroup.main("-m", "*") == 1
        assert fgroup.main("-r", "nonexistantdir") == 1
        assert fgroup.main("-f") == 1
        assert fgroup.main("-f", "notafiletype") == 1
        assert fgroup.main("-f", "folder") == 1
        assert fgroup.main("-t", "NaN") == 1
        assert fgroup.main("-g") == 1
        assert fgroup.main("-g", "notagroup") == 1
        assert fgroup.main("-i", "NaN") == 1
        assert fgroup.main("-o") == 1
        assert fgroup.main("-o", "*") == 1
        assert fgroup.main("-m", ".:a", "-s") == 1
        assert fgroup.main("-m", ".:a", "-s", "notafile") == 1
        assert fgroup.main("-m", ".:a", "-s", "blankfile", "-f") == 1
        assert fgroup.main("-m", ".:a", "-s", "blankfile", "-t") == 1
        assert fgroup.main("-m", ".:a", "-s", "blankfile", "-g") == 1
        assert fgroup.main("-m", ".:a", "-s", "blankfile", "-i") == 1

# Test manual globs (-m)
def test_regular_glob():
    with file_tree(["a.py", "b.py", "b.txt", "a.txt"]):
        fgroup.main("out.json", "-m", "*.py:python", "*.txt:text")
        assert_json_equal("out.json", {"python": ["a.py", "b.py"], "text": ["a.txt", "b.txt"]})

def test_default_unknown():
    with file_tree(["a.py", "b.py", "b.txt", "a.txt"]):
        fgroup.main("out.json", "-m", "a.*:afiles")
        assert_json_equal("out.json", {"afiles": ["a.py", "a.txt"], fgroup.DEFAULT_GROUP: ["b.py", "b.txt"]})

def test_existing_glob():
    with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
        fgroup.main("out.json", "-m", "*.txt:text", "a*:other", "*.py:third")
        assert_json_equal("out.json", {"text": ["a.txt", "b.txt", "c.txt"], "other": ["a.py"], "third": ["b.py", "c.py"]})

def test_multiple_globs():
    with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
        fgroup.main("out.json", "-m", "b*, c*:nota")
        assert_json_equal("out.json", {"nota": ["b.py", "b.txt", "c.py", "c.txt"], fgroup.DEFAULT_GROUP: ["a.py", "a.txt"]})

def test_recursive_glob():
    with file_tree({
        "": ["d.txt", "d.py"],
        "1": {"": ["b.py", "c.py", "c.txt"],
            "2": ["a.txt", "b.txt", "a.py"]
        }
    }):
        fgroup.main("out.json", "-m", "**/*.py:python", "**/*.txt:text")

        assert_json_equal("out.json", ntify({
            "python": ["1/2/a.py", "1/b.py", "1/c.py", "d.py"],
            "text": ["1/2/a.txt", "1/2/b.txt", "1/c.txt", "d.txt"]
        }))

def test_parent_glob():
    with file_tree({
        "": ["d.txt", "d.py"],
        "1": {"": ["b.py", "c.py", "c.txt"],
            "2": ["a.txt", "b.txt", "a.py"]
        }
    }):
        fgroup.main("out.json", "-m", "1/2/../*.py:python", "1/../*.txt:text")

        assert_json_equal("out.json", ntify({
            "python": ["1/b.py", "1/c.py"],
            "text": ["d.txt"],
            fgroup.DEFAULT_GROUP: ["1/2", "1/c.txt", "d.py"]
        }))

def test_ancestor_glob():
    with file_tree({
        "1": {"2": {"3": ["a.txt", "b.txt", "a.py"]}, "": ["c.txt", "b.py"]},
        "4": {"5": ["c.py", "d.py", "d.txt"], "6": ["e.txt", "e.py"], "7": ["f.txt", "g.txt"], "": ["h.txt", "f.py"]},
        "": ["i.txt", "g.py"]
    }):
        fgroup.main("out.json", "-m", "1/2/3/../../*.txt:text", "4/*/*.py/..:python", "4/*/*.txt/../..:extra")

        assert_json_equal("out.json", ntify({
            "text": ["1/c.txt"],
            "python": ["4/5", "4/6"],
            "extra": ["4/7", "4/f.py", "4/h.txt"],
            fgroup.DEFAULT_GROUP: ["1/2", "1/b.py", "g.py", "i.txt"]
        }))

def test_recursive_parent_glob():
    with file_tree({
        "1": {"2": {"3": ["match.txt", "other.txt"], "": ["other.txt"]}, "": ["other.txt"]},
        "4": {"5": ["match.txt"], "": ["other.txt"]},
        "6": ["match.txt"],
        # NOTE: Parent elements should have priority over children.
        "7": {"8": ["match.txt"], "": ["match.txt", "other.txt"]},
        "10": {"9": ["match.txt"], "": ["match.txt", "other.txt"]},
        "": ["other.txt"]
    }):
        fgroup.main("out.json", "-m", "**/match.txt/..:matching")

        assert_json_equal("out.json", ntify({
            "matching": ["1/2/3", "10", "4/5", "6", "7", ],
            fgroup.DEFAULT_GROUP: ["1/2/other.txt", "1/other.txt", "4/other.txt", "other.txt"]
        }))

def test_funhouse_glob():
    funhouse = {"1": {"x": ["a.py"], "y": ["a.txt"]}, "2": {"x": ["b.py"], "y": ["b.txt"]}, "3": {"x": ["c.py"], "y": ["c.txt"]}, "": ["d.txt", "d.py"]}
    with file_tree({"a": funhouse, "b": funhouse, "c": funhouse, "d": funhouse, "e": funhouse}):
        fgroup.main("out.json", "-m", "*/./*/*/./*.py/..:x", "**/./*.py/.././.././**/*.txt/.././.././y/.:y")

        assert_json_equal("out.json", ntify({
            "x": list(flatten([[f"{l}/{i}/x" for i in "123"] for l in "abcde"])),
            "y": list(flatten([[f"{l}/{i}/y" for i in "123"] for l in "abcde"])),
            fgroup.DEFAULT_GROUP: list(flatten([[f"{l}/d.{e}" for e in ("py", "txt")] for l in "abcde"])),
        }))

def test_stdout(capfd: 'CaptureFixture'):
    with file_tree({}):
        fgroup.main("-m", ".:a")
        out, _ = capfd.readouterr()
        assert out == "a\n.\n\n"

# Test abs_path function
def test_abs_path_func():
    cwd = "\\\\?\\"+os.getcwd().lstrip("\\/?") if os.name == "nt" else os.getcwd()

    assert fgroup.abs_path(cwd, "") == ""
    assert fgroup.abs_path("", "") == ""
    assert fgroup.abs_path(cwd, ".") == cwd
    assert fgroup.abs_path(cwd, "path") == os.path.join(cwd, "path")

    if os.name == "nt": # pragma: cover-if-unix
        assert fgroup.abs_path(cwd, "/") == "\\\\?\\" + os.path.abspath("/")
        assert fgroup.abs_path(cwd, "//X:") == "\\\\?\\X:\\"
        assert fgroup.abs_path(cwd, "X:") == "\\\\?\\X:\\"
        assert fgroup.abs_path(cwd, "//") == "\\\\?\\"
        assert fgroup.abs_path(cwd, "//?/") == "\\\\?\\"
        assert fgroup.abs_path("", "/") == "\\\\?\\" + os.path.abspath("/")
        assert fgroup.abs_path("", "//") == "\\\\?\\"
        assert fgroup.abs_path("", "/Users") == "\\\\?\\" + os.path.abspath("/") + "Users"

    else: # pragma: cover-if-win
        assert fgroup.abs_path(cwd, "/") == "/"
        assert fgroup.abs_path(cwd, "//") == "/"
        assert fgroup.abs_path("", "/") == "/"
        assert fgroup.abs_path("", "/home") == "/home"

# Test list_path function
def test_list_path_func():
    with file_tree({"a": ["b.txt", "c.py"], "": ["d.txt", "e.py"]}):
        assert fgroup.list_path("") == []
        assert fgroup.list_path("d.txt") == []
        assert fgroup.list_path("nonexistant") == []

        assert sorted(fgroup.list_path(".")) == ["a", "d.txt", "e.py"]
        assert sorted(fgroup.list_path("a")) == ["b.txt", "c.py"]

# Test absolute paths (-a)
def test_absolute_paths():
    with file_tree({
        "a": ["b.py"],
        "c.py": 0
    }):
        cwd = os.getcwd()
        fgroup.main("out.json", "-a", "-m", "*.py:python", "a/*.py:python")
        assert_json_equal("out.json", {"python": [fgroup.abs_path(cwd, "a/b.py"), fgroup.abs_path(cwd, "c.py")]})

# Test distinct grouping (-d)
def test_distinct_groups():
    with file_tree({"a1": {"a2": ["a3"], "c1": ["c2"]}, "b1": {"b2": ["b3"], "c3": ["c4"]}}):
        fgroup.main("out.json", "-d", "-m", "**/a*:as", "**/*3:3s")
        assert_json_equal("out.json", ntify({
            "as": ["a1", "a1/a2", "a1/a2/a3"],
            "3s": ["b1/b2/b3", "b1/c3"]
        }))

def test_distinct_and_parent():
    with file_tree({"a": {"b": ["file.txt"], "c": {"d": ["file.txt"], "": ["other.py"]}}, "": ["file.txt"]}):
        fgroup.main("out.json", "-d", "-m", "**/*.txt/..:hastext")
        assert_json_equal("out.json", ntify({
            "hastext": [".", "a/b", "a/c/d"]
        }))

# Test 4 output formats
def test_output_text():
    with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
        fgroup.main("out.txt", "-m", "a*:a", "b*:b")
        assert_file_equal("out.txt", f"a\na.py\na.txt\n\nb\nb.py\nb.txt\n\n{fgroup.DEFAULT_GROUP}\nc.py\nc.txt\n\n")
def test_output_json():
    with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
        fgroup.main("out.json", "-m", "a*:a", "b*:b")
        assert_file_equal("out.json", '{"a": ["a.py", "a.txt"], "b": ["b.py", "b.txt"], "'+fgroup.DEFAULT_GROUP+'": ["c.py", "c.txt"]}')
def test_output_yaml():
    with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
        fgroup.main("out.yaml", "-m", "a*:a", "b*:b")
        assert_file_equal("out.yaml", f"a:\n- a.py\n- a.txt\nb:\n- b.py\n- b.txt\n{fgroup.DEFAULT_GROUP}:\n- c.py\n- c.txt\n")
def test_output_folder():
    with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
        fgroup.main("out", "-f", "folder", "-m", "a*:a", "b*:b")
        assert_file_equal("out/a.txt", "a.py\na.txt\n")
        assert_file_equal("out/b.txt", "b.py\nb.txt\n")
        assert_file_equal(f"out/{fgroup.DEFAULT_GROUP}.txt", "c.py\nc.txt\n")
def test_autodetect_output_folder():
    with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
        os.mkdir("out.json")
        fgroup.main("out.json", "-m", "a*:a", "b*:b")
        assert_file_equal("out.json/a.txt", "a.py\na.txt\n")
        assert_file_equal("out.json/b.txt", "b.py\nb.txt\n")
        assert_file_equal(f"out.json/{fgroup.DEFAULT_GROUP}.txt", "c.py\nc.txt\nout.json\n")

# Test 4 output formats with -g
def test_group_text():
    for g, out in [("a", "a.py\na.txt\n"), ("b", "b.py\nb.txt\n"), (fgroup.DEFAULT_GROUP, "c.py\nc.txt\n")]:
        with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
            fgroup.main("out.txt", "-g", g, "-m", "a*:a", "b*:b")
            assert_file_equal("out.txt", out)
def test_group_json():
    for g, out in [("a", '["a.py", "a.txt"]'), ("b", '["b.py", "b.txt"]'), (fgroup.DEFAULT_GROUP, '["c.py", "c.txt"]')]:
        with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
            fgroup.main("out.json", "-g", g, "-m", "a*:a", "b*:b")
            assert_file_equal("out.json", out)
def test_group_yaml():
    for g, out in [("a", "- a.py\n- a.txt\n"), ("b", "- b.py\n- b.txt\n"), (fgroup.DEFAULT_GROUP, "- c.py\n- c.txt\n")]:
        with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
            fgroup.main("out.yaml", "-g", g, "-m", "a*:a", "b*:b")
            assert_file_equal("out.yaml", out)
def test_group_folder():
    for g, others, out in [
        ("a", ("b", fgroup.DEFAULT_GROUP), "a.py\na.txt\n"),
        ("b", ("a", fgroup.DEFAULT_GROUP), "b.py\nb.txt\n"),
        (fgroup.DEFAULT_GROUP, ("a", "b"), "c.py\nc.txt\n")
    ]:
        with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
            fgroup.main("out", "-f", "folder", "-g", g, "-m", "a*:a", "b*:b")
            assert_file_equal(f"out/{g}.txt", out)
            for other in others: assert not os.path.exists(f"out/{other}.txt")

# Test -t -1, -t 0, -t 2, and -t
def test_top_with_arg():
    results = ntify([
        ["a/b/c",9],["a",8],["a/b/c/1.py",4],["a/b/c/1.txt",4],["a/b/c/2.txt",4],
        ["a/b",3],[".",2],["a/2.py",2],["a/3.py",2],["a/3.txt",2],["4.py",1],["4.txt",1]
    ])
    for args, result in [(("-1",), results), (("0",), results), (("2",), results[:2]), ((), results[:fgroup.DEFAULT_TOP])]:
        with file_tree({"a": {"b": {"c": ["1.txt", "1.py", "2.txt"]}, "": ["3.txt", "2.py", "3.py"]}, "": ["4.txt", "4.py"]}):
            fgroup.main("out.json", "-t", *args, "-m", "a/b/**.py:py", "a/**/*.txt:txt")
            assert_json_equal("out.json", result)

# Test 4 output formats with -t
def test_top_text():
    with file_tree({"a": {"b": {"c": ["1.txt", "1.py", "2.txt", "2.py"]}, "": ["3.txt", "3.py", "4.py"]}, "": ["4.txt", "5.py"]}):
        fgroup.main("out.txt", "-t", "5", "-m", "a/b/*.py:py", "a/**/*.txt:txt", "a/**:rest")
        assert_file_equal("out.txt", ntify("14  a/b/c\n 8  a\n 4  a/b/c/1.py\n 4  a/b/c/1.txt\n 4  a/b/c/2.py\n"))
def test_top_json():
    with file_tree({"a": {"b": {"c": ["1.txt", "1.py", "2.txt", "2.py"]}, "": ["3.txt", "3.py", "4.py"]}, "": ["4.txt", "5.py"]}):
        fgroup.main("out.json", "-t", "5", "-m", "a/b/*.py:py", "a/**/*.txt:txt", "a/**:rest")
        assert_file_equal("out.json", ntify('[["a/b/c", 14], ["a", 8], ["a/b/c/1.py", 4], ["a/b/c/1.txt", 4], ["a/b/c/2.py", 4]]').replace("\\", "\\\\"))
def test_top_yaml():
    with file_tree({"a": {"b": {"c": ["1.txt", "1.py", "2.txt", "2.py"]}, "": ["3.txt", "3.py", "4.py"]}, "": ["4.txt", "5.py"]}):
        fgroup.main("out.yaml", "-t", "5", "-m", "a/b/*.py:py", "a/**/*.txt:txt", "a/**:rest")
        assert_file_equal("out.yaml", ntify("- - a/b/c\n  - 14\n- - a\n  - 8\n- - a/b/c/1.py\n  - 4\n- - a/b/c/1.txt\n  - 4\n- - a/b/c/2.py\n  - 4\n"))
def test_top_folder():
    with file_tree({}):
        assert fgroup.main("out", "-f", "folder", "-t") == 1
        assert not os.path.exists("out")

# Test indentation with -i (-i -1, -i 0, -i 2, and -i)
def test_indent_json():
    for args, indent in [(("-1",), ""), (("0",), ""), (("2",), "  "), ((), " "*fgroup.DEFAULT_INDENT)]:
        jdata = f'{{\n{indent}"a": [\n{indent}{indent}"."\n{indent}]\n}}'
        with file_tree({}):
            fgroup.main("out.json", "-m", ".:a", "-i", *args)
            assert_file_equal("out.json", jdata)
def test_indent_yaml():
    for args, indent in [(("-1",), ""), (("0",), ""), (("2",), "  "), ((), " "*fgroup.DEFAULT_INDENT)]:
        # No difference in yaml with indentation here.
        ydata = "a:\n- .\n"
        with file_tree({}):
            fgroup.main("out.yaml", "-m", ".:a", "-i", *args)
            assert_file_equal("out.yaml", ydata)

# Test indentation with -i and -t
def test_indent_top_json():
    for args, indent in [(("-1",), ""), (("0",), ""), (("2",), "  "), ((), " "*fgroup.DEFAULT_INDENT)]:
        jdata = f'[\n{indent}[\n{indent}{indent}".",\n{indent}{indent}1\n{indent}]\n]'
        with file_tree({}):
            fgroup.main("out.json", "-m", ".:a", "-t", "-i", *args)
            assert_file_equal("out.json", jdata)
def test_indent_top_yaml():
    for args, indent in [(("-1",), ""), (("0",), ""), (("3",), " "), ((), " "*(fgroup.DEFAULT_INDENT-2))]:
        ydata = f"- {indent}- .\n  {indent}- 1\n"
        with file_tree({}):
            fgroup.main("out.yaml", "-m", ".:a", "-t", "-i", *args)
            assert_file_equal("out.yaml", ydata)

# Test indentation with -i and -g
def test_indent_group_json():
    for args, indent in [(("-1",), ""), (("0",), ""), (("2",), "  "), ((), " "*fgroup.DEFAULT_INDENT)]:
        for g, out in [
            ("a", f'[\n{indent}"a.py",\n{indent}"a.txt"\n]'),
            ("b", f'[\n{indent}"b.py",\n{indent}"b.txt"\n]'),
            (fgroup.DEFAULT_GROUP, f'[\n{indent}"c.py",\n{indent}"c.txt"\n]')
        ]:
            with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
                fgroup.main("out.json", "-g", g, "-m", "a*:a", "b*:b", "-i", *args)
                assert_file_equal("out.json", out)
def test_indent_group_yaml():
    for args, indent in [(("-1",), ""), (("0",), ""), (("2",), "  "), ((), " "*fgroup.DEFAULT_INDENT)]:
        # No difference in yaml with indentation here.
        for g, out in [
            ("a", "- a.py\n- a.txt\n"),
            ("b", "- b.py\n- b.txt\n"),
            (fgroup.DEFAULT_GROUP, "- c.py\n- c.txt\n")
        ]:
            with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
                fgroup.main("out.yaml", "-g", g, "-m", "a*:a", "b*:b", "-i", *args)
                assert_file_equal("out.yaml", out)

# Test overrides
def test_overrides():
    with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]):
        fgroup.main("out.json", "-m", "b*:a", "a*:b", "-o", "a:b", "b:a", fgroup.DEFAULT_GROUP+":bad")
        assert_json_equal("out.json", {"a": ["a.py", "a.txt"], "b": ["b.py", "b.txt"], fgroup.DEFAULT_GROUP: ["c.py", "c.txt"]})

# Test root (-r)
def test_root():
    with file_tree({"": ["a.txt", "a.py"], "1": {"": ["b.txt", "b.py"], "2": ["c.txt", "c.py"]}}):
        fgroup.main("out.json", "-r", "1", "-m", "**/*.py:py")
        assert_json_equal("out.json", ntify({"py": ["2/c.py", "b.py"], fgroup.DEFAULT_GROUP: ["2/c.txt", "b.txt"]}))
def test_absolute_root():
    with file_tree(["a.txt", "b.txt", "c.txt", "a.py", "b.py", "c.py"]) as folder:
        fgroup.main("out.json", "-d", "-r", "-m", f"{folder}/b*:b", f"{folder}/a*:a")
        assert_json_equal("out.json", ntify({"a": [f"{folder}/a.py", f"{folder}/a.txt"], "b": [f"{folder}/b.py", f"{folder}/b.txt"]}))
def test_absolute_root_fill_children():
    with file_tree(["a.txt", "b.txt"]) as folder:
        fgroup.main("out.json", "-r", "", "-m", f"{folder}/a.txt:a")
        with open("out.json") as file: data = json.load(file)
        assert len(data[fgroup.DEFAULT_GROUP]) > 0

# Test basic config
def test_config_read():
    with file_tree({}):
        with file_config({}) as config:
            fgroup.main("out.json", "-c", config)
            assert_json_equal("out.json", {fgroup.DEFAULT_GROUP: ["."]})
def test_config_errors():
    bad_data = [[], [3], 3, {3: "number"}, {None: "none"}, {"seven": 7}, {"none2": None}]
    bad_file_data = bad_data + [{"": "nothing"}, {", ", "emptysplit"}, {"s, ", "emptysplit2"}]

    with file_tree({}):
        for conf_data in [
            "", *bad_data,
            *({"overrides": bad} for bad in bad_data),
            *({"root": bad} for bad in bad_data),
            *({"config_relative_root": bad} for bad in bad_data),
            *({"files": bad} for bad in bad_file_data),
            *({"files": {"good": "a", "bad": bad}} for bad in bad_file_data),

            *({k: False} for k in ["overrides", "root", "files"]),
            {"config_relative_root": None}
        ]:
            with file_config(conf_data) as config:
                print(conf_data, file=sys.stderr)
                assert fgroup.main("out.json", "-c", config) == 1
def test_config_basic():
    with file_tree(["a.py", "b.py", "a.txt", "b.txt"]):
        with file_config({"files": {"*.py": "python", "*.txt": "text"}}) as config:
            fgroup.main("out.json", "-c", config)
            assert_json_equal("out.json", {"python": ["a.py", "b.py"], "text": ["a.txt", "b.txt"]})

# Test option priority over config
def test_manual_priority():
    with file_tree(["a.py", "b.py", "c.py", "a.txt", "b.txt", "c.txt"]):
        with file_config({"files": {"b*": "bs", "c*": "config"}}) as config:
            fgroup.main("out.json", "-m", "a*:as", "c*:manual", "-c", config)
            assert_json_equal("out.json", {"as": ["a.py", "a.txt"], "bs": ["b.py", "b.txt"], "manual": ["c.py", "c.txt"]})
def test_override_priority():
    with file_tree(["a.py", "b.py", "c.py", "a.txt", "b.txt", "c.txt"]):
        with file_config({"files": {"a*": "a", "b*": "b", "c*": "c"}, "overrides": {"b": "bs", "c": "config"}}) as config:
            fgroup.main("out.json", "-o", "a:as", "c:manual", "-c", config)
            assert_json_equal("out.json", {"as": ["a.py", "a.txt"], "bs": ["b.py", "b.txt"], "manual": ["c.py", "c.txt"]})

# Test config dir-only matching
def test_config_dir_only_match():
    with file_tree({"1": {"2": ["a.txt", "a.py", "b.txt", "b.py"], "": ["2.txt", "c.txt", "c.py"]}, "": ["1.txt", "d.txt", "d.py"]}):
        with file_config({"files": {"1*": {"2*/a*": "a", "*": "bc", ".": "left"}}}) as config:
            fgroup.main("out.json", "-c", config)
            assert_json_equal("out.json", ntify({
                "a": ["1/2/a.py", "1/2/a.txt"],
                "bc": ["1/2/b.py", "1/2/b.txt", "1/2.txt", "1/c.py", "1/c.txt"],
                fgroup.DEFAULT_GROUP: ["1.txt", "d.py", "d.txt"]
            }))

# Test config relative-to-current root
def test_config_root_current_directory():
    with file_tree({"1": ["a.txt"], "": ["b.txt"]}):
        with open("1/config.yaml", "w") as file:
            json.dump({"root": ".", "files": {"*.txt": "text"}}, file)
        fgroup.main("out.json", "-c", "1/config.yaml")
        assert_json_equal("out.json", {"text": ["b.txt"], fgroup.DEFAULT_GROUP: ["1"]})
# Test config relative-to-config root
def test_config_root_relative_to_config():
    with file_tree({"1": ["a.txt"], "": ["a.txt"]}):
        with open("1/config.yaml", "w") as file:
            json.dump({"root": ".", "config_relative_root": True, "files": {"*.txt": "text"}}, file)
        fgroup.main("out.json", "-c", "1/config.yaml")
        assert_json_equal("out.json", {"text": ["a.txt"], fgroup.DEFAULT_GROUP: ["config.yaml"]})

# Test script (-s)
def test_bad_script():
    for script in ["[", "run_action_a = 7", "run_action_b = None", "def run_action_a(): pass", "def run_action_b(l): raise ValueError"]:
        with file_tree(["a.txt", "a.py", "b.txt", "b.py"]):
            with open("script.py", "w") as file: file.write(script)
            assert fgroup.main("-m", "a*:a", "b*:b", "-s", "script.py") == 1
def test_good_script():
    with file_tree(["a.txt", "a.py", "b.txt", "b.py", "c.txt", "c.py"]):
        with open("script.py", "w") as file: file.write(
            "import os\n"
            "def run_action_a(l):\n for i in l: os.unlink(i)\n"
            "def run_actions(d):\n for i in d['b']: os.rename(i, i+'.rename')"
        )
        fgroup.main("-m", "a*:a", "b*:b", "-s", "script.py")

        for f in ["a.txt", "a.py", "b.txt", "b.py"]:
            assert not os.path.exists(f)
        for f in ["b.txt.rename", "b.py.rename", "c.txt", "c.py"]:
            assert os.path.exists(f)
def test_script_args():
    with file_tree(["a.txt", "a.py", "b.txt", "b.py"]):
        with open("script.py", "w") as file: file.write(
            "import os\ndef run_actions(d, *args):\n for f in args: os.unlink(f)"
        )
        fgroup.main("-m", "*:all", "-s", "script.py", "-A", "a.txt", "a.py")

        assert not os.path.exists("a.txt")
        assert not os.path.exists("a.py")
        assert os.path.exists("b.txt")
        assert os.path.exists("b.py")

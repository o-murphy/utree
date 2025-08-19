import re
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from typing import TypedDict, Literal, Any, Union, List, Optional, cast, Tuple, Sequence

from tree.tree_exc import *
from tree.tree_format import (
    _get_fullname_str,
    _escape_non_printable,
    _get_quotes,
    _colorize,
    _get_suffix,
    perms_to_str
)
from tree.tree_parser import parser


class ErrorContent(TypedDict):
    error: Union[Exception, str]


class TreeNode(TypedDict, total=True):
    type: Literal['link', 'directory', 'file', 'report']


class TreeReport(TreeNode, total=False):
    directories: int
    files: int


class TreePathNode(TreeNode, total=True):
    path: Path


class FileNode(TreePathNode, total=False):
    inode: Union[str, int, None]
    dev: Union[str, int, None]
    mode: Union[int, None]
    prot: Union[str, None]
    user: Union[str, int, None]
    group: Union[str, int, None]
    size: Optional[int]
    time: Optional[datetime]
    contents: List[Union[ErrorContent, TreeNode]]


class DirNode(FileNode, total=False):
    pass


class LinkNode(TreePathNode, total=False):
    contents: List[Union[Any, ErrorContent]]


Tree = Union[TreeNode, List[TreeNode]]


def file_dict(path: Path) -> FileNode:
    return {
        "type": "file",
        "path": path,
    }


def dir_dict(path: Path) -> DirNode:
    return {
        "type": "directory",
        "path": path,
        "contents": []
    }


def errs_dict(path: Path) -> LinkNode:
    return {
        "type": "link",
        "path": path,
        "contents": []
    }


def err_dict(err: Union[Exception, str]) -> ErrorContent:
    return {"error": err}


def check_pattern(name: str, pattern: str, ignore_case=False):
    if not pattern:
        return True
    flags = re.IGNORECASE if ignore_case else 0
    return re.search(pattern, name, flags=flags) is not None


def filter_item(item: TreePathNode, ns: Namespace) -> bool:
    """Check if node should be displayed"""

    name = item['path'].name
    if not ns.a and name not in {'.', '..'} and name.startswith("."):
        return False
    if not ns.P and not ns.I:
        return True

    should_match_pattern = (
            item['type'] == "directory" and ns.matchdirs or item['type'] != "directory"
    )
    if should_match_pattern:

        if ns.I:
            if check_pattern(name, ns.I, ns.ignore_case):
                return False
        if ns.P:
            if not check_pattern(name, ns.P, ns.ignore_case):
                return False
    return True


def filter_tree(tree_list: List[TreePathNode], ns: Namespace) -> Tree:
    """Filter tree on post processing"""
    filtered_list = []
    for item in tree_list:
        if filter_item(item, ns):
            filtered_list.append(item)
    return filtered_list


def sort_tree(tree_list: List[TreeNode], ns: Namespace) -> Tree:
    """
    Sorts a dictionary representing a file tree based on user-defined options.
    """

    if ns.sort and ns.sort not in TreeSortTypeError.possible_values:
        raise TreeSortTypeError

    if ns.U:
        sorted_items = tree_list.copy()

    else:

        # No sorting if '-U' is present or if sorting by a specific key that's not 'name'
        if ns.sort and ns.sort.lower() == "name":
            # The default sorted() behavior is by name, so no custom key is needed here
            sorted_items = sorted(tree_list, key=lambda x: x['path'].name.lower())

        # Sort by version if '-v' is specified
        elif ns.v or (ns.sort and ns.sort.lower() == "version"):
            # A simple version sort can be achieved by splitting and comparing parts
            def version_key(item):
                name = item['path'].name.lower()
                return [int(c) if c.isdigit() else c for c in re.split("([0-9]+)", name)]

            sorted_items = sorted(tree_list, key=version_key)

        # Sort by modification time if '-t' is specified
        elif ns.t or (ns.sort and ns.sort.lower() == "mtime"):
            sorted_items = sorted(tree_list, key=lambda x: x['path'].stat().st_mtime, reverse=True)

        # Sort by status change time if '-c' is specified
        elif ns.c or (ns.sort and ns.sort.lower() == "ctime"):
            sorted_items = sorted(tree_list, key=lambda x: x['path'].stat().st_ctime, reverse=True)

        # Sort by size if '--sort size' is specified
        elif ns.sort and ns.sort.lower() == "size":
            sorted_items = sorted(tree_list, key=lambda x: x['path'].stat().st_size)

        # The default sort is by name if no other option is specified
        else:
            sorted_items = sorted(tree_list, key=lambda x: x['path'].name.lower())

        # Reverse the sort order if '-r' is specified
        if ns.r:
            sorted_items = sorted_items[::-1]

        # Handle the '--dirsfirst' option, but only if '-U' is not present
        if ns.dirsfirst and not ns.U:
            def dirsfirst_key(item):
                type_order = {
                    "directory": 0,
                    "file": 1,
                }
                return type_order.get(item['type'], 2)

            sorted_items = sorted(sorted_items, key=dirsfirst_key)

    return sorted_items


def get_st_size(path: Path, ns: Namespace) -> Optional[int]:
    if ns.s or ns.h or ns.si:
        return path.stat().st_size
    return None


def get_datetime(path: Path, ns: Namespace) -> Optional[datetime]:
    if ns.timefmt or ns.D:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts)
    return None


def get_owner_and_group(path: Path, ns: Namespace) -> Tuple[Union[int, str, None], Union[int, str, None]]:
    owner = None
    group = None
    if ns.u or ns.g:
        try:
            import pwd
            import grp

            st = path.stat()
            if ns.u:
                owner = getattr(pwd, "getpwuid")(st.st_uid).pw_name
            if ns.g:
                group = grp.getgrgid(st.st_gid).gr_name
        except (ImportError, AttributeError):
            st = path.stat()
            if ns.u:
                owner = st.st_uid
            if ns.g:
                group = st.st_gid
    return owner, group


def fill_stat(node: Union[FileNode, LinkNode], ns: Namespace) -> Union[FileNode, LinkNode]:
    if not node['type'] in {"file", "directory"}:
        return node

    path = cast(Path, node['path'])
    try:
        st = path.stat()
        perms = st.st_mode if ns.p else None
        owner, group = get_owner_and_group(path, ns)
        return {
            **node,
            'inode': st.st_ino if ns.inodes else None,
            'dev': st.st_dev if ns.device else None,
            'mode': perms,
            'prot': perms_to_str(perms) if perms else None,
            'user': owner,
            'group': group,
            'size': get_st_size(path, ns),
            'time': get_datetime(path, ns),
        }
    except OSError as err:
        errors = errs_dict(path)
        errors['contents'].append(err_dict(
            TreePermissionError(err)
        ))
        return errors


def fmt_size(node: FileNode, ns: Namespace) -> str:
    st_size = node.get('size', None)
    if not st_size:
        return str(st_size)
    if ns.h:
        for unit in ["B", "K", "M", "G", "T", "P", "E", "Z"]:
            if st_size < 1024:
                size_str = f"{st_size:.1f}{unit}"
                break
            st_size /= 1024
        else:
            size_str = f"{st_size:.1f}Y"
    elif ns.si:
        for unit in ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]:
            if st_size < 1000:
                size_str = f"{st_size:.1f}{unit}"
                break
            st_size /= 1000
        else:
            size_str = f"{st_size:.1f}YB"
    else:
        size_str = str(st_size)
    return size_str


def fmt_time(node: FileNode, ns: Namespace) -> str:
    if ns.timefmt or ns.D:
        ts = node.get('time', None)
        if ts:
            return ts.strftime(ns.timefmt or "%b %d %H:%M")
    return ""


def fmt_name(node: FileNode, ns: Namespace) -> str:
    path = node['path']
    path_name = _get_fullname_str(path, ns)
    path_name = _escape_non_printable(path_name, ns)
    path_name = _get_quotes(path_name, ns)
    suffix = _get_suffix(path, ns)
    name = _colorize(path, path_name + suffix, ns)
    return name


def tree_dir(path: Path, ns: Namespace, level: int = 0) -> Tree:
    """returns Tree for one path dir/file"""

    if path.is_file():
        node = file_dict(path)
        if not filter_item(node, ns):
            return []
        return fill_stat(node, ns)

    dir_node = dir_dict(path)
    if not filter_item(dir_node, ns):
        return []

    dir_node = cast(DirNode, fill_stat(dir_node, ns))

    if ns.L and level >= int(ns.L):
        return dir_node

    try:
        subpaths = sorted(path.iterdir())
    except OSError as err:
        errors = errs_dict(path)
        errors["contents"].append(err_dict(TreePermissionError(err)))
        dir_node["contents"] = [errors]
        return dir_node

    if ns.filelimit and len(subpaths) > int(ns.filelimit):
        err = err_dict(TreeFileLimitError(len(subpaths)))
        dir_node["contents"] = [err]
        return dir_node

    contents: List[TreeNode] = []
    for sub_path in subpaths:
        child = tree_dir(sub_path, ns, level + 1)
        if isinstance(child, list):
            contents.extend(child)
        elif child:
            contents.append(child)

    dir_node["contents"] = sort_tree(contents, ns)
    return dir_node


def count_nodes(node: TreeNode) -> Tuple[int, int]:
    """Return (dirs, files) count for one node (recursively)."""
    if node["type"] == "file":
        return (0, 1)
    elif node["type"] == "directory":
        dirs, files = 1, 0
        for child in node.get("contents", []):
            if "type" in child:  # TreeNode
                d, f = count_nodes(child)
                dirs += d
                files += f
        return dirs, files
    else:
        return 0, 0


def tree(paths: Sequence[Path], ns: Namespace) -> List[TreeNode]:
    nodes: List[TreeNode] = []
    for path in paths:
        node = tree_dir(path, ns)
        if isinstance(node, list):
            nodes.extend(node)
        elif node:
            nodes.append(node)

    if not ns.noreport:
        total_dirs, total_files = 0, 0
        for node in nodes:
            d, f = count_nodes(node)
            total_dirs += d
            total_files += f

        report: TreeReport = {
            "type": "report",
            "directories": total_dirs,
            "files": total_files,
        }
        nodes.append(report)

    return nodes


paths_ = ['..', ]
ns_ = parser.parse_args([*paths_, '-L', '3',
                        '-s', '-D',
                        # "-P", ".*\.txt", "--matchdirs"
                        # "--filelimit", "2",
                        ])
r = tree([Path(p) for p in paths_], ns_)
from pprint import pprint
pprint(r, sort_dicts=False)

import mimetypes
import os
import stat
from argparse import Namespace
from pathlib import Path
from typing import Any

from tree.tree_types import LinkNode
from tree_types import FileNode


CONSOLE_WIDTH = 35

CHARSETS = {
    "utf-8": {"vertical": "│   ", "branch": "├── ", "last": "└── ", "space": "    "},
    "ascii": {"vertical": "|   ", "branch": "|-- ", "last": "`-- ", "space": "    "},
    "utf-8-old": {
        "vertical": "║   ",
        "branch": "╠══ ",
        "last": "╚══ ",
        "space": "    ",
    },
}

# ANSI escape codes for colors and styles
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RED = "\033[31m"
YELLOW = "\033[33m"
BG_BLACK = "\033[40m"
BOLD_BLUE = BOLD + BLUE
BOLD_CYAN = BOLD + CYAN
BOLD_GREEN = BOLD + GREEN
BOLD_RED = BOLD + RED
BOLD_MAGENTA = BOLD + MAGENTA


def perms_to_str(st_mode):
    file_type = "-"
    if stat.S_ISDIR(st_mode):
        file_type = "d"
    elif stat.S_ISLNK(st_mode):
        file_type = "l"
    elif stat.S_ISCHR(st_mode):
        file_type = "c"
    elif stat.S_ISBLK(st_mode):
        file_type = "b"
    elif stat.S_ISFIFO(st_mode):
        file_type = "p"
    elif stat.S_ISSOCK(st_mode):
        file_type = "s"

    perms = ""
    perms += "r" if st_mode & stat.S_IRUSR else "-"
    perms += "w" if st_mode & stat.S_IWUSR else "-"
    perms += "x" if st_mode & stat.S_IXUSR else "-"
    perms += "r" if st_mode & stat.S_IRGRP else "-"
    perms += "w" if st_mode & stat.S_IWGRP else "-"
    perms += "x" if st_mode & stat.S_IXGRP else "-"
    perms += "r" if st_mode & stat.S_IROTH else "-"
    perms += "w" if st_mode & stat.S_IWOTH else "-"
    perms += "x" if st_mode & stat.S_IXOTH else "-"

    # setuid, setgid, sticky
    if st_mode & stat.S_ISUID:
        perms = perms[:2] + ("s" if perms[2] == "x" else "S") + perms[3:]
    if st_mode & stat.S_ISGID:
        perms = perms[:5] + ("s" if perms[5] == "x" else "S") + perms[6:]
    if st_mode & stat.S_ISVTX:
        perms = perms[:8] + ("t" if perms[8] == "x" else "T")

    return file_type + perms


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


def get_fullname_str(path: Path, is_full: bool = False) -> str:
    if is_full:
        return path.as_posix()
    return path.name or "."

def replace_non_printable(path_name: str, ns: Namespace) -> str:
    if ns.q:
        path_name = "".join(c if c.isprintable() else "?" for c in path_name)
    elif not ns.N:
        path_name = "".join(c if c.isprintable() else "" for c in path_name)
    return path_name


def get_quotes(path_name: str) -> str:
    return f'"{path_name}"'


def get_suffix(path: Path) -> str:
    suffix = ""
    try:
        if path.is_dir():
            suffix = "/"
        elif path.is_symlink():
            suffix = "@"
        elif os.access(path, os.X_OK) and not path.is_dir():
            suffix = "*"
        elif path.is_fifo():
            suffix = "|"
        elif path.is_socket():
            suffix = "="
        elif path.is_file() and path.suffix.lower() in {".bat", ".cmd"}:  # Windows-style executables
            suffix = ">"
    except OSError:
        suffix = ""
    return suffix


def colorize(path: Path, path_name: str, ns: Namespace) -> str:
    """
    Applies color to the path name based on the file type.
    """
    # 1. I should be off
    #    -C having higher priority
    if ns.n and not ns.C:
        return path_name

    # 2. If -C set - apply colors.
    if ns.C:
        color = ""
        # Check for directories first, as it's the most common and highest priority type
        if path.is_dir():
            color = BOLD_BLUE
        # Check for symbolic links
        elif path.is_symlink():
            color = BOLD_CYAN
        # Check for executable files
        elif os.access(path, os.X_OK):
            color = BOLD_GREEN
        else:
            # Use mimetypes to guess the file's MIME type
            mime_type, _ = mimetypes.guess_type(path)

            if mime_type:
                # Assign colors based on the general MIME type category
                if mime_type.startswith("image/"):
                    color = MAGENTA
                elif mime_type.startswith("audio/"):
                    color = CYAN
                elif mime_type.startswith("video/"):
                    color = MAGENTA
                elif mime_type.startswith("application/"):
                    # For archives, check for common substrings in the MIME type
                    if any(
                        x in mime_type
                        for x in ["zip", "tar", "gzip", "compressed", "x-bzip2", "x-xz"]
                    ):
                        color = BOLD_RED
                # No color for text or other generic file types

        if color:
            return color + path_name + RESET

    return path_name


def fmt_name(node: FileNode, ns: Namespace) -> str:
    path = node['path']
    name = get_fullname_str(path, ns.f)
    name = replace_non_printable(name, ns)
    if ns.Q:
        name = get_quotes(name)
    if ns.F:
        name += get_suffix(path)
    name = colorize(path, name, ns)
    return name


def fmt_error(content: LinkNode, ns: Namespace) -> str:
    # if coloured
    if ns.C:
        return f"{RED}{str(content.get('error', 'unknown error'))}{RESET}"
    return f"{content}"

from datetime import datetime
from pathlib import Path
from typing import Union, List, Any, Optional, Literal, TypedDict

NodeType = Literal['link', 'directory', 'file', 'report']


class ErrorContent(TypedDict):
    error: Union[Exception, str]


class TreeNode(TypedDict, total=True):
    type: NodeType


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

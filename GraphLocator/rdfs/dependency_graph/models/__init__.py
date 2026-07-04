from typing import Union
from pathlib import Path

try:
    from rdfs.dependency_graph.models.virtual_fs.virtual_path import VirtualPath
except ImportError:
    class VirtualPath:
        pass

PathLike = Union[str, Path, VirtualPath]

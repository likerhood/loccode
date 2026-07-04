"""Multi-language entity helpers for LocAgent.

This package is intentionally small and adapter-like: it turns multilingual
repo structures or checked-out repositories into LocAgent's existing file /
class / function shape without coupling the core graph code to each language.
"""

from muladapter.entities.extractor import CodeEntity
from muladapter.entities.graph_builder import build_multilang_graph
from muladapter.entities.structure_index import StructureIndex, load_structure_index

__all__ = [
    "CodeEntity",
    "StructureIndex",
    "build_multilang_graph",
    "load_structure_index",
]

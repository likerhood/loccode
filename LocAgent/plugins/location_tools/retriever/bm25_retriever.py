import os
import pickle
import Stemmer
import fnmatch
import mimetypes
from typing import Dict, List, Optional

from llama_index.core import SimpleDirectoryReader
from llama_index.core import Document
from llama_index.core.node_parser import SimpleFileNodeParser
from llama_index.core.schema import TextNode
from llama_index.retrievers.bm25 import BM25Retriever
from repo_index.index.epic_split import EpicSplitter

from dependency_graph import RepoEntitySearcher
from dependency_graph.traverse_graph import is_test_file
from dependency_graph.build_graph import (
    NODE_TYPE_DIRECTORY,
    NODE_TYPE_FILE,
    NODE_TYPE_CLASS,
    NODE_TYPE_FUNCTION,
)
from muladapter.search_defaults import SOURCE_EXTENSIONS, is_source_file, normalize_repo_path

import warnings

warnings.simplefilter('ignore', FutureWarning)

NTYPES = [
    NODE_TYPE_DIRECTORY,
    NODE_TYPE_FILE,
    NODE_TYPE_FUNCTION,
    NODE_TYPE_CLASS,
]


def _relative_file_path(raw_path: str, repo_path: str) -> str:
    path = normalize_repo_path(raw_path)
    repo = normalize_repo_path(repo_path)
    if path.startswith(repo.rstrip("/") + "/"):
        path = path[len(repo.rstrip("/")) + 1:]
    return normalize_repo_path(path)


def _should_skip_fallback_file(file_path: str) -> bool:
    normalized = normalize_repo_path(file_path)
    basename = os.path.basename(normalized)
    if basename.endswith((".min.js", ".min.css")):
        return True
    return not is_source_file(normalized)


def _build_text_fallback_nodes(
    docs,
    repo_path: str,
    *,
    chunk_lines: int = 120,
    overlap_lines: int = 20,
    max_nodes: int = 4000,
) -> list[TextNode]:
    """Build simple line-window BM25 nodes when language-aware splitting fails."""
    nodes: list[TextNode] = []
    step = max(1, chunk_lines - overlap_lines)

    for doc in docs:
        metadata = dict(getattr(doc, "metadata", {}) or {})
        raw_file_path = metadata.get("file_path") or getattr(doc, "id_", "") or ""
        file_path = _relative_file_path(str(raw_file_path), repo_path)
        if _should_skip_fallback_file(file_path):
            continue

        text = doc.get_content() if hasattr(doc, "get_content") else getattr(doc, "text", "")
        if not text or not str(text).strip():
            continue

        lines = str(text).splitlines()
        if not lines:
            continue

        for start_index in range(0, len(lines), step):
            end_index = min(len(lines), start_index + chunk_lines)
            chunk = "\n".join(lines[start_index:end_index]).strip()
            if not chunk:
                continue
            start_line = start_index + 1
            end_line = end_index
            node_metadata = {
                **metadata,
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "start_line": start_line,
                "end_line": end_line,
                "span_ids": ["text_fallback"],
            }
            nodes.append(
                TextNode(
                    id_=f"{file_path}:{start_line}-{end_line}",
                    text=chunk,
                    metadata=node_metadata,
                )
            )
            if len(nodes) >= max_nodes:
                return nodes
    return nodes


def build_code_retriever_from_repo(repo_path,
                                   similarity_top_k=10,
                                   min_chunk_size=100,
                                   chunk_size=500,
                                   max_chunk_size=2000,
                                   hard_token_limit=2000,
                                   max_chunks=200,
                                   persist_path=None,
                                   show_progress=False,
                                   ):
    # print(repo_path)
    # Only extract file name and type to not trigger unnecessary embedding jobs
    def file_metadata_func(file_path: str) -> Dict:
        # print(file_path)
        file_path = file_path.replace(repo_path, '')
        if file_path.startswith('/'):
            file_path = file_path[1:]

        test_patterns = [
            '**/test/**',
            '**/tests/**',
            '**/test_*.py',
            '**/*_test.py',
        ]
        category = (
            'test'
            if any(fnmatch.fnmatch(file_path, pattern) for pattern in test_patterns)
            else 'implementation'
        )

        return {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'file_type': mimetypes.guess_type(file_path)[0],
            'category': category,
        }

    reader = SimpleDirectoryReader(
        input_dir=repo_path,
        exclude=[
            '**/test/**',
            '**/tests/**',
            '**/test_*.py',
            '**/*_test.py',
        ],
        file_metadata=file_metadata_func,
        filename_as_id=True,
        required_exts=list(SOURCE_EXTENSIONS),
        recursive=True,
    )
    docs = reader.load_data()

    # splitter = CodeSplitter(
    #     language="python",
    #     chunk_lines=100,  # lines per chunk
    #     chunk_lines_overlap=15,  # lines overlap between chunks
    #     max_chars=3000,  # max chars per chunk
    # )

    splitter = EpicSplitter(
        min_chunk_size=min_chunk_size,
        chunk_size=chunk_size,
        max_chunk_size=max_chunk_size,
        hard_token_limit=hard_token_limit,
        max_chunks=max_chunks,
        repo_path=repo_path,
    )
    prepared_nodes = splitter.get_nodes_from_documents(docs, show_progress=show_progress)
    if not prepared_nodes:
        prepared_nodes = _build_text_fallback_nodes(docs, repo_path)
    if not prepared_nodes:
        raise ValueError(f"No source code nodes could be built for BM25 index at {repo_path}")

    # We can pass in the index, docstore, or list of nodes to create the retriever
    retriever = BM25Retriever.from_defaults(
        nodes=prepared_nodes,
        similarity_top_k=similarity_top_k,
        stemmer=Stemmer.Stemmer("english"),
        language="english",
    )
    if persist_path:
        retriever.persist(persist_path)
    return retriever
    # keyword = 'FORBIDDEN_ALIAS_PATTERN'
    # retrieved_nodes = retriever.retrieve(keyword)


def build_retriever_from_persist_dir(path: str):
    retriever = BM25Retriever.from_persist_dir(path)
    return retriever


def build_module_retriever_from_graph(graph_path: Optional[str] = None,
                                      entity_searcher: Optional[RepoEntitySearcher] = None,
                                      search_scope: str = 'all',
                                      # enum = {'function', 'class', 'file', 'all'}
                                      similarity_top_k: int = 10,

                                      ):
    assert search_scope in NTYPES or search_scope == 'all'
    assert graph_path or isinstance(entity_searcher, RepoEntitySearcher)

    if graph_path:
        G = pickle.load(open(graph_path, "rb"))
        entity_searcher = RepoEntitySearcher(G)
    else:
        G = entity_searcher.G

    selected_nodes = list()
    for nid in G:
        if is_test_file(nid): continue

        ndata = entity_searcher.get_node_data([nid])[0]
        ndata['nid'] = nid  # add `nid` property
        if search_scope == 'all':  # and ndata['type'] in NTYPES[2:]
            selected_nodes.append(ndata)
        elif ndata['type'] == search_scope:
            selected_nodes.append(ndata)

    # initialize node parser
    splitter = SimpleFileNodeParser()
    documents = [Document(text=t['nid']) for t in selected_nodes]
    nodes = splitter.get_nodes_from_documents(documents)

    # We can pass in the index, docstore, or list of nodes to create the retriever
    retriever = BM25Retriever.from_defaults(
        nodes=nodes,
        similarity_top_k=similarity_top_k,
        stemmer=Stemmer.Stemmer("english"),
        language="english",
    )

    return retriever

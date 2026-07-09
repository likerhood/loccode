from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from mmir.retrievers.base import Retriever
from mmir.schema import Document, ScoredDocument


class EmbeddingBackend(Protocol):
    def encode(self, texts: list[str], *, batch_size: int, is_query: bool) -> np.ndarray:
        ...


@dataclass(frozen=True)
class DenseModelConfig:
    model_name: str
    backend: str = "sentence-transformers"
    query_prefix: str = ""
    document_prefix: str = ""
    trust_remote_code: bool = False
    pooling: str = "mean"


DENSE_MODEL_CONFIGS: dict[str, DenseModelConfig] = {
    "e5-mmir": DenseModelConfig(
        model_name="intfloat/e5-base-v2",
        query_prefix="query: ",
        document_prefix="passage: ",
    ),
    "jina-code-v2-mmir": DenseModelConfig(
        model_name="jinaai/jina-embeddings-v2-base-code",
        trust_remote_code=True,
    ),
    "codesage-large-v2-mmir": DenseModelConfig(
        model_name="codesage/codesage-large-v2",
        backend="transformers",
        trust_remote_code=True,
        pooling="cls",
    ),
    "coderankembed-mmir": DenseModelConfig(
        model_name="nomic-ai/CodeRankEmbed",
        trust_remote_code=True,
    ),
}


def available_dense_methods() -> list[str]:
    return sorted(DENSE_MODEL_CONFIGS)


def resolve_dense_config(method: str, model_name: str | None = None) -> DenseModelConfig:
    if method not in DENSE_MODEL_CONFIGS:
        raise ValueError(f"Unknown dense MM-IR method: {method}")
    config = DENSE_MODEL_CONFIGS[method]
    if model_name:
        return DenseModelConfig(
            model_name=model_name,
            backend=config.backend,
            query_prefix=config.query_prefix,
            document_prefix=config.document_prefix,
            trust_remote_code=config.trust_remote_code,
            pooling=config.pooling,
        )
    return config


def _normalize(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _resolve_torch_device(requested: str | None, torch_module: Any) -> str:
    device = (requested or "auto").strip().lower()
    if device in {"", "auto"}:
        return "cuda" if torch_module.cuda.is_available() else "cpu"
    if device.startswith("cuda") and not torch_module.cuda.is_available():
        raise RuntimeError(
            f"DENSE_DEVICE={requested!r} was requested, but torch cannot access CUDA. "
            "Use DENSE_DEVICE=cpu on this machine, or run on a host where `nvidia-smi` and "
            "`python -c \"import torch; print(torch.cuda.is_available())\"` both work."
        )
    return device


def _install_transformers_compat_shims(torch_module: Any | None = None) -> None:
    """Restore tiny APIs removed from newer transformers for older remote models."""
    try:
        import transformers.pytorch_utils as pytorch_utils
        from transformers.configuration_utils import PretrainedConfig
        from transformers.modeling_utils import PreTrainedModel
    except ImportError:
        return

    # Some older trust_remote_code models still read these attributes directly
    # from their config object. Newer transformers no longer guarantees every
    # custom config has the old BERT defaults, so provide class-level fallbacks.
    for attr, value in {
        "is_decoder": False,
        "add_cross_attention": False,
        "chunk_size_feed_forward": 0,
    }.items():
        if not hasattr(PretrainedConfig, attr):
            setattr(PretrainedConfig, attr, value)

    if not hasattr(pytorch_utils, "find_pruneable_heads_and_indices"):
        if torch_module is None:
            try:
                import torch as torch_module  # type: ignore[no-redef]
            except ImportError:
                return

        def find_pruneable_heads_and_indices(
            heads: list[int] | set[int],
            n_heads: int,
            head_size: int,
            already_pruned_heads: set[int],
        ) -> tuple[set[int], Any]:
            heads = set(heads) - already_pruned_heads
            mask = torch_module.ones(n_heads, head_size)
            for head in heads:
                head = head - sum(1 if pruned_head < head else 0 for pruned_head in already_pruned_heads)
                mask[head] = 0
            mask = mask.view(-1).contiguous().eq(1)
            index = torch_module.arange(len(mask))[mask].long()
            return heads, index

        pytorch_utils.find_pruneable_heads_and_indices = find_pruneable_heads_and_indices

    if not hasattr(PreTrainedModel, "_convert_head_mask_to_5d"):

        def _convert_head_mask_to_5d(self: Any, head_mask: Any, num_hidden_layers: int) -> Any:
            if head_mask.dim() == 1:
                head_mask = head_mask.unsqueeze(0).unsqueeze(0).unsqueeze(-1).unsqueeze(-1)
                head_mask = head_mask.expand(num_hidden_layers, -1, -1, -1, -1)
            elif head_mask.dim() == 2:
                head_mask = head_mask.unsqueeze(1).unsqueeze(-1).unsqueeze(-1)
            if head_mask.dim() != 5:
                raise ValueError(f"head_mask.dim != 5, instead {head_mask.dim()}")
            dtype = getattr(self, "dtype", None)
            if dtype is None:
                try:
                    dtype = next(self.parameters()).dtype
                except StopIteration:
                    dtype = head_mask.dtype
            return head_mask.to(dtype=dtype)

        PreTrainedModel._convert_head_mask_to_5d = _convert_head_mask_to_5d

    if not hasattr(PreTrainedModel, "get_head_mask"):

        def get_head_mask(
            self: Any,
            head_mask: Any,
            num_hidden_layers: int,
            is_attention_chunked: bool = False,
        ) -> Any:
            if head_mask is not None:
                converted = self._convert_head_mask_to_5d(head_mask, num_hidden_layers)
                if is_attention_chunked:
                    converted = converted.unsqueeze(-1)
                return converted
            return [None] * num_hidden_layers

        PreTrainedModel.get_head_mask = get_head_mask


class SentenceTransformersBackend:
    _model_cache: dict[tuple[str, bool, str | None], Any] = {}

    def __init__(self, config: DenseModelConfig, *, device: str | None = None):
        try:
            import torch
            _install_transformers_compat_shims(torch)
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Dense MM-IR requires sentence-transformers for this backend. "
                "Install it in the active environment or run BM25-MMIR."
            ) from exc
        target_device = _resolve_torch_device(device, torch)
        key = (config.model_name, config.trust_remote_code, target_device)
        if key not in self._model_cache:
            kwargs: dict[str, Any] = {}
            kwargs["device"] = target_device
            if config.trust_remote_code:
                kwargs["trust_remote_code"] = True
            self._model_cache[key] = SentenceTransformer(config.model_name, **kwargs)
        self.model = self._model_cache[key]
        self.config = config

    def encode(self, texts: list[str], *, batch_size: int, is_query: bool) -> np.ndarray:
        prefix = self.config.query_prefix if is_query else self.config.document_prefix
        prepared = [prefix + text for text in texts]
        return _normalize(
            self.model.encode(
                prepared,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=False,
                show_progress_bar=False,
            )
        )


class TransformersBackend:
    _model_cache: dict[tuple[str, bool, str | None], tuple[Any, Any, Any]] = {}

    def __init__(self, config: DenseModelConfig, *, device: str | None = None):
        try:
            import torch
            _install_transformers_compat_shims(torch)
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Dense MM-IR requires transformers and torch for this backend. "
                "Install them in the active environment or override --dense-model with a sentence-transformers model."
            ) from exc
        key = (config.model_name, config.trust_remote_code, device)
        if key not in self._model_cache:
            tokenizer = AutoTokenizer.from_pretrained(config.model_name, trust_remote_code=config.trust_remote_code)
            model = AutoModel.from_pretrained(config.model_name, trust_remote_code=config.trust_remote_code)
            target_device = _resolve_torch_device(device, torch)
            model.to(target_device)
            model.eval()
            self._model_cache[key] = (tokenizer, model, torch)
        self.tokenizer, self.model, self.torch = self._model_cache[key]
        self.config = config

    def _pool(self, outputs: Any, attention_mask: Any) -> Any:
        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            return outputs.pooler_output
        hidden = outputs.last_hidden_state if hasattr(outputs, "last_hidden_state") else outputs[0]
        if self.config.pooling == "cls":
            return hidden[:, 0]
        mask = attention_mask.unsqueeze(-1).expand(hidden.size()).float()
        summed = (hidden * mask).sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        return summed / counts

    def encode(self, texts: list[str], *, batch_size: int, is_query: bool) -> np.ndarray:
        prefix = self.config.query_prefix if is_query else self.config.document_prefix
        prepared = [prefix + text for text in texts]
        vectors: list[np.ndarray] = []
        device = next(self.model.parameters()).device
        with self.torch.no_grad():
            for start in range(0, len(prepared), batch_size):
                batch = prepared[start : start + batch_size]
                tokens = self.tokenizer(batch, padding=True, truncation=True, max_length=512, return_tensors="pt")
                tokens = {key: value.to(device) for key, value in tokens.items()}
                outputs = self.model(**tokens)
                pooled = self._pool(outputs, tokens["attention_mask"])
                vectors.append(pooled.detach().cpu().numpy())
        if not vectors:
            return np.zeros((0, 0), dtype=np.float32)
        return _normalize(np.vstack(vectors))


class DenseRetriever(Retriever):
    name = "dense-mmir"

    def __init__(
        self,
        *,
        method: str,
        model_name: str | None = None,
        embedder: EmbeddingBackend | None = None,
        batch_size: int = 16,
        device: str | None = None,
        max_document_chars: int = 12000,
    ):
        self.method = method
        self.config = resolve_dense_config(method, model_name)
        self.batch_size = batch_size
        self.max_document_chars = max_document_chars
        self.docs: list[Document] = []
        self.doc_vectors = np.zeros((0, 0), dtype=np.float32)
        if embedder is not None:
            self.embedder = embedder
        elif self.config.backend == "transformers":
            self.embedder = TransformersBackend(self.config, device=device)
        else:
            self.embedder = SentenceTransformersBackend(self.config, device=device)

    def build_index(self, docs: list[Document]) -> None:
        self.docs = docs
        texts = [doc.text[: self.max_document_chars] for doc in docs]
        self.doc_vectors = self.embedder.encode(texts, batch_size=self.batch_size, is_query=False)

    def search(self, query: str, top_k: int) -> list[ScoredDocument]:
        if not query.strip() or not self.docs or self.doc_vectors.size == 0:
            return []
        query_vector = self.embedder.encode([query], batch_size=1, is_query=True)
        scores = self.doc_vectors @ query_vector[0]
        order = np.argsort(-scores)[:top_k]
        return [
            ScoredDocument(document=self.docs[int(idx)], score=float(scores[int(idx)]), rank=rank)
            for rank, idx in enumerate(order, start=1)
            if float(scores[int(idx)]) > 0
        ]

import os

import config
from llama_index.core.base.llms.types import LLMMetadata, MessageRole
from google.oauth2 import service_account
from llama_index.core.llms.llm import LLM
from llama_index.llms.anthropic import Anthropic
from llama_index.llms.openai import OpenAI
from llama_index.llms.vertex import Vertex

from .utils import VertexAnthropicWithCredentials


class Config:
    def __init__(self, file_path=None, provider=None):
        self.file_path = file_path
        if self.file_path and os.path.isfile(self.file_path):
            self.file_config = config.Config(self.file_path)
        else:
            self.file_config = dict()
        self.fallback_config = dict()
        self.fallback_config["OPENAI_API_BASE_URL"] = ""
        self.provider = provider

    def __getitem__(self, index):
        # Values in key.cfg has priority over env variables
        if self.file_config.get(index):
            return self.file_config.get(index)
        if index in os.environ:
            return os.environ[index]
        if index in self.fallback_config:
            return self.fallback_config[index]
        raise KeyError(
            f"Cannot find {index} in either cfg file '{self.file_path}' or env variables"
        )


class OpenAICompatible(OpenAI):
    """OpenAI wrapper for local OpenAI-compatible models not known to llama-index."""

    @property
    def metadata(self) -> LLMMetadata:
        context_window = int(
            os.environ.get("ORCALOCA_OPENAI_CONTEXT_WINDOW")
            or os.environ.get("OPENAI_CONTEXT_WINDOW")
            or "131072"
        )
        return LLMMetadata(
            context_window=context_window,
            num_output=self.max_tokens or -1,
            is_chat_model=True,
            is_function_calling_model=False,
            model_name=self.model,
            system_role=MessageRole.SYSTEM,
        )


def _config_value(orcar_config: Config | None, key: str, default: str = "") -> str:
    if orcar_config is None:
        return os.environ.get(key, default)
    try:
        return orcar_config[key]
    except KeyError:
        return os.environ.get(key, default)


def _is_openai_compatible_model(model: str) -> bool:
    return (
        model.startswith("gpt")
        or model.startswith("openai/")
        or model.startswith("qwen")
    )


def _served_openai_model_name(model: str) -> str:
    if model.startswith("openai/"):
        return model.split("/", 1)[1]
    return model


def get_llm(**kwargs) -> LLM:
    # key.cfg is in the parent directory of this file
    orcar_config: Config = kwargs.get("orcar_config", None)
    model = kwargs.get("model", None)
    if not model:
        raise ValueError("Missing model name for OrcaLoca LLM initialization.")
    if model.startswith("claude"):
        # first check if the provider has been set
        if orcar_config and orcar_config.provider == "vertexanthropic":
            print(f"Using AnthropicVertex model: {model}")
            service_account_path = os.path.expanduser(
                orcar_config["VERTEX_SERVICE_ACCOUNT_PATH"]
            )
            if not os.path.exists(service_account_path):
                raise FileNotFoundError(
                    f"Google Cloud Service Account file not found: {service_account_path}"
                )
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_path,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                kwargs["credentials"] = credentials
                kwargs["project_id"] = credentials.project_id
                kwargs["region"] = orcar_config["VERTEX_REGION"]
                LLM_func = VertexAnthropicWithCredentials
            except Exception as e:
                raise Exception(f"gen_config: Failed to get vertexanthropic LLM") from e
        else:
            kwargs["api_key"] = _config_value(orcar_config, "ANTHROPIC_API_KEY")
            LLM_func = Anthropic
    elif _is_openai_compatible_model(model):
        kwargs["model"] = _served_openai_model_name(model)
        kwargs["api_key"] = _config_value(orcar_config, "OPENAI_API_KEY", "dummy")
        api_base = (
            _config_value(orcar_config, "OPENAI_API_BASE_URL")
            or _config_value(orcar_config, "OPENAI_API_BASE")
            or _config_value(orcar_config, "OPENAI_BASE_URL")
        )
        if api_base:
            kwargs["api_base"] = api_base
        LLM_func = OpenAI if model.startswith("gpt") else OpenAICompatible
    elif model.startswith("gemini"):
        # Load Google Cloud credentials
        service_account_path = orcar_config["VERTEX_SERVICE_ACCOUNT_PATH"]

        if not os.path.exists(service_account_path):
            raise FileNotFoundError(
                f"Google Cloud Service Account file not found: {service_account_path}"
            )

        credentials = service_account.Credentials.from_service_account_file(
            service_account_path
        )

        kwargs["project"] = credentials.project_id
        kwargs["credentials"] = credentials
        LLM_func = Vertex
    else:
        raise ValueError(
            f"Unsupported model '{model}'. Expected claude*, gpt*, gemini*, "
            "openai/*, or qwen*."
        )

    # delete orcar_config from kwargs
    if "orcar_config" in kwargs:
        del kwargs["orcar_config"]

    try:
        llm: LLM = LLM_func(**kwargs)
        _ = llm.complete("Say 'Hi'")
        return llm
    except Exception as e:
        raise Exception(f"Failed to initialize LLM: {e}")

import os
import time
from abc import ABC, abstractmethod
from typing import Any, List

from litellm import completion, get_model_info


def litellm_model_for_request(model: str) -> str:
    """Return the model name LiteLLM should see for OpenAI-compatible endpoints."""
    backend_model = (
        os.environ.get("COSIL_BACKEND_MODEL")
        or os.environ.get("COSIL_COMPLETION_MODEL")
        or os.environ.get("LITELLM_MODEL")
        or model
    ).strip()
    if "/" not in backend_model:
        return f"openai/{backend_model}"
    return backend_model


def litellm_endpoint_kwargs() -> dict[str, str]:
    kwargs = {}
    api_base = (
        os.environ.get("OPENAI_API_BASE")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("LITELLM_API_BASE")
    )
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LITELLM_API_KEY")
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    return kwargs


def _fail_fast_enabled() -> bool:
    return os.environ.get("LLM_FAIL_FAST", "1").strip().lower() not in {"0", "false", "no", "off"}


def _fail_fast_patterns() -> list[str]:
    raw = os.environ.get(
        "LLM_FAIL_FAST_PATTERNS",
        "insufficient_quota|quota exceeded|quota_exceeded|insufficient balance|no credit|credit exhausted|"
        "balance not enough|out of quota|余额不足|额度不足|额度已用完|欠费|无可用额度",
    )
    return [item.strip().lower() for item in raw.split("|") if item.strip()]


def assert_valid_llm_text(content: str, context: str) -> None:
    if not _fail_fast_enabled():
        return
    text = (content or "").strip()
    if not text:
        raise RuntimeError(f"{context}: empty LLM response; stop to avoid writing empty localization results.")
    lowered = text.lower()
    for pattern in _fail_fast_patterns():
        if pattern in lowered:
            preview = text[:500].replace("\n", "\\n")
            raise RuntimeError(f"{context}: LLM response looks like an API quota/balance failure: {preview}")


def _empty_response_retries() -> int:
    raw = os.environ.get("LLM_EMPTY_RESPONSE_RETRIES", "2")
    try:
        return max(0, int(raw))
    except ValueError:
        return 2


def _empty_response_retry_sleep() -> float:
    raw = os.environ.get("LLM_EMPTY_RESPONSE_RETRY_SLEEP", "5")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 5.0


def _message_has_tool_call(message: dict) -> bool:
    return bool(message.get("tool_calls") or message.get("function_call"))


def assert_valid_llm_message(message: dict, context: str) -> None:
    if not _fail_fast_enabled():
        return
    if _message_has_tool_call(message):
        return
    assert_valid_llm_text(message.get("content") or "", context)


class DecoderBase(ABC):
    def __init__(
        self,
        name: str,
        logger,
        batch_size: int = 1,
        temperature: float = 0.8,
        max_new_tokens: int | None = None,
        **kwargs,
    ) -> None:
        self.name = name
        self.logger = logger
        self.batch_size = batch_size
        self.temperature = temperature
        try:
            model_info = get_model_info(name)
        except Exception:
            model_info = {}
        self.max_context_tokens = model_info.get("max_input_tokens") or model_info.get("max_tokens") or 100000
        self.max_new_tokens = max_new_tokens
        if self.max_new_tokens is None:
            self.max_new_tokens = model_info.get("max_output_tokens") or model_info.get("max_tokens") or 4096

    @abstractmethod
    def codegen(
            self, message: str | list, num_samples: int = 1, prompt_cache: bool = False, **kwargs
    ) -> List[dict]:
        pass

    @abstractmethod
    def is_direct_completion(self) -> bool:
        pass

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name


class LiteLLMChatDecoder(DecoderBase):
    def __init__(
        self,
        name: str,
        logger,
        litellm_kwargs: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(name, logger, **kwargs)
        self.litellm_kwargs = litellm_kwargs or {}

    def _messages(self, message: str | list) -> list[dict]:
        if isinstance(message, list):
            return message
        return [{"role": "user", "content": message}]

    def _serialize_message(self, message) -> dict:
        if isinstance(message, dict):
            return {k: v for k, v in message.items() if v is not None}
        if hasattr(message, "model_dump"):
            return message.model_dump(exclude_none=True)
        return message.to_dict()

    def _get_usage_value(self, usage, key: str) -> int:
        if usage is None:
            return 0
        if isinstance(usage, dict):
            return usage.get(key, 0) or 0
        return getattr(usage, key, 0) or 0

    def codegen(
            self,
            message: str | list,
            num_samples: int = 1,
            prompt_cache: bool = False,
            tools: list | None = None,
            tool_choice: str | dict | None = None,
            return_message: bool = False,
            allow_empty_response: bool = False,
            **kwargs,
    ) -> List[dict]:
        if self.temperature == 0:
            assert num_samples == 1

        batch_size = min(self.batch_size, num_samples)
        config = {
            "model": litellm_model_for_request(self.name),
            "messages": self._messages(message),
            "temperature": self.temperature,
            "n": batch_size,
            **litellm_endpoint_kwargs(),
            **self.litellm_kwargs,
            **kwargs,
        }
        if self.max_new_tokens is not None:
            config["max_tokens"] = self.max_new_tokens
        if tools is not None:
            config["tools"] = tools
        if tool_choice is not None:
            config["tool_choice"] = tool_choice

        retries = _empty_response_retries()
        retry_sleep = _empty_response_retry_sleep()
        last_empty_error: RuntimeError | None = None
        for attempt in range(retries + 1):
            ret = completion(**config)
            choices = ret["choices"] if isinstance(ret, dict) else ret.choices
            messages = []
            for choice in choices:
                choice_message = choice["message"] if isinstance(choice, dict) else choice.message
                messages.append(self._serialize_message(choice_message))

            usage = ret.get("usage", {}) if isinstance(ret, dict) else getattr(ret, "usage", {})
            completion_tokens = self._get_usage_value(usage, "completion_tokens")
            prompt_tokens = self._get_usage_value(usage, "prompt_tokens")
            responses = [msg.get("content") or "" for msg in messages]
            try:
                if not messages and not allow_empty_response:
                    raise RuntimeError(
                        f"CoSIL LiteLLM request model={config['model']}: empty LLM response; "
                        "stop to avoid writing empty localization results."
                    )
                for msg in messages:
                    if allow_empty_response and not str(msg.get("content") or "").strip():
                        continue
                    assert_valid_llm_message(msg, f"CoSIL LiteLLM request model={config['model']}")
                break
            except RuntimeError as exc:
                if "empty LLM response" not in str(exc) or attempt >= retries:
                    raise
                last_empty_error = exc
                if self.logger is not None:
                    self.logger.warning(
                        "Empty LLM response from %s; retrying %s/%s after %.1fs",
                        config["model"],
                        attempt + 1,
                        retries,
                        retry_sleep,
                    )
                if retry_sleep:
                    time.sleep(retry_sleep)
        else:
            if last_empty_error is not None:
                raise last_empty_error

        traj = {
            "response": responses[0] if responses else "",
            "usage": {
                "completion_tokens": completion_tokens,
                "prompt_tokens": prompt_tokens,
            },
        }
        if return_message:
            traj["message"] = messages[0] if messages else {"role": "assistant", "content": ""}
        trajs = [traj]

        for idx, response in enumerate(responses[1:], start=1):
            traj = {
                "response": response,
                "usage": {
                    "completion_tokens": 0,
                    "prompt_tokens": 0,
                },
            }
            if return_message:
                traj["message"] = messages[idx] if idx < len(messages) else {"role": "assistant", "content": response}
            trajs.append(traj)
        return trajs

    def is_direct_completion(self) -> bool:
        return False


def make_model(
    model: str,
    logger,
    batch_size: int = 1,
    max_tokens: int | None = None,
    temperature: float = 0.0,
    litellm_kwargs: dict[str, Any] | None = None,
):
    return LiteLLMChatDecoder(
        name=model,
        logger=logger,
        batch_size=batch_size,
        max_new_tokens=max_tokens,
        temperature=temperature,
        litellm_kwargs=litellm_kwargs,
    )

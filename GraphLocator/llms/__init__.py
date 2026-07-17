import time
import os
import litellm


def _litellm_model_for_request(model_name: str) -> str:
    backend_model = (
        os.environ.get("GRAPHLOCATOR_BACKEND_MODEL")
        or os.environ.get("GRAPHLOCATOR_COMPLETION_MODEL")
        or os.environ.get("LITELLM_MODEL")
        or model_name
    ).strip()
    if "/" not in backend_model:
        return f"openai/{backend_model}"
    return backend_model


def _litellm_endpoint_kwargs() -> dict:
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


def _empty_response_retries() -> int:
    try:
        return max(0, int(os.environ.get("LLM_EMPTY_RESPONSE_RETRIES", "2")))
    except ValueError:
        return 2


def _empty_response_retry_sleep() -> float:
    try:
        return max(0.0, float(os.environ.get("LLM_EMPTY_RESPONSE_RETRY_SLEEP", "5")))
    except ValueError:
        return 5.0


def _connection_error_retries() -> int:
    try:
        return max(0, int(os.environ.get("LLM_CONNECTION_ERROR_RETRIES", "8")))
    except ValueError:
        return 8


def _connection_error_retry_sleeps() -> list[float]:
    raw = os.environ.get("LLM_CONNECTION_ERROR_RETRY_SLEEPS", "30,50,60,100")
    sleeps: list[float] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            sleeps.append(max(0.0, float(item)))
        except ValueError:
            return []
    return sleeps


def _connection_error_retry_sleep() -> float:
    try:
        return max(0.0, float(os.environ.get("LLM_CONNECTION_ERROR_RETRY_SLEEP", "10")))
    except ValueError:
        return 10.0


def _connection_error_sleep_for_attempt(attempt: int) -> float:
    sleeps = _connection_error_retry_sleeps()
    if sleeps:
        return sleeps[min(attempt, len(sleeps) - 1)]
    return _connection_error_retry_sleep() * min(attempt + 1, 6)


def _is_transient_llm_connection_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    markers = (
        "connection error",
        "apiconnectionerror",
        "connecterror",
        "connection reset",
        "connection aborted",
        "remote protocol error",
        "read timeout",
        "timeout",
        "temporarily unavailable",
        "server disconnected",
        "tls",
        "ssl",
    )
    return any(marker in text for marker in markers)


def _message_has_tool_call(message: dict) -> bool:
    tool_calls = message.get("tool_calls") or message.get("function_call")
    return bool(tool_calls)


def _assert_valid_llm_message(message: dict, context: str) -> None:
    if not _fail_fast_enabled():
        return
    content = message.get("content") or ""
    if not str(content).strip() and _message_has_tool_call(message):
        return
    text = str(content).strip()
    if not text:
        raise RuntimeError(f"{context}: empty LLM response; stop to avoid writing empty localization results.")
    lowered = text.lower()
    for pattern in _fail_fast_patterns():
        if pattern in lowered:
            preview = text[:500].replace("\n", "\\n")
            raise RuntimeError(f"{context}: LLM response looks like an API quota/balance failure: {preview}")


def get_llm_response(model_name: str, messages, with_tool=False, tools=None,
                     temperature=0.0, n=1, max_completion_tokens=8192):
    """
    Get a response from the specified model.
    :param model_name: The name of the model to use (e.g., "claude", "gpt").
    :param messages: List of messages for the conversation.
    :param temperature: Sampling temperature.
    :param with_tool: Whether to use tools in the request.
    :param tools: List of tools to use (if any).
    :return: Decoded response, finish reason, and usage.
    """
    use_text_tools = os.environ.get("GRAPHLOCATOR_TEXT_TOOLS", "").lower() in {"1", "true", "yes"}
    tool_list = None if (use_text_tools and with_tool) else (tools if with_tool else None)
    request_model_name = _litellm_model_for_request(model_name)
    endpoint_kwargs = _litellm_endpoint_kwargs()

    def _call_model(model_name, messages, temperature, tools):
        connection_retries = _connection_error_retries()
        request_retries = max(5, _empty_response_retries() + 1, connection_retries + 1)
        retry_sleep = _empty_response_retry_sleep()
        for attempt in range(request_retries):
            try:
                if tools is None:
                    response = litellm.completion(
                        model=request_model_name,
                        messages=messages,
                        temperature=temperature,
                        n=n,
                        max_completion_tokens=max_completion_tokens,
                        **endpoint_kwargs,
                    )
                else:
                    response = litellm.completion(
                        model=request_model_name,
                        messages=messages,
                        temperature=temperature,
                        tools=tools,
                        parallel_tool_calls=False,
                        n=n,
                        max_completion_tokens=max_completion_tokens,
                        **endpoint_kwargs,
                    )
                decoded_answer = [choice["message"].to_dict() for choice in response.choices]
                for answer in decoded_answer:
                    _assert_valid_llm_message(answer, f"GraphLocator LiteLLM request model={request_model_name}")
                return response, decoded_answer
            except RuntimeError as e:
                if "empty LLM response" not in str(e):
                    raise
                if attempt == request_retries - 1:
                    raise
                print(
                    f"Empty response in {model_name} request via {request_model_name}: {e}. "
                    f"Retrying after {retry_sleep}s..."
                )
                time.sleep(retry_sleep)
            except Exception as e:
                if not _is_transient_llm_connection_error(e) or attempt >= connection_retries:
                    raise
                sleep_for = _connection_error_sleep_for_attempt(attempt)
                print(
                    f"Transient LLM connection error in {model_name} request via {request_model_name}: {e}. "
                    f"Retrying {attempt + 1}/{connection_retries} after {sleep_for}s..."
                )
                time.sleep(sleep_for)
        raise Exception(f"Failed to get a response from {model_name} after {request_retries} attempts.")

    llm_response, decoded_answer = _call_model(model_name, messages, temperature, tool_list)
    finish_reason = [choice["finish_reason"] for choice in llm_response.choices]
    usage = llm_response.usage.to_dict() if hasattr(llm_response, "usage") else {}
    return decoded_answer, finish_reason, usage

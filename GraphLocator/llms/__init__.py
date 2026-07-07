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
        for attempt in range(5):  # Retry up to 5 times
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
                    return response
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
                    return response
            except Exception as e:
                print(f"Error in {model_name} request via {request_model_name}: {e}. Retrying...")
                time.sleep(5)
        raise Exception(f"Failed to get a response from {model_name} after 5 attempts.")

    llm_response = _call_model(model_name, messages, temperature, tool_list)
    decoded_answer = [choice["message"].to_dict() for choice in llm_response.choices]
    finish_reason = [choice["finish_reason"] for choice in llm_response.choices]
    usage = llm_response.usage.to_dict() if hasattr(llm_response, "usage") else {}
    return decoded_answer, finish_reason, usage

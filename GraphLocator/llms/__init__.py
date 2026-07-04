import time
import os
import litellm


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

    def _call_model(model_name, messages, temperature, tools):
        for attempt in range(5):  # Retry up to 5 times
            try:
                if tools is None:
                    response = litellm.completion(
                        model=model_name,
                        messages=messages,
                        temperature=temperature,
                        n=n,
                        max_completion_tokens=max_completion_tokens
                    )
                    return response
                else:
                    response = litellm.completion(
                        model=model_name,
                        messages=messages,
                        temperature=temperature,
                        tools=tools,
                        parallel_tool_calls=False,
                        n=n,
                        max_completion_tokens=max_completion_tokens
                    )
                    return response
            except Exception as e:
                print(f"Error in {model_name} request: {e}. Retrying...")
                time.sleep(5)
        raise Exception(f"Failed to get a response from {model_name} after 5 attempts.")

    llm_response = _call_model(model_name, messages, temperature, tool_list)
    decoded_answer = [choice["message"].to_dict() for choice in llm_response.choices]
    finish_reason = [choice["finish_reason"] for choice in llm_response.choices]
    usage = llm_response.usage.to_dict() if hasattr(llm_response, "usage") else {}
    return decoded_answer, finish_reason, usage

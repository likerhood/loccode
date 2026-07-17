import argparse
import os
import json
import logging
import logging.handlers
import re
import time
import toml
from queue import Empty
from typing import List
from tqdm import tqdm
from copy import deepcopy
from util.benchmark.dataset_loader import load_benchmark_dataset

from util.runtime.execute_ipython import execute_ipython
from util.runtime import function_calling
from util.actions.action_parser import ResponseParser
from util.actions.action import ActionType
from util.prompts.prompt import PromptManager
from util.prompts import general_prompt
from util.prompts.pipelines import (
    simple_localize_pipeline as simple_loc,
    auto_search_prompt as auto_search,
)
from util.cost_analysis import calc_cost
from util.utils import *
from util.process_output import (
    parse_raw_loc_output,
    get_loc_results_from_raw_outputs,
    merge_sample_locations,
)
from plugins import LocationToolsRequirement
from plugins.location_tools.repo_ops.repo_ops import (
    set_current_issue,
    reset_current_issue,
)
import litellm
from litellm import Message as LiteLLMMessage
from openai import APITimeoutError
from evaluation.eval_metric import filtered_instances


from time import sleep
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import torch.multiprocessing as mp
from util.runtime.fn_call_converter import (
    convert_fncall_messages_to_non_fncall_messages,
    convert_non_fncall_messages_to_fncall_messages,
    STOP_WORDS as NON_FNCALL_STOP_WORDS
)
from muladapter.candidate_ranker import extract_file_candidates, format_ranked_symbol_candidates
# litellm.set_verbose=True
# os.environ['LITELLM_LOG'] = 'DEBUG


def litellm_model_for_request(model_name: str) -> str:
    """Return the concrete LiteLLM model used for API requests.

    ``model_name`` is also used by LocAgent to select prompt/tool behavior and
    is intentionally restricted by argparse. Server runs may use an arbitrary
    OpenAI-compatible backend model, so allow an environment override without
    weakening the internal model choices.
    """
    backend_model = (
        os.getenv("LOCAGENT_BACKEND_MODEL")
        or os.getenv("LOCAGENT_COMPLETION_MODEL")
        or os.getenv("LITELLM_MODEL")
        or ""
    ).strip()
    if not backend_model:
        return model_name
    if "/" not in backend_model:
        return f"openai/{backend_model}"
    return backend_model


def llm_fail_fast_enabled() -> bool:
    return os.getenv("LLM_FAIL_FAST", "1").strip().lower() not in {"0", "false", "no", "off"}


def llm_fail_fast_patterns() -> list[str]:
    raw = os.getenv(
        "LLM_FAIL_FAST_PATTERNS",
        "insufficient_quota|quota exceeded|quota_exceeded|insufficient balance|no credit|credit exhausted|"
        "balance not enough|out of quota|余额不足|额度不足|额度已用完|欠费|无可用额度",
    )
    return [item.strip().lower() for item in raw.split("|") if item.strip()]


def llm_empty_response_retries() -> int:
    try:
        return max(0, int(os.getenv("LLM_EMPTY_RESPONSE_RETRIES", "2")))
    except ValueError:
        return 2


def llm_empty_response_retry_sleep() -> float:
    try:
        return max(0.0, float(os.getenv("LLM_EMPTY_RESPONSE_RETRY_SLEEP", "5")))
    except ValueError:
        return 5.0


def llm_connection_error_retries() -> int:
    try:
        return max(0, int(os.getenv("LLM_CONNECTION_ERROR_RETRIES", "8")))
    except ValueError:
        return 8


def llm_connection_error_retry_sleep() -> float:
    try:
        return max(0.0, float(os.getenv("LLM_CONNECTION_ERROR_RETRY_SLEEP", "10")))
    except ValueError:
        return 10.0


def llm_connection_error_retry_sleeps() -> list[float]:
    raw = os.getenv("LLM_CONNECTION_ERROR_RETRY_SLEEPS", "30,50,60,100")
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


def llm_connection_error_sleep_for_attempt(attempt: int) -> float:
    sleeps = llm_connection_error_retry_sleeps()
    if sleeps:
        return sleeps[min(attempt, len(sleeps) - 1)]
    return llm_connection_error_retry_sleep() * min(attempt + 1, 6)


def is_transient_llm_connection_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    transient_markers = (
        "apiconnectionerror",
        "apierror",
        "connection error",
        "connection reset",
        "connection aborted",
        "connection refused",
        "remote protocol error",
        "server disconnected",
        "timeout",
        "timed out",
        "temporarily unavailable",
        "tls",
        "ssl",
    )
    fatal_markers = (
        "badrequest",
        "contextwindow",
        "insufficient_quota",
        "quota exceeded",
        "insufficient balance",
        "no credit",
        "余额不足",
        "额度不足",
    )
    return any(marker in text for marker in transient_markers) and not any(
        marker in text for marker in fatal_markers
    )


def assert_valid_llm_message(message, context: str) -> None:
    if not llm_fail_fast_enabled():
        return
    content = getattr(message, "content", None) or ""
    tool_calls = getattr(message, "tool_calls", None) or getattr(message, "function_call", None)
    if not str(content).strip() and tool_calls:
        return
    text = str(content).strip()
    if not text:
        raise RuntimeError(f"{context}: empty LLM response; stop to avoid writing empty localization results.")
    lowered = text.lower()
    for pattern in llm_fail_fast_patterns():
        if pattern in lowered:
            preview = text[:500].replace("\n", "\\n")
            raise RuntimeError(f"{context}: LLM response looks like an API quota/balance failure: {preview}")


def truncate_observation(text: str) -> str:
    max_chars = int(os.getenv("LOCAGENT_MAX_OBSERVATION_CHARS", "24000"))
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    half = max_chars // 2
    omitted = len(text) - max_chars
    return (
        text[:half]
        + f"\n\n[LocAgent truncated {omitted} characters from a long tool observation. "
        "Use narrower search_terms, file_path_or_pattern, or get_entity_contents on an exact path if needed.]\n\n"
        + text[-half:]
    )


def looks_like_final_localization(content: str) -> bool:
    if not content:
        return False
    lowered = content.lower()
    if "<execute_ipython>" in lowered or "search_code_snippets(" in content:
        return False
    has_final_marker = any(
        marker in lowered
        for marker in ("final answer", "final response", "final output")
    )
    has_code_block = "```" in content
    has_repo_path = re.search(
        r"(?m)(?:^|\s|`)([\w@.+-]+/)+(?:[\w@.+-]+)\.(?:py|js|jsx|ts|tsx|java|php|go|rs|rb|vue|svelte|css|scss|html)\b",
        content,
    )
    return bool(has_repo_path and (has_final_marker or has_code_block))


def _conversation_problem_context(messages: list[dict]) -> str:
    return "\n\n".join(
        str(message.get("content") or "")
        for message in messages
        if message.get("role") == "user"
    )


def _fallback_localization_from_candidates(
        observed_file_candidates: list[str],
        problem_context: str,
        instance_id: str | None = None,
) -> str:
    return format_ranked_symbol_candidates(
        observed_file_candidates,
        problem_context,
        instance_id=instance_id,
        limit=int(os.getenv("LOCAGENT_MAX_FALLBACK_FILES", "15")),
    )


def filter_dataset(dataset, filter_column: str, used_list: str):
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.toml')
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = toml.load(file)
            if used_list in data:
                selected_ids = data[used_list]
                logging.info(
                    f'Filtering {len(selected_ids)} tasks from "selected_ids"...'
                )
                def filter_function(example):
                    return example[filter_column] in selected_ids  # Replace 'id' with the actual field name in the dataset
                filtered_dataset = dataset.filter(filter_function)
                # subset = dataset[dataset[filter_column].isin(selected_ids)]
                logging.info(f'Retained {len(filtered_dataset)} tasks after filtering')
                return filtered_dataset
    return dataset


def get_task_instruction(instance: dict, task: str = 'auto_search', include_pr=False, include_hint=False):
    output_format = None
    instruction = ""
    
    # for auto-search pipeline
    if task.strip() == 'auto_search':
        task_description = auto_search.TASK_INSTRUECTION.format(
            package_name=instance['instance_id'].split('_')[0]
        )
    
    elif task.strip() == 'simple_localize':
        task_description = simple_loc.SEARCH_LOC_TASK_INSTRUCTION
        output_format = simple_loc.OUTPUT_FORMAT_LOC
        
    else:
        return None

    instruction += task_description
        
    if include_pr:
        problem_statement = instance['problem_statement']
        instruction += general_prompt.PR_TEMPLATE.format(
            title=problem_statement.strip().split('\n')[0],
            description = '\n'.join(problem_statement.strip().split('\n')[1:]).strip()
        )
    
    if output_format:
        instruction += output_format
    
    if include_hint:
        instruction += (
            'IMPORTANT: You should ONLY interact with the environment provided to you AND NEVER ASK FOR HUMAN HELP.\n'
            'Don\'t include any lambda functions!\n'
            'You should NOT modify any files!\n'
        )

    # NOTE: You can actually set slightly different instruction for different task
    # instruction += AGENT_CLS_TO_INST_SUFFIX
    return instruction


def auto_search_process(result_queue,
                        model_name, messages, fake_user_msg,
                        instance_id=None,
                        tools = None,
                        traj_data=None,
                        temp=1.0,
                        max_iteration_num=20,
                        use_function_calling=True):
    request_model_name = litellm_model_for_request(model_name)
    if tools and ('hosted_vllm' in model_name or 'qwen' in model_name.lower() 
    #             #   or model_name=='azure/gpt-4o' 
    #             #   or model_name == 'litellm_proxy/o3-mini-2025-01-31'
                ):
        use_function_calling = False
        
    # for LLM which do not support function calling
    if not use_function_calling and tools:
        # 转换message
        messages = convert_fncall_messages_to_non_fncall_messages(messages, tools, add_in_context_learning_example=False)
            
    # code_history = []
    parser = ResponseParser()
    if not traj_data:
        traj_msgs = messages.copy()
        prompt_tokens = 0
        completion_tokens = 0
    else:
        # continue from last traj
        traj_msgs = traj_data['messages']
        prompt_tokens = traj_data['usage']['prompt_tokens']
        completion_tokens = traj_data['usage']['completion_tokens']
        
    cur_interation_num = 0
    last_message = None
    finish = False
    final_output = ""
    problem_context = _conversation_problem_context(messages)
    observed_file_candidates: list[str] = []
    while not finish:
        cur_interation_num += 1
        if cur_interation_num > max_iteration_num:
            final_output = last_message or ""
            if not looks_like_final_localization(final_output):
                fallback_output = _fallback_localization_from_candidates(
                    observed_file_candidates, problem_context, instance_id
                )
                if fallback_output:
                    final_output = fallback_output
            logging.warning(
                "Maximum iteration count %s exceeded. Stop this sample and use the last model message as final output.",
                max_iteration_num,
            )
            break
        if cur_interation_num == max_iteration_num:
            candidate_block = _fallback_localization_from_candidates(
                observed_file_candidates, problem_context, instance_id
            )
            candidate_hint = (
                "\n\nObserved candidate files/symbols from tool results. Rank these exact repository paths first if relevant:\n"
                + candidate_block
                if candidate_block
                else ""
            )
            messages.append({
                'role': 'user',
                'content': (
                    'The maximum number of iterations has been reached. '
                    'Generate only the final ranked localization code block using exact repository paths, '
                    'and include class/function/line entries whenever shown below, then finish with:\n'
                    '<function=finish>\n</function>'
                    + candidate_hint
                )
            })
            traj_msgs.append({
                'role': 'user',
                'content': (
                    'The maximum number of iterations has been reached. '
                    'Generate only the final ranked localization code block using exact repository paths, '
                    'and include class/function/line entries whenever shown below, then finish with:\n'
                    '<function=finish>\n</function>'
                    + candidate_hint
                )
            })

        empty_retries = llm_empty_response_retries()
        connection_retries = llm_connection_error_retries()
        retry_sleep = llm_empty_response_retry_sleep()
        response_retries = max(empty_retries, connection_retries)
        for response_attempt in range(response_retries + 1):
            try:
                # new conversation
                if tools and ('hosted_vllm' in model_name or 'qwen' in model_name.lower()):
                    request_messages = convert_fncall_messages_to_non_fncall_messages(
                        messages,
                        tools,
                        add_in_context_learning_example=False,
                    )
                    response = litellm.completion(
                        model=request_model_name,
                        temperature=temp, top_p=0.8, repetition_penalty=1.05, 
                        messages=request_messages,
                        stop=NON_FNCALL_STOP_WORDS
                    )
                elif tools:
                    response = litellm.completion(
                        model=request_model_name,
                        tools=tools,
                        messages=messages,
                        temperature=temp,
                        # stop=['</execute_ipython>'], #</finish>',
                    )
                else:
                    response = litellm.completion(
                        model=request_model_name,
                        messages=messages,
                        temperature=temp,
                        stop=['</execute_ipython>'], #</finish>',
                    )
                assert_valid_llm_message(
                    response.choices[0].message,
                    f"LocAgent LiteLLM request model={request_model_name}",
                )
                break
            except litellm.BadRequestError as e:
                # If there's an error, send the error info back to the parent process
                result_queue.put({'error': str(e), 'type': 'BadRequestError'})
                return
            except RuntimeError as e:
                if "empty LLM response" in str(e) and response_attempt < empty_retries:
                    logging.warning(
                        "Empty LLM response from %s; retrying %s/%s after %.1fs",
                        request_model_name,
                        response_attempt + 1,
                        empty_retries,
                        retry_sleep,
                    )
                    if retry_sleep:
                        time.sleep(retry_sleep)
                    continue
                result_queue.put({'error': str(e), 'type': 'RuntimeError'})
                return
            except Exception as e:
                if is_transient_llm_connection_error(e) and response_attempt < connection_retries:
                    sleep_for = llm_connection_error_sleep_for_attempt(response_attempt)
                    logging.warning(
                        "Transient LLM connection error from %s; retrying %s/%s after %.1fs: %s",
                        request_model_name,
                        response_attempt + 1,
                        connection_retries,
                        sleep_for,
                        e,
                    )
                    if sleep_for:
                        time.sleep(sleep_for)
                    continue
                result_queue.put({'error': str(e), 'type': type(e).__name__})
                return
        
        if last_message and response.choices[0].message.content == last_message:
            messages.append({
                "role": "user",
                "content": "OBSERVATION:\n" + "Don't repeat your response.\n" + fake_user_msg,
            })
            traj_msgs.append({
                "role": "user",
                "content": "OBSERVATION:\n" + "Don't repeat your response.\n" + fake_user_msg,
            })
            continue
        
        raw_response = deepcopy(response)
        # logging.info('response.choices[0].message')
        if tools and ('hosted_vllm' in model_name or 'qwen' in model_name.lower()
                      or 'deepseek' in model_name
                      ):
            try:
                non_fncall_response_message = response.choices[0].message
                fn_call_messages_with_response = (
                    convert_non_fncall_messages_to_fncall_messages(
                        [non_fncall_response_message], tools # messages + 
                    )
                )
                fn_call_response_message = fn_call_messages_with_response[-1]
                if not isinstance(fn_call_response_message, LiteLLMMessage):
                    fn_call_response_message = LiteLLMMessage(
                        **fn_call_response_message
                    )
                response.choices[0].message = fn_call_response_message
            except Exception as exc:
                raw_content = response.choices[0].message.content or ""
                if looks_like_final_localization(raw_content):
                    logging.info(
                        "convert none fncall messages failed, but response looks like final localization output: %s",
                        exc,
                    )
                else:
                    logging.info(
                        'convert none fncall messages failed; keep the response as a normal message and ask the model to either use a valid tool call or finish.'
                    )
                
        last_message = response.choices[0].message.content
        observed_file_candidates.extend(extract_file_candidates(last_message or ""))
        print(response.choices[0].message)
        messages.append(convert_to_json(raw_response.choices[0].message))
        traj_msgs.append(convert_to_json(raw_response.choices[0].message))
        prompt_tokens += response.usage.prompt_tokens
        completion_tokens += response.usage.completion_tokens  
            
        actions = parser.parse(response)
        if not isinstance(actions, List):
            actions = [actions]
        for action in actions:
            logging.debug(action.action_type)
            if action.action_type == ActionType.FINISH:
                final_output = (action.thought or "").strip()
                if not final_output:
                    final_output = _fallback_localization_from_candidates(
                        observed_file_candidates, problem_context, instance_id
                    )
                logging.info('='*15)
                logging.info("\nFinal Response:=\n" + final_output)
                finish = True # break
            elif action.action_type == ActionType.MESSAGE:
                if looks_like_final_localization(action.content):
                    final_output = action.content
                    logging.info('='*15)
                    logging.info("\nFinal Response:=\n" + final_output)
                    finish = True
                    break
                logging.debug("thought:\n" + action.content)
                # check if enough
                messages.append({"role": "user", "content": fake_user_msg})
                traj_msgs.append({"role": "user", "content": fake_user_msg})
                # continue
            elif action.action_type == ActionType.RUN_IPYTHON:
                ipython_code = action.code.strip('`')
                logging.info(f"Executing code:\n```\n{ipython_code}\n```")
                function_response = execute_ipython(ipython_code)
                try:
                    function_response = eval(function_response)
                except SyntaxError:
                    function_response = function_response
                if not isinstance(function_response, str):
                    function_response = str(function_response)
                function_response = truncate_observation(function_response)
                observed_file_candidates.extend(extract_file_candidates(function_response))
                
                logging.info("OBSERVATION:\n" + function_response)
                if not tools:
                    messages.append({
                        "role": "user",
                        "content": "OBSERVATION:\n" + function_response,
                    })
                    traj_msgs.append({
                        "role": "user",
                        "content": "OBSERVATION:\n" + function_response,
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": action.tool_call_id,
                        "name": action.function_name,
                        "content": "OBSERVATION:\n" + function_response,
                    })
                    traj_msgs.append({
                        "role": "tool",
                        "tool_call_id": action.tool_call_id,
                        "name": action.function_name,
                        "content": "OBSERVATION:\n" + function_response,
                    })
            else:
                logging.warning('Error Action!')
                # return

    # save traj
    traj_data = {
        'messages': traj_msgs,
        'tools': tools,
        'usage': {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens
        }
    }
    # return final_output, messages, traj_data
    result_queue.put((final_output, messages, traj_data))


def run_localize(rank, args, bug_queue, log_queue, output_file_lock, traj_file_lock):
    queue_handler = logging.handlers.QueueHandler(log_queue)
    logger = logging.getLogger()
    logger.setLevel(logging.getLevelName(args.log_level))
    logger.handlers = []
    logger.addHandler(queue_handler)

    logger.debug(f"------ rank {rank} start ------")

    while True:
        try:
            bug = bug_queue.get_nowait()
        except Empty:
            break

        instance_id = bug["instance_id"]
        prompt_manager = PromptManager(
            prompt_dir=os.path.join(os.path.dirname(__file__), 'util/prompts'),
            agent_skills_docs=LocationToolsRequirement.documentation,
        )

        logger.info("=" * 60)
        logger.info(f"==== rank {rank} setup localize {instance_id} ====")
        set_current_issue(
            instance_data=bug,
            dataset=args.dataset,
            split=args.split,
            rank=rank,
        )

        # loc result
        raw_output_loc = []
        loc_trajs = {'trajs': []}
        total_prompt_tokens, total_completion_tokens = 0, 0

        for _ in range(args.num_samples):
            logger.info("=" * 60)
            logger.info(f"==== rank {rank} begin localizing {instance_id} ====")
            max_attempt_num = args.max_attempt_num
            while max_attempt_num:
                logger.info("=" * 60)
                logger.info(f"==== {instance_id} Count down: attempt {max_attempt_num} ====")
                loc_start_time = time.time()
                try:
                    """
                    Basic instructions:
                        - CodeAct instruction
                        - Few-shot Examples
                    """
                    if args.use_function_calling:
                        system_prompt = function_calling.SYSTEM_PROMPT
                        # system_prompt = CLAUDE_THINKING_INSTRUCTION
                    else:
                        system_prompt = prompt_manager.system_message
                        
                    messages: list[dict] = [{
                        "role": "system",
                        "content": system_prompt
                    }]
                        
                    if args.use_example:
                        messages.append({
                            "role": "user",
                            "content": prompt_manager.initial_user_message
                        })

                    logger.info(f"==== {instance_id} start auto search ====")
                    messages.append({
                        "role": "user",
                        "content": get_task_instruction(bug, include_pr=True, include_hint=True),
                    })
                    
                    ctx = mp.get_context('fork')  # use fork to inherit context!!
                    result_manager = ctx.Manager()
                    result_queue = result_manager.Queue()
                    try:
                        tools = None
                        if args.use_function_calling:
                            tools = function_calling.get_tools(
                                codeact_enable_search_keyword=True,
                                codeact_enable_search_entity=True,
                                codeact_enable_tree_structure_traverser=True,
                                simple_desc = args.simple_desc,
                            )
                        process = ctx.Process(target=auto_search_process, kwargs={
                            'result_queue': result_queue,
                            'model_name': args.model,
                            'messages': messages,
                            'fake_user_msg': auto_search.FAKE_USER_MSG_FOR_LOC,
                            'instance_id': instance_id,
                            'temp': 1,
                            'tools': tools,
                            'use_function_calling': args.use_function_calling,
                        })
                        process.start()
                        process.join(timeout=args.timeout)
                        if process.is_alive():
                            logger.warning(f"{instance_id} attempt {max_attempt_num} execution flow "
                                            f"reconstruction exceeded timeout. Terminating.")
                            process.terminate()
                            process.join()
                            raise TimeoutError
                        
                        if process.exitcode not in (0, None) and result_queue.empty():
                            raise RuntimeError(
                                f"auto_search_process exited with code {process.exitcode} before returning a result."
                            )

                        # loc_result, messages, traj_data = result_queue.get()
                        try:
                            result = result_queue.get(timeout=5)
                        except Empty:
                            raise RuntimeError(
                                "auto_search_process finished but did not return a result."
                            )
                    finally:
                        result_manager.shutdown()
                    if isinstance(result, dict) and 'error' in result and result.get('type') == 'BadRequestError':
                        raise litellm.BadRequestError(result['error'], args.model, args.model.split('/')[0])
                        # print(f"Error occurred in subprocess: {result['error']}")
                    if isinstance(result, dict) and 'error' in result:
                        raise RuntimeError(f"{result.get('type', 'Error')}: {result['error']}")
                    else:
                        loc_result, messages, traj_data = result
                        
                except litellm.BadRequestError as e:
                    logger.warning(f'{e}. Try again.')
                    continue
                except APITimeoutError:
                    logger.warning(f"APITimeoutError. Try again.")
                    sleep(10)
                    continue
                except TimeoutError:
                    logger.warning(f"Processing time exceeded 15 minutes. Try again.")
                    max_attempt_num = max_attempt_num - 1
                    continue
                except litellm.exceptions.ContextWindowExceededError as e:
                    logger.warning(f'{e}. Try again.')
                    max_attempt_num = max_attempt_num - 1
                    continue
                except RuntimeError as e:
                    if "quota/balance failure" in str(e) or "empty LLM response" in str(e):
                        raise
                    logger.warning(f'{e}. Try next attempt if available.')
                    max_attempt_num = max_attempt_num - 1
                    continue

                loc_end_time = time.time()
                if not loc_result:
                    logger.warning(
                        "%s produced an empty final localization output. Try next attempt if available.",
                        instance_id,
                    )
                    max_attempt_num = max_attempt_num - 1
                    continue

                total_prompt_tokens += traj_data['usage']['prompt_tokens']
                total_completion_tokens += traj_data['usage']['completion_tokens']
                traj_data['time'] = loc_end_time - loc_start_time
                loc_trajs['trajs'].append(traj_data)

                # generate correct output or finish last attempt
                raw_output_loc.append(loc_result)
                break

        if not raw_output_loc:
            # loc generalization failed
            logger.info(f"==== localizing {instance_id} failed, save empty outputs ====")
            loc_res = {
                    "instance_id": instance_id,
                    "found_files": [[]],
                    "found_modules": [[]],
                    "found_entities": [[]],
                    "found_functions": [[]],
                    "raw_output_loc": raw_output_loc,
                    "meta_data": {
                        'repo': bug['repo'],
                        'base_commit': bug['base_commit'],
                        'problem_statement': bug['problem_statement'],
                        'patch': bug['patch'],
                        # 'gt_file_changes': gt_file_changes
                    }
                }
            with output_file_lock:
                append_to_jsonl(loc_res, args.output_file)
        else:
            # process multiple loc outputs
            logger.info(f"==== localizing {instance_id} succeed, process multiple loc outputs ====")

            # all_valid_files = get_all_valid_files()
            all_found_files, all_found_modules, all_found_entities = get_loc_results_from_raw_outputs(
                instance_id, raw_output_loc
            )
            
            loc_res = {
                "instance_id": instance_id,
                "found_files": all_found_files,
                "found_modules": all_found_modules,
                "found_entities": all_found_entities,
                "found_functions": all_found_entities,
                "raw_output_loc": raw_output_loc,
                "meta_data": {
                    'repo': bug['repo'],
                    'base_commit': bug['base_commit'],
                    'problem_statement': bug['problem_statement'],
                    'patch': bug['patch'],
                    # 'gt_file_changes': gt_file_changes
                }
            }
            
            with output_file_lock:
                append_to_jsonl(loc_res, args.output_file)

            cost = calc_cost(args.model, total_prompt_tokens, total_completion_tokens)
            loc_res['usage'] = {'cost($)': f'{round(cost, 5)}', 'prompt_tokens': total_prompt_tokens,
                                'completion_tokens': total_completion_tokens}
            loc_res['loc_trajs'] = loc_trajs
            traj_file = os.path.join(args.output_folder, 'loc_trajs.jsonl')
            with traj_file_lock:
                append_to_jsonl(loc_res, traj_file)

        reset_current_issue()


def localize(args):
    bench_data = load_benchmark_dataset(args.dataset, split=args.split)
    bench_tests = filter_dataset(bench_data, 'instance_id', args.used_list)
    if args.eval_n_limit:
        eval_n_limit = min(args.eval_n_limit, len(bench_tests))
        bench_tests = bench_tests.select(range(0, eval_n_limit))
        logging.info(f'Limiting evaluation to first {eval_n_limit} instances.')

    manager = mp.Manager()
    queue = manager.Queue()
    output_file_lock, traj_file_lock = manager.Lock(), manager.Lock()

    # collect processed instances
    processed_instance = []
    if os.path.exists(args.output_file):
        traj_file = os.path.join(args.output_folder, 'loc_trajs.jsonl')
        locs = load_jsonl(args.output_file)        
        if args.rerun_empty_location:
            traj_datas = load_jsonl(traj_file)
            backup_loc_output = backup_file(args.output_file)
            backup_traj_output = backup_file(traj_file)
            clear_file(args.output_file)
            clear_file(traj_file)
            for loc in locs:
                if loc['found_files'] != [[]]:
                    append_to_jsonl(loc, args.output_file)
                    processed_instance.append(loc['instance_id'])
                    
            for loc_traj in traj_datas:
                if loc_traj['found_files'] != [[]]:
                    append_to_jsonl(loc_traj, traj_file)
        else:
            processed_instance = [loc['instance_id'] for loc in locs]
    
    num_bugs = 0
    for bug in bench_tests:
        instance_id = bug["instance_id"]
        if instance_id in processed_instance:
        # if instance_id in processed_instance or instance_id in filtered_instances:
            print(f"instance {instance_id} has already been processed, skip.")
        else:
            queue.put(bug)
            num_bugs += 1

    log_queue = manager.Queue()
    queue_listener = logging.handlers.QueueListener(log_queue, *logging.getLogger().handlers)
    queue_listener.start()
    mp.spawn(
        run_localize,
        nprocs=min(num_bugs, args.num_processes) if args.num_processes > 0 else num_bugs,
        args=(args, queue, log_queue, output_file_lock, traj_file_lock),
        join=True
    )
    queue_listener.stop()
    
    if args.rerun_empty_location:
        try:
            delete_file(backup_loc_output)
            delete_file(backup_traj_output)
        except:
            return


def merge(args):
    args.merge_file = os.path.join(args.output_folder, 'merged_' + os.path.basename(args.output_file))
    
    if args.ranking_method == 'mrr':
        args.merge_file = args.merge_file.replace('.jsonl', f'_{args.ranking_method}.jsonl')
        
    clear_file(args.merge_file)
    with open(args.output_file, 'r') as file:
        for line in file:
            loc_data = json.loads(line)
            if loc_data['found_files'] == [[]]:
                raw_outputs = loc_data.get('raw_output_loc') or []
                if raw_outputs:
                    try:
                        (
                            reparsed_files,
                            reparsed_modules,
                            reparsed_entities,
                        ) = get_loc_results_from_raw_outputs(
                            loc_data['instance_id'], raw_outputs
                        )
                        if any(reparsed_files):
                            ranked_files, ranked_modules, ranked_funcs = merge_sample_locations(
                                reparsed_files,
                                reparsed_modules,
                                reparsed_entities,
                                ranking_method=args.ranking_method,
                            )
                            loc_data['found_files'] = ranked_files
                            loc_data['found_modules'] = ranked_modules
                            loc_data['found_entities'] = ranked_funcs
                            loc_data['found_functions'] = ranked_funcs
                        else:
                            loc_data['found_files'] = []
                            loc_data['found_modules'] = []
                            loc_data['found_entities'] = []
                            loc_data['found_functions'] = []
                    except Exception as exc:
                        logging.warning(
                            "Failed to reparse empty localization for %s: %s",
                            loc_data.get('instance_id'),
                            exc,
                        )
                        loc_data['found_files'] = []
                        loc_data['found_modules'] = []
                        loc_data['found_entities'] = []
                        loc_data['found_functions'] = []
                else:
                    loc_data['found_files'] = []
                    loc_data['found_modules'] = []
                    loc_data['found_entities'] = []
                    loc_data['found_functions'] = []
            else:
                loc_data['found_files'] = loc_data['found_files']
                loc_data['found_modules'] = loc_data['found_modules']
                loc_data['found_entities'] = loc_data['found_entities']
                ranked_files, ranked_modules, ranked_funcs = merge_sample_locations(loc_data['found_files'], 
                                                                    loc_data['found_modules'],
                                                                    loc_data['found_entities'],
                                                                    ranking_method=args.ranking_method,
                                                                    )
                loc_data['found_files'] = ranked_files
                loc_data['found_modules'] = ranked_modules
                loc_data['found_entities'] = ranked_funcs
                loc_data['found_functions'] = ranked_funcs
            with open(args.merge_file, 'a') as f:
                f.write(json.dumps(loc_data) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--localize", action="store_true")
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--use_example", action="store_true")
    parser.add_argument("--ranking_method", type=str, default='mrr',
                        choices=['mrr', 'majority'])
    
    parser.add_argument("--dataset", type=str, default="princeton-nlp/SWE-bench_Lite")
    parser.add_argument("--split", type=str, default="test")
    parser.add_argument("--eval_n_limit", type=int, default=0)
    parser.add_argument("--used_list", type=str, default='selected_ids')
    
    parser.add_argument("--output_folder", type=str, required=True)
    parser.add_argument("--output_file", type=str, default="loc_outputs.jsonl")
    parser.add_argument("--merge_file", type=str, default="merged_loc_outputs.jsonl")
    
    parser.add_argument(
        "--model", type=str,
        default="openai/gpt-4o-2024-05-13",
        choices=["gpt-4o", 
                 "azure/gpt-4o", "openai/gpt-4o-2024-05-13",
                 "deepseek/deepseek-chat", "deepseek-ai/DeepSeek-R1",
                 "litellm_proxy/claude-3-5-sonnet-20241022", "litellm_proxy/gpt-4o-2024-05-13", "litellm_proxy/o3-mini-2025-01-31",
                 # fine-tuned model
                 "openai/qwen-7B", "openai/qwen-7B-128k", "openai/ft-qwen-7B", "openai/ft-qwen-7B-128k",
                 "openai/qwen-32B", "openai/qwen-32B-128k", "openai/ft-qwen-32B", "openai/ft-qwen-32B-128k",
                 "openai/qwen9b", "openai/qwen3-vl-8b"
        ]
    )
    parser.add_argument("--use_function_calling", action="store_true",
                        help='Enable function calling features of LLMs. If disabled, codeact will be used to support function calling.')
    parser.add_argument("--simple_desc", action="store_true", 
                        help="Use simplified function descriptions due to certain LLM limitations. Set to False for better performance when using Claude.")
    
    parser.add_argument("--max_attempt_num", type=int, default=1, 
                        help='Only use in generating training trajectories.')
    parser.add_argument("--num_samples", type=int, default=2)
    parser.add_argument("--num_processes", type=int, default=-1)
    parser.add_argument("--repo_cache_mode", type=str,
                        default=os.environ.get("LOCAGENT_REPO_CACHE_MODE", "instance"),
                        choices=["instance", "shared"],
                        help="Repository cache strategy. 'instance' uses a mirror plus one working tree per instance. "
                             "'shared' uses a mirror plus one resettable working tree per GitHub repo and requires "
                             "--num_processes 1.")
    
    parser.add_argument("--log_level", type=str, default='INFO')
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--rerun_empty_location", action="store_true")
    args = parser.parse_args()
    if args.repo_cache_mode == "shared" and args.num_processes != 1:
        raise ValueError("--repo_cache_mode shared requires --num_processes 1")
    os.environ["LOCAGENT_REPO_CACHE_MODE"] = args.repo_cache_mode

    args.output_file = os.path.join(args.output_folder, args.output_file)
    os.makedirs(args.output_folder, exist_ok=True)

    # write the arguments
    with open(f"{args.output_folder}/args.json", "w") as f:
        json.dump(vars(args), f, indent=4)

    logging.basicConfig(
        level=logging.getLevelName(args.log_level),
        format="%(asctime)s %(filename)s %(levelname)s %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(f"{args.output_folder}/localize.log"),
            logging.StreamHandler()
        ]
    )
    
    if args.localize:
        localize(args)
    
    
    if args.merge:
        merge(args)


if __name__ == "__main__":

    start_time = time.time()
    main()
    end_time = time.time()
    logging.info("Total time: {:.4f} min".format((end_time - start_time)/60))

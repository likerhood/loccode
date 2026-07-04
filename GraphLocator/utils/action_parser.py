import re
import json
from typing import Union, List
from utils.action import Action, IPythonRunCellAction, FinishAction, MessageAction, ActionType


def parse_tool_calls_to_actions(response, graph) -> list[Action]:
    actions: list[Action] = []
    if "tool_calls" in response[0][0].keys():
        for i, tool_call in enumerate(response[0][0]["tool_calls"]):
            action: Action
            try:
                arguments = json.loads(tool_call["function"]["arguments"])
            except json.decoder.JSONDecodeError as e:
                raise RuntimeError(
                    f'Failed to parse tool call arguments: {tool_call["function"]["arguments"]}'
                ) from e
            if tool_call["function"]["name"] == 'finish':
                if list(arguments.values()):
                    action = FinishAction(thought=list(arguments.values())[0])
                else:
                    action = FinishAction()

            elif tool_call["function"]["name"] in ["search_node", "search_edge"]:
                func_name = tool_call["function"]["name"]
                org_pattern = '\''
                new_pattern = '\\\''
                arguments_str_list = [f"'{k}': '{v.replace(org_pattern, new_pattern)}'" for k, v in arguments.items()]
                arguments_str = "{" + ", ".join(arguments_str_list) + ", 'graph': graph}"
                code = f'print({func_name}(**{arguments_str}))'
                action = IPythonRunCellAction(code=code,
                                              function_name=func_name,
                                              tool_call_id=tool_call["id"]) 
            else:
                raise RuntimeError(f'Unknown tool call: {tool_call.function.name}')

            actions.append(action)
    else:
        actions.append(
            MessageAction(raw_content=response[0][0]["content"], content=response[0][0]["content"])
        )

    assert len(actions) >= 1
    return actions


class ResponseParser:
    def __init__(self):
        self.action_parsers = [
            CodeActActionParserFinish(),
            CodeActActionParserIPythonRunCell(),
        ]
        self.default_parser = CodeActActionParserMessage()

    def parse(self, response, graph) -> Union[List[Action], Action]:
        if response[0][0].get("tool_calls"):
            actions = parse_tool_calls_to_actions(response, graph)
            return actions
        action_str = self.parse_response(response)
        text_tool_actions = self.parse_text_tool_calls(action_str, graph)
        if text_tool_actions:
            return text_tool_actions
        return self.parse_action(action_str)

    def parse_response(self, response) -> str:
        action = response[0][0].get("content", "")
        if action is None:
            return ''
        for lang in ['bash', 'ipython', 'browse']:
            if f'<execute_{lang}>' in action and f'</execute_{lang}' in action and f'</execute_{lang}>' not in action:
                action += '>'
            if f'<execute_{lang}>' in action and f'</execute_{lang}>' not in action:
                action += f'</execute_{lang}>'
        return action

    def parse_text_tool_calls(self, action_str: str, graph) -> list[Action]:
        """Parse model-emitted pseudo tool calls when the backend lacks tool calling.

        Some local OpenAI-compatible backends return tool calls as plain text like:
        <tools><name=search_node><arguments>...</arguments></name></tools>
        instead of populating message.tool_calls. Convert that format into the same
        internal action used by native tool calls.
        """
        actions: list[Action] = []
        tool_blocks = re.finditer(
            r"<name=(search_node|search_edge|finish)>\s*<arguments>(.*?)</arguments>\s*</name>",
            action_str,
            re.DOTALL,
        )
        for idx, match in enumerate(tool_blocks):
            func_name = match.group(1)
            arg_block = match.group(2)
            arguments = {
                key: value.strip()
                for key, value in re.findall(r"<([A-Za-z_][\w]*)>(.*?)</\1>", arg_block, re.DOTALL)
            }
            if func_name == "finish":
                actions.append(FinishAction(thought=arguments.get("thought", "")))
                continue
            if func_name == "search_node":
                arguments.setdefault("node_type", "*")
                arguments.setdefault("node_name", "*")
            elif func_name == "search_edge":
                arguments.setdefault("src_node_type", "*")
                arguments.setdefault("src_node_name", "*")
                arguments.setdefault("edge_type", "HasMember")
                arguments.setdefault("trg_node_type", "*")
                arguments.setdefault("trg_node_name", "*")
            org_pattern = "'"
            new_pattern = "\\'"
            arguments_str_list = [
                f"'{k}': '{v.replace(org_pattern, new_pattern)}'"
                for k, v in arguments.items()
            ]
            arguments_str = "{" + ", ".join(arguments_str_list) + ", 'graph': graph}"
            code = f"print({func_name}(**{arguments_str}))"
            actions.append(
                IPythonRunCellAction(
                    raw_content=action_str,
                    code=code,
                    function_name=func_name,
                    tool_call_id=f"manual-{func_name}-{idx}",
                )
            )
        return actions

    def parse_action(self, action_str: str) -> Union[List[Action], Action]:
        for action_parser in self.action_parsers:
            if action_parser.check_condition(action_str):
                return action_parser.parse(action_str)
        return self.default_parser.parse(action_str)


class CodeActActionParserMessage:
    """Parser action:
    - MessageAction(content) - Message action to run (e.g. ask for clarification)
    """

    def __init__(
            self,
    ):
        pass

    def check_condition(self, action_str: str) -> bool:
        return True

    def parse(self, action_str: str) -> Action:
        action = MessageAction(raw_content=action_str, content=action_str)
        return action


class CodeActActionParserIPythonRunCell:
    def __init__(self):
        self.commands = []

    def check_condition(self, action_str: str) -> bool:
        python_code = re.search(
            r'<execute_ipython>(.*?)</execute_ipython>', action_str, re.DOTALL
        )
        return python_code is not None

    def parse(self, action_str: str) -> str:
        """
        Extracts and stores the commands within the <execute_ipython> tags.
        """
        python_code = re.search(
            r'<execute_ipython>(.*?)</execute_ipython>', action_str, re.DOTALL
        )
        assert (
                python_code is not None
        ), 'python_code should not be None when parse is called'

        code_group = python_code.group(1).strip()
        thought = action_str.replace(python_code.group(0), '').strip()

        action = IPythonRunCellAction(raw_content=action_str, code=code_group, thought=thought)
        
        return action
    
    def extract_function(self, code_str):
        """
        Extracts the function name and arguments from a string like `open_file('app.py')`.
        """
        func_pattern = r"(\w+)\((.*)\)"
        match = re.match(func_pattern, code_str)
        if match:
            func_name = match.group(1)
            # Evaluate the arguments safely (this assumes simple literals like strings, numbers, etc.)
            args = eval(f"[{match.group(2)}]") if match.group(2) else []
            return func_name, args
        return None, None


class CodeActActionParserFinish:
    def check_condition(self, action_str: str) -> bool:
        self.finish_command = re.search(r'<finish>.*</finish>', action_str, re.DOTALL)
        return self.finish_command is not None

    def parse(self, action_str: str) -> Action:
        assert (
                self.finish_command is not None
        ), 'self.finish_command should not be None when parse is called'
        thought = action_str.replace(self.finish_command.group(0), '').strip()
        return FinishAction(raw_content=action_str, thought=thought)

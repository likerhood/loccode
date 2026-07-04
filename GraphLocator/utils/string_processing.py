import re
import os
import json
from rdfs.dependency_graph.models.graph_data import Node, Edge

def _truncate_text(text, max_chars: int | None) -> str:
    text = "" if text is None else str(text)
    if max_chars is None or max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...[truncated {len(text) - max_chars} chars]"


def node_to_json(node: Node, max_content_chars: int | None = None) -> str:
    """
    Convert a Node object to a JSON string.
    
    Arguments:
    node -- the Node object to convert
    
    Returns:
    A JSON string representation of the Node object.
    """
    node_dict = {
        "type": node.type,
        "name": node.name,
        "location": str(node.location.file_path) if node.location else None,
        "content": _truncate_text(node.content, max_content_chars)
    }
    return json.dumps(node_dict, ensure_ascii=False)

def node_deserialization(node_list_str: str):
    node_list = node_list_str.splitlines(keepends=False)
    res = []
    for node_str in node_list:
        try:
            res.append(Node(type=None, name=None, location=None).from_json(node_str))
        except:
            pass
    return res


def edge_deserialization(edge_list_str: str):
    edge_list = edge_list_str.splitlines(keepends=False)
    res = []
    for edge_str in edge_list:
        if not edge_str:
            continue
        try:
            edge_obj = json.loads(edge_str)
            res.append((Node(type=None, name=None, location=None).from_json(edge_obj["src_node"]),
                        Node(type=None, name=None, location=None).from_json(edge_obj["trg_node"]),
                        Edge(relation=None, location=None).from_json(edge_obj["edge"])
                        ))
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    return res


def load_jsonl(filepath):
    """
    Load a JSONL file from the given filepath.

    Arguments:
    filepath -- the path to the JSONL file to load

    Returns:
    A list of dictionaries representing the data in each line of the JSONL file.
    """
    with open(filepath, "r") as file:
        return [json.loads(line) for line in file if line.strip()]


def write_jsonl(obj, filepath):
    "wirte an object to a JSONL file at the given filepath."
    if isinstance(obj, list):
        obj = [json.dumps(item) for item in obj]
    elif isinstance(obj, dict):
        obj = json.dumps(obj)
    else:
        raise ValueError("Object must be a list or a dictionary.")
    with open(filepath, "w") as file:
        file.write(obj + "\n")

def write_json(obj, filepath):
    """
    Write an object to a JSON file at the given filepath.

    Arguments:
    obj -- the object to write to the file
    filepath -- the path to the JSON file to write

    Returns:
    None
    """
    with open(filepath, "w") as file:
        json.dump(obj, file, indent=4, ensure_ascii=False)

def calculate_import_path(current_file, import_string):
    """
    计算相对导入的绝对路径

    参数:
        current_file (str): 当前文件的路径，如 "a/b/c.py"
        import_string (str): 导入语句，如 "....utils.exceptions"

    返回:
        str: 导入文件的绝对路径
    """
    # 解析导入字符串中的点号数量
    dots_match = re.match(r'(\.+)(.*)', import_string)
    if not dots_match:
        raise ValueError(f"无效的相对导入字符串: {import_string}")

    dots, module_path = dots_match.groups()
    dot_count = len(dots)

    # 获取当前文件所在的目录
    current_dir = os.path.dirname(current_file)

    # 向上移动目录层级
    parent_dir = current_dir
    for _ in range(dot_count - 1):  # 减1是因为已经在当前目录了
        parent_dir = os.path.dirname(parent_dir)

    # 将模块路径转换为文件路径
    module_parts = module_path.split('.')
    module_file = module_parts[-1] + '.py'
    module_dir = os.path.join(parent_dir, *module_parts[:-1])

    # 返回完整的文件路径
    return os.path.join(module_dir, module_file)


def filter_none_python_java(structure):
    for key, value in list(structure.items()):
        if (
            not "functions" in value.keys()
            and not "classes" in value.keys()
            and not "text" in value.keys()
        ) or not len(value.keys()) == 3:
            filter_none_python_java(value)

            if structure[key] == {}:
                del structure[key]
        else:
            if not (key.endswith(".py") or key.endswith(".java")):
                del structure[key]

def filter_out_test_files(structure):
    """filter out test files from the project structure"""
    for key, value in list(structure.items()):
        if key.startswith("test"):
            del structure[key]
        elif isinstance(value, dict):
            filter_out_test_files(value)


def show_project_structure(structure, spacing=0) -> str:
    """pprint the project structure"""

    pp_string = ""

    for key, value in structure.items():
        if "." in key and (".py" not in key and ".java" not in key):
            continue  # skip none python/java files
        if "." in key:
            pp_string += " " * spacing + str(key) + "\n"
        else:
            pp_string += " " * spacing + str(key) + "/" + "\n"
        if "classes" not in value:
            pp_string += show_project_structure(value, spacing + 4)

    return pp_string


def get_repo_structure_str(instance_id):
    # read the repo strucuture from json
    with open(f"/home/liuwei.aicoding/CoSIL/repo_structures/{instance_id}.json", 'r') as f:
        full_repo_structure = json.load(f)
    repo_structure = full_repo_structure['structure']
    filter_none_python_java(repo_structure)  # some basic filtering steps
    filter_out_test_files(repo_structure)
    return show_project_structure(repo_structure).strip()

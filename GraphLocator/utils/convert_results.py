from utils.string_processing import node_deserialization
from rdfs.dependency_graph.models.graph_data import Node, NodeType


def reformat_entity_name(graph, target_node) -> str:
    changed_entities = ""
    if not target_node.location:
        return changed_entities
    target_node = _resolve_graph_node(graph, target_node)
    file_path = _relative_file_path(graph, target_node)
    node_name = _clean_entity_name(target_node.name)
    if target_node.type in [NodeType.METHOD, NodeType.FUNCTION, NodeType.CONSTRUCTOR]:
        try:
            parent_node = graph.get_membership_parent(target_node)
        except Exception:
            parent_node = None
        if parent_node and parent_node.type in [NodeType.CLASS, NodeType.INTERFACE, NodeType.ENUM]:
            parent_name = _clean_entity_name(parent_node.name)
            changed_entities = f"{file_path}::{parent_name}.{node_name}"
        elif parent_node and parent_node.type == NodeType.FILE:
            changed_entities = f"{file_path}::{node_name}"
        else:
            changed_entities = f"{file_path}::{node_name}"
    elif target_node.type in [NodeType.CLASS, NodeType.INTERFACE, NodeType.ENUM]:
        changed_entities = f"{file_path}::{node_name}"
    elif target_node.type == NodeType.FILE:
        changed_entities = f"{file_path}"
    return changed_entities


def _resolve_graph_node(graph, target_node):
    if target_node in graph.graph:
        return target_node
    target_path = str(target_node.location.file_path) if target_node.location else ""
    for candidate in graph.graph.nodes:
        if candidate.type != target_node.type or candidate.name != target_node.name:
            continue
        candidate_path = str(candidate.location.file_path) if candidate.location else ""
        if candidate_path == target_path:
            return candidate
        if candidate_path.endswith(target_path) or target_path.endswith(candidate_path):
            return candidate
    return target_node


def _relative_file_path(graph, target_node) -> str:
    file_path = target_node.location.file_path
    try:
        rel_path = str(file_path.relative_to(graph.repo_path))
    except Exception:
        rel_path = str(file_path)
    rel_path = rel_path.replace("\\", "/").lstrip("./")
    repo_name = getattr(graph.repo_path, "name", "")
    if repo_name and rel_path.startswith(f"{repo_name}/"):
        return rel_path[len(repo_name) + 1:]
    return rel_path


def _clean_entity_name(name: str) -> str:
    return str(name).split("::")[-1]


def get_graph_results(cig, rdfs_graph):
    _ = rdfs_graph
    return cig


def convert_results(cig_graph, rdfs_graph):
    graph = get_graph_results(cig_graph, rdfs_graph)
    return convert_nodes_to_results(
        [
            code_element
            for factor in graph.nodes
            for code_element in graph.nodes[factor].get("code_element", [])
        ],
        rdfs_graph,
    )


def convert_nodes_to_results(nodes, rdfs_graph, already_reformatted=False):
    results = {"found_files": [], "found_modules": [], "found_functions": []}
    node_list = []
    for code_element in nodes:
        if isinstance(code_element, Node):
            node_list.append(code_element)
        elif isinstance(code_element, str):
            node_list.extend(node_deserialization(code_element))

    for max_code_entity in node_list:
        if not already_reformatted:
            new_name = reformat_entity_name(rdfs_graph, max_code_entity)
            if not new_name:
                continue
        else:
            new_name = max_code_entity.name
        if max_code_entity.type in [NodeType.METHOD, NodeType.FUNCTION, NodeType.CONSTRUCTOR]:
            if "::" not in new_name:
                continue
            file_path = new_name.split("::", 1)[0]
            entity_name = new_name.split("::", 1)[1]
            if "." in entity_name:
                module_name = f"{file_path}::{'.'.join(entity_name.split('.')[:-1])}"
                if module_name not in results["found_modules"]:
                    results["found_modules"].append(module_name)
            if new_name not in results["found_functions"]:
                results["found_functions"].append(new_name)
            if file_path not in results["found_files"]:
                results["found_files"].append(file_path)
        elif max_code_entity.type in [NodeType.CLASS, NodeType.INTERFACE, NodeType.ENUM]:
            if "::" not in new_name:
                continue
            file_path = new_name.split("::", 1)[0]
            if new_name not in results["found_modules"]:
                results["found_modules"].append(new_name)
            if file_path not in results["found_files"]:
                results["found_files"].append(file_path)
        elif max_code_entity.type == NodeType.FILE:
            file_name = new_name
            if file_name not in results["found_files"]:
                results["found_files"].append(file_name)
    return results


def has_any_result(results) -> bool:
    return any(results.get(key) for key in ("found_files", "found_modules", "found_functions"))

import json
import Levenshtein
import networkx as nx
from IPython.utils.capture import capture_output
from IPython.terminal.interactiveshell import TerminalInteractiveShell
from rdfs.dependency_graph.models.graph_data import NodeType


def string_distance(str1: str, str2: str) -> int:
    str1 = str1.lower()
    str2 = str2.lower()
    if str1.endswith('.py') or str1.endswith('.java'):
        str1 = str1.removesuffix('.py').removesuffix('.java')
    if str2.endswith('.py') or str2.endswith('.java'):
        str2 = str2.removesuffix('.py').removesuffix('.java')
    if str1 in str2 or str2 in str1:
        return 0
    else:
        return Levenshtein.distance(str1, str2) / max(len(str1), len(str2))


def search_node(graph: nx.MultiDiGraph, node_type: str, node_name: str, top_k=5):
    # mix method and Function
    if node_type == "METHOD":
        node_type = "FUNCTION"

    if node_type == "*" and node_name != "*":
        res = [v.to_json() for v in graph.nodes if (v.name == node_name or v.name.split('.')[0] == node_name)]
        if len(res) == 0:
            res_all = [(v, string_distance(v.name, node_name)) for v in graph.nodes]
            res_all.sort(key=lambda x: x[1])
            res = [node[0].to_json() for node in res_all[0:5]]
        return "\n".join(res)
    elif node_type != "*" and node_name == "*":
        # A wildcard name can match thousands of fields/functions in large
        # repositories. Return a bounded sample so one broad tool call cannot
        # overflow the LLM context during relevance filtering.
        return "\n".join([v.to_json() for v in graph.nodes if v.type == node_type][:top_k])
    elif node_type != "*" and node_name != "*":
        if node_type == "BODY":
            res = [v.to_json() for v in graph.nodes if v.type in ["METHOD", "FUNCTION"] and node_name in v.content]
            if len(res) == 0:
                res_all = [(v, string_distance(v.content, node_name)) for v in graph.nodes if v.type in ["METHOD", "FUNCTION"]]
                res_all.sort(key=lambda x: x[1])
                res = [node[0].to_json() for node in res_all[0:5]]
            return "\n".join(res)
        else:
            res = [v.to_json() for v in graph.nodes if (v.name == node_name or v.name.split('.')[0] == node_name) and v.type == node_type]
            if len(res) == 0:
                res_all = [(v, string_distance(v.name, node_name)) for v in graph.nodes if v.type == node_type]
                res_all.sort(key=lambda x: x[1])
                res = [node[0].to_json() for node in res_all[0:top_k]]
            return "\n".join(res)
    else:
        raise ValueError("Search Error: both the node type and node same is set to wildcard.")


def search_edge(graph: nx.MultiDiGraph, src_node_type, src_node_name, edge_type, trg_node_type, trg_node_name, top_k=5):
    if src_node_type == "METHOD":
        src_node_type = "FUNCTION"
    if trg_node_type == "METHOD":
        trg_node_type = "FUNCTION"
    edge_list = []
    if trg_node_type == "BODY" and edge_type == "HasMember":
        if trg_node_name == "*":
            return ""
        if src_node_name == "*":
            res = [v for v in graph.nodes if v.type in ["METHOD", "FUNCTION"] and trg_node_name in v.content]
            for node in res:
                edge_list.append(json.dumps({"src_node": node.to_json(), "trg_node": node.to_json(), "edge": {"relation": "HasMember"}}))
        else:
            res = [v for v in graph.nodes if v.type in ["METHOD", "FUNCTION"] and (v.name == src_node_name or v.name.split('.')[0] == src_node_name) and trg_node_name in v.content]
            if len(res) == 0:
                return ""
            for node in res:
                edge_list.append(json.dumps({"src_node": node.to_json(), "trg_node": node.to_json(), "edge": {"relation": "HasMember"}}))
    else:
        for edge in graph.edges(data="relation"):
            src_node = edge[0]
            trg_node = edge[1]
            relation = edge[2].relation.value
            if src_node.type == NodeType.VIRTUAL_CLASS:
                src_node = [v for v in nx.predecessor(graph, src_node)][0]
            if trg_node.type == NodeType.VIRTUAL_CLASS:
                trg_node = [v for v in nx.neighbors(graph, trg_node)][0]
            if src_node.type == NodeType.METHOD or src_node.type == NodeType.FUNCTION:
                curr_src_node_type = NodeType.FUNCTION
            else:
                curr_src_node_type = src_node.type
            if trg_node.type == NodeType.METHOD or trg_node.type == NodeType.FUNCTION:
                curr_trg_node_type = NodeType.FUNCTION
            else:
                curr_trg_node_type = trg_node.type
            if (src_node_type == "*" or curr_src_node_type == src_node_type) and \
            (src_node_name == "*" or src_node.name == src_node_name) and \
            edge_type == relation and \
            (trg_node_type == "*" or curr_trg_node_type == trg_node_type) and \
            (trg_node_name == "*" or trg_node.name == trg_node_name):
                edge_list.append(json.dumps({"src_node": src_node.to_json(), "trg_node": trg_node.to_json(), "edge": edge[2].to_json()}))
            elif (src_node_type == "*" or curr_src_node_type == src_node_type) and \
            (src_node_name == "*" or src_node.name == src_node_name) and \
            edge_type == relation and \
            (trg_node_type == "BODY") and \
            (trg_node_name == "*" or trg_node_name in trg_node.content):
                edge_list.append(json.dumps({"src_node": src_node.to_json(), "trg_node": trg_node.to_json(), "edge": edge[2].to_json()}))
    return "\n".join(edge_list[:top_k])



def execute_search(code, graph, top_k=5):
    ipython_shell = TerminalInteractiveShell.instance()

    ipython_shell.user_ns['search_node'] = lambda *args, **kwargs: search_node(*args, **kwargs, top_k=top_k)
    ipython_shell.user_ns['search_edge'] = lambda *args, **kwargs: search_edge(*args, **kwargs, top_k=top_k)
    ipython_shell.user_ns['graph'] = graph
    with capture_output() as captured:
        ipython_shell.run_cell(code)

    output = ''
    if captured.stdout:
        output += captured.stdout
    if captured.stderr:
        output += captured.stderr

    return output if output else None

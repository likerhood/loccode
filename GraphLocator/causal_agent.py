import re
import networkx as nx
from ast import literal_eval
from llms import get_llm_response
from prompts.causal_agent_prompt import *
from rdfs.dependency_graph.models.graph_data import NodeType
from utils.string_processing import node_to_json


INITIAL_ELEMENT_LIMIT = 80
UPDATE_ELEMENT_LIMIT = 60
NODE_CONTENT_CHAR_LIMIT = 1200
UPDATE_NODE_CONTENT_CHAR_LIMIT = 800
CODE_ELEMENT_LIST_CHAR_BUDGET = 120000
EXISTING_GRAPH_CODE_ELEMENT_LIMIT = 5


NODE_TYPE_PRIORITY = {
    NodeType.METHOD: 80,
    NodeType.FUNCTION: 80,
    NodeType.CONSTRUCTOR: 80,
    NodeType.CLASS: 70,
    NodeType.INTERFACE: 70,
    NodeType.ENUM: 65,
    NodeType.STRUCTURE: 65,
    NodeType.FIELD: 40,
    NodeType.GLOBAL_VAR: 35,
    NodeType.FILE: 20,
}

class CausalAgent:

    def __init__(self, model_name: str, repo_graph, max_turn=20):
        self.model_name = model_name
        self.causal_graph = nx.DiGraph()
        self.repo_graph = repo_graph
        self.max_turn = max_turn
        self.messages = []
        self.messages.append({
            "role": "system",
            "content": SYSTEM_PROMPT
        })
        
    def parse_mermaid_to_networkx(self, mermaid_str, node_list):
        selected_nodes = []
        G = nx.DiGraph()
        pattern = re.compile(
            r'(?P<source>\w+)\[(?P<source_name>[^<]+)<br>Code Elements: \[(?P<source_code>[^\]]*)\]\]'
            r'\s*-->\|(?P<weight>[\d.]+)\|\s*'
            r'(?P<target>\w+)(?:\[[^\]]*\])?'
        )
        for line in mermaid_str.split('\n'):
            line = line.strip()
            if not line or line.startswith('graph'):
                continue

            match = pattern.match(line)
            if match:
                groups = match.groupdict()
                code_elements = []
                if groups['source'] not in self.causal_graph:
                    if groups['source_code']:
                        try:
                            code_elements_id = literal_eval(f"[{groups['source_code']}]")
                            if not isinstance(code_elements_id, list):
                                code_elements_id = [code_elements_id]
                            code_elements = [node_list[int(ce_id) - 1] for ce_id in code_elements_id]
                            for ce_id in code_elements_id:
                                selected_nodes.append(node_list[int(ce_id) - 1])
                        except:
                            code_elements = []
                if groups['source'] not in G:
                    G.add_node(
                        groups['source'],
                        name=groups['source_name'].strip(),
                        code_element=code_elements
                    )
                if groups['target'] not in G:
                    G.add_node(groups['target'], name='Issue', code_element=[])
                G.add_edge(
                    groups['source'],
                    groups['target'],
                    weight=float(groups['weight'])
                )
        if len(self.causal_graph.nodes) != 0:
            for v in self.causal_graph.nodes:
                if v in G.nodes:
                    G.nodes[v]['name'] = self.causal_graph.nodes[v]['name']
                    for element in self.causal_graph.nodes[v]['code_element']:
                        if element not in G.nodes[v]['code_element']:
                            G.nodes[v]['code_element'].append(element)
                else:
                    G.add_node(v, name=self.causal_graph.nodes[v]['name'], code_element=self.causal_graph.nodes[v]['code_element'])
            for x, y, data in self.causal_graph.edges(data=True):
                weight = data.get('weight', 1.0)
                if not G.has_edge(x, y):
                    G.add_edge(x, y, weight=weight)

        new_factors = []
        for v in G.nodes:
            if v not in self.causal_graph.nodes:
                new_factors.append(v)
        return G, new_factors, selected_nodes

    def networkx_to_mermaid(self):
        mermaid_lines = ["graph TD"]
        processed_nodes = set()
        for u, v, data in self.causal_graph.edges(data=True):
            weight = data.get('weight', 1.0)

            if u not in processed_nodes:
                u_name = self.causal_graph.nodes[u].get('name', f'Node {u}')
                mermaid_lines.append(f'    {u}[{u_name}] -->|{weight}| ')
                processed_nodes.add(u)
            else:
                mermaid_lines.append(f'    {u} -->|{weight}| ')

            if v not in processed_nodes:
                v_name = self.causal_graph.nodes[v].get('name', f'Node {v}')
                v_code = ', '.join(map(str, self.causal_graph.nodes[v].get('code_element', [])))
                mermaid_lines[-1] += f'{v}[{v_name}]'
                processed_nodes.add(v)
            else:
                mermaid_lines[-1] += f'{v}'

        for node in self.causal_graph.nodes:
            mermaid_lines.append(f"Node {node}:")
            for code_element in self.causal_graph.nodes[node]['code_element'][:EXISTING_GRAPH_CODE_ELEMENT_LIMIT]:
                if code_element.location:
                    mermaid_lines.append(f"Location in repository: {code_element.location.file_path}")
                    mermaid_lines.append(
                        f"Name: {code_element.name}; Type: {getattr(code_element, 'type', '')}"
                    )
            if len(self.causal_graph.nodes[node]['code_element']) > EXISTING_GRAPH_CODE_ELEMENT_LIMIT:
                hidden = len(self.causal_graph.nodes[node]['code_element']) - EXISTING_GRAPH_CODE_ELEMENT_LIMIT
                mermaid_lines.append(f"...[{hidden} more code elements omitted]")

        return '\n'.join(mermaid_lines)

    def _get_factor_priority(self, factor):
        weights = [
            data.get('weight', 1.0)
            for _, _, data in self.causal_graph.out_edges(factor, data=True)
        ]
        return max(weights) if weights else None

    def _keywords(self, issue_description):
        return {
            token.lower()
            for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", issue_description or "")
            if len(token) > 2
        }

    def _node_path(self, node):
        if not getattr(node, "location", None) or not node.location.file_path:
            return ""
        return str(node.location.file_path).lower()

    def _node_score(self, node, keywords, anchor_paths=None):
        anchor_paths = anchor_paths or set()
        name = str(getattr(node, "name", "") or "").lower()
        path = self._node_path(node)
        content = str(getattr(node, "content", "") or "").lower()
        score = NODE_TYPE_PRIORITY.get(getattr(node, "type", None), 10)
        score += sum(3 for token in keywords if token in name)
        score += sum(2 for token in keywords if token in path)
        score += sum(1 for token in keywords if token in content[:4000])
        if path and path in anchor_paths:
            score += 25
        elif path and any(path == anchor or path.endswith(anchor) or anchor.endswith(path) for anchor in anchor_paths):
            score += 15
        return score

    def _rank_and_limit_nodes(self, nodes, issue_description, limit, anchor_nodes=None):
        keywords = self._keywords(issue_description)
        anchor_paths = {self._node_path(node) for node in (anchor_nodes or []) if self._node_path(node)}
        unique_nodes = []
        seen = set()
        for node in nodes:
            key = (
                getattr(node, "type", None),
                getattr(node, "name", None),
                str(node.location.file_path) if getattr(node, "location", None) else "",
            )
            if key in seen:
                continue
            seen.add(key)
            unique_nodes.append(node)
        unique_nodes.sort(
            key=lambda node: self._node_score(node, keywords, anchor_paths),
            reverse=True,
        )
        return unique_nodes[:limit]

    def _format_code_elements(self, nodes, content_limit):
        lines = []
        total_chars = 0
        for ith, node in enumerate(nodes):
            line = f"#Code element {ith + 1}: " + node_to_json(
                node,
                max_content_chars=content_limit,
            )
            if total_chars + len(line) > CODE_ELEMENT_LIST_CHAR_BUDGET:
                omitted = len(nodes) - ith
                lines.append(f"...[{omitted} code elements omitted due to prompt budget]")
                break
            lines.append(line)
            total_chars += len(line)
        return "\n".join(lines)

    def _fallback_graph_from_nodes(self, nodes):
        self.causal_graph = nx.DiGraph()
        self.causal_graph.add_node("I", name="Issue", code_element=[])
        for index, node in enumerate(nodes[:5]):
            factor = f"F{index + 1}"
            self.causal_graph.add_node(
                factor,
                name=f"Candidate code element {index + 1}",
                code_element=[node],
            )
            self.causal_graph.add_edge(factor, "I", weight=max(0.1, 1.0 - index * 0.1))
        return self.causal_graph

    def generate_causal_graph(self, issue_description, node_list):
        node_list = self._rank_and_limit_nodes(
            node_list,
            issue_description,
            INITIAL_ELEMENT_LIMIT,
        )
        element_str_list = self._format_code_elements(node_list, NODE_CONTENT_CHAR_LIMIT)
        self.messages.append({"role": "user",
                            "content": f"{GENERATE_CAUSAL_GRAPH_INSTRUCTION}\n# Issue Description:\n{issue_description}\n# Code Element List:\n{element_str_list}"})
        
        try:
            response = get_llm_response(self.model_name, self.messages, with_tool=False)
        except Exception as e:
            print(f"Causal graph initial generation failed: {e}; falling back to seed nodes.")
            return self._fallback_graph_from_nodes(node_list)
        self.messages.append({"role": "assistant",
                            "content": response[0][0]['content']})
        self.causal_graph, new_factors, selected_node = self.parse_mermaid_to_networkx(response[0][0]['content'], node_list)

        visited = set()
        for node in selected_node:
            visited.add(node)

        priority_queue = []
        for v in self.causal_graph.nodes:
            if v != 'I':
                priority = self._get_factor_priority(v)
                if priority is not None:
                    priority_queue.append((v, priority))
        priority_queue.sort(key=lambda x: -x[1])
        res = []
        turn = 0
        while len(priority_queue) != 0:
            print(self.networkx_to_mermaid())
            if turn > self.max_turn:
                print("Max turn reached, stopping.")
                break
            factor, score = priority_queue.pop(0)
            to_be_visited_nodes = list()
            for node in self.causal_graph.nodes[factor]['code_element']:
                self.repo_graph.incremental_add_dependency(node)
                one_hop_neighbors = set(self.repo_graph.repo_graph.graph.predecessors(node)) | set(self.repo_graph.repo_graph.graph.successors(node))
                for neighbor in one_hop_neighbors:
                    if neighbor not in to_be_visited_nodes and neighbor not in visited:
                        to_be_visited_nodes.append(neighbor)
            to_be_visited_nodes = self._rank_and_limit_nodes(
                to_be_visited_nodes,
                issue_description,
                UPDATE_ELEMENT_LIMIT,
                anchor_nodes=self.causal_graph.nodes[factor]['code_element'],
            )
            if len(to_be_visited_nodes) == 0:
                print(f"No unvisited graph neighbors for factor {factor}; skip refinement.")
                turn += 1
                continue
            element_str_list = self._format_code_elements(
                to_be_visited_nodes,
                UPDATE_NODE_CONTENT_CHAR_LIMIT,
            )
            update_prompt = (
                f"{UPDATE_CAUSAL_GRAPH_INSTRUCTION}\n# Issue Description:\n{issue_description}"
                f"\n#Existing causal graph:\n{self.networkx_to_mermaid()}"
                f"\n# Factor to be refined:{factor} [{self.causal_graph.nodes[factor]['name']}]"
                f"\n# New Code Element List:\n{element_str_list}"
            )
            try:
                response = get_llm_response(
                    self.model_name,
                    [{"role": "user", "content": update_prompt}],
                    with_tool=False,
                )
            except Exception as e:
                print(f"Causal graph refinement failed for factor {factor}: {e}; skip this factor.")
                turn += 1
                continue
            self.messages.append({"role": "assistant",
                                "content": response[0][0]['content']})
            self.causal_graph, new_factors, selected_node = \
            self.parse_mermaid_to_networkx(response[0][0]['content'], to_be_visited_nodes)
            turn += 1
            if turn > self.max_turn:
                break

            for new_factor in new_factors:
                prob_list = [data.get('weight', 1.0) for _, _, data in self.causal_graph.out_edges(new_factor, data=True)]
                if len(prob_list) != 0:
                    priority_queue.append((new_factor, max(prob_list)))
            for node in selected_node:
                visited.add(node)
            priority_queue.sort(key=lambda x: -x[1])


        return self.causal_graph

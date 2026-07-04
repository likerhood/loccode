from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk

GET_SEED_LOC_INSTRUCTION="""
# Task:
You will be provided with a GitHub problem description and you have a hierarchical graph representation of current code repository that includes the following levels: DIRECTORY, FILE, CLASS, METHOD, FUNCTION, FIELD, and so on. The relationship between these levels is expressed using `HasMember`.
Your objective is to localize the specific files, classes, functions, or statement in this graph representation that require modification or contain essential information to resolve the issue.

1. Analyze the issue: Understand the problem described in the issue and identify what might be causing it.
2. List all potential keywords for searching from the issue and then call retrieval-based tools one by one.
3. If there are no any other keywords to search, use the Finish tool to indicate the end of the search.
4. Do not use the \'.\' in the search name.
"""


IS_RELEVANT_INSTRUCTION = """
# Task:
Please look through the following GitHub problem description and the code element list.
Your objective is to judge whether each code element is the cause of the issue.

1. Analyze the issue: Understand the problem described in the issue and analyze the code elements what may cause it.
2. For each code element, if it is selected as **irrelevant** to resolve the issue, return **False**, otherwise return **True**. Results should be separated by new lines and wrapped with ```
3. Only use the markdown code block format to return the results, without additional text. Do not use it in explanation.
For example:
```
True
False
```
"""


_SEARCHNODETOOL_DESCRIPTION = """Search the codebase to retrieve relevant code element based on given queries(code element type and name).
** Note:
- Either `node_type` or `node_name` must be provided to perform a search.
- The `node_type` must be chosen from [DIRECTORY, FILE, CLASS, METHOD, FUNCTION, FIELD, BODY], where BODY signifies function or method body.
- If the you are note sure for part of the parameters, you can use "*" to represent a wildcard, which will match any type or name.

** Example Usage:
# Search for a file `myfile.py`
search_node(node_type='FILE', node_name='myfile.py')

# Search for a class
search_node(node_type='CLASS', node_name='MyClass')

# Search for all nodes whose name is `TargetName`
search_node(node_type='*', node_name='TargetName')
"""


_SEARCHEDGETOOL_DESCRIPTION = """Search the codebase to retrieve a set of pairs of code elements that has a specific dependency relationship.
** Note:
- At least one of the parameters is provided to perform a search.
- The `node_type` must be chosen from [DIRECTORY, FILE, CLASS, METHOD, FUNCTION, FIELD, BODY], where BODY signifies function or method body.
- The `edge_type` must be chosen from [ImportedBy, BaseClassOf, UsedBy, HasMember, ImplementedBy].
- `src_node_type` `src_node_name` `edge_type` `trg_node_type` `trg_node_name` represents that `src_node_name` of type `src_node_type` is `edge_type` `trg_node_name` of type `trg_node_type`.
- If the you are note sure for part of the parameters, you can use "*" to represent a wildcard, which will match any type or name.

** Example Usage:
# Search for a class `MyClass` has a method member `MyFunc`
search_edge(src_node_type='CLASS', src_node_name='MyClass', edge_type='HasMember', trg_node_type='METHOD', trg_node_name='MyFunc')

# Search for all functions that use the function `MyFunc`
search_edge(src_node_type='FUNCTION', src_node_name='MyFunc', edge_type='UseBy', trg_node_type='FUNCTION', trg_node_name='*')

# Search for a method that has exception in its body
search_edge(src_node_type='METHOD', src_node_name='*', edge_type='HasMember', trg_node_type='BODY', trg_node_name='Exception')
"""

SearchNodeTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='search_node',
        description=_SEARCHNODETOOL_DESCRIPTION,
        parameters={
            'type': 'object',
            'properties': {
                'node_type': {
                    'type': 'string',
                    'description': 'The node type to search for within the codebase. ' \
                                   'The value must be chosen from [DIRECTORY, FILE, CLASS, METHOD, FUNCTION, FIELD, BODY] '\
                                   'If the you are note sure for the node type, you can use "*" to represent a wildcard, which will match any node type.'
                },
                'node_name': {
                    'type': 'string',
                    'description': 'Specific node name to locate corresponding code element of type node_type within codebase. '\
                                    'It is must be provided to perform a search.'
                                    'Note that if the name has \' or \", use the escape character to ensure a correct string search',
                },
            },
            'required': [],
        },
    ),
)

SearchEdgeTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='search_edge',
        description=_SEARCHEDGETOOL_DESCRIPTION,
        parameters={
            'type': 'object',
            'properties': {
                'src_node_type': {
                    'type': 'string',
                    'description': 'The source node type to search for within the codebase. ' \
                                   'The value must be chosen from [DIRECTORY, FILE, CLASS, METHOD, FUNCTION, FIELD, BODY] '\
                                   'If the you are note sure for the node type, you can use "*" to represent a wildcard, which will match any node type.'
                },
                'src_node_name': {
                    'type': 'string',
                    'description': 'The source node name to locate corresponding code element of type node_type within codebase. '
                                   'If the you are note sure for the node type, you can use "*" to represent a wildcard, which will match any node name.'
                                   'Note that if the name has \' or \", use the escape character to ensure a correct string search.'

                },
                'edge_type': {
                    'type': 'string',
                    'description': 'The edge type that point from source node to the target node. ' \
                                   'The value must be chosen from [ImportedBy, BaseClassOf, UsedBy, HasMember, ImplementedBy] '
                                   'If the you are note sure for the node type, you can use "*" to represent a wildcard, which will match any edge type.'
                },
                'trg_node_type': {
                    'type': 'string',
                    'description': 'The target node type to search for within the codebase. ' \
                                   'The value must be chosen from [DIRECTORY, FILE, CLASS, METHOD, FUNCTION, FIELD, BODY] ' \
                                   'If the you are note sure for the node type, you can use "*" to represent a wildcard, which will match any node type.'
                },
                'trg_node_name': {
                    'type': 'string',
                    'description': 'The target node name to locate corresponding code element of type node_type within codebase. '
                                   'If the you are note sure for the node type, you can use "*" to represent a wildcard, which will match any node name.'
                },
            },
            'required': [],
        },
    ),
)


_FINISH_DESCRIPTION = """Finish the interaction when the task is complete OR if the assistant cannot proceed further with the task."""

FinishTool = ChatCompletionToolParam(
    type='function',
    function=ChatCompletionToolParamFunctionChunk(
        name='finish',
        description=_FINISH_DESCRIPTION,
        parameters={
            'type': 'object',
            'properties': {
                'finished': {
                    'type': 'boolean',
                    'description': 'Set to be True if the interaction is finished.'
                }
            }
        },
    ),
)
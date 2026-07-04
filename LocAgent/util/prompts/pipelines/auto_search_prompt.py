TASK_INSTRUECTION="""
Given the following GitHub problem description, your objective is to localize the specific files, classes or functions, and lines of code that need modification or contain key information to resolve the issue.

Follow these steps to localize the issue:
## Step 1: Categorize and Extract Key Problem Information
 - Classify the problem statement into the following categories:
    Problem description, error trace, code to reproduce the bug, and additional context.
- Identify modules in the '{package_name}' package mentioned in each category.
- Use extracted keywords and line numbers to search for relevant code references for additional context.
- When using retrieval tools, never call `search_code_snippets` with empty arguments. Always provide concrete `search_terms` or `line_nums`.
- For JavaScript/TypeScript/frontend repositories, search JS/TS/JSX/TSX files first. For example:
  `search_code_snippets(search_terms=["route", "component", "state"], file_path_or_pattern="**/*")`.

## Step 2: Locate Referenced Modules
- Accurately determine specific modules
    - Explore the repo to familiarize yourself with its structure.
    - Analyze the described execution flow to identify specific modules or components being referenced.
- Pay special attention to distinguishing between modules with similar names using context and described execution flow.
- Output Format for collected relevant modules:
    - Use the format: 'file_path:QualifiedName'
    - E.g., for a function `calculate_sum` in the `MathUtils` class located in `src/helpers/math_helpers.py`, represent it as: 'src/helpers/math_helpers.py:MathUtils.calculate_sum'.

## Step 3: Analyze and Reproducing the Problem
- Clarify the Purpose of the Issue
    - If expanding capabilities: Identify where and how to incorporate new behavior, fields, or modules.
    - If addressing unexpected behavior: Focus on localizing modules containing potential bugs.
- Reconstruct the execution flow
    - Identify main entry points triggering the issue.
    - Trace function calls, class interactions, and sequences of events.
    - Identify potential breakpoints causing the issue.
    Important: Keep the reconstructed flow focused on the problem, avoiding irrelevant details.

## Step 4: Locate Areas for Modification
- Locate specific files, functions, or lines of code requiring changes or containing critical information for resolving the issue.
- Consider upstream and downstream dependencies that may affect or be affected by the issue.
- If applicable, identify where to introduce new fields, functions, or variables.
- Think Thoroughly: List multiple potential solutions and consider edge cases that could impact the resolution.

## Output Format for Final Results:
Your final output should list the locations requiring modification, wrapped with triple backticks ```
Each location should use this three-level structure whenever evidence is available:
1. exact file path
2. `class: ClassName` or `function: functionName` / `function: ClassName.methodName`
3. `line: 123` or `line: 123-140`
Do not return file-only locations unless no function, class, or line evidence is available.
Prefer exact functions/classes/lines observed from tool outputs or repository structure.
Your answer would better include about 5 files.
Use exact repository paths returned by tools. Do not invent paths. File paths may be Python, JavaScript, TypeScript, JSX/TSX, Java, CSS, or other languages.
Only output paths that were observed from retrieval results or exact repository structure. If a guessed path is not an exact repository path, replace it with the closest exact path returned by tools or omit it.
The final answer must be concise: output only the ranked locations in one code block, without explanations, dependency analysis, or search plans.

### Examples:
```
full_path1/file1.py
line: 10
class: MyClass1
function: my_function1

full_path2/file2.py
line: 76
function: MyClass2.my_function2

full_path3/file3.py
line: 24
line: 156
function: my_function3

client/components/example.jsx
function: ExampleComponent

src/utils/example.ts
line: 42
```

Return just the location(s)

Note: Your thinking should be thorough and so it's fine if it's very long.
"""

FAKE_USER_MSG_FOR_LOC = (
    'Verify that the final locations are exact repository paths returned by tools or repository structure. '
    'Do not include guessed paths, explanations, dependency analysis, or search plans in the final answer.\n'
    'Use the three-level format: file path, then class/function if known, then line if known. '
    'Do not return file-only locations unless no function/class/line evidence is available.\n'
    'If you have enough evidence, send only a concise ranked code block of locations and then finish with exactly:\n<function=finish>\n</function>\n'
    'If evidence is insufficient, run one narrower search with concrete search_terms and a specific file_path_or_pattern.\n'
    'IMPORTANT: YOU SHOULD NEVER ASK FOR HUMAN HELP.\n'
)

# GALA: Multimodal Graph Alignment for Bug Localization in Automated Program Repair

Zhuoyao Liu\* Sichuan University Chengdu, China liuzhuoyao@stu.scu.edu.cn

Yang Liu Sichuan University Chengdu, China liuyyy111@gmail.com Zhengran Zeng\*
Peking University
Beijing, China
zhengranzeng@stu.pku.edu.cn

Shikun Zhang Peking University Beijing, China zhangsk@pku.edu.cn Shudong Huang Sichuan University Chengdu, China huangsd@scu.edu.cn

Wei Ye<sup>†</sup> Peking University Beijing, China wye@pku.edu.cn

#### **Abstract**

Large Language Model (LLM)-based Automated Program Repair (APR) has shown strong potential on textual benchmarks, yet struggles in multimodal scenarios where bugs are reported with GUI screenshots. Existing methods typically convert images into plain text, which discards critical spatial relationships and causes a severe disconnect between visual observations and code components. Consequently, localization degrades into imprecise keyword matching. To bridge this gap, we propose GALA (Graph Alignment for Localization in APR), a framework that shifts multimodal APR from implicit semantic guessing to explicit structural reasoning. GALA operates in four stages: first, it constructs an Image UI Graph to capture visual elements and their structural relationships. Second, it performs file-level alignment by cross-referencing this UI graph with repository-level structures (e.g., file references) to locate candidate files. Third, it conducts function-level alignment by reasoning over fine-grained code dependencies (e.g., call graphs) to precisely ground visual elements to corresponding code components. Finally, conditioned on the aligned files and functions, it performs patch generation within the grounded code context. By systematically enforcing both semantic and relational consistency across modalities, GALA establishes a highly accurate visual-to-code mapping. Evaluations on the SWE-bench Multimodal benchmark demonstrate that GALA achieves state-of-the-art performance, highlighting the effectiveness of hierarchical structural alignment.

#### 1 Introduction

Automated Program Repair (APR) [16, 45, 46] aims to automatically identify and fix software defects, reducing human effort and improving software reliability. With the rapid advancement of large language models (LLMs), recent APR systems have achieved strong performance on real-world benchmarks[20, 23, 28] such as SWEbench[14]. However, these approaches are predominantly designed for unimodal settings, where both problem understanding and localization rely solely on textual inputs, including issue descriptions and source code

In modern software development, especially for front-end systems, bug reports often include visual artifacts such as graphical

<span id="page-0-0"></span>![](_page_0_Figure_15.jpeg)

Figure 1: Comparison between previous works on Multimodal APR and our proposed method.

user interface (GUI) screenshots. These visual signals provide critical information about layout, rendering, and interaction issues that cannot be fully captured by text alone. To address this, recent multimodal APR methods [10, 29] attempt to incorporate visual inputs. As illustrated in Figure 1 (top), their typical workflow leverages Vision Large Language Models (vLLMs) to translate bug screenshots into natural language descriptions. These textual descriptions are then injected as supplementary context into traditional, single-modal fault localization and repair pipelines. However, we argue that this paradigm suffers from two fundamental limitations:

- Loss of visual structural relationships: Translating images to text naturally discards the complex spatial and structural relationships among UI elements. For example, consider a UI issue where a search box overlaps with a text label. A caption-based approach may correctly recognize the keywords "search box" and "text label," but fails to capture the critical "overlap" interaction that defines the layout bug.
- Inaccurate localization from visual-code disconnect: Existing methods rely on implicit semantic keyword matching rather than structurally linking visual observations to the codebase. Consequently, given the previous overlapping issue, the model might retrieve unrelated files with similar semantics (e.g., text)

<sup>\*</sup>These authors contributed equally to this work.

<sup>&</sup>lt;sup>†</sup>Corresponding author.

rendering utilities) instead of targeting the actual layout components responsible for the bug across the file and function hierarchies.

To address these limitations, we propose GALA (Graph Alignment for Localization in APR), a framework that formulates multimodal localization as a structured cross-modal alignment problem. As shown in Figure [1](#page-0-0) (bottom), our method consists of three key stages designed to systematically bridge the modalities.

First, to explicitly preserve visual structures (addressing Limitation 1), we construct an Image UI Graph. By leveraging a Vision-Language Model (vLM) guided by the issue description, we extract key UI elements as graph nodes and their spatial or interactive relationships as edges, effectively capturing the topological context of the bug. Second, to overcome the visual-code disconnect (addressing Limitation 2), we perform file-level alignment. Instead of relying on isolated text matching, we model the repository context by extracting file paths and their inter-file reference relations. By feeding the textualized UI graph alongside this repository-level structural information into a Large Language Model (LLM), the model is able to cross-reference visual interactions with architectural dependencies to select candidate files. Third, we conduct function-level alignment within the selected files. We construct fine-grained code graphs containing function signatures and function call graphs. By jointly reasoning over the UI graph and these function-level structures, the LLM precisely grounds the visual elements to specific executable components.

Ultimately, by explicitly modeling structured representations across modalities and granularities, GALA transforms multimodal APR from implicit semantic guessing to explicit structural reasoning. This produces a highly accurate set of edit targets for downstream patch generation. Evaluated on the SWE-bench Multimodal benchmark, GALA achieves state-of-the-art performance, demonstrating the effectiveness of structure-aware alignment.

Our contributions are summarized as follows:

- We reformulate multimodal bug localization as a hierarchical cross-modal alignment problem across visual and code structures.
- We propose an image UI graph and multi-level code graphs to explicitly model both visual semantics and code dependencies.
- We design a hierarchical graph alignment mechanism that bridges visual elements to code components from file-level to functionlevel with both semantic and relational consistency.
- We demonstrate that our approach achieves superior performance on SWE-bench Multimodal, validating the effectiveness of structure-aware alignment for multimodal APR.

## 2 Related Work

## 2.1 LLM for Code Localization

Recent advances in Large Language Models (LLMs) have substantially improved bug localization by enabling deeper semantic understanding of both natural language issue descriptions and source code. Existing approaches can be broadly categorized into trainingbased models and prompt-based reasoning methods.

Training-based approaches learn to align bug reports with relevant code artifacts through supervised learning. For example, DNNLOC [\[15\]](#page-8-7) integrates multiple handcrafted and learned features, while FBL-BERT [\[7\]](#page-8-8) adopts a ColBERT-style late interaction mechanism to capture fine-grained token-level relevance. BLAZE [\[5\]](#page-8-9) further enhances retrieval via contrastive learning and dynamic chunking. Other neural approaches also explore learned representations for bug localization, highlighting the importance of finegrained semantic alignment between bug reports and code [\[1,](#page-8-10) [11\]](#page-8-11). However, these methods depend on task-specific training and frequent retraining, limiting scalability in evolving codebases.

Prompt-based approaches instead leverage the reasoning capability of LLMs without additional training, framing localization as a combination of retrieval and structured reasoning. Some methods directly rank relevant files or code snippets based on textual similarity [\[25\]](#page-8-12). Building on this, recent work introduces iterative reasoning that progressively refines candidate sets through multi-step exploration of repository contexts [\[13,](#page-8-13) [40\]](#page-8-14). Agent-based frameworks further extend this paradigm by enabling tool use, allowing LLMs to perform code search, file inspection, and hypothesis verification [\[3,](#page-8-15) [6,](#page-8-16) [18,](#page-8-17) [26\]](#page-8-18). To better capture repository-scale dependencies, several methods incorporate long-context modeling or repository-level memory [\[30,](#page-8-19) [33\]](#page-8-20), while others introduce structural representations such as code graphs to guide search and constrain the solution space [\[21\]](#page-8-21). However, these approaches remain largely unimodal and fail to capture structured visual semantics, limiting their effectiveness for multimodal software issues.

# 2.2 LLM/MLLM for APR

LLMs have also been widely explored for automated program repair (APR). Early approaches focus on function-level repair through fine-tuning [\[9,](#page-8-22) [12,](#page-8-23) [32,](#page-8-24) [34,](#page-8-25) [37,](#page-8-26) [38\]](#page-8-27) or prompting [\[4,](#page-8-28) [8,](#page-8-29) [17,](#page-8-30) [24,](#page-8-31) [39,](#page-8-32) [41,](#page-8-33) [44,](#page-8-34) [47,](#page-9-2) [49\]](#page-9-3). Recent works shift toward repository-level issue resolution, where agent-based frameworks enable LLMs to interact with execution environments and handle complex tasks [\[2,](#page-8-35) [22,](#page-8-36) [36,](#page-8-37) [48\]](#page-9-4). For example, SWE-agent [\[42\]](#page-8-38) builds on SWE-Bench [\[14\]](#page-8-4) and adopts an interactive agent paradigm for end-to-end issue resolution. Despite strong performance, these approaches are designed for unimodal settings and lack mechanisms to incorporate visual evidence.

A growing line of work extends APR to multimodal settings by incorporating visual inputs. Several emerging benchmarks have also explored multimodal software reasoning scenarios[\[19,](#page-8-39) [31\]](#page-8-40), highlighting the increasing importance of visual understanding in APR. Early frameworks such as Agentless [\[35\]](#page-8-41) and SWE-agent [\[42\]](#page-8-38) have been adapted to SWE-bench Multimodal, demonstrating competitive performance. OpenHands-Versa [\[27\]](#page-8-42) further integrates visual observations into the repair loop for grounded reasoning. GUIRepair [\[10\]](#page-8-5) leverages vision-language models to translate visual artifacts into executable reproduction scripts for localization and patch generation. SVRepair [\[29\]](#page-8-6) advances this direction by incorporating structured visual cues to improve performance. However, existing methods still rely on implicit or weakly structured visual representations, failing to explicitly model fine-grained UI elements and their relational dependencies. This leads to the loss of critical visual context and limits precise cross-modal reasoning. In contrast, our approach constructs a structured intermediate representation that explicitly models UI elements and their structural and relational dependencies, enabling more accurate cross-modal alignment

<span id="page-2-0"></span>![](_page_2_Figure_1.jpeg)

Figure 2: Architecture of GALA. The overall workflow consists of four key stages: (1) the Image Graph Construction module, which converts issue images into a problem-centric structured graph via type-aware parsing and rooted expansion; (2) the File-level Alignment module, which grounds visual semantics to the repository and identifies a compact set of seed files through structure-aware refinement; (3) the Function-level Alignment module, which performs cross-modal graph alignment to establish node- and relation-consistent correspondences between visual elements and code components, producing precise edit targets; and (4) the Graph-guided Patch Generation module, which leverages the aligned graph structure to constrain localization and generate minimal yet complete patches.

between visual evidence and code semantics, and improving both localization and repair.

#### 3 Method

#### 3.1 Overview

We propose GALA, a graph-based framework for multimodal bug localization and repair that bridges visual symptoms and code semantics through hierarchical graph alignment. As illustrated in Figure 2, given an issue description, its corresponding issue images, and the code repository, GALA follows a four-stage pipeline. First, we construct a problem-centric image graph to capture structured visual elements and their relationships. Second, we perform file-level alignment to identify a compact set of candidate files by grounding visual semantics into the repository structure and refining them into seed files. Third, we conduct function-level alignment within the selected files, where visual elements are grounded to finegrained code components through cross-modal graph alignment, producing precise edit targets. Finally, we perform graph-guided patch generation, where the repair process is constrained by the aligned graph structure, enabling targeted and reliable code modification. Each stage of this pipeline is instantiated through stage-wise simplified prompts, as illustrated in Figure 2.

## 3.2 Image Graph Construction

To enable structured visual reasoning, we construct an Image Graph that represents the input image as a problem-centric structured graph, as illustrated in Fig. 3. Formally, the image graph is defined

<span id="page-2-1"></span>![](_page_2_Figure_9.jpeg)

Figure 3: Example of the image graph constructed by GALA from alibaba-fusion\_next-4021(left: input image; right: image graph)

as  $G_v = (V_v, E_v)$ , where nodes  $V_v$  denote issue-relevant visual entities and edges  $E_v$  denote relations that are necessary for explaining the reported problem. Instead of directly extracting a global scene graph, our approach performs a type-aware and rooted graph construction process that retains only issue-relevant elements and their relations. This design is motivated by the observation that global visual parsing often introduces a large amount of irrelevant context, while bug understanding typically depends on a small set of semantically critical elements and their interactions.

**Image Type Identification.** Given an input image and the corresponding issue description, we first identify the high-level visual

type of the image using a vision-language model. Specifically, the model predicts one of five predefined categories—ui page, chart plot, code screenshot, document layout, or generic diagram. Outputs a discrete image type label to guide subsequent graph construction. This step establishes a type-specific structural prior. Different image types exhibit distinct structural patterns and salient elements (e.g., UI components in web pages versus data entities in charts), making a unified extraction strategy prone to introducing irrelevant structures. By conditioning on the predicted type, the model adapts its perception strategy to focus on task-relevant visual semantics, while the predicted type also constrains the candidate node categories and admissible relation patterns for graph construction.

Root Object Selection. We use a vision-language model (VLM) to identify a small set of root objects that serve as anchors of the graph, conditioned on the issue image, issue description, and the predicted image type from the previous stage. Conceptually, root object identification, supporting node expansion, and relation construction are defined as three constrained substeps, although they can be instantiated within a single structured VLM generation for efficiency. Root objects correspond to elements that are directly related to the issue, including: (i) objects affected by the bug, (ii) objects visually involved in the reported abnormality, and (iii) objects explicitly referenced in the issue description. As illustrated in Fig. 3, these root objects are highlighted by blue boxes and capture the key elements involved in the bug. We prioritize objects supported by both visual evidence and textual description, while also allowing visually evident abnormal objects when the textual description is underspecified. To improve reliability, each selected root object must be explicitly grounded in observable visual content and justified as issue-relevant; candidates lacking clear support are discarded. Each root object is associated with a justification explaining its relevance to the issue. This step establishes the semantic core of the graph and enforces a rooted structure, where subsequent nodes are introduced only to explain these anchors, preventing the graph from expanding into irrelevant visual regions.

**Supporting Node Expansion.** Conditioned on the identified root objects, the model further introduces additional nodes that are necessary to explain the issue within the same generation process. These supporting nodes provide minimal contextual information required for understanding the problem, including local context (e.g., neighboring UI components), structural context (e.g., containers or boundaries), and objects that participate in issue-relevant relations. As shown in Fig. 3, these supporting nodes are highlighted by yellow boxes and provide the minimal context needed to interpret the relationships among root objects. Rather than aiming for exhaustive scene coverage, node expansion is restricted to one-hop issue-relevant context that is indispensable for explaining the retained root objects and relations, ensuring that the resulting graph remains a localized, problem-centric substructure instead of a global scene representation. This design significantly reduces graph size and suppresses irrelevant visual context, which is critical for stabilizing downstream reasoning. Each node is accompanied by a textual rationale describing its role in the explanation.

**Relation Construction.** Within the same generation process, the vision-language model (VLM) further infers directed edges between the identified nodes to capture issue-relevant structural and functional relations. Each edge is defined as  $e_{ij} = (v_i, r, v_j)$ ,

where r denotes a relation label generated by the model according to the local visual structure and issue context. Edges are added only when the inferred relations are visually grounded and contribute to understanding the reported issue; uncertain or weakly supported relations are omitted. Rather than constructing a dense graph over all detected entities, relation generation is restricted to the smallest connected issue-relevant substructure centered on the most relevant UI components and their associated stateful elements. Consequently, the resulting graph preserves sparse but informative dependencies that support downstream code alignment. Each relation is further associated with a justification explaining both its visual evidence and its role in problem understanding. Together with node identification, this step completes the construction of a coherent, problem-centric image graph.

# 3.3 File-level Alignment

Given the constructed image graph, the goal of file-level alignment is to perform coarse cross-modal grounding at the repository level by identifying a compact set of files that are most likely related to the observed visual issue. As illustrated in Figure 2, this stage progressively reduces the search space from the full repository to a dependency-consistent seed file set by combining repository structure, issue-relevant visual semantics, and lightweight interfile relations. This coarse grounding step is designed to improve downstream localization efficiency while preserving the files most likely to contain the bug-related implementation.

Repository Grounding. We construct a repository snapshot for each target commit, and recursively traverse the repository to collect file paths. During traversal, we filter out irrelevant directories (e.g., <code>.git</code>, <code>node\_modules</code>, <code>dist</code>) and test related paths, and retain only repair relevant file types such as <code>JavaScript/TypeScript</code> files, style sheets, configuration files, and documentation. The retained file paths are then organized into a hierarchical directory structure (<code>repo tree</code>), which serves as a structured prompt input for subsequent candidate and seed file selection, enabling the model to reason over repository organization rather than treating files as an unstructured collection.

Visual Semantic Candidate Retrieval. However, repository structure alone does not indicate which files are relevant to the visual issue. To introduce problem-specific signals, we perform a semantics-guided candidate retrieval step by conditioning the model on the problem statement, the hierarchical repo tree derived from the filtered repository snapshot, and compact structured summaries of all image graphs in the instance. These summaries retain key nodes, edges, and issue-relevant reasons from the original image graphs, while serializing them into a compact text-friendly form that can be readily consumed by the text LLM, reducing the overhead of passing full JSON graphs as well as the context length and inference cost. The problem statement provides behavioral descriptions, and the repo tree constrains retrieval within the filtered repository structure. Based on these complementary inputs, the model retrieves a fixed-size candidate file set that is semantically consistent with the observed issue. This stage focuses on semantically grounding the search space before refinement, but does not yet explicitly dependencies between files; such structural evidence is introduced in the subsequent graph-based refinement step.

## Image Graph

#### <span id="page-4-0"></span>Prompt:

Build a compa ct rooted visual graph for the issue Issue Text:{issue text} Visual Evidence:{issue image}

- 1. Select root, objects: the visible entities most directly related to the issue. For each root object, briefly justify with issue text + visual evidence
- 2. Build nodes around the selected root\_objects and issue text: include root nodes plus only necessary supporting visible nodes that help explain the issue 3. Add edges only when relations are visually grounded and useful for issue understanding; omit uncertain relations.

Focus on the UI components that are most relevant to the issue, then expand outward through the smallest connected set of related stateful elements

#### Output:

"root nodes": [

{"id": "id given by LLM", "text": "The text within this node region. "reason": "Explanation of why this node is related with the solving issue ." }, 

{"id": "...", "text": "...", "reason": "..."}, {"id": "...", "text": "...", "reason": "..."}] edges":

- section label --labels--> numberpicker input.

## File Graph Alignment

## Prompt:

Select the most useful seed files for code localization. Use only the provided candidate files and supporting graph evidence. Return only valid JSON. Issue:{issue\_text} Image Graph:{image\_graph} File Graph:{file\_graph}

Task:

- 1. Read the issue and image graph, identify files likely related to the bug behavior.
- 2. Use the image graph and file graph to identify potential semantic node alignments, and prioritize files involved in edge-supported subgraph correspondences.
- 3. Return exactly {n} files when enough files exist, otherwise return all suitable files

#### Output:

"Candidate Files": { "src/hooks/button.js", "src/store/checkoutSlice.jsx", "..." }

## Function Graph Alignment

#### Prompt:

Align issue-relevant image graph anchors and relations to a UI-focused function graph. Use only the provided graph evidence. Return only valid JSON. Issue:{issue\_text} Image Graph:{image\_graph} Function Graph:{function\_graph}

- 1. Read the image graph summary directly and identify the most important root of issue-relevant image nodes.
- 2. Match image nodes to concrete code function nodes using the provided code node 'file' and 'name' fields.
- . Judge whether the image relations are reflected by local code graph relations

#### Output:

```
"anchor_matches": [{"image_node_id": "...", "code_node_id": "...", "reason": "..."}, {...}]
relation alignment": [
 eauti_aiginiear...
("image_edge": ("source": "","target": "","type": "edge type")
"code_edge": ("source": "...", "target": "...", "type": "...", },"reason": ""], {...}]
```

## Patch Generation

#### Prompt:

You are fixing a real repository bug. Inspect the codebase, and make the smallest correct code change that resolves the reported behavior. The final result should be an executable code change that can be captured as a git diff.

Bug Report: {{problem statement}} Visual Evidence:{{image graph summary}} Seed Files:{{localization\_guidance}} Edit function target:{{edit\_function\_target}} Working Approach:

By checking the Bug Report and visual evidence, understand the underlying code issue before making any edits.

Start from seed files and edit function targets, then expand only if needed Trace the relevant code path and verify decisions with code evidence. Make the smallest complete fix: avoid unrelated refactors or formatting-only edits. Edit only necessary files, and ensure the final patch is coherent and directly

## Output:

diff --git a/src/store/checkoutSlice.jsx b/src/store/checkoutSlice.jsx function validateEmail(state) {

- state.showEmailError = false;
- mailError = !state.email || !state.email.includes("@");

Figure 4: Stage-wise Simplified Prompt for GALA

## Structure aware Refinement via File Graph Alignment.

Within the same model call, we further introduce structural constraints by constructing a *candidate file graph* over the retrieved candidate file list, where nodes correspond to candidate files and edges represent inter-file dependencies derived from static import relationships. This graph enables structure aware reasoning beyond purely semantic matching. Building on this representation, the model refines the retrieved candidate file list into a compact set of seed files through a graph guided alignment step. Specifically, it jointly considers the problem statement, the image graph, and the candidate file graph, and prioritizes candidate files that are not only semantically relevant to the issue but also supported by consistent structural evidence. In particular, candidate files connected by supporting dependency relations in the file graph are favored over isolated matches. The model then returns a small fixed size set of seed files, which forms a dependency consistent subgraph likely to contain the bug and serves as the input for subsequent function level alignment.

# 3.4 Function-level Alignment

While file level alignment narrows the search space to a small set of seed files, it remains insufficient for precise localization, as individual files often contain multiple executable units with different responsibilities. We define alignment as identifying semantically compatible and structurally supported correspondences between issue-relevant image nodes and candidate code nodes within the induced code graph. To further bridge the gap between visual symptoms and executable code, we perform function-level alignment to align image graphs with the code structure and identify concrete edit targets. Formally, we define the function graph as  $G_c = (V_c, E_c)$ , where nodes  $V_c$  correspond to functions, component-level units, or class methods, and edges  $E_c$  encode UI-relevant interactions such as rendering, data propagation, and state updates.

UI-oriented Function Graph Construction. Given the selected seed files, we construct a closed-domain UI-oriented function graph within the seed files. We parse JavaScript/TypeScript source files in the seed set and extract three types of callable program units using fixed syntactic patterns, including function declarations, variable-assigned functions / arrow functions, and class methods, and normalize them into function-level nodes with identifiers, types, names, and file-level provenance. We then construct directed edges using regex/heuristic patterns with fixed triggers over function bodies, covering UI-relevant relations such as renders, calls, reads\_state, writes\_state, passes\_props, and applies\_style. For each source node, candidate target names are extracted from JSX component tags, call expressions, and state- or style-related symbols, and resolved in a fixed order: exact-name match within the same file, short-name match within the same file, and finally lookup through a seed-scoped symbol index. Edges are added when the referenced targets can be resolved to nodes inside the same seed-scoped graph; otherwise they are discarded, enforcing the closed-domain constraint. The resulting graph  $G_c = (V_c, E_c)$  provides a compact structural view of rendering logic, component interaction, and state transitions, and serves as the code-side input for subsequent cross-modal alignment and edit target identification.

Cross-modal Graph Alignment. Given the constructed function graph, we perform function-level alignment with the image graph through a structured cross-modal reasoning step. The model is conditioned on the problem statement, the image graph summary, and the function graph, as specified in the simplified prompt shown in Fig. [4,](#page-4-0) so that node semantics and typed relations are preserved for joint reasoning over visual and code structures. Pure semantic similarity is often insufficient for reliable grounding, as visually similar elements may correspond to structurally unrelated code components. We therefore restrict alignment to issue-relevant image nodes and candidate function nodes in the seed-induced graph, and retain a correspondence only when semantic compatibility is supported by relation-consistent neighborhood evidence. Concretely, the model jointly grounds image nodes to semantically related function nodes and verifies whether image-side relations are supported by compatible UI-oriented interactions in the function graph. The resulting alignment output is a small aligned subgraph that includes matched nodes, relation-supported correspondences, and concise rationales for downstream target selection. By combining entity grounding with relation-aware verification, this design filters out structurally inconsistent matches and yields more reliable localization evidence than retrieval based solely on independent semantic similarity.

Edit Target Identification. Based on the alignment results, the model further identifies a small set of edit targets from the aligned subgraph within the same reasoning process to guide patch generation. Not all aligned functions are equally responsible for the observed issue, and directly modifying all candidates would introduce unnecessary changes and reduce reliability. Therefore, instead of relying on similarity alone, the model prioritizes functions that are strongly supported by both node-level and relation-level alignment evidence, and organizes them into primary, secondary, and contextual roles according to their expected repair relevance. The resulting target set provides a structured and interpretable bridge from multimodal alignment signals to actionable code edits, enabling focused and efficient bug fixing.

## 3.5 Graph-guided Patch Generation

After hierarchical localization, the system shifts from identifying issue-relevant code regions to generating an executable fix. We formulate this stage as graph-guided patch generation, where repair is initialized from the aligned results of the previous stages rather than from unconstrained repository exploration. Specifically, the repair agent is provided with the image graph summary, the seed files from file-level alignment, and the edit targets from functionlevel alignment. The image graph summary preserves the visual or behavioral symptom to be resolved, while the seed files and edit targets define where inspection and modification should begin. The agent expands beyond these aligned regions only when local dependency evidence indicates that adjacent components must also be considered.

Localized Repair Space. The outputs of file-level and functionlevel alignment jointly define a localized repair space. Seed files specify a compact set of issue-relevant files for prioritized inspection, while edit targets identify the classes, functions, or modules most directly implicated by the alignment results. Together, they

reduce the ambiguity of repository-wide search and preserve the most relevant code context.

Localized Dependency-aware Reasoning and Target Prioritization. Although the aligned repair space narrows the search scope, a bug may still involve interactions among nearby components. The agent therefore inspects short, issue-relevant dependency paths around the seed files and edit targets, considering relations such as function calls, component rendering, state access, and data propagation. This helps determine whether the anomaly is introduced locally or through a closely related upstream or downstream component. In addition, the agent uses the target roles produced during alignment (e.g., primary, secondary, and contextual) to prioritize inspection and editing: primary targets are examined first, secondary targets are considered when coordinated changes are needed, and contextual targets mainly support reasoning unless direct modification becomes necessary.

Patch Generation. Within the same repair process, the agent generates a candidate patch from the localized repair space, beginning with the primary edit targets whenever possible. It is encouraged to preserve surrounding logic and avoid broad refactoring unless dependency evidence indicates that coordinated modifications are necessary. After code modification, the repository state for each instance is exported as a standardized patch file. Rather than producing an arbitrary textual patch, the modified files are first staged with git add -A, and the final patch is then exported using git diff –cached to ensure a valid and reproducible diff format. The resulting patch file is subsequently submitted to the SWE-Bench Multimodal evaluation pipeline, where final correctness is determined by the downstream execution and test protocol.

## 4 Experiments

In this section, we conduct comprehensive experiments to evaluate the effectiveness of GALA on the SWE-Bench Multimodal benchmark. We begin by describing the experimental setup, including the benchmark, evaluation protocol, and baseline methods for comparison. We then report the main results in terms of end-to-end repair performance, followed by a detailed analysis of localization accuracy at both file-level and function-level. To further validate the robustness of our approach, we evaluate GALA under different model scales (Qwen3.5-35B-A3B and Qwen3.5-122B-A10B), examining how structured cross-modal alignment affects performance across varying model capacities. Finally, we conduct ablation studies to analyze the contribution of each component and to investigate the impact of code graph granularity. Together, these experiments provide a comprehensive assessment of both the effectiveness and the underlying mechanisms of our method.

## 4.1 Implementation Details

We implement GALA using large language models from the Qwen3.5 family, including Qwen3.5-35B-A3B and Qwen3.5-122B-A10B. These models are used throughout the full pipeline, including visual understanding, code localization, and patch generation. Specifically, the model serves as a vision-language model (VLM) for image graph construction and as a text model for subsequent reasoning and code-related tasks. This design helps maintain consistent semantic representations across stages. During file-level localization, we

| Method               | Base model        | %Resolved | #Resolved |
|----------------------|-------------------|-----------|-----------|
| SWE-Agent Multimodal | GPT-4o            | 12.19     | 63        |
| Agentless Lite       | Claude-3.5 Sonnet | 25.34     | 131       |
| Zencoder             | Claude-3.5 Sonnet | 30.56     | 158       |
| OpenHands-Versa      | Claude-Sonnet 4   | 34.43     | 178       |
| GUIRepair            | Qwen3.5-122B-A10B | 34.82     | 180       |
| SVRepair             | Qwen3.5-35B-A3B   | 32.10     | 166       |
| SVRepair             | Qwen3.5-122B-A10B | 33.66     | 174       |
| GALA                 | Qwen3.5-35B-A3B   | 33.66     | 174       |
| GALA                 | Qwen3.5-122B-A10B | 35.40     | 183       |

<span id="page-6-0"></span>Table 1: Comparison of Pass@1 resolve rate (%) on SWE-Bench Multimodal.

retrieve up to 10 candidate files and further select 5 seed files for downstream alignment. All generation and reasoning processes use a temperature of 0.0 to ensure deterministic outputs. For patch generation, we employ a cfuse-based agent guided by the structured alignment outputs. For fair baseline comparison, we re-implement GUIRepair and SVRepair using our deployed models while strictly following the implementation details reported in their original papers. The 35B model is served on 2 GPUs, while the 122B model is deployed on 8 GPUs. We set the maximum number of workers to 12 to parallelize inference. All experiments are conducted on a multi-GPU server equipped with NVIDIA A800-SXM4-80GB GPUs.

## 4.2 Experiment Setup

## Benchmark Selection

We evaluate GALA on SWE-Bench Multimodal (SWE-Bench M) [\[43\]](#page-8-43), a benchmark designed to assess the ability of AI agents to resolve real-world software issues requiring both code reasoning and visual understanding. It extends the original SWE-Bench by introducing 619 tasks from 17 widely-used JavaScript repositories focused on user-facing and visually intensive applications, such as web interfaces, data visualization, and interactive systems. Each task includes both natural language descriptions and visual inputs (e.g., screenshots, diagrams, or rendered outputs), which are often essential for identifying the underlying problem. Compared to SWE-Bench, which is limited to Python repositories and primarily text-based inputs, SWE-Bench M introduces greater complexity through multimodal reasoning and cross-language code modifications. The benchmark is divided into a test set of 517 instances and a development set of 102 instances. We report results on the test set for overall evaluation and use the development set for model selection and analysis.

## Baseline Selection

We compare GALA with several recent state-of-the-art approaches that have demonstrated strong performance on the SWE-Bench Multimodal benchmark. In particular, we include the top-performing methods reported in prior work as primary baselines. For the two strongest baselines, we further conduct additional experiments using our deployed model, Qwen3.5-122B-A10B, in addition to their originally reported models. This allows for a more controlled and fair comparison by evaluating these methods under a consistent

model setting, while also preserving their original reported performance for reference.

# 4.3 Evaluation Results on SWE-Bench Multimodal

Main Experiment. We evaluate the overall effectiveness of GALA on the SWE-Bench Multimodal benchmark, with results shown in Table [1.](#page-6-0) GALA achieves the best performance among all compared methods, reaching a resolution rate of 35.40%, outperforming strong multimodal baselines such as GUIRepair (34.82%) and OpenHands-Versa (34.43%). Notably, under the same base model setting (Qwen3.5-122B-A10B), GALA surpasses SVRepair (33.66%) by a clear margin, demonstrating that the improvement stems from our proposed image graph–code graph alignment rather than model scaling. Furthermore, GALA significantly outperforms earlier approaches such as Agentless Lite (25.34%) and SWE-Agent Multimodal (12.19%), highlighting the importance of structured crossmodal reasoning in multimodal program repair. We also observe that recent multimodal approaches, including GUIRepair and SVRepair, exhibit relatively modest gains over prior methods, suggesting that performance improvements in this benchmark are inherently incremental and further underscoring the effectiveness of our structured alignment strategy. Overall, these results validate that GALA provides a more accurate and structurally grounded localization and repair paradigm, achieving state-of-the-art performance on SWE-Bench Multimodal.

Localization Performance. We further evaluate the localization capability of GALA at both file-level and function-level on the validation split of SWE-Bench Multimodal, since the test split does not expose gold patches and thus does not support localization evaluation. As shown in Table [2,](#page-7-0) GALA consistently achieves the best performance across all settings. Under the 122B model, GALA reaches 29.22% file-level recall and 17.14% function-level recall, outperforming SVRepair (28.71% / 16.25%) and GUIRepair (24.3% / 12.4%). More importantly, the improvement is even more pronounced under the smaller 35B model: GALA achieves 28.22% filelevel and 15.88% function-level recall, exceeding SVRepair (25.50% / 13.63%) by a larger margin compared to the 122B setting. This observation suggests that our structured graph alignment provides stronger guidance when model capacity is limited, enabling more

<span id="page-7-0"></span>Table 2: File-level and function-level localization recall (%) on SWE-Bench M.

| Method          | File-level | Function-level |
|-----------------|------------|----------------|
| GUIRepair(35b)  | 21.78      | 10.17          |
| GUIRepair(122b) | 24.3       | 12.4           |
| SVRepair(35b)   | 25.50      | 13.63          |
| SVRepair(122b)  | 28.71      | 16.25          |
| GALA(35b)       | 28.22      | 15.88          |
| GALA(122b)      | 29.22      | 17.14          |

<span id="page-7-1"></span>Table 3: Ablation study on different components of our method.

| Image Graph | Code Graph | Alignment | Resolved (%) |
|-------------|------------|-----------|--------------|
| –           | –          | –         | 33.66        |
| ✓           | –          | –         | 34.43        |
| ✓           | ✓          | –         | 34.43        |
| ✓           | ✓          | ✓         | 35.40        |

<span id="page-7-2"></span>Table 4: Ablation study on different levels of code graph granularity.

| File-level Graph | Function-level Graph | Resolved (%) |
|------------------|----------------------|--------------|
| –                | –                    | 34.43        |
| ✓                | –                    | 34.62        |
| ✓                | ✓                    | 35.40        |

effective localization even with smaller models. These results further confirm that GALA improves not only final repair success but also the underlying localization quality, which is critical for multimodal bug fixing.

## 4.4 Ablation Studies

Ablation on core components. To evaluate the contribution of each component in our framework, we conduct a systematic ablation study on SWE-Bench Multimodal, as shown in Table [3.](#page-7-1) We consider four incremental configurations, implemented by selectively enabling or disabling structured components while keeping all other settings unchanged. We start from a text-only setting without structured visual or code representations, achieving 33.66%. In this setting, the model does not utilize image inputs and skips the candidate file retrieval stage, instead directly selecting seed files based on the problem description and repository context, with the model guided to focus on these seed files during reasoning. Introducing the image graph improves performance to 34.43%, indicating that structured visual information provides useful signals beyond pure text-based reasoning. Adding the code graph alone on top of the image graph does not yield further gains (34.43%), suggesting

that code-side structure without explicit cross-modal grounding is insufficient to improve localization. In contrast, enabling crossmodal alignment between the image graph and code graph leads to a substantial improvement, reaching 35.40%. This result highlights that the key performance gain comes from explicitly aligning visual and code structures, rather than modeling them independently.

Ablation on code graph granularity. We further investigate the impact of code graph granularity, with results summarized in Table [4.](#page-7-2) We consider configurations with different levels of structural granularity by selectively enabling file-level and finer-grained code graph representations while keeping all other components unchanged. Starting from a setting with image graph and file-level reasoning only (34.43%), introducing a file-level code graph improves performance to 34.62%, demonstrating that coarse-grained structural information is effective for narrowing down candidate regions. Further incorporating a finer-grained function-level graph leads to a higher performance of 35.40%, indicating that fine-grained representations provide more precise localization signals. This progression shows that multi-level structural modeling provides complementary benefits, where file-level graphs offer global structural context while finer-grained representations enable more accurate reasoning over local code regions.

## 5 Conclusion

In this paper, we presented GALA, a multimodal automated program repair framework that formulates bug localization as a hierarchical cross-modal graph alignment problem. By modeling visual structures with an image graph and code dependencies with multilevel code graphs, GALA enables structured reasoning between visual observations and executable code. Through file- and functionlevel alignment, our approach enforces semantic and relational consistency, yielding more accurate and interpretable localization. Experiments on SWE-bench Multimodal show that GALA outperforms existing methods, validating the effectiveness of structureaware alignment in multimodal APR. Consistent gains across model scales further indicate that our framework provides robust guidance beyond specific model capacities. This work highlights the importance of moving beyond implicit textual representations toward explicit structural reasoning, opening new directions for graphbased multimodal software engineering.

## 6 Limitations

Despite its effectiveness, our method has several limitations. Due to limited context capacity of current LLMs, fine-grained alignment between visual elements and line-level code remains challenging, and we instead adopt hierarchical alignment from files to functions. Consequently, the method depends on repository organization and may degrade under ambiguous naming or modular structures, though partially mitigated by increasingly standardized, AI-assisted development. In addition, our framework introduces structured intermediate representations as external reasoning scaffolds to simplify multimodal understanding. As LLMs and agent systems advance, such structures may become internalized, enabling more direct end-to-end reasoning. Balancing explicit structural guidance with increasingly powerful implicit reasoning remains an important direction for future work.

## References

- <span id="page-8-10"></span>[1] Waqas Ali, Lili Bo, Xiaobing Sun, Xiaoxue Wu, Saifullah Memon, Saima Siraj, and Ann Suwaree Ashton. 2023. Automated software bug localization enabled by meta-heuristic-based convolutional neural network and improved deep neural network. Expert Systems with Applications 232 (2023), 120562.
- <span id="page-8-35"></span>[2] Antonis Antoniades, Albert Örwall, Kexun Zhang, Yuxi Xie, Anirudh Goyal, and William Wang. 2024. Swe-search: Enhancing software agents with monte carlo tree search and iterative refinement. arXiv preprint arXiv:2410.20285 (2024).
- <span id="page-8-15"></span>[3] Fraol Batole, David OBrien, Tien Nguyen, Robert Dyer, and Hridesh Rajan. 2025. An LLM-Based Agent-Oriented Approach for Automated Code Design Issue Localization. In 2025 IEEE/ACM 47th International Conference on Software Engineering (ICSE). IEEE Computer Society, 637–637.
- <span id="page-8-28"></span>[4] Islem Bouzenia, Premkumar Devanbu, and Michael Pradel. 2025. Repairagent: An autonomous, llm-based agent for program repair. In 2025 IEEE/ACM 47th International Conference on Software Engineering (ICSE). IEEE, 2188–2200.
- <span id="page-8-9"></span>[5] Partha Chakraborty, Mahmoud Alfadel, and Meiyappan Nagappan. 2025. BLAZE: Cross-language and cross-project bug localization via dynamic chunking and hard example learning. IEEE Transactions on Software Engineering (2025).
- <span id="page-8-16"></span>[6] Zhaoling Chen, Robert Tang, Gangda Deng, Fang Wu, Jialong Wu, Zhiwei Jiang, Viktor Prasanna, Arman Cohan, and Xingyao Wang. 2025. Locagent: Graphguided llm agents for code localization. In Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers). 8697– 8727.
- <span id="page-8-8"></span>[7] Agnieszka Ciborowska and Kostadin Damevski. 2022. Fast changeset-based bug localization with BERT. In Proceedings of the 44th international conference on software engineering. 946–957.
- <span id="page-8-29"></span>[8] Zhiyu Fan, Xiang Gao, Martin Mirchev, Abhik Roychoudhury, and Shin Hwei Tan. 2023. Automated repair of programs from large language models. In 2023 IEEE/ACM 45th International Conference on Software Engineering (ICSE). IEEE, 1469–1481.
- <span id="page-8-22"></span>[9] Kai Huang, Jian Zhang, Xiangxin Meng, and Yang Liu. 2025. Template-Guided Program Repair in the Era of Large Language Models.. In ICSE. 1895–1907.
- <span id="page-8-5"></span>[10] Kai Huang, Jian Zhang, Xiaofei Xie, and Chunyang Chen. 2025. Seeing is fixing: Cross-modal reasoning with multimodal llms for visual software issue fixing. arXiv preprint arXiv:2506.16136 (2025).
- <span id="page-8-11"></span>[11] Xuan Huo and Ming Li. 2017. Enhancing the Unified Features to Locate Buggy Files by Exploiting the Sequential Nature of Source Code.. In IJCAI. 1909–1915.
- <span id="page-8-23"></span>[12] Nan Jiang, Kevin Liu, Thibaud Lutellier, and Lin Tan. 2023. Impact of code language models on automated program repair. In 2023 IEEE/ACM 45th International Conference on Software Engineering (ICSE). IEEE, 1430–1442.
- <span id="page-8-13"></span>[13] Zhonghao Jiang, Xiaoxue Ren, Meng Yan, Wei Jiang, Yong Li, and Zhongxin Liu. 2025. Issue Localization via LLM-Driven Iterative Code Graph Searching. In 2025 40th IEEE/ACM International Conference on Automated Software Engineering (ASE). IEEE, 3034–3045.
- <span id="page-8-4"></span>[14] Carlos E Jimenez, John Yang, Alexander Wettig, Shunyu Yao, Kexin Pei, Ofir Press, and Karthik Narasimhan. 2023. Swe-bench: Can language models resolve real-world github issues? arXiv preprint arXiv:2310.06770 (2023).
- <span id="page-8-7"></span>[15] An Ngoc Lam, Anh Tuan Nguyen, Hoan Anh Nguyen, and Tien N Nguyen. 2017. Bug localization with combination of deep learning and information retrieval. In 2017 IEEE/ACM 25th International Conference on Program Comprehension (ICPC). IEEE, 218–229.
- <span id="page-8-0"></span>[16] Claire Le Goues, Michael Pradel, and Abhik Roychoudhury. 2019. Automated program repair. Commun. ACM 62, 12 (2019), 56–65.
- <span id="page-8-30"></span>[17] Cheryl Lee, Chunqiu Steven Xia, Longji Yang, Jen-tse Huang, Zhouruixing Zhu, Lingming Zhang, and Michael R Lyu. 2025. Unidebugger: Hierarchical multiagent framework for unified software debugging. In Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing. 18248–18277.
- <span id="page-8-17"></span>[18] Han Li, Yuling Shi, Shaoxin Lin, Xiaodong Gu, Heng Lian, Xin Wang, Yantao Jia, Tao Huang, and Qianxiang Wang. 2025. Swe-debate: Competitive multi-agent debate for software issue resolution. arXiv preprint arXiv:2507.23348 (2025).
- <span id="page-8-39"></span>[19] Kaixin Li, Yuchen Tian, Qisheng Hu, Ziyang Luo, Zhiyong Huang, and Jing Ma. 2024. Mmcode: Benchmarking multimodal large language models for code generation with visually rich programming problems. In Findings of the Association for Computational Linguistics: EMNLP 2024. 736–783.
- <span id="page-8-1"></span>[20] Derrick Lin, James Koppel, Angela Chen, and Armando Solar-Lezama. 2017. QuixBugs: A multi-lingual program repair benchmark set based on the Quixey Challenge. In Proceedings Companion of the 2017 ACM SIGPLAN international conference on systems, programming, languages, and applications: software for humanity. 55–56.
- <span id="page-8-21"></span>[21] Wei Liu, Chao Peng, Pengfei Gao, Aofan Liu, Wei Zhang, Haiyan Zhao, and Zhi Jin. 2025. GraphLocator: Graph-guided Causal Reasoning for Issue Localization. arXiv preprint arXiv:2512.22469 (2025).
- <span id="page-8-36"></span>[22] Yingwei Ma, Qingping Yang, Rongyu Cao, Binhua Li, Fei Huang, and Yongbin Li. 2025. Alibaba lingmaagent: Improving automated issue resolution via comprehensive repository exploration. In Proceedings of the 33rd ACM International Conference on the Foundations of Software Engineering. 238–249.

- <span id="page-8-2"></span>[23] Yicheng Ouyang, Jun Yang, and Lingming Zhang. 2024. Benchmarking automated program repair: An extensive study on both real-world and artificial bugs. In Proceedings of the 33rd ACM SIGSOFT International Symposium on Software Testing and Analysis. 440–452.
- <span id="page-8-31"></span>[24] Yun Peng, Shuzheng Gao, Cuiyun Gao, Yintong Huo, and Michael Lyu. 2024. Domain knowledge matters: Improving prompts with fix templates for repairing python type errors. In Proceedings of the 46th ieee/acm international conference on software engineering. 1–13.
- <span id="page-8-12"></span>[25] Revanth Gangi Reddy, Tarun Suresh, JaeHyeok Doo, Ye Liu, Xuan Phi Nguyen, Yingbo Zhou, Semih Yavuz, Caiming Xiong, Heng Ji, and Shafiq Joty. 2025. Swerank: Software issue localization with code ranking. arXiv preprint arXiv:2505.07849 (2025).
- <span id="page-8-18"></span>[26] Asif Mohammed Samir and Mohammad Masudur Rahman. 2026. Improved Bug Localization with AI Agents Leveraging Hypothesis and Dynamic Cognition. arXiv preprint arXiv:2601.12522 (2026).
- <span id="page-8-42"></span>[27] Aditya Bharat Soni, Boxuan Li, Xingyao Wang, Valerie Chen, and Graham Neubig. 2025. Coding Agents with Multimodal Browsing are Generalist Problem Solvers. In ICML 2025 Workshop on Computer Use Agents.
- <span id="page-8-3"></span>[28] Shin Hwei Tan, Jooyong Yi, Sergey Mechtaev, Abhik Roychoudhury, et al. 2017. Codeflaws: a programming competition benchmark for evaluating automated program repair tools. In 2017 IEEE/ACM 39th International Conference on Software Engineering Companion (ICSE-C). IEEE, 180–182.
- <span id="page-8-6"></span>[29] Xiaoxuan Tang, Jincheng Wang, Liwei Luo, Jingxuan Xu, Sheng Zhou, Dajun Chen, Wei Jiang, and Yong Li. 2026. SVRepair: Structured Visual Reasoning for Automated Program Repair. arXiv preprint arXiv:2602.06090 (2026).
- <span id="page-8-19"></span>[30] Boshi Wang, Weijian Xu, Yunsheng Li, Mei Gao, Yujia Xie, Huan Sun, and Dongdong Chen. 2025. Improving code localization with repository memory. arXiv preprint arXiv:2510.01003 (2025).
- <span id="page-8-40"></span>[31] Hanbin Wang, Xiaoxuan Zhou, Zhipeng Xu, Keyuan Cheng, Yuxin Zuo, Kai Tian, Jingwei Song, Junting Lu, Wenhui Hu, and Xueyang Liu. 2025. Codevision: evaluating multimodal LLMs logic understanding and code generation capabilities. arXiv preprint arXiv:2502.11829 (2025).
- <span id="page-8-24"></span>[32] Weishi Wang, Yue Wang, Shafiq Joty, and Steven CH Hoi. 2023. Rap-gen: Retrieval-augmented patch generation with codet5 for automatic program repair. In Proceedings of the 31st ACM Joint European Software Engineering Conference and Symposium on the Foundations of Software Engineering. 146–158.
- <span id="page-8-20"></span>[33] Ying Wang, Wenjun Mao, Chong Wang, Zhenhao Zhou, Yicheng Zhou, Wenyun Zhao, Yiling Lou, and Xin Peng. 2025. Extracting Conceptual Knowledge to Locate Software Issues. arXiv preprint arXiv:2509.21427 (2025).
- <span id="page-8-25"></span>[34] Yi Wu, Nan Jiang, Hung Viet Pham, Thibaud Lutellier, Jordan Davis, Lin Tan, Petr Babkin, and Sameena Shah. 2023. How effective are neural networks for fixing security vulnerabilities. In Proceedings of the 32nd ACM SIGSOFT International Symposium on Software Testing and Analysis. 1282–1294.
- <span id="page-8-41"></span>[35] Chunqiu Steven Xia, Yinlin Deng, Soren Dunn, and Lingming Zhang. 2024. Agentless: Demystifying llm-based software engineering agents. arXiv preprint arXiv:2407.01489 (2024).
- <span id="page-8-37"></span>[36] Chunqiu Steven Xia, Yinlin Deng, Soren Dunn, and Lingming Zhang. 2025. Demystifying llm-based software engineering agents. Proceedings of the ACM on Software Engineering 2, FSE (2025), 801–824.
- <span id="page-8-26"></span>[37] Chunqiu Steven Xia, Yifeng Ding, and Lingming Zhang. 2023. The plastic surgery hypothesis in the era of large language models. In 2023 38th IEEE/ACM International Conference on Automated Software Engineering (ASE). IEEE, 522– 534.
- <span id="page-8-27"></span>[38] Chunqiu Steven Xia, Yuxiang Wei, and Lingming Zhang. 2023. Automated program repair in the era of large pre-trained language models. In 2023 IEEE/ACM 45th International Conference on Software Engineering (ICSE). IEEE, 1482–1494.
- <span id="page-8-32"></span>[39] Chunqiu Steven Xia and Lingming Zhang. 2022. Less training, more repairing please: revisiting automated program repair via zero-shot learning. In Proceedings of the 30th ACM Joint European Software Engineering Conference and Symposium on the Foundations of Software Engineering. 959–971.
- <span id="page-8-14"></span>[40] Ke Xu, Siyang Xiao, Ming Liang, Yichen Yu, Zhixiang Wang, Jingxuan Xu, Dajun Chen, Wei Jiang, and Yong Li. 2026. Learning Adaptive Parallel Execution for Efficient Code Localization. arXiv preprint arXiv:2601.19568 (2026).
- <span id="page-8-33"></span>[41] Boyang Yang, Haoye Tian, Weiguo Pian, Haoran Yu, Haitao Wang, Jacques Klein, Tegawendé F Bissyandé, and Shunfu Jin. 2024. Cref: An llm-based conversational software repair framework for programming tutors. In Proceedings of the 33rd ACM SIGSOFT International Symposium on Software Testing and Analysis. 882– 894.
- <span id="page-8-38"></span>[42] John Yang, Carlos E Jimenez, Alexander Wettig, Kilian Lieret, Shunyu Yao, Karthik Narasimhan, and Ofir Press. 2024. Swe-agent: Agent-computer interfaces enable automated software engineering. Advances in Neural Information Processing Systems 37 (2024), 50528–50652.
- <span id="page-8-43"></span>[43] John Yang, Carlos E Jimenez, Alex L Zhang, Kilian Lieret, Joyce Yang, Xindi Wu, Ori Press, Niklas Muennighoff, Gabriel Synnaeve, Karthik R Narasimhan, et al. 2025. SWE-bench Multimodal: Do AI Systems Generalize to Visual Software Domains?. In The Thirteenth International Conference on Learning Representations.
- <span id="page-8-34"></span>[44] Xin Yin, Chao Ni, Shaohua Wang, Zhenhao Li, Limin Zeng, and Xiaohu Yang. 2024. Thinkrepair: Self-directed automated program repair. In Proceedings of the

- 33rd ACM SIGSOFT International Symposium on Software Testing and Analysis. 1274–1286.
- <span id="page-9-0"></span>[45] Quanjun Zhang, Chunrong Fang, Yuxiang Ma, Weisong Sun, and Zhenyu Chen. 2023. A survey of learning-based automated program repair. ACM Transactions on Software Engineering and Methodology 33, 2 (2023), 1–69.
- <span id="page-9-1"></span>[46] Quanjun Zhang, Chunrong Fang, Yang Xie, YuXiang Ma, Weisong Sun, Yun Yang, and Zhenyu Chen. 2024. A systematic literature review on large language models for automated program repair. ACM Transactions on Software Engineering and Methodology (2024).
- <span id="page-9-2"></span>[47] Quanjun Zhang, Chunrong Fang, Tongke Zhang, Bowen Yu, Weisong Sun, and Zhenyu Chen. 2023. Gamma: Revisiting template-based automated program
- repair via mask prediction. In 2023 38th IEEE/ACM International Conference on Automated Software Engineering (ASE). IEEE, 535–547.
- <span id="page-9-4"></span>[48] Yuntong Zhang, Haifeng Ruan, Zhiyu Fan, and Abhik Roychoudhury. 2024. Autocoderover: Autonomous program improvement. In Proceedings of the 33rd ACM SIGSOFT International Symposium on Software Testing and Analysis. 1592– 1604.
- <span id="page-9-3"></span>[49] Jiuang Zhao, Donghao Yang, Li Zhang, Xiaoli Lian, Zitian Yang, and Fang Liu. 2024. Enhancing automated program repair with solution design. In Proceedings of the 39th IEEE/ACM International Conference on Automated Software Engineering. 1706–1718.
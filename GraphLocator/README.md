# GraphLocator


## Project Overview


In this paper, we propose GraphLocator, an LLM-based approach that mitigates symptom–to-cause mismatches through causal structure discovering and resolves one-to-many mismatches via dynamic issue disentangling. The key artifact of GraphLocator is the causal issue graph (CIG), in which vertices represent discovered sub-issues along with their associated code entities, and edges encode the causal dependencies between them. The workflow of GraphLocator consists of two phases: symptom vertices locating and dynamic CIG discovering; it first identifies symptom locations on the repository graph, then dynamically expands the CIG by iteratively reasoning over neighboring vertices, discovering new sub-issues and updating causal dependencies.


## Project Structure

The structure of this project is shown as follows:
```
├─ rdfs     # The package for generating RDFS for a given repository
├─ datasets # The issue-resolving dataset and extracted localization ground truth used by GraphLocator
├─ prompts  # The prompt templates used by GraphLocator
├─ llms     # Call LLMs via litellm
├─ utils    # Utils for GraphLocator
├─ eval_metrics.py  # Experimental metrics
├─ causal_agent.py  # Implementation of CausalAgent
├─ search_agent.py  # Implementation of SearchAgent
└─ graphlocator.py  # The entry of running GraphLocator
```

## Quick Start

### Environment Setup

```
conda create -n graphlocator python=3.13
conda activate graphlocator
pip install -r requirements.txt
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

Then export your OpenAI and Anthropic API key

```commandline
export OPENAI_API_KEY={key_here}
export ANTHROPIC_API_KEY={key_here}
```

### Run GraphLocator

- **SWE-bench Lite**

```
python graphlocator.py --dataset_name swe_bench_lite --dataset_language python --model_name gpt-4o-2024-11-20 --results_dir ./results/swe_bench_lite/gpt4o --repo_playground ABSOLUTE_PATH
```

- **LocBench**

```
python graphlocator.py --dataset_name locbench --dataset_language python --model_name gpt-4o-2024-11-20 --results_dir ./results/locbench/gpt4o --repo_playground ABSOLUTE_PATH
```

- **Multi-SWE-bench (Java)**

```
python graphlocator.py --dataset_name multi_swe_bench_java --dataset_language python --model_name gpt-4o-2024-11-20 --results_dir ./results/multi_swe_bench_java/gpt4o --repo_playground ABSOLUTE_PATH
```
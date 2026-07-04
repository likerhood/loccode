import re
import os
import json
import argparse
from utils.constants import NON_VAILD_ISSUES
from utils.string_processing import load_jsonl
from rdfs.dependency_graph.dependency_graph import DependencyGraph
from utils.construct_graph import construct_rdfs_skeleton, clone_repo, checkout_commit
from utils.convert_results import convert_nodes_to_results, convert_results, has_any_result
from utils.structure_fallback import supplement_results_with_structure
from search_agent import SearchAgent
from causal_agent import CausalAgent 

def parse_arguments():
    parser = argparse.ArgumentParser(description="GraphLocator for issue localization and causal graph generation.")
    parser.add_argument("--dataset_name", type=str, default="swe_bench_lite",
                        help="Name of the dataset to process.")
    parser.add_argument(
        "--dataset_language",
        type=str,
        choices=[
            "auto",
            "mixed",
            "python",
            "java",
            "javascript",
            "typescript",
            "c_sharp",
            "kotlin",
            "php",
            "ruby",
            "c",
            "cpp",
            "go",
            "swift",
            "rust",
            "lua",
            "bash",
            "r",
        ],
        default="auto",
                        help="Programming language of the dataset.")
    parser.add_argument("--model_name", type=str, default="gpt-4o-2024-11-20",
                        help="Name of the model to use for generating causal graphs, can be gpt-4o-2024-11-20 or claude-3-5-sonnet-20241022.")
    parser.add_argument("--repo_playground", type=str, default="AbsolutePath/GraphLocator/repo_playground",
                        help="Path to the repository playground.")
    parser.add_argument("--repo_skeleton_path", type=str, default="./repo_skeleton",
                        help="Path to the repository skeleton.")
    parser.add_argument("--results_dir", type=str, default="./results/swe_bench_lite/gpt4o",
                        help="Directory to save the results.")
    parser.add_argument("--search_topk", type=int, default=5,
                        help="Top K search results to consider.")
    parser.add_argument("--skip_exist", action='store_true',
                        help="Whether to skip already processed issues.")
    parser.add_argument("--max_search_turn", type=int, default=5,
                        help="Maximum number of search turns for the SearchAgent.")
    parser.add_argument("--max_causal_turn", type=int, default=20,
                        help="Number of causal graph generation turns for the CausalAgent.")
    parser.add_argument("--structure_dir", type=str, default=os.environ.get("STRUCTURE_DIR", ""),
                        help="Optional repo_structures directory used to supplement module/function predictions.")
                        
    return parser.parse_args()

def main(args):

    # Read the issue dataset and load the already processed issues if skip_exist is set
    ds = load_jsonl(f"./datasets/{args.dataset_name}.jsonl")
    loc_res = dict()

    if not os.path.exists(args.results_dir):
        os.makedirs(args.results_dir)
    if args.skip_exist:
        loc_results_path = f"{args.results_dir}/loc_results.json"
        if os.path.exists(loc_results_path):
            with open(loc_results_path, "r") as f:
                loc_res = json.load(f)
            already_processed = set(loc_res)
        elif not os.path.exists(f"{args.results_dir}/causal_graph/"):
            already_processed = set()
        else:
            already_processed = {
                f.split('.')[0]
                for f in os.listdir(f"{args.results_dir}/causal_graph/")
                if f.endswith('.json')
            }

    # Process each issue in the dataset
    for issue in ds:

        issue_id = issue['instance_id']
        if issue_id in NON_VAILD_ISSUES or (args.skip_exist and issue_id in already_processed):
            continue
        
        # Step 0: Prepare the repository graph and checkout the correct commit
        if not os.path.exists(args.repo_skeleton_path):
            os.makedirs(args.repo_skeleton_path)
        skeleton_file = f"{args.repo_skeleton_path}/{issue_id}.{args.dataset_language}.json"
        legacy_skeleton_file = f"{args.repo_skeleton_path}/{issue_id}.json"
        if not os.path.exists(skeleton_file):
            print(f"Graph cache for issue {issue_id} not found, construct...")
            try:
                construct_rdfs_skeleton(issue, args.repo_skeleton_path, args.repo_playground, args.dataset_language)
            except Exception as exc:
                print(f"Graph construction failed for {issue_id}: {exc}")
        if not os.path.exists(skeleton_file) and os.path.exists(legacy_skeleton_file):
            skeleton_file = legacy_skeleton_file
        if not os.path.exists(skeleton_file):
            results = supplement_results_with_structure(
                {"found_files": [], "found_modules": [], "found_functions": []},
                issue,
                args.structure_dir,
            )
            loc_res[issue_id] = results
            with open(f"{args.results_dir}/loc_results.json", "w") as f:
                json.dump(loc_res, f, indent=2)
            continue
        with open(skeleton_file, "r") as f:
            graph_data = f.read()
        try:
            graph = DependencyGraph.from_json(graph_data)
        except Exception as exc:
            print(f"Graph cache load failed for {issue_id}: {exc}")
            results = supplement_results_with_structure(
                {"found_files": [], "found_modules": [], "found_functions": []},
                issue,
                args.structure_dir,
            )
            loc_res[issue_id] = results
            with open(f"{args.results_dir}/loc_results.json", "w") as f:
                json.dump(loc_res, f, indent=2)
            continue

        repo_name = issue['repo'].split('/')[-1]
        commit_id = issue["base_commit"]
        checkout_commit(f"{args.repo_playground}/{repo_name}", commit_id)

        # Step 1: symptom vertices localization
        try:
            search_agent = SearchAgent(repo_graph=graph, model_name=args.model_name, max_search_turn=args.max_search_turn, top_k=args.search_topk)
            seed_locations = search_agent.get_seed_location(issue['problem_statement'])

            # Step 2: dynamic CIG discovering
            causal_agent = CausalAgent(model_name=args.model_name, repo_graph=search_agent.repo_graph, max_turn=args.max_causal_turn)
            cig = causal_agent.generate_causal_graph(issue['problem_statement'], seed_locations)

            # Convert CIG to 3-level of granularity results. Local/open models may
            # produce a valid-looking CIG without binding factors to Code Elements;
            # in that case, fall back to the seed locations found by SearchAgent.
            result_graph = search_agent.repo_graph.repo_graph
            results = convert_results(cig, result_graph)
            if not has_any_result(results) and seed_locations:
                print(f"CIG conversion produced empty results for {issue_id}; fall back to seed locations.")
                results = convert_nodes_to_results(seed_locations, result_graph)
        except Exception as exc:
            print(f"GraphLocator failed for {issue_id}: {exc}")
            results = {"found_files": [], "found_modules": [], "found_functions": []}
        results = supplement_results_with_structure(results, issue, args.structure_dir)
        loc_res[issue_id] = results
        with open(f"{args.results_dir}/loc_results.json", "w") as f:
            json.dump(loc_res, f, indent=2)


if __name__ == "__main__":

    args = parse_arguments()
    main(args)

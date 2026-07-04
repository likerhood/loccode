import os
import uuid
import subprocess
from typing import Any
from time import time
from utils.constants import NON_VAILD_ISSUES
from rdfs.dependency_graph.graph_generator import GraphGeneratorType
from rdfs.dependency_graph import construct_dependency_graph, Repository
from rdfs.dependency_graph.dependency_graph import DependencyGraph
from rdfs.dependency_graph.graph_generator.tree_sitter_generator import TreeSitterDependencyGraphGenerator
class IncremantalRDFS:
    def __init__(self, repo_graph: DependencyGraph):
        self.repo_graph = repo_graph
        self.updated_files = set()
        self.graph_generator = TreeSitterDependencyGraphGenerator()

    def incremental_add_dependency(self, node: Any):
        if not node.location or not node.location.file_path:
            return
        file_path = node.location.file_path
        if not os.path.isfile(file_path):
            return
        if file_path not in self.updated_files:
            self.updated_files.add(file_path)
            try:
                self.repo_graph = self.graph_generator.incremental_update_graph_with_dependency(self.repo_graph, [file_path])
            except Exception as exc:
                print(f"Skipping incremental dependency update for {file_path}: {exc}")
        return
    

def clone_repo(repo_name, repo_playground):
    try:
        if not os.path.exists(repo_playground):
            os.makedirs(repo_playground)
        print(
            f"\nCloning repository from https://github.com/{repo_name}.git to {repo_playground}/{repo_name.split('/')[-1]}..."
        )
        subprocess.run(
            [
                "git",
                "clone",
                f"https://github.com/{repo_name}.git",
                f"{repo_playground}/{repo_name.split('/')[-1]}",
            ],
            check=True,
        )
        print("\nRepository cloned successfully.")
    except subprocess.CalledProcessError as e:
        print(f"\nAn error occurred while running git command: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")


def checkout_commit(repo_path, commit_id):
    """Checkout the specified commit in the given local git repository.
    :param repo_path: Path to the local git repository
    :param commit_id: Commit ID to checkout
    :return: None
    """
    try:
        # Change directory to the provided repository path and checkout the specified commit
        print(f"\nChecking out commit {commit_id} in repository at {repo_path}...")
        subprocess.run(["git", "-C", repo_path, "checkout", commit_id], check=True)
        print("\nCommit checked out successfully.")
    except subprocess.CalledProcessError as e:
        print(f"\nAn error occurred while running git command: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

def construct_rdfs_skeleton(issue_instance, output_dir, repo_playground, language):

    if not os.path.exists(repo_playground):
        os.makedirs(repo_playground)

    instance_id = issue_instance["instance_id"]
    if instance_id in NON_VAILD_ISSUES:
        return
    repo_name = issue_instance["repo"].split('/')[-1]
    commit_id = issue_instance["base_commit"]

    saved_graph_path = os.path.join(output_dir, f"{instance_id}.{language}.json")

    if not os.path.exists(f"{repo_playground}/{repo_name}"):
        clone_repo(issue_instance["repo"], repo_playground)
    checkout_commit(f"{repo_playground}/{repo_name}", commit_id)

    start_time = time()
    repo_obj = Repository(f"{repo_playground}/{repo_name}", language)
    repo_graph = construct_dependency_graph(repo_obj,
                                            GraphGeneratorType.TREE_SITTER,
                                            language)
    end_time = time()
    print("Saving graph to", saved_graph_path)
    with open(saved_graph_path, "w") as f:
        f.write(repo_graph.to_json())

import logging
import os
import subprocess
import time
logger = logging.getLogger(__name__)

# 重试配置
CLONE_MAX_RETRIES = 3
CLONE_RETRY_DELAY = 5  # 秒

def get_repo_dir_name(repo: str):
    return repo.replace("/", "_")


def setup_github_repo(repo: str, base_commit: str, base_dir: str = "/tmp/repos") -> str:
    repo_name = get_repo_dir_name(repo)
    repo_url = f"https://github.com/{repo}.git"
    path = f"{base_dir}/{repo_name}"
    logger.info(
        f"Clone Github repo {repo_url} to {path} and checkout commit {base_commit}"
    )
    if not os.path.exists(path):
        os.makedirs(path)
        logger.info(f"Directory '{path}' was created.")
    maybe_clone(repo_url, path)
    checkout_commit(path, base_commit)
    return path


def maybe_clone(repo_url, repo_dir, max_retries=CLONE_MAX_RETRIES, retry_delay=CLONE_RETRY_DELAY):
    """克隆仓库，支持重试机制以应对网络瞬时故障"""
    if os.path.exists(f"{repo_dir}/.git"):
        logger.info(f"Repo already exists at '{repo_dir}'")
        return

    # 清理可能存在的不完整克隆目录
    if os.path.exists(repo_dir) and not os.path.exists(f"{repo_dir}/.git"):
        import shutil
        logger.warning(f"Removing incomplete clone directory: {repo_dir}")
        shutil.rmtree(repo_dir, ignore_errors=True)

    for attempt in range(1, max_retries + 1):
        logger.info(f"Cloning repo '{repo_url}' (attempt {attempt}/{max_retries})")
        try:
            result = subprocess.run(
                ["git", "clone", repo_url, repo_dir],
                check=True,
                text=True,
                capture_output=True,
            )

            if result.returncode == 0:
                logger.info(f"Repo '{repo_url}' was cloned to '{repo_dir}'")
                return
            else:
                logger.warning(f"Failed to clone repo '{repo_url}' to '{repo_dir}' (exit code: {result.returncode})")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Clone attempt {attempt} failed for '{repo_url}': {e}")

            # 清理失败的克隆目录
            if os.path.exists(repo_dir):
                import shutil
                shutil.rmtree(repo_dir, ignore_errors=True)

            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                # 指数退避：每次重试增加等待时间
                retry_delay *= 2
            else:
                logger.error(f"All {max_retries} clone attempts failed for '{repo_url}'")
                raise


def pull_latest(repo_dir):
    subprocess.run(
        ["git", "pull"],
        cwd=repo_dir,
        check=True,
        text=True,
        capture_output=True,
    )


def clean_and_reset_state(repo_dir):
    subprocess.run(
        ["git", "clean", "-fd"],
        cwd=repo_dir,
        check=True,
        text=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "reset", "--hard"],
        cwd=repo_dir,
        check=True,
        text=True,
        capture_output=True,
    )


def create_branch(repo_dir, branch_name):
    try:
        subprocess.run(
            ["git", "branch", branch_name],
            cwd=repo_dir,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error(e.stderr)
        raise e


def create_and_checkout_branch(repo_dir, branch_name):
    try:
        branches = subprocess.run(
            ["git", "branch"],
            cwd=repo_dir,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.split("\n")
        branches = [branch.strip() for branch in branches]
        if branch_name in branches:
            subprocess.run(
                ["git", "checkout", branch_name],
                cwd=repo_dir,
                check=True,
                text=True,
                capture_output=True,
            )
        else:
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=repo_dir,
                check=True,
                text=True,
                capture_output=True,
            )
    except subprocess.CalledProcessError as e:
        logger.error(e.stderr)
        raise e


def commit_changes(repo_dir, commit_message):
    subprocess.run(
        ["git", "commit", "-m", commit_message, "--no-verify"],
        cwd=repo_dir,
        check=True,
        text=True,
        capture_output=True,
    )


def checkout_branch(repo_dir, branch_name):
    subprocess.run(
        ["git", "checkout", branch_name],
        cwd=repo_dir,
        check=True,
        text=True,
        capture_output=True,
    )


def push_branch(repo_dir, branch_name):
    subprocess.run(
        ["git", "push", "origin", branch_name, "--no-verify"],
        cwd=repo_dir,
        check=True,
        text=True,
        capture_output=True,
    )


def get_diff(repo_dir):
    output = subprocess.run(
        ["git", "diff"], cwd=repo_dir, check=True, text=True, capture_output=True
    )

    return output.stdout


def stage_all_files(repo_dir):
    subprocess.run(
        ["git", "add", "."], cwd=repo_dir, check=True, text=True, capture_output=True
    )


def checkout_commit(repo_dir, commit_hash):
    try:
        subprocess.run(
            ["git", "reset", "--hard", commit_hash],
            cwd=repo_dir,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error(e.stderr)
        raise e


def create_and_checkout_new_branch(repo_dir: str, branch_name: str):
    try:
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_dir,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error(e.stderr)
        raise e


def setup_repo(repo_url, repo_dir, branch_name="master"):
    maybe_clone(repo_url, repo_dir)
    clean_and_reset_state(repo_dir)
    checkout_branch(repo_dir, branch_name)
    pull_latest(repo_dir)


def clean_and_reset_repo(repo_dir, branch_name="master"):
    clean_and_reset_state(repo_dir)
    checkout_branch(repo_dir, branch_name)
    pull_latest(repo_dir)
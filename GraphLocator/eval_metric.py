import json
import torch
import argparse
import pandas as pd
from torch import Tensor
from utils.string_processing import load_jsonl


def precision(pred_dict: dict, gt_dict: dict, key):
    precisions = []

    for instance_id in gt_dict.keys():
        gt_entities = list(set(gt_dict[instance_id][key]))
        if not gt_entities:
            continue

        if instance_id not in pred_dict.keys() or not pred_dict[instance_id]:
            precisions.append(0.0)
            continue
        pred_entities = list(set(pred_dict[instance_id][key]))

        relevant_count = 0
        for j in range(len(pred_entities)):
            if pred_entities[j] in gt_entities:
                relevant_count += 1
        if len(pred_entities) == 0:
            precisions.append(0.0)
        else:
            precisions.append(relevant_count / len(pred_entities))
    return torch.tensor(precisions).mean()


def f1_score(pred_dict: dict, gt_dict: dict, key):
    f1_scores = []
    for instance_id in gt_dict.keys():
        gt_entities = list(set(gt_dict[instance_id][key]))
        if not gt_entities:
            continue

        if instance_id not in pred_dict.keys() or not pred_dict[instance_id]:
            f1_scores.append(0.0)
            continue

        pred_entities = list(set(pred_dict[instance_id][key]))

        relevant_count = 0
        for j in range(len(pred_entities)):
            if pred_entities[j] in gt_entities:  # 如果是相关文档
                relevant_count += 1
        if relevant_count == 0:
            f1_scores.append(0)
        else:
            f1_scores.append(2/(len(pred_entities)/ relevant_count + len(gt_entities)/ relevant_count))
    return torch.tensor(f1_scores).mean()


def recall(pred_dict: dict, gt_dict: dict, key) -> Tensor:
    recalls = []
    for instance_id in gt_dict.keys():
        gt_entities = list(set(gt_dict[instance_id][key]))
        if not gt_entities:
            continue

        if instance_id not in pred_dict.keys() or not pred_dict[instance_id]:
            recalls.append(0.0)
            continue
        pred_entities = list(set(pred_dict[instance_id][key]))

        relevant_count = 0
        for j in range(len(pred_entities)):
            if pred_entities[j] in gt_entities:
                relevant_count += 1
        recalls.append(relevant_count / len(gt_entities))
    return torch.tensor(recalls).mean()


def success_location(pred_dict: dict, gt_dict: dict, key) -> Tensor:
    succ_locs = []
    succ_locs_id = []
    for instance_id in gt_dict.keys():

        gt_entities = list(set(gt_dict[instance_id][key]))
        if not gt_entities:
            continue

        if instance_id not in pred_dict.keys() or not pred_dict[instance_id]:
            succ_locs.append(0.0)
            continue
        pred_entities = list(set(pred_dict[instance_id][key]))

        relevant_count = 0
        for j in range(len(pred_entities)):
            if pred_entities[j] in gt_entities:
                relevant_count += 1
        if relevant_count == len(gt_entities):
            succ_locs.append(1.0)
            if key == "found_functions":
                succ_locs_id.append(instance_id)
        else:
            succ_locs.append(0.0)
    return torch.tensor(succ_locs).mean()

METRIC_FUNC = {
    'precision': precision,
    'f1': f1_score,
    'recall': recall,
    'success_location': success_location
}

METRIC_NAME = {
    'f1': 'F1',
    'precision': 'PRE',
    'recall': 'REC',
    'success_location': "SuccLoc"
}


def cal_metrics_w_dataset(pred_dict, key, gt_dict, metrics):
    result = {}
    for metric in metrics:
        assert metric in METRIC_FUNC.keys()
        metric_func = METRIC_FUNC[metric]
        name = METRIC_NAME[metric]

        value = metric_func(pred_dict, gt_dict, key)
        result[name] = round(value.item()*100, 2)

    return result


def evaluate_results(loc_file, dataset, level2key_dict, metrics=None):
    file_res = cal_metrics_w_dataset(loc_file, level2key_dict['file'], dataset, metrics=metrics)
    module_res = cal_metrics_w_dataset(loc_file, level2key_dict['module'], dataset, metrics=metrics)
    function_res = cal_metrics_w_dataset(loc_file, level2key_dict['function'], dataset, metrics=metrics)
    all_df = pd.concat([pd.DataFrame(res, index=[0])
                        for res in [file_res, module_res, function_res]],
                        axis=1,
                        keys=['file', 'module', 'function'])
    all_df = all_df.map(lambda x: f"{x:.2f} &" if isinstance(x, (int, float)) else x)
    return all_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--res_file_path", type=str, default='./results/graphlocator_swe_bench_lite_entities_3levels.json',
                        help="Path to the result file.")
    parser.add_argument("--gt_file_path", type=str, default='./datasets/swe_bench_lite_gt_entities_3levels.json',
                        help="Path to the ground truth file.")
    parser.add_argument("--dataset_name", type=str, default='swe_bench_lite',
                        help="Name of the dataset: 'swe_bench_lite' or 'locbench' or 'multi_swe_bench_java'.")
    args = parser.parse_args()

    level2key_dict = {
        'file': 'found_files',
        'module': 'found_modules',
        'function': 'found_functions',
    }

    
    with open(args.res_file_path, 'r') as f:
        pred_res = json.load(f)
    with open(args.gt_file_path, 'r') as f:
        gt_res = json.load(f)
    
    res = evaluate_results(pred_res, gt_res, level2key_dict,
                           metrics=['success_location', 'recall', 'precision', 'f1'],)
    print(res)

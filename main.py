import os
import json
import re
from typing import Dict, List, Optional, Tuple

from config import INPUT_DIR, OUTPUT_DIR

from extraction import process_document

from text_utils import (
    norm,
    normh,
    normk,
    sem,
    similar,
    lot_key,
    same_lot,
    best_location,
    find_similar_task,
)


def find_existing_lot_key(
    lot: Optional[str],
    enterprise: Optional[str],
    enterprise_map: Dict[Tuple, Dict],
) -> Optional[Tuple]:
    for key, value in enterprise_map.items():
        if normk(value.get("enterprise")) != normk(enterprise):
            continue

        if same_lot(value.get("lot"), lot):
            return key

    return None


def get_canonical_enterprise(new_ent: str, existing_ents: List[str]) -> str:
    new_norm = normh(new_ent)

    for enterprise in existing_ents:
        if similar(new_norm, normh(enterprise)):
            return enterprise

    return new_ent


def merge_null_enterprises(enterprise_map: Dict[Tuple, Dict]) -> Dict[Tuple, Dict]:
    keys_to_delete = []

    for key, value in list(enterprise_map.items()):
        enterprise = normk(value.get("enterprise"))

        if enterprise != "null":
            continue

        real_keys = [
            real_key
            for real_key, real_value in enterprise_map.items()
            if normk(real_value.get("enterprise")) != "null"
            and same_lot(real_value.get("lot"), value.get("lot"))
        ]

        if len(real_keys) != 1:
            continue

        target_tasks = enterprise_map[real_keys[0]]["tasks_index"]

        for task_key, task_value in value["tasks_index"].items():
            matched_key = find_similar_task(
                task_value.get("task"),
                task_value.get("location"),
                target_tasks,
            )

            final_key = matched_key or task_key

            if final_key not in target_tasks:
                target_tasks[final_key] = task_value
                continue

            entry = target_tasks[final_key]

            entry["location"] = best_location(
                entry.get("location"),
                task_value.get("location"),
            )

            if task_value.get("start_date") and (
                not entry["start_date"]
                or task_value["start_date"] < entry["start_date"]
            ):
                entry["start_date"] = task_value["start_date"]

            if task_value.get("end_date") and (
                not entry["end_date"]
                or task_value["end_date"] > entry["end_date"]
            ):
                entry["end_date"] = task_value["end_date"]

        keys_to_delete.append(key)

    for key in keys_to_delete:
        del enterprise_map[key]

    return enterprise_map


def lot_sort_key(lot_name: Optional[str]) -> Tuple[int, str]:
    text = normh(lot_name or "")
    match = re.search(r"\blot\s*0*(\d+)", text)

    if match:
        return int(match.group(1)), text

    return 999999, text


def build_project_output(documents: List[Dict]) -> Dict:
    project_name = next(
        (doc["project_name"] for doc in documents if doc.get("project_name")),
        None,
    )

    enterprise_map: Dict[Tuple, Dict] = {}

    for doc in documents:
        report_date = doc.get("report_date")

        for ent in doc.get("enterprises", []):
            canonical_lot = ent.get("lot")

            existing_enterprises = [
                value["enterprise"]
                for value in enterprise_map.values()
                if same_lot(value.get("lot"), canonical_lot)
            ]

            canonical_enterprise = get_canonical_enterprise(
                ent.get("enterprise"),
                existing_enterprises,
            )

            ent_key = find_existing_lot_key(
                canonical_lot,
                canonical_enterprise,
                enterprise_map,
            ) or (lot_key(canonical_lot), normk(canonical_enterprise))

            if ent_key not in enterprise_map:
                enterprise_map[ent_key] = {
                    "lot": canonical_lot,
                    "enterprise": canonical_enterprise,
                    "tasks_index": {},
                }

            elif len(canonical_lot or "") > len(
                enterprise_map[ent_key].get("lot") or ""
            ):
                enterprise_map[ent_key]["lot"] = canonical_lot

        for task in doc.get("tasks", []):
            canonical_lot = task.get("lot")
            enterprise = task.get("enterprise")

            existing_enterprises = [
                value["enterprise"]
                for value in enterprise_map.values()
                if same_lot(value.get("lot"), canonical_lot)
                and value.get("enterprise")
                and normk(value.get("enterprise")) != "null"
            ]

            if not enterprise:
                enterprise = (
                    existing_enterprises[0]
                    if len(existing_enterprises) == 1
                    else "null"
                )

            canonical_enterprise = get_canonical_enterprise(
                enterprise,
                existing_enterprises,
            )

            ent_key = find_existing_lot_key(
                canonical_lot,
                canonical_enterprise,
                enterprise_map,
            ) or (lot_key(canonical_lot), normk(canonical_enterprise))

            if ent_key not in enterprise_map:
                enterprise_map[ent_key] = {
                    "lot": canonical_lot,
                    "enterprise": canonical_enterprise,
                    "tasks_index": {},
                }

            elif len(canonical_lot or "") > len(
                enterprise_map[ent_key].get("lot") or ""
            ):
                enterprise_map[ent_key]["lot"] = canonical_lot

            tasks_index = enterprise_map[ent_key]["tasks_index"]

            matched_key = find_similar_task(
                task.get("task"),
                task.get("location"),
                tasks_index,
            )

            task_key = matched_key or (
                sem(task.get("task")),
                sem(task.get("location")),
            )

            start_date = task.get("start_date") or report_date
            end_date = task.get("end_date") or report_date

            if task_key not in tasks_index:
                tasks_index[task_key] = {
                    "task": task.get("task"),
                    "location": task.get("location"),
                    "start_date": start_date,
                    "end_date": end_date,
                }
                continue

            entry = tasks_index[task_key]

            entry["location"] = best_location(
                entry.get("location"),
                task.get("location"),
            )

            if start_date and (
                not entry["start_date"]
                or start_date < entry["start_date"]
            ):
                entry["start_date"] = start_date

            if end_date and (
                not entry["end_date"]
                or end_date > entry["end_date"]
            ):
                entry["end_date"] = end_date

    enterprise_map = merge_null_enterprises(enterprise_map)

    return {
        "project_name": project_name,
        "enterprises": sorted(
            [
                {
                    "lot": value["lot"],
                    "enterprise": value["enterprise"],
                    "tasks": list(value["tasks_index"].values()),
                }
                for value in enterprise_map.values()
            ],
            key=lambda item: (
                lot_sort_key(item.get("lot")),
                normk(item.get("enterprise")),
            ),
        ),
    }


def process_folder(input_dir: str, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    files = sorted(
        filename
        for filename in os.listdir(input_dir)
        if filename.lower().endswith(".json")
    )

    processed_docs = []

    for filename in files:
        path = os.path.join(input_dir, filename)

        try:
            with open(path, "r", encoding="utf-8") as file:
                doc = json.load(file)

            result = process_document(doc, filename)
            processed_docs.append(result)

        except Exception as error:
            print(f"{filename}: {error}")

    output = build_project_output(processed_docs)

    project_name = output.get("project_name") or "project_output"
    slug = re.sub(r"[^\w\s\-]", "", norm(project_name), flags=re.UNICODE)
    slug = re.sub(r"\s+", "_", slug).strip("_")[:120] or "project_output"

    output_path = os.path.join(output_dir, f"{slug}.json")

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    total_tasks = sum(
        len(enterprise.get("tasks", []))
        for enterprise in output.get("enterprises", [])
    )

    print(f"Empresas: {len(output.get('enterprises', []))} | Tareas: {total_tasks}")


if __name__ == "__main__":
    process_folder(INPUT_DIR, OUTPUT_DIR)
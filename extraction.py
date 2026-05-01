import re
from typing import Any, Dict, List, Optional

from config import (
    EMAIL_PAT,
    PHONE_PAT,
    DATE_PAT,
    FRENCH_DATE_PAT,
    MONTHS_FR,
    LOT_PAT,
    BANNED_TASK_WORDS,
    PLANNING_HEADERS,
    TASK_KEYS,
    SECTION_MARKERS,
    TASK_LIKE_PREFIXES,
)

from text_utils import (
    norm,
    normh,
    normk,
    is_noise,
    lot_key,
    find_place,
    merge_loc,
)


def find_col(headers: List[str], candidates: set) -> Optional[int]:
    for index, header in enumerate(headers):
        if header in candidates:
            return index
    return None


def extract_date(text: str) -> Optional[str]:
    text = norm(text)

    match = FRENCH_DATE_PAT.search(text)
    if not match:
        return None

    day = match.group(1).zfill(2)
    month = MONTHS_FR.get(normh(match.group(2)))
    year = match.group(3)

    if not month:
        return None

    return f"{year}-{month}-{day}"


def split_pages(doc: Any) -> List[Dict]:
    pages = doc if isinstance(doc, list) else [doc]
    result = []

    for i, page in enumerate(pages):
        data = page.get("data", page)

        lines = [
            norm(part)
            for block in data.get("text_blocks", [])
            for part in str(
                block if isinstance(block, str) else block.get("text", "")
            )
            .replace("\r", "\n")
            .split("\n")
            if norm(part) and not is_noise(part)
        ]

        result.append({
            "page_number": page.get("page", i + 1),
            "lines": lines,
            "tables": data.get("tables", []),
        })

    return result


def extract_project_name(pages: List[Dict]) -> Optional[str]:
    lines = [
        norm(line)
        for page in pages[:2]
        for line in page["lines"][:10]
        if norm(line)
    ]

    for i in range(len(lines)):
        line = lines[i].upper()

        if (
            "EIFFAGE CONSTRUCTION" in line
            and i + 2 < len(lines)
            and "PAYS BASQUE LANDES" in lines[i + 1].upper()
        ):
            return lines[i + 2]

        if (
            "EIFFAGE CONSTRUCTION PAYS BASQUE LANDES" in line
            and i + 1 < len(lines)
        ):
            return lines[i + 1]

    return lines[0] if lines else None


def extract_report_date(pages: List[Dict]) -> Optional[str]:
    header_lines = [
        line
        for page in pages[:3]
        for line in page["lines"][:15]
    ]

    for line in header_lines:
        date = extract_date(line)

        if date:
            return date

    return None


def detect_page_lots(page: Dict) -> List[Dict]:
    lots = []
    seen = set()

    for line in page["lines"]:
        match = LOT_PAT.match(norm(line))

        if not match:
            continue

        code = norm(match.group(1) or "")
        name = norm(match.group(2) or "")

        code = re.sub(r"\b0+(\d+)\b", r"\1", code)
        full = f"LOT {code} {name}".strip()
        full = re.sub(r"\s+", " ", full)

        key = lot_key(full)

        if key and key not in seen:
            seen.add(key)
            lots.append({
                "lot": full,
                "lot_code": code or None,
            })

    return lots


def table_kind(table: Dict) -> str:
    headers = [normh(header) for header in table.get("headers", [])]

    if "entreprise" in headers:
        return "enterprise"

    if "taches" in headers or "tâches" in headers:
        return "planning"

    return "other"


def get_enterprises(table: Dict) -> List[str]:
    headers = [normh(h) for h in table.get("headers", [])]

    if "entreprise" not in headers:
        return []

    idx = headers.index("entreprise")
    seen = set()
    result = []

    for row in table.get("rows", []):
        if idx >= len(row):
            continue

        enterprise = norm(row[idx])

        if not enterprise or is_noise(enterprise):
            continue

        key = normk(enterprise)

        if key not in seen:
            seen.add(key)
            result.append(enterprise)

    return result


def norm_task_text(text: str) -> str:
    text = norm(text)
    text = DATE_PAT.sub("", text)
    text = re.sub(r"\bsem(?:aine)?\.?\s*\d+\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+\s*/\s*\d+\b", "", text)

    return re.sub(r"\s+", " ", text).strip(" -:;,.")


def is_task(text: str) -> bool:
    text = norm(text)
    low = normh(text)

    if (
        not text
        or len(text) < 2
        or is_noise(text)
        or EMAIL_PAT.search(text)
        or PHONE_PAT.search(text)
        or low in PLANNING_HEADERS
        or low in BANNED_TASK_WORDS
    ):
        return False

    return bool(re.search(r"[A-Za-zÀ-ÿ0-9]", text))


def is_section_row(cells: List[str]) -> bool:
    parts = [norm(cell) for cell in cells if norm(cell)]

    if not parts:
        return False

    joined_low = normh(" ".join(parts).strip())

    if joined_low.startswith(TASK_LIKE_PREFIXES):
        return False

    if joined_low in SECTION_MARKERS:
        return True

    if len(joined_low) <= 25 and re.fullmatch(
        r"(cage\s+[a-z0-9]+|interieure|exterieure|pvc\s+cage\s+[a-z0-9]+)",
        joined_low,
    ):
        return True

    joined_clean = re.sub(r"\([^)]*\)", "", joined_low).strip()

    if re.fullmatch(r"cage\s+[a-z0-9]+", joined_clean):
        return True

    return False


def extract_tasks(
    table: Dict,
    report_date: Optional[str],
    page_lot: Optional[str],
    enterprises: List[str],
) -> List[Dict]:
    tasks = []
    headers = [normh(header) for header in table.get("headers", [])]

    task_index = find_col(headers, TASK_KEYS)

    if task_index is None:
        return []

    current_section = None
    current_parent = None
    enterprise = enterprises[0] if len(enterprises) == 1 else None

    for row in table.get("rows", []):
        if not isinstance(row, list):
            continue

        def get(index):
            return norm(row[index]) if index is not None and index < len(row) else ""

        if is_section_row([norm(cell) for cell in row]):
            current_section = " ".join(
                norm(cell) for cell in row if norm(cell)
            )
            current_section = re.sub(
                r"\([^)]*\)",
                "",
                current_section,
            ).strip(" -:;,.")
            continue

        raw_task = get(task_index)
        task_text = norm_task_text(raw_task)

        if not task_text:
            continue

        if norm(raw_task).endswith(":"):
            current_parent = task_text
            continue

        real_loc = find_place(task_text)
        is_loc_only = bool(real_loc) and normk(task_text) == normk(real_loc)

        if current_parent and is_loc_only:
            tasks.append({
                "lot": page_lot,
                "enterprise": enterprise,
                "task": current_parent,
                "location": merge_loc(page_lot, current_section, task_text),
                "start_date": report_date,
                "end_date": report_date,
            })
            continue

        if not is_task(task_text):
            continue

        task_clean = (
            re.sub(r"\s+", " ", task_text.replace(real_loc, "")).strip(" -:;,.")
            if real_loc else task_text
        )

        if not is_task(task_clean):
            continue

        current_parent = task_clean

        tasks.append({
            "lot": page_lot,
            "enterprise": enterprise,
            "task": task_clean,
            "location": merge_loc(page_lot, current_section, real_loc),
            "start_date": report_date,
            "end_date": report_date,
        })

    return tasks


def process_document(doc: Any, filename: str) -> Dict:
    pages = split_pages(doc)
    report_date = extract_report_date(pages)

    all_tasks = []
    enterprise_blocks = []

    for page in pages:
        page_lots = detect_page_lots(page)
        current_lot = page_lots[0]["lot"] if page_lots else None
        current_enterprises: List[str] = []
        ent_lot_idx = 0

        for table in page.get("tables", []):
            kind = table_kind(table)

            if kind == "enterprise":
                enterprises = get_enterprises(table)

                if page_lots:
                    current_lot = page_lots[
                        min(ent_lot_idx, len(page_lots) - 1)
                    ]["lot"]

                current_enterprises = enterprises

                for enterprise in enterprises:
                    enterprise_blocks.append({
                        "lot": current_lot,
                        "enterprise": enterprise,
                    })

                if page_lots and ent_lot_idx < len(page_lots) - 1:
                    ent_lot_idx += 1

            elif kind == "planning":
                all_tasks.extend(
                    extract_tasks(
                        table=table,
                        report_date=report_date,
                        page_lot=current_lot,
                        enterprises=current_enterprises,
                    )
                )

    unique_enterprises = {}

    for item in enterprise_blocks:
        key = (
            lot_key(item.get("lot")),
            normk(item.get("enterprise")),
        )
        unique_enterprises[key] = item

    return {
        "source_file": filename,
        "report_date": report_date,
        "project_name": extract_project_name(pages),
        "enterprises": list(unique_enterprises.values()),
        "tasks": all_tasks,
    }
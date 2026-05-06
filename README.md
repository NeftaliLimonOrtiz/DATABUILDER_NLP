# DATABUILDER_NLP
This project implements an NLP pipeline for extracting information from OCR JSON files of construction site reports.

The pipeline processes construction documents and extracts:

- Project names
- LOT identifiers
- Enterprises
- Construction tasks
- Locations
- Dates

The extracted information is normalized, merged, and grouped into a single JSON output.

## Overview

The pipeline performs the following steps:

1. Loads OCR-generated JSON construction reports.
2. Extracts project names and report dates.
3. Detects LOTs and associated enterprises.
4. Identifies tables containing construction tasks.
5. Extracts tasks, locations, and dates.
6. Normalizes LOT and enterprise names.
7. Merges semantically similar tasks across reports.
8. Consolidates locations and date ranges.
9. Exports the data as JSON files.

## Installation
Install dependencies:

```bash
pip install -r requirements.txt
```
## Usage

Edit the following paths in config.py:
```bash
PDF_PATH = "path/to/pdf/or/folder"
OUTPUT_DIR = "path/to/output/folder"
```
Then run:

```bash
python main.py
```
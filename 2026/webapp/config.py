"""Application configuration resolved relative to the submission folder."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DISPATCH_DATA_DIR", BASE_DIR / "data"))
SOURCE_DIR = Path(os.getenv("DISPATCH_SOURCE_DIR", DATA_DIR / "source"))
RUNTIME_DIR = Path(os.getenv("DISPATCH_RUNTIME_DIR", DATA_DIR / "runtime"))

MODEL_WORKBOOK = SOURCE_DIR / "모델링_최종후보표.xlsx"
OD_WORKBOOK = SOURCE_DIR / "순차모델링_OD캐시.xlsx"
FIXED_HISTORY_WORKBOOK = SOURCE_DIR / "순차모델링_FIXED스케줄.xlsx"
MODEL_DATASET = RUNTIME_DIR / "model_dataset.json"
STATE_FILE = Path(os.getenv("DISPATCH_STATE_FILE", RUNTIME_DIR / "dispatch_state.json"))

MIN_ARRIVAL_SLACK_MIN = int(os.getenv("MIN_ARRIVAL_SLACK_MIN", "25"))
MAX_WORK_GAP_H = float(os.getenv("MAX_WORK_GAP_H", "24"))
STATE_STALE_CUTOFF_H = float(os.getenv("STATE_STALE_CUTOFF_H", "120"))
TOP_CANDIDATES = int(os.getenv("TOP_CANDIDATES", "10"))


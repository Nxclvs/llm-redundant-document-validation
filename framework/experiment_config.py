from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List


def load_experiments(config_path: str) -> List[Dict[str, Any]]:
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with p.open("r", encoding="utf-8") as f:
        cfg = json.load(f)


    exps = cfg.get("experiments")
    if not isinstance(exps, list) or not exps:
        raise ValueError("'experiments' key is missing")
    
    return exps


def get_experiment(config_path: str, name: str) -> Dict[str, Any]:
    exps = load_experiments(config_path)
    for e in exps:
        if e.get("name") == name:
            return e
    available = [e.get("name") for e in exps]
    raise ValueError(f"Experiment '{name}' not found. Available: {available}")


def list_experiment_names(config_path: str) -> List[str]:
    return [e.get("name") for e in load_experiments(config_path)]
#!/usr/bin/env python3
"""Обучение и проверка модели по признакам попыток.

Что делает:
  1) читает train_data/dataset.csv (получен из export_dataset.py);
  2) делит попытки ПО СТУДЕНТАМ (GroupKFold) — иначе метрика врёт;
  3) для каждой из пяти меток учит две модели: логистическую регрессию и градиентный бустинг;
  4) сравнивает модель с текущими порогами из scoring.py на той же разметке;
  5) считает согласие экспертов (каппа Коэна), если одну попытку разметили двое;
  6) пишет отчёт train_data/report.md и модель backend/models/technique_model.pkl.

Запуск:
    python tools/train_model.py
    python tools/train_model.py --dataset train_data/dataset.csv --min-kappa 0.7

Порог внедрения — каппа ≥ 0,7 по каждой метке. Ниже порога модель не внедряем,
оставляем пороги: это нормальный результат, а не провал.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.dataset_schema import FEATURES, LABELS, LABEL_RU, rule_prediction  # noqa: E402

MIN_ROWS = 40          # меньше — учить нечему, честно говорим об этом
MIN_PER_CLASS = 8      # нужно хотя бы столько «да» и столько «нет»


# ------------------------------------------------------------------ метрики
def cohen_kappa(y_true: list[int], y_pred: list[int]) -> float:
    """Каппа Коэна: согласие за вычетом случайного. 1 — полное, 0 — случайное."""
    n = len(y_true)
    if n == 0:
        return float("nan")
    labels = sorted(set(y_true) | set(y_pred))
    if len(labels) < 2:
        return 1.0
    agree = sum(1 for t, p in zip(y_true, y_pred) if t == p) / n
    expected = 0.0
    for label in labels:
        pt = y_true.count(label) / n
        pp = y_pred.count(label) / n
        expected += pt * pp
    if abs(1.0 - expected) < 1e-12:
        return float("nan")
    return (agree - expected) / (1.0 - expected)


def confusion(y_true: list[int], y_pred: list[int]) -> dict[str, int]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn}


def f1_from(c: dict[str, int]) -> float:
    denom = 2 * c["tp"] + c["fp"] + c["fn"]
    return (2 * c["tp"] / denom) if denom else float("nan")


def as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ данные
def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for row in rows:
        labels = {}
        for label in LABELS:
            v = as_float(row.get(label))
            if v is None:
                break
            labels[label] = int(v > 0)
        else:
            features = [as_float(row.get(f)) for f in FEATURES]
            out.append({
                "id": row.get("id"),
                "student": (row.get("student") or row.get("id") or "?").strip(),
                "expert": (row.get("expert") or "?").strip(),
                "labels": labels,
                "features": features,
                "raw": row,
            })
    return out


def complete_mask(rows: list[dict[str, Any]]) -> list[int]:
    return [i for i, r in enumerate(rows) if all(v is not None for v in r["features"])]


# ------------------------------------------------------------------ обучение
def train_label(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    y = np.array([r["labels"][label] for r in rows], dtype=int)
    X = np.array([[v if v is not None else np.nan for v in r["features"]] for r in rows], dtype=float)
    groups = np.array([r["student"] for r in rows])

    pos, neg = int(y.sum()), int(len(y) - y.sum())
    base = {
        "label": label,
        "ru": LABEL_RU[label],
        "rows": len(y),
        "pos": pos,
        "neg": neg,
        "status": "ok",
        "models": {},
        "rule": {},
    }
    if len(y) < MIN_ROWS or pos < MIN_PER_CLASS or neg < MIN_PER_CLASS:
        base["status"] = "мало данных"
        base["hint"] = (f"нужно ≥ {MIN_ROWS} попыток и ≥ {MIN_PER_CLASS} в каждом классе "
                        f"(сейчас да={pos}, нет={neg})")
        return base

    n_splits = min(5, len(set(groups)))
    if n_splits < 2:
        # один студент — групповое деление невозможно, честно помечаем
        base["status"] = "один студент"
        base["hint"] = "нужны записи минимум двух разных людей, иначе проверка бессмысленна"
        return base

    cv = GroupKFold(n_splits=n_splits)
    candidates = {
        "logreg": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]),
        "boost": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("clf", HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.08,
                                                   random_state=0)),
        ]),
    }

    best_name, best_kappa, best_model, best_pred = None, -2.0, None, None
    for name, model in candidates.items():
        try:
            pred = cross_val_predict(model, X, y, groups=groups, cv=cv, method="predict")
        except Exception as exc:  # noqa: BLE001
            base["models"][name] = {"error": str(exc)}
            continue
        kappa = cohen_kappa(list(y), list(pred))
        c = confusion(list(y), list(pred))
        base["models"][name] = {
            "kappa": round(kappa, 3) if not math.isnan(kappa) else None,
            "f1": round(f1_from(c), 3) if not math.isnan(f1_from(c)) else None,
            "accuracy": round(float((pred == y).mean()), 3),
            "confusion": c,
        }
        if not math.isnan(kappa) and kappa > best_kappa:
            best_name, best_kappa, best_model, best_pred = name, kappa, model, pred

    # правило из scoring.py на тех же данных
    rule_pred, rule_true = [], []
    for r in rows:
        p = rule_prediction(label, r["raw"])
        if p is not None:
            rule_pred.append(p)
            rule_true.append(r["labels"][label])
    if rule_pred:
        c = confusion(rule_true, rule_pred)
        kappa = cohen_kappa(rule_true, rule_pred)
        base["rule"] = {
            "kappa": round(kappa, 3) if not math.isnan(kappa) else None,
            "f1": round(f1_from(c), 3) if not math.isnan(f1_from(c)) else None,
            "coverage": round(len(rule_pred) / len(rows), 3),
            "confusion": c,
        }

    if best_model is not None:
        best_model.fit(X, y)                     # финальное обучение на всех данных
        base["best"] = best_name
        base["kappa"] = round(best_kappa, 3)
        base["_fitted"] = best_model
        base["feature_importance"] = importance(best_model, X, y, FEATURES)
    return base


def importance(model: Any, X: Any, y: Any, names: list[str]) -> list[dict[str, Any]]:
    """Грубая важность признаков: насколько падает каппа, если признак перемешать."""
    import numpy as np

    try:
        base_pred = model.predict(X)
        base = cohen_kappa(list(y), list(base_pred))
        rng = np.random.default_rng(0)
        out = []
        for i, name in enumerate(names):
            Xp = X.copy()
            rng.shuffle(Xp[:, i])
            k = cohen_kappa(list(y), list(model.predict(Xp)))
            drop = (base - k) if not (math.isnan(base) or math.isnan(k)) else 0.0
            out.append({"feature": name, "drop": round(float(drop), 4)})
        out.sort(key=lambda d: -d["drop"])
        return out[:6]
    except Exception:  # noqa: BLE001
        return []


def inter_expert_kappa(rows_all: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Согласие экспертов: одна попытка (id) размечена двумя разными экспертами."""
    by_id: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    for r in rows_all:
        by_id[r["id"]][r["expert"]] = r["labels"]
    pairs = [(v) for v in by_id.values() if len(v) >= 2]
    if not pairs:
        return None
    result = {}
    for label in LABELS:
        a, b = [], []
        for annotators in pairs:
            experts = list(annotators.values())[:2]
            a.append(experts[0][label])
            b.append(experts[1][label])
        kappa = cohen_kappa(a, b)
        result[label] = round(kappa, 3) if not math.isnan(kappa) else None
    result["_pairs"] = len(pairs)
    return result


# ------------------------------------------------------------------ отчёт
def write_report(path: Path, results: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    lines = [
        "# Отчёт обучения модели",
        "",
        f"Попыток в датасете: **{meta['rows']}** · студентов: **{meta['students']}** · "
        f"экспертов: **{meta['experts']}**",
        "",
        "Проверка — по студентам (GroupKFold): кадры одного человека не попадают "
        "одновременно в обучение и проверку.",
        "",
        "| Критерий | Попыток | Пороги сейчас (каппа) | Модель (каппа) | F1 модели | Что делать |",
        "|---|---|---|---|---|---|",
    ]
    for res in results:
        rule = res["rule"].get("kappa")
        model = res.get("kappa")
        f1 = res["models"].get(res.get("best", ""), {}).get("f1") if res.get("best") else None
        if res["status"] != "ok":
            verdict = f"мало данных: {res.get('hint', '')}"
        elif model is None:
            verdict = "модель не лучше порогов — оставить пороги"
        elif model >= 0.7:
            verdict = "внедрять модель"
        elif rule is not None and model <= rule:
            verdict = "оставить пороги"
        else:
            verdict = "модель лучше, но ниже 0,7 — собрать больше данных"
        lines.append(
            f"| {res['ru']} | {res['rows']} | {rule if rule is not None else '—'} | "
            f"{model if model is not None else '—'} | {f1 if f1 is not None else '—'} | {verdict} |"
        )

    lines += ["", "## Подробности по критериям", ""]
    for res in results:
        lines.append(f"### {res['ru']} (`{res['label']}`)")
        lines.append("")
        lines.append(f"Попыток: {res['rows']}, «да»: {res['pos']}, «нет»: {res['neg']}.")
        for name, data in res["models"].items():
            if "error" in data:
                lines.append(f"- {name}: сбой — {data['error']}")
            else:
                c = data["confusion"]
                lines.append(
                    f"- {name}: каппа {data['kappa']}, F1 {data['f1']}, точность {data['accuracy']}; "
                    f"ошибки: пропустил {c['fn']}, придумал {c['fp']}"
                )
        if res["rule"]:
            lines.append(f"- правило сейчас: каппа {res['rule']['kappa']}, F1 {res['rule']['f1']}")
        if res.get("feature_importance"):
            top = ", ".join(f"{d['feature']} {d['drop']:+.3f}" for d in res["feature_importance"][:4])
            lines.append(f"- важные признаки: {top}")
        lines.append("")

    lines += [
        "## Как читать",
        "",
        "- **каппа ≥ 0,7** — модель можно внедрять вместо порогов;",
        "- **каппа 0,5–0,7** — лучше порогов, но данных мало: добрать попытки;",
        "- **каппа < 0,5** — либо модель плохая, либо разметка противоречивая: сначала уточнить критерии;",
        "- если каппа между экспертами ниже 0,5, обучать бессмысленно — эксперты сами не договорились.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


# ------------------------------------------------------------------ главное
def main() -> int:
    parser = argparse.ArgumentParser(description="Обучение модели по признакам попыток")
    parser.add_argument("--dataset", default=str(ROOT / "train_data" / "dataset.csv"))
    parser.add_argument("--report", default=str(ROOT / "train_data" / "report.md"))
    parser.add_argument("--model-out", default=str(ROOT / "backend" / "models" / "technique_model.pkl"))
    parser.add_argument("--min-kappa", type=float, default=0.7)
    parser.add_argument("--save", action="store_true", help="сохранить модель в .pkl")
    args = parser.parse_args()

    try:
        import sklearn  # noqa: F401
    except ImportError:
        print("нужен scikit-learn: pip install -r requirements-train.txt", file=sys.stderr)
        return 1

    path = Path(args.dataset)
    if not path.exists():
        print(f"нет датасета {path}\nсначала: python tools/export_dataset.py", file=sys.stderr)
        return 1

    rows_all = load_rows(path)
    if not rows_all:
        print("в датасете нет строк с заполненными метками — проверьте разметку", file=sys.stderr)
        return 1
    rows = [rows_all[i] for i in complete_mask(rows_all)]
    if not rows:
        print("у всех строк есть пустые признаки — пересчитайте датасет (--force)", file=sys.stderr)
        return 1

    meta = {
        "rows": len(rows),
        "students": len({r["student"] for r in rows}),
        "experts": len({r["expert"] for r in rows}),
    }
    print(f"попыток: {meta['rows']} · студентов: {meta['students']} · экспертов: {meta['experts']}")

    experts = inter_expert_kappa(rows_all)
    if experts:
        print(f"согласие экспертов (каппа): {experts}")

    results = []
    for label in LABELS:
        res = train_label(rows, label)
        results.append(res)
        rule = res["rule"].get("kappa") if res["rule"] else None
        print(f"  {label:18s} правило: {str(rule):6s} модель: {str(res.get('kappa')):6s} "
              f"({res['status']})")

    write_report(Path(args.report), results, meta)
    print(f"\nотчёт: {args.report}")

    ready = [r for r in results if r.get("kappa") is not None and r["kappa"] >= args.min_kappa]
    if args.save and ready:
        import joblib
        payload = {
            "features": FEATURES,
            "labels": LABELS,
            "min_kappa": args.min_kappa,
            "models": {r["label"]: r["_fitted"] for r in ready},
            "kappa": {r["label"]: r["kappa"] for r in ready},
            "thresholds_fallback": {
                "tempo": (100.0, 120.0), "depth": (5.0, 6.0), "pct": 85.0,
            },
        }
        out = Path(args.model_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(payload, out)
        (out.with_suffix(".json")).write_text(
            json.dumps({k: v for k, v in payload.items() if k != "models"},
                       ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"модель сохранена: {out} (критериев: {len(ready)})")
    elif args.save:
        print(f"модель не сохранена: ни один критерий не достиг каппы {args.min_kappa} — "
              "оставляем пороги scoring.py")

    if not any(r["status"] == "ok" for r in results):
        print("\nВНИМАНИЕ: данных мало для обучения. Цепочка работает, но каппу считать не на чем.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed remapping of rater-bundle IDs to scorer IDs."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def remap_bundle_rows(
    rows: Iterable[dict[str, str]],
    key_path: Path,
    *,
    scorer_id_field: str,
) -> list[dict[str, str]]:
    """Return copied rows with nonce-derived bundle IDs mapped to scorer IDs.

    Legacy scorer-format rows whose IDs are already scorer IDs remain valid. A
    mixed or unknown ID namespace is fatal, preventing accidental partial joins.
    """

    copied = [dict(row) for row in rows]
    if not copied:
        raise ValueError("ratings CSV is empty")
    if not key_path.exists():
        raise FileNotFoundError(f"bundle key does not exist: {key_path}")

    key_rows = read_csv(key_path)
    required = {"bundle_rating_id", "scorer_rating_id"}
    if not key_rows or not required.issubset(key_rows[0]):
        raise ValueError(f"invalid bundle key schema: {key_path}")
    mapping = {
        row["bundle_rating_id"].strip(): row["scorer_rating_id"].strip()
        for row in key_rows
    }
    if len(mapping) != len(key_rows) or "" in mapping or "" in mapping.values():
        raise ValueError(f"bundle key has blank or duplicate IDs: {key_path}")
    scorer_ids = set(mapping.values())

    input_field = scorer_id_field if scorer_id_field in copied[0] else "rating_id"
    if input_field not in copied[0]:
        raise ValueError(
            f"ratings CSV must contain {scorer_id_field!r} or 'rating_id'"
        )
    incoming = [row.get(input_field, "").strip() for row in copied]
    if any(not value for value in incoming):
        raise ValueError("ratings CSV contains blank IDs")

    bundle_namespace = all(value in mapping for value in incoming)
    scorer_namespace = all(value in scorer_ids for value in incoming)
    if not bundle_namespace and not scorer_namespace:
        unknown = sorted(set(incoming) - set(mapping) - scorer_ids)
        raise ValueError(
            "ratings IDs do not form a complete bundle or scorer namespace; "
            f"unknown IDs: {unknown[:5]}"
        )
    if bundle_namespace and scorer_namespace:
        raise ValueError("bundle and scorer ID namespaces overlap")

    if bundle_namespace:
        for row, incoming_id in zip(copied, incoming, strict=True):
            row[scorer_id_field] = mapping[incoming_id]
            if input_field != scorer_id_field:
                row.pop(input_field, None)
    elif input_field != scorer_id_field:
        for row, incoming_id in zip(copied, incoming, strict=True):
            row[scorer_id_field] = incoming_id
            row.pop(input_field, None)
    return copied

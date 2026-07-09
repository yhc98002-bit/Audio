# EVPD Split Report

{
  "train": {
    "candidates": 1680,
    "prompts": 210
  },
  "val": {
    "candidates": 368,
    "prompts": 46
  },
  "test": {
    "candidates": 2048,
    "prompts": 256
  },
  "prompt_overlap_train_test": 0,
  "prompt_overlap_train_val": 0,
  "prompt_overlap_val_test": 0,
  "label_pos_rate_overall": 0.5869
}

- test = held_out (untouched). dev -> train/val by prompt hash. 0 overlap required.
- All 8 candidates of a prompt share a split (split assigned per prompt_id).
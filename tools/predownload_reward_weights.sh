#!/usr/bin/env bash
# Pre-stage all reward-model weights into the shared Lustre FS so the M0 D2
# reward harness on compute nodes (slow proxy egress) doesn't have to fetch
# them at run time. Run this on a node with fast network (login node usually
# has higher outbound bandwidth than compute nodes).
#
# Total transfer: ~1.7 GB. At ~10 MB/s on a login node this is ~3 min.
#
# Safe to re-run: each file is skipped if already present + non-empty.
#
# After this finishes, launch_phase_a.sh on the compute node will read the
# LAION_CLAP_{BERT,ROBERTA,BART}_DIR, AUDIOBOX_AES_CKPT, and MERT_LOCAL_PATH
# env vars (set automatically in the script's Paratera activation block).

set -euo pipefail

# Need proxy for hf-mirror.com + fbaipublicfiles.com (overseas hosts)
if [[ -f "$HOME/proxy_on.sh" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/proxy_on.sh"
fi

# 2026-05-19 Codex review: preflight — fail loudly if the proxy / mirror is
# unreachable, rather than letting every curl retry-and-fail in silence.
if ! curl -fsS --connect-timeout 5 -o /dev/null "https://hf-mirror.com/" 2>/dev/null; then
    echo "ERROR: cannot reach https://hf-mirror.com/ (probably no mihomo on this node)." >&2
    echo "  If on a node WITHOUT mihomo: either start mihomo locally on port 7890," >&2
    echo "  set up an SSH tunnel ('ssh -L 7890:127.0.0.1:7890 -N pxy1289@an12 &')," >&2
    echo "  or unset http(s)_proxy if this node has direct outbound." >&2
    exit 2
fi

SRC_ROOT="$HOME/HDD_POOL/source"
mkdir -p "$SRC_ROOT"/{laion_clap_tokenizers,audiobox_aesthetics,mert}
mkdir -p "$HOME/.cache/clap" "$HOME/.cache/torch/hub/checkpoints"

HFM="https://hf-mirror.com"

# Curl helper: skip if file present + non-empty; atomic-write via temp file.
# 2026-05-19 Codex review: previously a curl killed mid-stream left a non-empty
# corrupt file that was skipped on re-run. Now we download to "${out}.tmp.$$"
# and `mv` only on success; on retry, the corrupt temp is overwritten and the
# stale final-name file is detected by content-length mismatch on first attempt.
fetch() {
    local out="$1" url="$2"
    if [[ -s "$out" ]]; then
        printf "  skip (already present, %s): %s\n" "$(du -h "$out" | cut -f1)" "$(basename "$out")"
        return 0
    fi
    printf "  fetch %s -> %s\n" "$url" "$out"
    local tmp="${out}.tmp.$$"
    rm -f "$tmp"
    # -f: fail on HTTP 4xx/5xx (avoid 0-byte files), -L: follow redirects,
    # --connect-timeout: bail fast on dead hosts.
    if curl -fL --retry 3 --retry-delay 2 --connect-timeout 20 -o "$tmp" "$url"; then
        mv -f "$tmp" "$out"
    else
        rm -f "$tmp"
        return 1
    fi
}

# 2026-05-19 Codex review: required files must fail hard, not || true. Compute
# nodes have ~2 MB/s bandwidth and we don't want to discover a missing tokenizer
# 6 hours into M1a. Only files we KNOW are absent upstream get tolerated below.
#
# Per Codex verification against HF Hub: bert-base-uncased and roberta-base both
# expose model.safetensors AND pytorch_model.bin; we prefer safetensors. BART
# does NOT ship tokenizer_config.json/special_tokens_map.json on main — they're
# omitted from the required list.

echo "=== [1/6] bert-base-uncased (transformers AutoModel + tokenizer) ==="
BERT="$SRC_ROOT/laion_clap_tokenizers/bert-base-uncased"
mkdir -p "$BERT"
for f in config.json tokenizer.json tokenizer_config.json vocab.txt model.safetensors; do
    fetch "$BERT/$f" "$HFM/bert-base-uncased/resolve/main/$f"
done
# special_tokens_map.json may be absent on some snapshots — tolerate.
fetch "$BERT/special_tokens_map.json" "$HFM/bert-base-uncased/resolve/main/special_tokens_map.json" || true

echo "=== [2/6] roberta-base (transformers AutoModel + tokenizer) ==="
ROBERTA="$SRC_ROOT/laion_clap_tokenizers/roberta-base"
mkdir -p "$ROBERTA"
for f in config.json tokenizer.json tokenizer_config.json vocab.json merges.txt model.safetensors; do
    fetch "$ROBERTA/$f" "$HFM/roberta-base/resolve/main/$f"
done
fetch "$ROBERTA/special_tokens_map.json" "$HFM/roberta-base/resolve/main/special_tokens_map.json" || true

echo "=== [3/6] facebook/bart-base (tokenizer only — no tokenizer_config / special_tokens_map upstream) ==="
BART="$SRC_ROOT/laion_clap_tokenizers/facebook--bart-base"
mkdir -p "$BART"
for f in config.json tokenizer.json vocab.json merges.txt; do
    fetch "$BART/$f" "$HFM/facebook/bart-base/resolve/main/$f"
done

echo "=== [4/6] audiobox-aesthetics checkpoint.pt (415 MB; fbaipublicfiles S3) ==="
fetch "$SRC_ROOT/audiobox_aesthetics/checkpoint.pt" \
      "https://dl.fbaipublicfiles.com/audiobox-aesthetics/checkpoint.pt"

echo "=== [5/6] MERT-v1-95M (377 MB; via hf-mirror) ==="
MERT="$SRC_ROOT/mert/MERT-v1-95M"
mkdir -p "$MERT"
for f in config.json configuration_MERT.py modeling_MERT.py preprocessor_config.json pytorch_model.bin; do
    fetch "$MERT/$f" "$HFM/m-a-p/MERT-v1-95M/resolve/main/$f"
done

echo "=== [6/6] CLAP 630k-audioset-best.pt (~144 MB; lukewys/laion_clap via hf-mirror) ==="
# laion_clap.CLAP_Module(...).load_ckpt(model_id=1) downloads to ~/.cache/clap/
# by default. Pre-stage here so first M0 D2 invocation is offline.
fetch "$HOME/.cache/clap/630k-audioset-best.pt" \
      "$HFM/lukewys/laion_clap/resolve/main/630k-audioset-best.pt"

echo
echo "=== Summary ==="
du -sh "$SRC_ROOT"/*/* 2>/dev/null
du -sh "$HOME/.cache/clap"/*.pt 2>/dev/null
echo
echo "Total weights staged:"
du -ch "$SRC_ROOT" "$HOME/.cache/clap" 2>/dev/null | tail -1
echo
echo "All done. Return to the compute node (an12) and tell Claude to continue."

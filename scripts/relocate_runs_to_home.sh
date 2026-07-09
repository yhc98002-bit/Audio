#!/usr/bin/env bash
# Relocate the two large ADSR run trees from /XYFS02 (over its 510GB user quota) to /HOME
# (XYFS01, no per-user quota), then symlink them back so every code path is unchanged.
# SAFETY: copy-and-verify BEFORE removing source; abort on any mismatch; never delete a tree
# whose dest file-count/bytes do not match the source. Idempotent-ish: skips a tree already
# relocated (source is already a symlink).
set -u
REPO=/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
DEST=/HOME/paratera_xy/pxy1289/AudioDiffusion_runs_offload   # real XYFS01 (NOT under HDD_POOL)
TREES=(adsr_recollect_20260604_full01 adsr_recollect_resume)
cd "$REPO" || { echo "FATAL cd"; exit 9; }

# 0) guard: no live writer (worker/collector) should be touching runs/ during the move
if pgrep -af "collect_early_tweedie_validation.py" | grep -qv pgrep; then
  echo "FATAL: a collector is running locally; stop it before relocating"; exit 8; fi

# 1) confirm DEST is on a DIFFERENT filesystem than the source (i.e. really XYFS01, not a loop
#    back to /XYFS02 via the HDD_POOL symlink). Compare the df mount source device strings.
mkdir -p "$DEST" || { echo "FATAL mkdir DEST"; exit 9; }
SRC_DEV=$(df -P runs 2>/dev/null | awk 'NR==2{print $1}')
DST_DEV=$(df -P "$DEST" 2>/dev/null | awk 'NR==2{print $1}')
echo "SRC_DEV=$SRC_DEV"; echo "DST_DEV=$DST_DEV"
case "$SRC_DEV" in *XYFS02*) :;; *) echo "FATAL: source not on XYFS02 ($SRC_DEV)"; exit 7;; esac
case "$DST_DEV" in *XYFS01*) :;; *) echo "FATAL: DEST not on XYFS01 ($DST_DEV) — would not free /XYFS02 quota"; exit 7;; esac

for T in "${TREES[@]}"; do
  echo "=================== $T ==================="
  if [ -L "runs/$T" ]; then echo "SKIP $T: already a symlink -> $(readlink runs/$T)"; continue; fi
  if [ ! -d "runs/$T" ]; then echo "SKIP $T: source dir missing"; continue; fi

  # pre-record source fingerprint
  SF=$(find "runs/$T" -type f | wc -l)
  SB=$(find "runs/$T" -type f -printf '%s\n' | awk '{s+=$1} END{print s+0}')
  echo "source: files=$SF bytes=$SB"

  # copy (do NOT remove source yet); -a preserves. rsync default = write temp then atomic rename,
  # so an interrupted file never appears complete -> the byte/count verify below catches it.
  rsync -a "runs/$T/" "$DEST/$T/"
  RC=$?
  if [ "$RC" -ne 0 ]; then echo "FATAL rsync rc=$RC for $T — source untouched, aborting"; exit 5; fi

  # verify dest fingerprint matches source EXACTLY before deleting anything
  DF=$(find "$DEST/$T" -type f | wc -l)
  DB=$(find "$DEST/$T" -type f -printf '%s\n' | awk '{s+=$1} END{print s+0}')
  echo "dest:   files=$DF bytes=$DB"
  if [ "$SF" != "$DF" ] || [ "$SB" != "$DB" ]; then
    echo "FATAL mismatch for $T (src f=$SF b=$SB vs dst f=$DF b=$DB) — source kept, aborting"; exit 4; fi

  # verified identical -> remove source tree, then symlink
  rm -rf "runs/$T" || { echo "FATAL rm source $T"; exit 3; }
  ln -s "$DEST/$T" "runs/$T" || { echo "FATAL symlink $T"; exit 2; }

  # post-check: symlink resolves and a sample file is readable through it
  SAMPLE=$(find "runs/$T" -type f -name '*.jsonl' 2>/dev/null | head -1)
  echo "symlink: runs/$T -> $(readlink runs/$T) ; sample=$SAMPLE readable=$([ -r "$SAMPLE" ] && echo yes || echo NO)"
  echo "DONE $T"
done
echo "=== quota after ==="; lfs quota -u pxy1289 . 2>/dev/null | awk 'NR==3{printf "used=%.1fGB soft=%.1fGB hard=%.1fGB\n",$1/1048576,$2/1048576,$3/1048576}'
echo "RELOCATE_COMPLETE"

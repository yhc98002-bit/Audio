# Preserved Failed Full-Suite Attempt

The first attached final suite found two duplicated numeric uses of the vocal
threshold in `calibrate_w2_instrument.py`. The implementation now imports the
canonical `THRESHOLD`; the targeted threshold-constant test passed before the
full suite was rerun. The original pytest output and exit-code file are
preserved in this directory.

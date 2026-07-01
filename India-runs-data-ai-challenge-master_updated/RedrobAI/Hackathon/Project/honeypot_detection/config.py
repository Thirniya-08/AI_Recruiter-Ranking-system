"""Central thresholds and penalty controls for honeypot detection."""

HONEYPOT_THRESHOLDS = {
    "min_honeypot_score": 2,
}

PENALTY_WEIGHTS = {
    0: 1.0,
    1: 0.5,
    2: 0.2,
    3: 0.05,
    4: 0.05,
    5: 0.05,
}

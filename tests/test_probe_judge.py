from tide.probe import _parse_verdicts


def test_parse_verdicts_basic():
    assert _parse_verdicts("1. PASS\n2. FAIL\n3. PASS", 3) == [True, False, True]


def test_parse_verdicts_conservative_on_garbage():
    # Missing lines, out-of-range indices, malformed text → FAIL, never credit.
    assert _parse_verdicts("1. PASS\nnonsense\n7. PASS", 3) == [True, False, False]
    assert _parse_verdicts("", 2) == [False, False]


def test_parse_verdicts_tolerates_decoration():
    assert _parse_verdicts("  1.  pass — clearly stated\n2. FAILED", 2) == [True, False]

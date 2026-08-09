from tide.trajectory import find_score_log, load_trace, parse_score_log


def test_parse_valid_and_sorted():
    text = '{"t": 5, "score": 0.6}\n{"t": 1, "score": 0.2, "snapshot": "a"}\n'
    points = parse_score_log(text)
    assert [p.t for p in points] == [1.0, 5.0]
    assert points[0].data == {"snapshot": "a"}


def test_parse_skips_malformed_lines():
    text = "\n".join(
        [
            '{"t": 1, "score": 0.1}',
            "not json",
            '{"t": 2}',  # missing score
            '{"score": 3}',  # missing t
            '{"t": "abc", "score": 1}',  # bad t
            '{"t": 4, "score": 0.4}',
        ]
    )
    points = parse_score_log(text)
    assert [p.score for p in points] == [0.1, 0.4]


def test_find_score_log_nested(tmp_path):
    # Harbor mirrors the agent publish dir at artifacts/logs/artifacts/.
    nested = tmp_path / "logs" / "artifacts"
    nested.mkdir(parents=True)
    (nested / "score_log.jsonl").write_text('{"t": 1, "score": 0.5}\n')
    assert find_score_log(tmp_path) == nested / "score_log.jsonl"
    assert [p.score for p in load_trace(tmp_path)] == [0.5]


def test_missing_dir_and_log(tmp_path):
    assert find_score_log(tmp_path / "nope") is None
    assert load_trace(tmp_path) == []

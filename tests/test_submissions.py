"""Submission-log parsing: the judge's history becomes trace points."""

from tide.submissions import parse_submissions


def test_parse_sorts_and_keeps_extras():
    text = "\n".join(
        [
            '{"t": 5.0, "score": 0.6, "n": 1}',
            '{"t": 1.0, "score": 0.2, "n": 0}',
        ]
    )
    points = parse_submissions(text)
    assert [(p.t, p.score) for p in points] == [(1.0, 0.2), (5.0, 0.6)]
    assert points[0].data == {"n": 0}


def test_parse_is_lenient_about_bad_lines():
    text = "\n".join(
        [
            "not json",
            '{"t": "oops", "score": 1}',
            '{"score": 0.4}',
            '{"t": 2.0, "score": 0.4}',
            "",
        ]
    )
    points = parse_submissions(text)
    assert [(p.t, p.score) for p in points] == [(2.0, 0.4)]

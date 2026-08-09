import json

import pytest

from tide.loaders import load_rubric_probes, strip_context


@pytest.fixture()
def corpus(tmp_path):
    records = [
        {
            "messages": [
                {"role": "system", "content": "You are a rules lawyer."},
                {"role": "user", "content": "CONTEXT: In gloamball, a flumb scores 3."},
                {"role": "user", "content": "How much does a flumb score?"},
            ],
            "rubrics": ["states that a flumb scores 3"],
            "metadata": {"category": "rule-system"},
        },
        {
            "messages": [{"role": "user", "content": "q2"}],
            "rubrics": [{"rubric_criteria": "  criterion from dict  "}],
        },
    ]
    path = tmp_path / "CL-bench.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records))
    return path


def test_load_rubric_probes(corpus):
    probes = load_rubric_probes(corpus)
    assert len(probes) == 2
    assert probes[0].id == "CL-bench/0"
    assert probes[0].rubrics == ("states that a flumb scores 3",)
    assert probes[0].data == {"category": "rule-system"}
    assert probes[1].rubrics == ("criterion from dict",)


def test_limit_and_prefix(corpus):
    probes = load_rubric_probes(corpus, id_prefix="clb", limit=1)
    assert [p.id for p in probes] == ["clb/0"]


def test_corrupt_line_is_loud(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"messages": []}\nnot json\n')
    with pytest.raises(ValueError, match="bad.jsonl:2"):
        load_rubric_probes(path)


def test_reveal_phases_by_message():
    from tide.probe import Probe

    probe = Probe(
        id="q",
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "fact A"},
            {"role": "user", "content": "fact B"},
            {"role": "user", "content": "fact C"},
            {"role": "user", "content": "question?"},
        ],
        rubrics=("r1",),
    )
    from tide.loaders import reveal_phases

    phases = reveal_phases(probe, 3)
    assert [p.id for p in phases] == ["q@r0", "q@r1", "q@r2"]
    # phase 0 reveals only the first chunk; the question is always last
    assert [m["content"] for m in phases[0].messages] == ["sys", "fact A", "question?"]
    # the final phase equals the full original probe
    assert phases[-1].messages == probe.messages
    assert all(p.rubrics == ("r1",) for p in phases)


def test_reveal_phases_by_paragraph_for_single_context_message():
    from tide.loaders import reveal_phases
    from tide.probe import Probe

    context = "para one\n\npara two\n\npara three\n\npara four"
    probe = Probe(
        id="q",
        messages=[
            {"role": "user", "content": context},
            {"role": "user", "content": "question?"},
        ],
    )
    phases = reveal_phases(probe, 2)
    assert len(phases) == 2
    assert "para one" in phases[0].messages[0]["content"]
    assert "para three" not in phases[0].messages[0]["content"]
    joined = " ".join(m["content"] for m in phases[-1].messages)
    assert all(p in joined for p in ["para one", "para two", "para three", "para four"])


def test_reveal_phases_edge_cases():
    from tide.loaders import reveal_phases
    from tide.probe import Probe

    probe = Probe(id="q", messages=[{"role": "user", "content": "just a question"}])
    assert len(reveal_phases(probe, 5)) == 1  # nothing to reveal → one phase
    import pytest as _pytest

    with _pytest.raises(ValueError):
        reveal_phases(probe, 0)


def test_strip_context_keeps_system_and_question(corpus):
    probe = load_rubric_probes(corpus)[0]
    stripped = strip_context(probe)
    assert [m["role"] for m in stripped.messages] == ["system", "user"]
    assert stripped.messages[-1]["content"] == "How much does a flumb score?"
    assert "CONTEXT" not in json.dumps(stripped.messages)
    assert stripped.rubrics == probe.rubrics  # judging is unchanged

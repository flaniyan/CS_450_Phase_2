from acmecli.reporter import Reporter


def test_reporter_format():
    reporter = Reporter()
    data = {"foo": "bar"}
    out = reporter.format(data)
    assert '"foo": "bar"' in out or "'foo': 'bar'" in out

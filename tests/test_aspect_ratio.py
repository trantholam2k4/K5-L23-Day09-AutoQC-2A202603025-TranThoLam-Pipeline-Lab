from pipeline.checks import aspect_ratio


def test_aspect_ratio_flags_extreme_boxes(make_ds, cfg):
    ds = make_ds(
        images={"a": 1, "b": 2},
        labels={
            "a": ["0 0.5 0.5 0.2 0.2", "1 0.5 0.5 0.9 0.05"],
            "b": ["2 0.5 0.5 0.04 0.8"],
        },
    )
    iss = aspect_ratio.run(ds, cfg)
    assert [(i.image, i.code, i.severity, i.line) for i in iss] == [
        ("a", "BOX_ASPECT_RATIO", "warn", 2),
        ("b", "BOX_ASPECT_RATIO", "warn", 1),
    ]


def test_aspect_ratio_ignores_invalid_or_empty(make_ds, cfg):
    ds = make_ds(
        images={"a": 1},
        labels={"a": ["0 0.5 0.5 0 0.2", "bad line", ""]},
    )
    assert aspect_ratio.run(ds, cfg) == []

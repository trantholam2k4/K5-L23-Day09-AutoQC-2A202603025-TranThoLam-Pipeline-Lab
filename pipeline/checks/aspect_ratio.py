"""Check bổ sung — phát hiện bounding box lệch tỉ lệ khung hình bất thường."""
from ..common import WARN, Issue


def run(ds, cfg):
    c = cfg.get("aspect_ratio", {})
    max_ratio = float(c.get("max_ratio", 8.0))
    issues = []
    for lf in ds.label_files():
        stem = lf.stem
        for idx, ln in ds.read_label_lines(stem) or []:
            tok = ln.split()
            if len(tok) < 5:
                continue
            try:
                w, h = float(tok[3]), float(tok[4])
            except ValueError:
                continue
            if w <= 0 or h <= 0:
                continue
            ratio = max(w / h, h / w)
            if ratio > max_ratio:
                issues.append(
                    Issue(
                        "aspect_ratio",
                        WARN,
                        "BOX_ASPECT_RATIO",
                        stem,
                        f"dòng {idx}: tỉ lệ cạnh {ratio:.1f} > {max_ratio}",
                        line=idx,
                        extra={"ratio": round(ratio, 2)},
                    )
                )
    return issues

"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401

def fix(ds, issues, cfg):
    errors = [iss for iss in issues if iss.severity == ERROR]
    fixes = []
    removed_images = set()

    DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    REMOVE_IMG_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}

    # =========================================================================
    # BƯỚC 1: SỬA TÊN LỚP TRONG data.yaml (BAD_CLASS_NAME)
    # =========================================================================
    yaml_fixed = False
    for iss in errors:
        if iss.code == "BAD_CLASS_NAME" and not yaml_fixed:
            if ds.yaml_path.exists():
                data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
                old_names = data.get("names", [])
                new_names = list(cfg["classes"])
                data["names"] = new_names
                ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
                fixes.append({
                    "image": iss.image,
                    "line": "",
                    "action": "rename_classes",
                    "before": str(old_names),
                    "after": str(new_names),
                })
            yaml_fixed = True

    # =========================================================================
    # BƯỚC 2: XÓA ẢNH HỎNG / TRÙNG / RÒ RỈ TEST
    # =========================================================================
    for iss in errors:
        if iss.code.startswith("DUP_IMAGE_") or iss.code in REMOVE_IMG_CODES:
            stem = iss.image
            if stem in removed_images:
                continue
            img_p = ds.image_path(stem)
            lbl_p = ds.label_path(stem)
            before_name = img_p.name if img_p else stem
            if img_p is not None and img_p.exists():
                img_p.unlink()
            if lbl_p.exists():
                lbl_p.unlink()
            removed_images.add(stem)
            fixes.append({
                "image": stem,
                "line": "",
                "action": "remove_image",
                "before": before_name,
                "after": "(deleted)",
            })

    # =========================================================================
    # BƯỚC 3: GHI NHẬN ẢNH THIẾU FILE NHÃN (MISSING_LABEL_FILE)
    # =========================================================================
    seen_missing = set()
    for iss in errors:
        if iss.code == "MISSING_LABEL_FILE":
            stem = iss.image
            if stem in removed_images or stem in seen_missing:
                continue
            seen_missing.add(stem)
            fixes.append({
                "image": stem,
                "line": "",
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })

    # =========================================================================
    # BƯỚC 4: GOM LỖI DÒNG THEO TỪNG FILE VÀ SỬA MỘT LẦN DUY NHẤT
    # =========================================================================
    line_actions = defaultdict(dict)
    for iss in errors:
        stem = iss.image
        if stem in removed_images or iss.line is None:
            continue
        if iss.code in DROP_CODES:
            line_actions[stem][iss.line] = "drop"
        elif iss.code == "BOX_OUT_OF_IMAGE":
            if line_actions[stem].get(iss.line) != "drop":
                line_actions[stem][iss.line] = "clip"

    for stem, actions_by_line in line_actions.items():
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue
        raw_lines = lbl_p.read_text(encoding="utf-8").splitlines()
        new_lines = []
        for idx, raw_line in enumerate(raw_lines, start=1):
            act = actions_by_line.get(idx)
            before_str = raw_line.strip()

            if act == "drop":
                fixes.append({
                    "image": stem,
                    "line": idx,
                    "action": "drop_line",
                    "before": before_str,
                    "after": "(deleted)",
                })
            elif act == "clip":
                cls_id, cx, cy, w, h = parse_yolo_line(before_str)
                x1 = max(0.0, min(1.0, cx - w / 2))
                y1 = max(0.0, min(1.0, cy - h / 2))
                x2 = max(0.0, min(1.0, cx + w / 2))
                y2 = max(0.0, min(1.0, cy + h / 2))
                nw, nh = x2 - x1, y2 - y1

                if nw <= 0 or nh <= 0:
                    fixes.append({
                        "image": stem,
                        "line": idx,
                        "action": "drop_line",
                        "before": before_str,
                        "after": "(deleted)",
                    })
                else:
                    ncx, ncy = (x1 + x2) / 2, (y1 + y2) / 2
                    after_str = f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                    fixes.append({
                        "image": stem,
                        "line": idx,
                        "action": "clip_box",
                        "before": before_str,
                        "after": after_str,
                    })
                    new_lines.append(after_str)
            else:
                new_lines.append(raw_line)

        lbl_p.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")

    return fixes
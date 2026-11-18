"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    scfg = cfg["second_opinion"]
    issues = []
    num_classes = len(ds.classes)

    for img_path in ds.image_files():
        stem = img_path.stem
        raw_lines = ds.read_label_lines(stem)

        if stem not in preds or raw_lines is None:
            continue

        size = ds.image_size(stem)
        if size is None:
            continue
        img_w, img_h = size
        img_preds = preds[stem]
        valid_gt = ds.valid_boxes(stem)

        # =====================================================================
        # CHIỀU 1: DUYỆT TỪNG DỰ ĐOÁN CỦA MODEL (P) ĐỂ BẮT MISSING / LOOSE / WRONG_CLASS
        # =====================================================================
        for p in img_preds:
            p_cls, conf, rx, ry, rw, rh = p
            area_px = (rw * img_w) * (rh * img_h)

            if conf < scfg["conf"] or area_px < scfg["min_area_px"]:
                continue

            r_box = (rx, ry, rw, rh)
            cands = []
            for l_cls, lx, ly, lw, lh in valid_gt:
                iou = iou_xywh(r_box, (lx, ly, lw, lh))
                if iou >= scfg["iou_missing"]:
                    cands.append((l_cls, iou))

            # Nhánh 1: Không có bất kỳ nhãn nào gần đó -> Model thấy vật mà người quên gán
            if len(cands) == 0:
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_MISSING", stem,
                    f"model phát hiện lớp {p_cls} (conf={conf:.2f}) nhưng thiếu nhãn",
                    extra={"conf": round(conf, 4)},
                ))
                continue

            same_cls = [iou for (l_cls, iou) in cands if l_cls == p_cls]
            diff_cls = [iou for (l_cls, iou) in cands if l_cls != p_cls]

            # Nhánh 2: Có nhãn cùng lớp -> Kiểm tra xem box vẽ có bị lỏng/lệch không
            if len(same_cls) > 0:
                best_same = max(same_cls)
                if best_same < scfg["iou_loose"]:
                    issues.append(Issue(
                        "second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                        f"box cùng lớp {p_cls} nhưng IoU thấp ({best_same:.2f})",
                        extra={"conf": round(conf, 4), "iou": round(best_same, 4)},
                    ))
            # Nhánh 3: Không có nhãn cùng lớp -> Kiểm tra xem có phải gán nhầm sang lớp khác không
            else:
                best_diff = max(diff_cls)
                if best_diff >= scfg["iou_match"]:
                    issues.append(Issue(
                        "second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                        f"nghi gán nhầm lớp (model đoán {p_cls}, IoU={best_diff:.2f})",
                        extra={"conf": round(conf, 4), "iou": round(best_diff, 4)},
                    ))

        # =====================================================================
        # CHIỀU 2: DUYỆT TỪNG DÒNG NHÃN HỢP LỆ ĐỂ BẮT POSSIBLE_FALSE_POS
        # =====================================================================
        fp_preds = [p for p in img_preds if p[1] >= scfg["fp_conf"]]

        for line_idx, line in raw_lines:
            try:
                l_cls, lx, ly, lw, lh = parse_yolo_line(line)
            except ValueError:
                continue
            if l_cls < 0 or l_cls >= num_classes:
                continue

            l_box = (lx, ly, lw, lh)
            best_iou = max((iou_xywh(l_box, (p[2], p[3], p[4], p[5])) for p in fp_preds), default=0.0)

            if best_iou < scfg["iou_missing"]:
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                    f"nhãn lớp {l_cls} không khớp dự đoán nào của model",
                    line=line_idx,
                    extra={"iou": round(best_iou, 4)},
                ))

    return issues
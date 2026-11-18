"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    # Ý nghĩ: "Lấy bảng quy định ngưỡng của riêng bài kiểm tra này và chuẩn bị một tờ giấy trắng để ghi lỗi"
    lcfg = cfg["label_format"]
    issues = []
    num_classes = len(ds.classes)

    # Ý nghĩ: "Đi kiểm tra lần lượt từng bức ảnh trong kho dữ liệu"
    for img_path in ds.image_files():
        stem = img_path.stem  # Lấy tên ảnh (bỏ đuôi .jpg) để làm mã định danh

        # Ý nghĩ: "Mở file nhãn của ảnh này ra đọc. Nếu ảnh chưa có file nhãn thì thôi, chuyển sang ảnh khác"
        lines = ds.read_label_lines(stem)
        if lines is None:
            continue

        # Ý nghĩ: "Lấy kích thước thật (rộng x cao) của ảnh để lát nữa đổi kích thước box ra đơn vị pixel"
        size = ds.image_size(stem)

        # Ý nghĩ: "Tạo một sổ tay tạm cho riêng bức ảnh này, ghi lại các box hợp lệ đã duyệt qua để bắt lỗi trùng lặp"
        seen_boxes = []

        # Ý nghĩ: "Đọc từng dòng nhãn trong file (đã kèm sẵn số thứ tự dòng line_idx)"
        for line_idx, line in lines:

            # =================================================================
            # BƯỚC 1: KIỂM TRA "SỐNG SÓT" (Dòng có đọc được thành số hợp lệ không?)
            # Tư duy: Nếu dòng hỏng ngay từ đầu thì ghi lỗi rồi BỎ QUA (continue) các bước đo đạc phía sau.
            # =================================================================

            # Ý nghĩ: "Thử tách dòng chữ thành 5 con số. Nếu chữ bị lỗi/thiếu cột làm hàm báo ValueError thì ghi lỗi BAD_FORMAT"
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(line)
            except ValueError as e:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, str(e), line=line_idx))
                continue

            # Ý nghĩ: "Nếu mã lớp (cls_id) bị âm hoặc vượt quá số lớp cho phép thì ghi lỗi BAD_CLASS_ID"
            if cls_id < 0 or cls_id >= num_classes:
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"id lớp {cls_id} ngoài phạm vi", line=line_idx))
                continue

            # Ý nghĩ: "Nếu chiều rộng hoặc chiều cao bằng 0 (hoặc âm) thì cái hộp không tồn tại -> ghi lỗi BOX_ZERO"
            if w <= 0 or h <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem, f"kích thước box <= 0 ({w}, {h})", line=line_idx))
                continue

            # =================================================================
            # BƯỚC 2: ĐO ĐẠC HÌNH HỌC (Kiểm tra xem hộp có bị tràn viền, quá bé, hay quá to không?)
            # Tư duy: Một cái hộp có thể VỪA tràn viền VỪA quá to, nên ở đây KHÔNG dùng continue để bắt đủ mọi lỗi.
            # =================================================================

            # Ý nghĩ: "Tính tọa độ 4 mép của hộp (tâm trừ/cộng một nửa chiều dài), xem mép nào thò ra ngoài khung [0, 1] nhiều nhất"
            left, right = cx - w / 2, cx + w / 2
            top, bottom = cy - h / 2, cy + h / 2
            overflow = max(0.0, -left, right - 1.0, -top, bottom - 1.0)

            # Ý nghĩ: "Nếu độ thò ra ngoài vượt quá mức châm chước (overflow_tol) thì báo lỗi tràn ảnh"
            if overflow > lcfg["overflow_tol"]:
                issues.append(Issue(
                    "label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                    f"box tràn ảnh {overflow:.4f}", line=line_idx,
                    extra={"overflow": round(overflow, 6)},
                ))

            # Ý nghĩ: "Nếu ảnh mở được (biết kích thước thật), nhân tỷ lệ w, h với kích thước ảnh để xem cạnh ngắn nhất có bị bé quá không"
            if size is not None:
                img_w, img_h = size
                short_side_px = min(w * img_w, h * img_h)
                if short_side_px < lcfg["min_box_px"]:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem, f"cạnh ngắn {short_side_px:.1f}px", line=line_idx))

            # Ý nghĩ: "Nếu diện tích hộp (w * h) chiếm tỷ lệ lớn hơn ngưỡng cho phép thì cảnh báo hộp quá khổng lồ"
            if (w * h) > lcfg["max_box_frac"]:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem, f"diện tích chiếm {w * h:.2f}", line=line_idx))

            # =================================================================
            # BƯỚC 3: ĐỐI CHIẾU VỚI QUÁ KHỨ (Hộp này có vẽ đè lên hộp nào ở các dòng trên không?)
            # =================================================================

            curr_box = (cx, cy, w, h)

            # Ý nghĩ: "Lật lại sổ tay các hộp đã duyệt ở các dòng trên của ảnh này..."
            for prev_cls, prev_box in seen_boxes:
                # Ý nghĩ: "...nếu cùng loại đối tượng VÀ độ chồng lấn (IoU) vượt ngưỡng thì báo trùng lặp rồi dừng tìm kiếm"
                if prev_cls == cls_id and iou_xywh(curr_box, prev_box) > lcfg["dup_box_iou"]:
                    issues.append(Issue("label_format", ERROR, "DUP_BOX", stem, "box trùng với dòng trước đó", line=line_idx))
                    break

            # Ý nghĩ: "Ghi hộp hiện tại vào sổ tay để các dòng phía dưới còn lấy ra đối chiếu"
            seen_boxes.append((cls_id, curr_box))

    # Ý nghĩ: "Duyệt xong hết tất cả ảnh thì nộp lại danh sách lỗi đã ghi chép"
    return issues
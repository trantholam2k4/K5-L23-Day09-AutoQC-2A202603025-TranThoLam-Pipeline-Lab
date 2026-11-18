"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    # Ý nghĩ: "Chuyển image_stems và reviewed sang dạng tập hợp (set) để tra cứu nhanh và đếm chính xác tổng số ảnh"
    valid_stems = set(image_stems)
    reviewed_set = set(reviewed)
    n_images = len(valid_stems)

    # Ý nghĩ: "Chuẩn bị biến đếm số lỗi bắt buộc (n_errors) và một tập hợp (set) lưu tên các ảnh bị cảnh báo"
    n_errors = 0
    warn_images = set()

    # Ý nghĩ: "Duyệt qua từng issue trong danh sách lỗi..."
    for iss in issues:
        # Ý nghĩ: "...nếu issue này không thuộc danh sách ảnh hợp lệ (vd: 'data.yaml') thì bỏ qua"
        if iss.image not in valid_stems:
            continue

        # Ý nghĩ: "...nếu là lỗi bắt buộc (ERROR) thì cộng 1 vào n_errors (không quan tâm đã review hay chưa)"
        if iss.severity == ERROR:
            n_errors += 1

        # Ý nghĩ: "...nếu là cảnh báo (WARN) VÀ ảnh này chưa được người duyệt (không nằm trong reviewed_set) thì ghi tên ảnh vào warn_images"
        elif iss.severity == WARN and iss.image not in reviewed_set:
            warn_images.add(iss.image)

    # Ý nghĩ: "Tính số ảnh bị cảnh báo và tỷ lệ cảnh báo (nhớ phòng trường hợp n_images == 0, làm tròn 4 chữ số)"
    n_warn_images = len(warn_images)
    warn_ratio = round(n_warn_images / n_images, 4) if n_images > 0 else 0.0
    hold_thresh = cfg["gate"]["warn_ratio_hold"]

    # Ý nghĩ: "Áp dụng cây quyết định 3 nhánh (Rework -> Hold -> Release) và ghi lý do bằng tiếng Việt kèm số liệu"
    reasons = []
    if n_errors >= 1:
        decision = "Rework"
        reasons.append(f"Còn {n_errors} lỗi bắt buộc (ERROR) chưa được xử lý.")
    elif warn_ratio >= hold_thresh:
        decision = "Hold"
        reasons.append(f"Tỉ lệ ảnh cảnh báo {warn_ratio:.4f} ({n_warn_images}/{n_images} ảnh) >= ngưỡng {hold_thresh}.")
    else:
        decision = "Release"
        reasons.append(f"Không còn lỗi bắt buộc; tỉ lệ ảnh cảnh báo {warn_ratio:.4f} ({n_warn_images}/{n_images} ảnh) đạt chuẩn.")

    # Ý nghĩ: "Đóng gói đủ 6 thông tin vào từ điển (dict) và trả về"
    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }
# Báo cáo Day 09 — Trần Thọ Lâm, 2A202603025

> Xoá mọi `` và dòng gợi ý. Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
 pipeline kết luận **Release / Hold / Rework**? Bao nhiêu ảnh vào, bao nhiêu ảnh ra dataset? Lý do chính (1–3 câu).
Kết luận: Hold
Số liệu vào/ra: Đầu vào 224 ảnh $\rightarrow$ Intake loại 22 ảnh $\rightarrow$ nhận 202 ảnh $\rightarrow$ xuất bản nháp submission/export/clean_v1 (202 ảnh).
Lý do: Đã xử lý hết lỗi bắt buộc (0 error), nhưng sau khi duyệt xong 80 ảnh vẫn còn 29 / 202 ảnh (14.36%) có cảnh báo $\ge$ ngưỡng 10% (0.10) nên chưa được Release.

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `POSSIBLE_MISSING` | 44 dòng | Người | Model phụ thấy vật thể nhưng thiếu box, cần người xác nhận |
| `POSSIBLE_FALSE_POS` | 29 dòng | Người | Box nhãn không khớp dự đoán nào của model phụ, cần kiểm tra nhãn thừa |
| `POSSIBLE_LOOSE_BOX` | 22 dòng | Người | Box đúng lớp nhưng vẽ lỏng (`IoU < 0.5`), cần người chỉnh khít lại |
| `POSSIBLE_WRONG_CLASS` | 16 dòng | Người | Vị trí khớp cao (`IoU >= 0.5`) nhưng khác lớp model đoán, cần người phân định |
| `EMPTY_LABEL` | 12 ảnh | Người | File nhãn rỗng, máy không tự biết là ảnh nền thật hay người quên gán |
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy (Intake) | Trùng từng byte (MD5), loại ngay ở cửa vào |
| `BOX_OUT_OF_IMAGE` | 8 dòng | Máy (Autofix) | Mép box tràn khỏi `[0, 1]`, máy cắt về biên (`clip_box`) |
| `DUP_BOX` | 7 dòng | Máy (Autofix) | Box trùng lặp cùng lớp (`IoU > 0.9`), máy xóa dòng lặp (`drop_line`) |
| `BAD_CLASS_ID` | 6 dòng | Máy (Autofix) | ID lớp ngoài `0..3` (`-1, 4, 7, 93`), máy xóa dòng (`drop_line`) |
| `MISSING_LABEL_FILE` | 6 ảnh | Người | Thiếu file `.txt`, máy không tự bịa nhãn được nên đẩy lên đầu hàng đợi |
| `BOX_TINY` | 6 dòng | Người | Cạnh ngắn `< 12px`, cần người xem có nằm ngoài quy định gán nhãn không |
| `LEAK_TEST` | 5 ảnh | Máy (Intake) | Trùng ảnh trong kho `test/val`, loại để chống rò rỉ dữ liệu |
| `DUP_IMAGE_NEAR` | 4 ảnh | Máy (Intake) | Trùng gần đúng (`phash <= 14`), loại để tránh lặp mẫu train |
| `BOX_ZERO` | 4 dòng | Máy (Autofix) | Chiều rộng hoặc cao `<= 0`, máy xóa dòng (`drop_line`) |
| `CLASS_RARE` | 4 dòng | Máy (Autofix) | Lớp hiếm (`-1, 4, 7, 93`) sinh ra do lỗi ID, tự hết sau khi xóa `BAD_CLASS_ID` |
| `BAD_SIZE` | 3 ảnh | Máy (Intake) | Cạnh ngắn `< 250px`, không đạt kích thước tối thiểu |
| `BAD_FORMAT` | 3 dòng | Máy (Autofix) | Sai số cột (4 cột) hoặc dính `nan/inf`, máy xóa dòng (`drop_line`) |
| `BOX_HUGE` | 3 dòng | Người | Box chiếm `0.97–0.99` diện tích ảnh, cần người xem có vẽ nhầm cả khung không |
| `CORRUPT_IMAGE` | 2 ảnh | Máy (Intake) | File ảnh hỏng (`UnidentifiedImageError`, `OSError`), không mở được |
| `BAD_CLASS_NAME` | 2 dòng | Máy (Autofix) | Tên lớp trong `data.yaml` sai chuẩn (`'Person'`, `'Bus'`), ghi lại đúng `cfg ["classes"]` |
 vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy? Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?
1.Vì sao xếp đầu hàng: Hàng đợi cộng điểm ưu tiên theo trọng số trong configs/pipeline.yaml (cao nhất là NEEDS_LABEL: 10 để giải tỏa lỗi bắt buộc chặn cổng, rồi tới POSSIBLE_WRONG_CLASS: 3, POSSIBLE_MISSING/FALSE_POS: 2...) kết hợp độ tự tin conf của model để ưu tiên duyệt ca nặng nhất trước.
2.Ngân sách 80 ảnh xem được bao nhiêu lỗi ngữ nghĩa: Ban đầu (v1) có 111 cảnh báo second_opinion, sau khi duyệt 80 ảnh (v3) chỉ còn 40 cảnh báo $\rightarrow$ người duyệt đã xử lý được 71 / 111 lỗi ngữ nghĩa (cộng thêm toàn bộ 6/6 ảnh MISSING_LABEL_FILE).

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **14** | `DUP_IMAGE_NEAR`: `1.00 / 0.50` → `1.00 / 0.67` (`DUP_IMAGE_EXACT` giữ `1.00 / 1.00`) | Tăng từ 2 lên 14 giúp bắt thêm ảnh gần trùng mà vẫn giữ `Precision = 1.00`, tránh rủi ro xóa nhầm ảnh tốt trên tập dữ liệu thật |
| `second_opinion.conf` | 0.25 | **0.7** | `WRONG_CLASS: 0.56/0.83 → 0.62/0.83`<br>`MISSING`: `0.50/1.00 → 0.58/0.88`<br>`LOOSE_BOX`: `0.29/0.40 → 0.50/0.20`<br>`FALSE_POS`: `0.31/1.00 → 0.31/1.00` | Tăng `conf` lên 0.6 giúp giảm báo động giả để đỡ làm tràn hàng đợi 80 ảnh, đồng thời vẫn giữ nguyên `Recall = 1.00` cho lỗi sót nhãn (`POSSIBLE_MISSING`) |

 **một chỗ calibration có thể đánh lừa bạn**, kèm bằng chứng từ dữ liệu của bạn (vd. mở xem vài cặp ảnh bị cho là trùng; số ảnh bị loại ở bước 1 có hợp lý không?).

Trên tập calib (chỉ 39 ảnh), phash_dist = 16 đạt F1 = 0.91 cao nhất, nhưng calib quá ít ảnh nên không đại diện hết các cặp ảnh đường phố khác nhau mà cùng góc chụp trên 224 ảnh raw (dễ xóa nhầm).

Bằng chứng thực tế khi chọn 14: xem 01_intake.txt, 4 ảnh bị loại do DUP_IMAGE_NEAR là img_0076 (trùng img_0042, phash 0), img_0143 (trùng img_0037, phash 0), img_0223 (trùng img_0077, phash 6) và img_0186 (trùng img_0061, phash 10) — đều là ảnh trùng thật, không xóa nhầm.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
 (a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.) (b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).

(a) Chứng minh gate chặn đúng: Khi chạy python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb, vì không có người duyệt nên 6 lỗi MISSING_LABEL_FILE vẫn còn nguyên $\rightarrow$ gate kết luận REWORK, trả về mã thoát 20 và không xuất thư mục work/exp_nb.
(b) 2 điểm mù (lấy ví dụ từ log của bạn):
    1.Ảnh gần trùng bị biến đổi mạnh có khoảng cách hash > 12 sẽ lọt qua bước Intake (trên calib ngưỡng 14 vẫn bỏ sót 2/6 ca DUP_IMAGE_NEAR).
    2.Box vẽ hơi lỏng nhưng vẫn có IoU >= 0.50 với model phụ sẽ không bị bắt lỗi POSSIBLE_LOOSE_BOX; hoặc 4 ảnh EMPTY_LABEL còn lại (img_0013, img_0097, img_0129, img_0192) pipeline không thể tự phân biệt là ảnh nền thật hay ảnh bị bỏ sót nhãn hoàn toàn

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).

 chênh mAP50 (clean − raw) so với **độ lệch chuẩn giữa các seed**; kết luận **trung thực** (nằm trong nhiễu thì nói là chưa kết luận được); ≥ 2 giả thuyết giải thích (ảnh trùng/rò rỉ test trong `raw`, nhãn máy còn lại trong `clean`, test chỉ 100 ảnh…) và cách kiểm.

Chưa chạy (tập trung hoàn thiện phần lõi pipeline và kiểm tra qua --no-train, chưa chạy huấn luyện đối chứng trên GPU)

## 6. Quyết định và ghi chú AI
(a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release? (b) Dùng AI viết code? Ghi 3 dòng: prompt chính, cách bạn kiểm code AI, 1 lần AI sai. Không dùng: ghi "không dùng".

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
(a) Quyết định & cách chuyển thành Release: Giữ Hold cho bản clean_v1. Để thành Release, cần duyệt thêm tối thiểu 9–10 ảnh nữa trong số 29 ảnh còn cảnh báo (ưu tiên các ca POSSIBLE_WRONG_CLASS như img_0078, img_0220 và POSSIBLE_MISSING như img_0183, img_0160) để kéo số ảnh cảnh báo xuống <= 20 / 202 ảnh (< 10%).
(b) 3 dòng ghi chú AI:
    1.Prompt chính: Hỏi giải thích đặc tả từng module trong docstring, xin mã giả từng bước và hướng dẫn cách trích xuất số liệu từ các file report.
    2.Cách kiểm code AI: Tự chuyển mã giả sang code Python, đối chiếu với common.py và chạy python -m pytest -q (đạt 79/79 passed) cùng python -m pipeline.run.
    3.1 lần gặp lỗi: Khi chuyển mã giả sang Python bị thụt lề nhầm khối lệnh trong autofix.py và second_opinion.py, đã tự rà soát lại thụt lề và chạy lại unit test để xác nhận.
# Kinh tế Vĩ mô

Trang cá nhân tổng hợp lý thuyết kinh tế và dữ liệu vĩ mô hiện tại cho **Châu Úc, Châu Âu, Châu Á**.

- `docs/`: trang web (GitHub Pages phục vụ từ thư mục này)
  - `content/*.md`: bài lý thuyết; thêm bài mới bằng cách tạo file `.md` rồi khai báo trong `content/index.json`
  - `data/macro.json`: dữ liệu do bot tạo, không sửa tay
- `fetch_macro.py`: lấy dữ liệu từ BIS, OECD, FRED, Eurostat, World Bank (không cần API key)
- `.github/workflows/update.yml`: chạy mỗi ngày lúc 6:00 sáng giờ Việt Nam

Thêm một nước: thêm một dòng vào `COUNTRIES` trong `fetch_macro.py`.

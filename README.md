# TSP Image to PDF Telegram Bot

Bot Telegram untuk menggabungkan foto atau dokumen gambar menjadi satu PDF. Setiap pengguna memiliki antrean gambar dan pengaturannya sendiri.

## Fitur

- Menerima foto Telegram serta dokumen **JPG, PNG, dan WEBP**.
- Menggabungkan hingga **30 gambar** menjadi satu PDF.
- Mengatur nama hasil PDF dengan `/nama`.
- Preset ukuran **A3, A4, A5, Letter, Legal**, atau ukuran detail sendiri dalam mm/cm/in, misalnya `/ukuran 300x300 mm`.
- Orientasi otomatis, potret, atau lanskap untuk setiap halaman.
- Margin 0–100 mm, mode gambar `pas` (tanpa terpotong), `penuhi` (crop), atau `regangkan`, serta warna latar halaman.
- Tombol pengaturan cepat melalui `/pengaturan` dan perintah teks lengkap melalui `/bantuan`.

## Menjalankan bot

1. Buat bot di [@BotFather](https://t.me/BotFather) dan salin tokennya.
2. Buat virtual environment lalu pasang dependensi:

   ```bash
   python -m venv .venv
   source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Simpan token secara aman sebagai environment variable (jangan commit token):

   ```bash
   export TELEGRAM_BOT_TOKEN='TOKEN_DARI_BOTFATHER'
   python telegram_image_to_pdf_bot.py
   ```

   Di PowerShell Windows:

   ```powershell
   $env:TELEGRAM_BOT_TOKEN = 'TOKEN_DARI_BOTFATHER'
   python .\telegram_image_to_pdf_bot.py
   ```

4. Buka chat bot, kirim gambar, sesuaikan opsi bila perlu, kemudian kirim `/buatpdf`.

## Perintah

| Perintah | Contoh | Kegunaan |
| --- | --- | --- |
| `/pengaturan` | `/pengaturan` | Menampilkan pengaturan aktif dan tombol cepat. |
| `/nama` | `/nama laporan-september.pdf` | Menentukan nama berkas hasil. Ekstensi `.pdf` ditambahkan otomatis. |
| `/ukuran` | `/ukuran A4` atau `/ukuran 300x300 mm` | Memilih preset atau ukuran halaman kustom. Unit `mm`, `cm`, dan `in` didukung. |
| `/margin` | `/margin 8` | Memberikan batas kosong dalam mm. |
| `/orientasi` | `/orientasi lanskap` | `otomatis`, `potret`, atau `lanskap`. |
| `/fit` | `/fit pas` | `pas`, `penuhi`, atau `regangkan`. |
| `/latar` | `/latar #FFF8E1` | Menetapkan warna latar halaman dalam hex. |
| `/hapus` | `/hapus` | Menghapus antrean gambar tanpa mengubah pengaturan. |
| `/buatpdf` | `/buatpdf` | Membuat satu PDF dan mengosongkan antrean gambar setelah berhasil. |

## Batas dan privasi

Bot memproses gambar di memori dan tidak menyimpannya ke disk. Berkas dibatasi hingga 20 MB dan 30 gambar per PDF agar penggunaan memori tetap aman. Untuk penggunaan publik, jalankan bot di server tepercaya dan gunakan token bot hanya dari environment variable.

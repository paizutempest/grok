# ⚡ Grok AI Auto-Signup & 9Router

Skrip ini berfungsi untuk melakukan registrasi massal akun Grok (x.ai) secara otomatis menggunakan perpaduan **Playwright Browser Automation**, **Paizu Temp Mail API**, eksekusi modul bypass **TurnstilePatch lokal** (tanpa capsolver), serta sinkronisasi sesi otomatis ke dalam **9Router Proxy Gateway**.

---

## 📦 Komponen yang Dibutuhkan & Harus Didownload

Sebelum menjalankan skrip, pastikan Anda telah menyiapkan folder proyek dengan struktur dan file berikut:

1. **Aplikasi 9Router (Proxy Core):** Siapkan binary core 9Router resmi sesuai OS Anda (Windows/Linux) dan pastikan service sudah berjalan sesuai port target Anda.
2. **Folder `turnstilePatch`:** Harus berisi file ekstensi bypass lokal (`manifest.json` dan `script.js`). Letakkan folder ini dalam satu direktori bersama skrip utama.
3. **Google Chrome Komersial:** Pastikan aplikasi resmi Google Chrome sudah terinstal di sistem Anda (bukan sekadar peramban Chromium bawaan python).
4. **Berkas Skrip Utama:** 
   - `grok-regist.py` (Skrip Python utama Anda)
   - `.env` (Berkas konfigurasi lingkungan)

---

## 🔄 Alur Kerja Sistem (System Workflow)

1. **Inisialisasi Ekstensi:** Skrip memuat folder `turnstilePatch` sebagai ekstensi resmi ke dalam browser Google Chrome.
2. **Email Provisioning:** Skrip memanggil API backend `PAIZUMAILER` secara *native* via `requests` untuk membuat email sementara dengan domain `paizu.my.id`.
3. **OTP Interception:** Email diisikan ke form x.ai. Skrip memasuki fase *looping listening buffer* pada inbox email. Begitu OTP tiba, skrip mengekstrak kode lewat *Regex* dan langsung menginjeksikannya ke form verifikasi.
4. **Turnstile Patch Remediation:** Saat form data diri terbuka, ekstensi `turnstilePatch` bekerja di latar belakang secara lokal untuk menyelesaikan tantangan Cloudflare. Skrip menunggu hingga *hidden input* `cf-turnstile-response` terisi token bypass yang valid.
5. **Session Mapping & Output:** Setelah pendaftaran selesai dan dialihkan ke `grok.com`, seluruh data kredensial serta `sso_cookies` disimpan ke `sso.txt`.
6. **9Router Injection:** Akun baru tersebut langsung disuntikkan ke dashboard 9Router via metode *Device Code Polling* agar langsung masuk ke pool kluster active.

---

## 💻 Kebutuhan Sistem & Langkah Instalasi

### 🧩 1. Setup di Windows (Lingkungan Lokal)
Skrip dijalankan menggunakan Google Chrome komersial bawaan laptop Anda.

**Langkah Instalasi di Windows:**
1. Pastikan **Python 3.10 ke atas** sudah terinstal dan opsi *Add Python to PATH* telah dicentang saat instalasi.
2. Buka PowerShell atau Command Prompt (CMD), masuk ke folder proyek Anda, lalu instal seluruh *library* pendukung:
```powershell
   pip install playwright requests colorama ```

### 🐧 2. Setup di Linux (VPS / Server Ubuntu)

Karena skrip ini mengontrol antarmuka browser grafis (GUI) secara langsung (`headless=False`), skrip **tidak bisa dijalankan langsung di terminal SSH kosongan**. Anda wajib menginstal **Xvfb** (X Virtual Framebuffer) untuk memanipulasi *virtual display* di latar belakang server.

**Langkah Instalasi di Linux:**
1. Perbarui indeks paket server dan instal dependensi grafis virtual Xvfb serta library system browser:
   ```bash
   sudo apt update
   sudo apt install -y xvfb libgbm1 libasound2
   ```powershell
   pip install playwright requests colorama

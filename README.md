# GFS Fleet Bot (gfs-fleet-bot)

TZ asosida Python Telegram bot: COI VIN tekshiruvi, Monday.com, guruhlar bazasi, administratorlar va Telegram Mini App orqali tarqatmalar.

## Ishga tushirish (Python 3.12+)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
# .env faylini o'zingizning qiymatlaringiz bilan to'ldiring
.venv\Scripts\python main.py
```

`.env` sozlamalari:

- `BOT_TOKEN`: @BotFather bergan token.
- `ADMIN_IDS`: boshlang'ich administratorlarning raqamli Telegram User IDlari, vergul bilan.
- `MONDAY_TOKEN`: faqat o'qish huquqi bor Monday API tokeni.
- `MONDAY_BOARD_ID`: TRUCK FILES doskasi IDsi; bo'sh bo'lsa nomi orqali qidiriladi. Bir xil nomli doskalar bo'lsa ID shart.
- `WEBAPP_URL`: shu serverga olib keladigan ochiq HTTPS URL. Masalan reverse proxy orqali `http://127.0.0.1:8000` ga yo'naltiring. `/start` shu manzilni ochadi. BotFather'da kerak bo'lsa domen / Mini App sozlang.
- `TIMEZONE`: standart `Asia/Tashkent`; haftalik tarqatma zonasini interfeysda tanlash mumkin. Bir martalik vaqt brauzerning mahalliy vaqtida kiritiladi.
- `DB_PATH`: SQLite bazasi. `data/` papkasini doimiy diskda saqlang va zaxiralang.

Botni ishchi guruhlarga qo'shing; xabar yuborish ruxsatini bering. Bot guruhga qo'shilish/chiqarilish, nom/avatarning xizmat xabarlarini kuzatadi va yuborish oldidan `getChat` bilan qayta tekshiradi. Oldindan bot bor bo'lgan guruhlar Telegram tomonidan umumiy ro'yxat qilib berilmaydi: botni qayta qo'shing yoki guruhda xabar yuboring (privacy mode yoqilgan bo'lsa botga qaratilgan buyruq yuboring). Kanal qo'llanilmaydi.

## Buyruqlar

- `/start`, `/help`: yordam va Mini App tugmasi, faqat whitelist uchun.
- PDF yuborish yoki PDFga reply `/check_coi`: VIN tekshiruvi va status auditi.
- `/sync`, `/groups`: Monday yangilash va Unit bog'lanishlari. Konfliktlarni Mini App orqali yeching; bo'sh Unit qo'lda bog'lashni bekor qiladi.
- `/add_admin 123456789` yoki `/add_admin @username`: administrator qo'shish. Username faqat bot ilgari ko'rgan foydalanuvchilar uchun; avval foydalanuvchi botga `/start` yuborsin. Ishonchli usul — raqamli ID. Administratorni o'chirish interfeysi yo'q; bazadan qo'lda o'chiriladi. O'sha IDni `ADMIN_IDS` dan ham olib tashlang, aks holda qayta ishga tushganda tiklanadi.
- Media/stiker yuboring: bot `file_id` qaytaradi. PDF yuborilganda qo'shimcha COI tekshiruvi boshlanadi; oddiy PDF tarqatma uchun Mini App upload ishlating.
- Botdagi istalgan xabarga reply `/source`: copy rejimi uchun manba IDlari. Nusxalanadigan xabar shaxsiy chatingizda bo'lishi kerak. Telegram nusxalashni cheklagan xabarlarni jo'nata olmaydi.

## Muhim qoidalar

Monday'da faqat `TRUCKS IN USAGE`, `owner operators`, `upcoming` guruhlari o'qiladi; boshqa guruhlar hatto Unit qidirish uchun ham olinmaydi. `Unit`, `VIN`, `Status` ustunlari nomi aniq mos bo'lishi kerak. Yetishmagan guruh/ustun xato sifatida qaytariladi; noto'liq natija muvaffaqiyat sifatida ko'rsatilmaydi. Har bir guruhdagi barcha sahifalar cursor orqali olinadi.

Guruh nomidagi barcha raqamlar Unitlar bilan solishtiriladi. Bitta moslik avtomatik bog'lanadi; nol yoki bir nechta moslik konflikt hisoblanadi. Qo'lda tanlangan Unit keyingi sync paytida saqlanadi. Monday statusi tarqatma filtriga ta'sir qilmaydi. Faqat `INACTIVE` so'zi bor **va** avatarsiz guruh o'tkazib yuboriladi; qolgan uch kombinatsiya yuboriladi. Konfliktli guruhlar ham bu qoidadan o'tsa tarqatma oladi. Aktivlik shu matritsa orqali belgilanadi, xabarlar soni orqali emas.

Status auditida SHOP, INACTIVE, AVAILIBLE (va AVAILABLE varianti) ogohlantirish chiqaradi. Faol Telegram chatlar COIda VIN bor-yo'qligidan mustaqil audit qilinadi. VINdan Unitni Monday maqsadli guruhlaridan aniqlab bo'lmasa, hisobotda VINning o'zi ko'rsatiladi.

Mini App: HTML/MarkdownV2, media upload, file_id, premium/oddiy stiker, URL/callback tugmalar, istalgan nusxalanadigan Telegram xabari, sinov xabari, bir martalik/haftalik reja, tahrirlash, bekor qilish va har bir chat bo'yicha yuborish jurnali. Callback tugmalari bosilganda tasdiq ko'rsatiladi; maxsus biznes amallari uchun alohida handler kerak. Telegram premium yoki himoyalangan kontentga cheklov qo'ysa, xato jurnalda ko'rinadi.

Mini App so'rovlari Telegram `initData` HMAC va bir soatlik muddat orqali tekshiriladi; whitelist har so'rovda tekshiriladi. Bir soatdan keyin Mini Appni qayta oching. Fayllar 20 MB bilan cheklangan. Faqat yuklangan yoki admin botga yuborgan file_id qabul qilinadi.

## OCR va ishlatish

Matnli PDF uchun OCR kerak emas. Skan yoki aralash PDFlar uchun `requirements.txt` bog'liqliklarini o'rnating va `OCR_ENABLED=true` qiling. OCR o'chirilgan bo'lsa matnsiz sahifali PDF bo'yicha qisman hisobot chiqarilmaydi. COI namunasi berilmagani uchun regex standart 17 belgili VINlarga moslangan; real namunada tekshirish kerak.

Faqat **bitta server jarayoni / bitta worker** ishga tushiring: polling va scheduler bir ilovada. Rejalar va yuborish natijalari SQLite'da saqlanadi; restartdan keyin kechikkan vazifa bir marta bajariladi, haftalik vazifa keyingi kelajak vaqtiga ko'chadi. Bot API `retry_after` javobi bo'yicha kutadi. Bir chatdagi xato boshqalariga yuborishni to'xtatmaydi. Bekor qilish allaqachon yuborilgan xabarlarni qaytarmaydi va yuborilayotgan bitta API so'rovini to'xtatmaydi.

Telegramda idempotency kaliti yo'q: yuborish vaqtida server to'xtasa, `sending` yozuvi natijasi noaniq hisoblanadi va takror yuborilmaydi. `failed` va `sending` yozuvlarini Mini App jurnalida tekshiring; zaruratda alohida qayta tarqatma yarating. Ko'p nusxa yoki yuqori yuklama uchun PostgreSQL/queue arxitekturasiga o'tish kerak.

## Tekshirish

```powershell
python -m pip install pytest
python -m pytest -q
```

Ishlayotgan bot bazasidan tekshirilgan zaxira yaratish: `python backup_db.py`. Nusxani boshqa diskda ham saqlang va rejalashtirilgan vazifa bilan muntazam bajaring.

Haqiqiy Telegram/Monday sinovi uchun tokenlar, doskaga kirish va HTTPS domen kerak. Tokenlarni gitga kiritmang. Reverse proxy ortida ishga tushiring, `data/` uchun backup tashkil qiling.

Windows OCR uchun PyMuPDF DLL yuklanmasa Microsoft Visual C++ 2015–2022 x64 runtime kerak. Bu muhitda OCR ishga tushirilmagan; matnli PDF parseri PyMuPDFsiz ishlaydi.

Haqiqiy GFS doskasiga moslash: `.env` ichida `MONDAY_UNIT_SOURCE=item_name` Unitni item nomining birinchi harf/raqamli tokenidan oladi (masalan `133 - LOCAL` → `133`, `A1` → `A1`). `MONDAY_GROUP_TITLES=TRUCKS IN USAGE|Owner Operators|UPCOMING UNITS:` faqat shu uch guruhni tanlaydi. Emoji bilan boshlangan TRUCK FILES nomi ham qabul qilinadi. Boshqa doskalarda standart Unit ustuni va TZdagi guruh nomlari ishlatiladi.

Server: `docker compose up -d --build` bitta bot va kunlik SQLite backup jarayonini ishga tushiradi. HTTPS reverse proxy va doimiy hosting alohida talab qilinadi. Eski bot jarayonini avval to'xtating.


## Shu Windows kompyuterida fonda ishlash

`powershell -NoProfile -ExecutionPolicy Bypass -File .\enable_background.ps1` joriy Windows foydalanuvchisi uchun avtomatik ishga tushishni yoqadi va yashirin `run_background.py` supervisorini boshlaydi. Ikkinchi nusxa lock orqali bloklanadi. Supervisor bot va Cloudflare HTTPS tunnelini kuzatadi, uzilgan jarayonni qayta boshlaydi, yangi tunnel manzilini `.env`ga yozadi va bot menyusini yangilaydi. Har 24 soatda yaxlitligi tekshirilgan SQLite backup yaratiladi; xatoda 5 daqiqadan keyin takrorlanadi.

Kompyuter yoqilgan, uyqu rejimida bo‘lmagan, internetga ulangan va Windows foydalanuvchisi tizimga kirgan bo‘lishi kerak. Quick tunnel qayta yaratilganda URL o‘zgaradi; botdagi yangi `/start` tugmasidan foydalaning. Bu usul doimiy domen bermaydi.

Jurnallar: `data/supervisor.log`, `data/managed-bot.log`, `data/managed-tunnel.log`, `data/backup.log`. Bir vaqtda qo‘lda `main.py` yoki Docker nusxasini ochmang. Avtoishga tushishni o‘chirish: `Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name GfsSpeakerBot`. Bu amal ishlab turgan jarayonni to‘xtatmaydi.

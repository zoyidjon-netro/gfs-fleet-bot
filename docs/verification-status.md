# GFS Speaker tekshiruv holati — 2026-11-04

- Telegram getMe: muvaffaqiyatli.
- Monday maqsadli guruhlarini o‘qish: 128 yozuv.
- Avtomatik testlar: 21 passed.
- JavaScript sintaksisi: node --check muvaffaqiyatli.
- Brauzer: 320/390/768/1280 px, light/dark; asosiy navigatsiya va 5 bosqichli forma; JavaScript xatolari va gorizontal overflow topilmadi.
- 320 px ekrandagi action bar ustma-ust tushishi tuzatildi.
- OCR: sintetik skan PDFdan 1M8GDM9AXKP042788 to‘g‘ri ajratildi. Haqiqiy COI namunasi hali berilmagan.
- Auditlar uchun strukturali VIN soni, tafovutlar va status ogohlantirishlari qo‘shildi. Eski hisobotlar saqlanadi; yangi tafsilotlar keyingi auditlardan yoziladi.
- SQLite online backup yaratildi va integrity_check o‘tdi.
- Windows HKCU Run orqali pythonw supervisor avtomatik ishga tushishi yoqildi.
- Supervisor: bitta nusxa lock, bot/tunnel restart, dinamik HTTPS URL va Telegram menyusini yangilash, har 24 soatda backup.
- Bot jarayonini to‘xtatib tiklanish tekshirildi: local va HTTPS health 200.

Operatsion shartlar: foydalanuvchi Windows’ga kirgan, kompyuter yoqilgan va uyquda bo‘lmagan, internet ishlayotgan bo‘lishi kerak. Cloudflare Quick Tunnel manzili qayta ishga tushganda o‘zgaradi. Bot menyusi yangilanadi; oldingi /start xabaridagi tugma uchun yangi /start yuborish kerak.

Real guruhlarga sinov tarqatmasi yuborilmadi. Scheduler va yuborish xatti-harakatlari avtomatik testlarda tekshirildi. Til va bildirishnoma sozlamalari backend qo‘llamagani uchun qo‘shilmadi.

Tunnel jarayonini to‘xtatib tiklanish ham tekshirildi: yangi HTTPS manzil 200 qaytardi va Telegram menyusi yangi manzilga mos keldi.

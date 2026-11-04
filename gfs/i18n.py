"""Internationalization (i18n) support for Uzbek (uz), Russian (ru), and English (en)."""

SUPPORTED_LANGUAGES = {"uz", "ru", "en"}
DEFAULT_LANGUAGE = "uz"

TRANSLATIONS = {
    "uz": {
        # General / Buttons
        "btn_webapp": "📱 Mini App (Boshqaruv paneli)",
        "btn_broadcast": "📨 Xabar tarqatish",
        "btn_sync": "🔄 Sinxronlash",
        "btn_resync": "🔄 Qayta sinxronlash",
        "btn_audits": "📊 COI Auditlari",
        "btn_jobs": "⏰ Rejalar",
        "btn_admins": "👥 Adminlar",
        "btn_help": "ℹ️ Yordam",
        "btn_lang": "🌐 Til / Language / Язык",
        "btn_main": "🔙 Bosh menyu",
        "btn_refresh": "🔄 Yangilash",
        "btn_all_groups": "📋 Barcha guruhlar",
        "btn_conflicts_only": "⚠️ Faqat konfliktlar",
        "btn_new_broadcast": "➕ Yangi tarqatish (Mini App)",
        "btn_cancel_job": "❌ #{id} vazifani bekor qilish",
        "btn_del_admin": "🗑 #{id}",
        "btn_add_admin": "➕ Yangi admin qo'shish",
        "btn_confirm_yes": "🗑 Ha, o'chirish",
        "btn_confirm_no": "❌ Bekor qilish",
        "btn_groups_status": "📋 Guruhlar holati",
        "btn_jobs_list": "⏰ Rejalar ro'yxati",
        "btn_manage_miniapp": "📱 Mini Appda boshqarish",

        # Main menu
        "main_title": "🚛 *GFS Fleet & Safety Bot*\n\nBotni boshqarish uchun quyidagi menyu tugmalaridan foydalaning:\n\n• 📱 *Mini App* — Xabar tarqatmalari va qulay vizual panel\n• 🔄 *Sinxronlash* — Monday.com va Telegram guruhlarni yangilash\n• 📋 *Guruhlar* — Guruhlarning Unit bog'lanishlari va konfliktlar\n• 📊 *COI Auditlari* — So'nggi COI VIN tekshiruvlari tarixi\n• ⏰ *Rejalar* — Rejalashtirilgan tarqatmalar ro'yxati\n• 👥 *Adminlar* — Administratorlar ro'yxati va CRUD\n• 🌐 *Til* — O'zbekcha / Русский / English\n\n📄 *COI tekshiruvi:* PDF faylni to'g'ridan-to'g'ri botga yuboring.\n📷 *Media file_id:* Rasm, video yoki stikerni yuboring.",

        # Language selection
        "lang_select_title": "🌐 *Tilni tanlang / Выберите язык / Select language:*",
        "lang_changed": "✅ Til muvaffaqiyatli o'zgartirildi: *O'zbekcha*",

        # Groups view
        "groups_title": "📋 *Telegram guruhlar va Unitlar holati:*",
        "groups_stat": "📊 *Jami guruhlar:* {total} ta (Faol: {present} ta)\n🔗 *Bog'langan:* {matched} ta | ⚠️ *Konfliktlar:* {conflicts} ta",
        "groups_conflicts_head": "⚠️ *Faqat konfliktli guruhlar:*",
        "groups_no_conflicts": "🎉 Barcha faol guruhlar muvaffaqiyatli bog'langan!",
        "groups_active_head": "👥 *Faol guruhlar ro'yxati:*",
        "groups_no_active": "Bot hozircha hech qaysi faol guruhda yo'q.",
        "groups_more": "\n_... va yana {count} ta guruh bor._",

        # Sync
        "sync_starting": "🔄 Sinxronlanmoqda...",
        "sync_success": "✅ *Sinxronlash muvaffaqiyatli yakunlandi!*\n\n🚛 *Monday yuk mashinalari:* {trucks} ta\n👥 *Faol Telegram guruhlar:* {groups} ta\n🔗 *Bog'langan Unitlar:* {matched} ta\n⚠️ *Konfliktli guruhlar:* {conflicts} ta",
        "sync_failures": "❌ *Yangilanmagan chatlar:* {count} ta",
        "sync_error": "❌ *Sinxronlash xatosi:*\n`{error}`",

        # Audits view
        "audits_empty": "📊 *COI Auditlari tarixi bo'sh.*\n\nYangi audit yaratish uchun sug'urta polisi (COI) PDF faylini botga yuboring.",
        "audits_title": "📊 *So'nggi COI Auditlari natijalari:*",

        # Jobs view
        "jobs_empty": "⏰ *Rejalashtirilgan tarqatmalar mavjud emas.*\n\nYangi tarqatish yaratish uchun *Mini App*dan foydalaning.",
        "jobs_title": "⏰ *Tarqatmalar va Rejalar ro'yxati:*",
        "job_cancelled": "✅ #{id} vazifa bekor qilindi",
        "job_not_found_or_done": "Vazifa topilmadi yoki allaqachon yakunlangan",
        "job_started": "🚀 *#{id} tarqatish boshlandi!*\n\nNatijalarni `⏰ Rejalar` bo'limida kuzatishingiz mumkin.",

        # Admins view & CRUD
        "admins_title": "👥 *Administratorlar ro'yxati* (Jami: {total} ta):",
        "admins_guide": "\n📌 *Buyruqlar orqali boshqarish:*\n• Qo'shish: `/add_admin ID yoki @username [ism] [rol]`\n• O'chirish: `/del_admin ID yoki @username`\n• Tahrirlash: `/edit_admin ID Yangi Ism`",
        "admin_add_prompt_title": "✍️ *Yangi administrator qo'shish:*\n\nFoydalanuvchining *Telegram ID* raqamini yoki *@username*ini yuboring:\n• Masalan: `123456789` yoki `@foydalanuvchi`\n• Ism va rol bilan: `123456789 Jasur admin`\n\n_Rollar: `admin`, `dispatcher`, `superadmin`_",
        "admin_del_confirm": "⚠️ *Haqiqatan ham #{id} administratorni o'chirmoqchimisiz?*",
        "admin_deleted": "✅ #{id} admin o'chirildi",
        "admin_last_error": "Oxirgi administratorni o'chirib bo'lmaydi!",
        "admin_not_found": "Administrator `#{id}` topilmadi.",
        "admin_added": "✅ Administrator muvaffaqiyatli qo'shildi: `{id}`",
        "admin_updated": "✅ Administrator `#{id}` ma'lumotlari yangilandi: *{name}*",
        "admin_user_not_found": "❌ Foydalanuvchi `@{username}` topilmadi.\nFoydalanuvchi avval botga /start yuborgan bo'lishi yoki to'g'ri Telegram ID kiriting.",
        "admin_id_missing": "⚠️ ID yoki @username kiritilmadi.",

        # Broadcast info view
        "broadcast_info_title": "📨 *Guruhlarga Xabar Tarqatish va Rejalashtirish*",
        "broadcast_info_stats": "📊 *Faol guruhlar:* {total} ta (Mos: {eligible} ta)",
        "broadcast_info_desc": "Bot quyidagi imkoniyatlarni taqdim etadi:\n• 📢 *Barcha guruhlarga* yoki 👥 *Tanlangan guruhlarga* yuborish\n• ⚡️ *Hozir jo'natish* yoki ⏰ *Kelajakdagi vaqtga rejalashtirish*\n• 🌐 *Vaqt zonalari mosligi:*\n   🇺🇿 *Asia (Toshkent)* — UTC+5\n   🇺🇸 *USA Central (Chicago, Dallas)* — CT\n   🇺🇸 *USA Eastern (New York, Florida)* — ET\n   🇺🇸 *USA Pacific (Los Angeles, California)* — PT\n\n📌 *Qanday yuborish mumkin:*\n1. *Mini App orqali (Tavsiya etiladi):* Guruhlarni tanlash, media, stiker, inline tugmalar va vaqt zonalari kalkulyatori bilan.\n2. *Tezkor buyruq:* `/broadcast Matn` — barcha faol guruhlarga darhol matn tarqatish.",

        # Help view
        "help_title": "ℹ️ *GFS Fleet & Safety Bot — Qo'llanma*",
        "help_desc": "🤖 *Asosiy imkoniyatlar:*\n• *COI VIN tekshiruvi:* COI PDF faylini shunchaki botga yuboring yoki reply qilib `/check_coi` bering.\n• *Monday.com sinxronlash:* Guruh nomlarini Monday doskasidagi Unitlar bilan avtomatik bog'laydi.\n• *Xabar tarqatish (Mini App):* Guruhlarga matn, media, stiker va inline tugmali xabarlarni tarqating.\n• *Rejalashtirish:* Bir martalik yoki haftalik avtomatik tarqatmalarni sozlang.\n• *Vaqt zonalari:* Asia/Tashkent va AQSh (Central, Eastern, Pacific) vaqtlari.\n\n📌 *Buyruqlar:*\n• `/start` yoki `/help` — Bosh menyuni ochish\n• `/sync` — Monday va guruhlarni sinxronlash\n• `/groups` — Guruhlar va Unitlar holati\n• `/check_coi` — PDF faylga reply qilib audit qilish\n• `/add_admin` — Yangi admin qo'shish (ID yoki @username)\n• `/del_admin` — Adminni o'chirish\n• `/edit_admin` — Admin ismini tahrirlash\n• `/lang` — Tilni o'zgartirish (O'zbek / Русский / English)\n• `/source` — Mini App uchun nusxa xabari IDlarini olish",

        # Other messages
        "no_permission": "Sizda ruxsat yo'q!",
        "pdf_size_error": "PDF 20 MB dan oshmasin",
        "coi_checking": "COI tekshirilmoqda…",
        "coi_failed": "COI tekshiruvi bajarilmadi: {error}",
        "media_saved": "📎 *Media saqlandi!*\n\n• Turi: `{kind}`\n• `file_id`: `{file_id}`\n\n_Bu file_id'dan Mini App orqali tarqatishda foydalanishingiz mumkin._",
    },
    "ru": {
        # General / Buttons
        "btn_webapp": "📱 Mini App (Панель управления)",
        "btn_broadcast": "📨 Рассылка сообщений",
        "btn_sync": "🔄 Синхронизация",
        "btn_resync": "🔄 Пересинхронизировать",
        "btn_audits": "📊 Аудиты COI",
        "btn_jobs": "⏰ Расписание",
        "btn_admins": "👥 Администраторы",
        "btn_help": "ℹ️ Помощь",
        "btn_lang": "🌐 Til / Language / Язык",
        "btn_main": "🔙 Главное меню",
        "btn_refresh": "🔄 Обновить",
        "btn_all_groups": "📋 Все группы",
        "btn_conflicts_only": "⚠️ Только конфликты",
        "btn_new_broadcast": "➕ Новая рассылка (Mini App)",
        "btn_cancel_job": "❌ Отменить задачу #{id}",
        "btn_del_admin": "🗑 #{id}",
        "btn_add_admin": "➕ Добавить администратора",
        "btn_confirm_yes": "🗑 Да, удалить",
        "btn_confirm_no": "❌ Отмена",
        "btn_groups_status": "📋 Статус групп",
        "btn_jobs_list": "⏰ Список расписания",
        "btn_manage_miniapp": "📱 Управление в Mini App",

        # Main menu
        "main_title": "🚛 *GFS Fleet & Safety Bot*\n\nИспользуйте меню ниже для управления ботом:\n\n• 📱 *Mini App* — Рассылки сообщений и удобная визуальная панель\n• 🔄 *Синхронизация* — Обновление Monday.com и Telegram-групп\n• 📋 *Группы* — Привязка групп к номерам Unit и конфликты\n• 📊 *Аудиты COI* — История проверок VIN номеров по полисам COI\n• ⏰ *Расписание* — Список запланированных рассылок\n• 👥 *Администраторы* — Список и CRUD управление админами\n• 🌐 *Язык* — O'zbekcha / Русский / English\n\n📄 *Проверка COI:* Отправьте PDF файл прямо в чат бота.\n📷 *file_id медиа:* Отправьте фото, видео или стикер.",

        # Language selection
        "lang_select_title": "🌐 *Выберите язык / Tilni tanlang / Select language:*",
        "lang_changed": "✅ Язык успешно изменён: *Русский*",

        # Groups view
        "groups_title": "📋 *Статус групп Telegram и Unit:*",
        "groups_stat": "📊 *Всего групп:* {total} (Активных: {present})\n🔗 *Привязано:* {matched} | ⚠️ *Конфликтов:* {conflicts}",
        "groups_conflicts_head": "⚠️ *Только конфликтные группы:*",
        "groups_no_conflicts": "🎉 Все активные группы успешно сопоставлены!",
        "groups_active_head": "👥 *Список активных групп:*",
        "groups_no_active": "Бот пока не состоит ни в одной активной группе.",
        "groups_more": "\n_... и ещё {count} групп._",

        # Sync
        "sync_starting": "🔄 Синхронизация данных...",
        "sync_success": "✅ *Синхронизация успешно завершена!*\n\n🚛 *Траки в Monday:* {trucks} шт.\n👥 *Активные группы Telegram:* {groups} шт.\n🔗 *Привязано Unit:* {matched} шт.\n⚠️ *Конфликтов:* {conflicts} шт.",
        "sync_failures": "❌ *Не обновлено чатов:* {count} шт.",
        "sync_error": "❌ *Ошибка синхронизации:*\n`{error}`",

        # Audits view
        "audits_empty": "📊 *История аудитов COI пуста.*\n\nДля запуска аудита отправьте PDF-файл страхового сертификата (COI) боту.",
        "audits_title": "📊 *Результаты последних аудитов COI:*",

        # Jobs view
        "jobs_empty": "⏰ *Запланированных рассылок нет.*\n\nСоздайте новую рассылку через *Mini App*.",
        "jobs_title": "⏰ *Список рассылок и задач:*",
        "job_cancelled": "✅ Задача #{id} отменена",
        "job_not_found_or_done": "Задача не найдена или уже завершена",
        "job_started": "🚀 *Рассылка #{id} запущена!*\n\nВы можете отслеживать результат в разделе `⏰ Расписание`.",

        # Admins view & CRUD
        "admins_title": "👥 *Список администраторов* (Всего: {total}):",
        "admins_guide": "\n📌 *Управление командами:*\n• Добавить: `/add_admin ID или @username [имя] [роль]`\n• Удалить: `/del_admin ID или @username`\n• Изменить имя: `/edit_admin ID Новое Имя`",
        "admin_add_prompt_title": "✍️ *Добавление администратора:*\n\nОтправьте *Telegram ID* или *@username* пользователя:\n• Например: `123456789` или `@username`\n• С именем и ролью: `123456789 Иван admin`\n\n_Роли: `admin`, `dispatcher`, `superadmin`_",
        "admin_del_confirm": "⚠️ *Вы действительно хотите удалить администратора #{id}?*",
        "admin_deleted": "✅ Администратор #{id} удален",
        "admin_last_error": "Нельзя удалить последнего администратора!",
        "admin_not_found": "Администратор `#{id}` не найден.",
        "admin_added": "✅ Администратор успешно добавлен: `{id}`",
        "admin_updated": "✅ Данные администратора `#{id}` обновлены: *{name}*",
        "admin_user_not_found": "❌ Пользователь `@{username}` не найден.\nПользователь должен сначала отправить /start боту или укажите числовой Telegram ID.",
        "admin_id_missing": "⚠️ ID или @username не указан.",

        # Broadcast info view
        "broadcast_info_title": "📨 *Рассылка сообщений и расписание*",
        "broadcast_info_stats": "📊 *Активных групп:* {total} (Подходит: {eligible})",
        "broadcast_info_desc": "Возможности бота:\n• 📢 Отправка *во все группы* или 👥 *в выбранные группы*\n• ⚡️ Отправка *сейчас* или ⏰ *по расписанию*\n• 🌐 *Поддержка часовых поясов:*\n   🇺🇿 *Asia (Ташкент)* — UTC+5\n   🇺🇸 *USA Central (Чикаго, Даллас)* — CT\n   🇺🇸 *USA Eastern (Нью-Йорк, Флорида)* — ET\n   🇺🇸 *USA Pacific (Лос-Анджелес, Калифорния)* — PT\n\n📌 *Как отправить:*\n1. *Через Mini App (Рекомендуется):* Выбор групп, прикрепление медиа, стикеров, кнопок и расчёт часовых поясов.\n2. *Быстрая команда:* `/broadcast Текст` — немедленно отправить текст во все активные группы.",

        # Help view
        "help_title": "ℹ️ *GFS Fleet & Safety Bot — Руководство*",
        "help_desc": "🤖 *Основные возможности:*\n• *Проверка COI VIN:* Просто отправьте PDF сертификата боту или ответьте на него `/check_coi`.\n• *Синхронизация Monday.com:* Автоматически связывает группы Telegram с Unit из Monday.\n• *Рассылка сообщений (Mini App):* Отправляйте текст, медиа, стикеры и inline-кнопки.\n• *Планирование:* Разовые или еженедельные автоматические рассылки.\n• *Часовые пояса:* Ташкент (Asia/Tashkent) и США (Central, Eastern, Pacific).\n\n📌 *Команды:*\n• `/start` или `/help` — Открыть главное меню\n• `/sync` — Синхронизировать Monday и группы\n• `/groups` — Состояние групп и номеров Unit\n• `/check_coi` — Проверить прикрепленный PDF файл\n• `/add_admin` — Добавить админа (ID или @username)\n• `/del_admin` — Удалить админа\n• `/edit_admin` — Изменить имя админа\n• `/lang` — Сменить язык (Узбекский / Русский / English)\n• `/source` — Получить ID сообщения для режима копирования",

        # Other messages
        "no_permission": "У вас нет доступа!",
        "pdf_size_error": "Размер PDF не должен превышать 20 МБ",
        "coi_checking": "Проверка COI…",
        "coi_failed": "Проверка COI не удалась: {error}",
        "media_saved": "📎 *Медиа сохранено!*\n\n• Тип: `{kind}`\n• `file_id`: `{file_id}`\n\n_Этот file_id можно использовать при рассылке в Mini App._",
    },
    "en": {
        # General / Buttons
        "btn_webapp": "📱 Mini App (Control Panel)",
        "btn_broadcast": "📨 Broadcast Message",
        "btn_sync": "🔄 Synchronize",
        "btn_resync": "🔄 Re-sync",
        "btn_audits": "📊 COI Audits",
        "btn_jobs": "⏰ Scheduled Jobs",
        "btn_admins": "👥 Administrators",
        "btn_help": "ℹ️ Help",
        "btn_lang": "🌐 Til / Language / Язык",
        "btn_main": "🔙 Main Menu",
        "btn_refresh": "🔄 Refresh",
        "btn_all_groups": "📋 All Groups",
        "btn_conflicts_only": "⚠️ Conflicts Only",
        "btn_new_broadcast": "➕ New Broadcast (Mini App)",
        "btn_cancel_job": "❌ Cancel Job #{id}",
        "btn_del_admin": "🗑 #{id}",
        "btn_add_admin": "➕ Add Administrator",
        "btn_confirm_yes": "🗑 Yes, delete",
        "btn_confirm_no": "❌ Cancel",
        "btn_groups_status": "📋 Groups Status",
        "btn_jobs_list": "⏰ Jobs List",
        "btn_manage_miniapp": "📱 Manage in Mini App",

        # Main menu
        "main_title": "🚛 *GFS Fleet & Safety Bot*\n\nUse the buttons below to control the bot:\n\n• 📱 *Mini App* — Broadcasts & intuitive visual dashboard\n• 🔄 *Sync* — Refresh Monday.com and Telegram groups\n• 📋 *Groups* — Group Unit bindings and conflicts\n• 📊 *COI Audits* — History of recent COI VIN checks\n• ⏰ *Schedule* — List of scheduled broadcasts\n• 👥 *Admins* — Administrators list & full CRUD\n• 🌐 *Language* — O'zbekcha / Русский / English\n\n📄 *COI verification:* Send a PDF certificate directly to the bot.\n📷 *Media file_id:* Send a photo, video, or sticker.",

        # Language selection
        "lang_select_title": "🌐 *Select language / Tilni tanlang / Выберите язык:*",
        "lang_changed": "✅ Language successfully updated: *English*",

        # Groups view
        "groups_title": "📋 *Telegram Groups and Units Status:*",
        "groups_stat": "📊 *Total Groups:* {total} (Active: {present})\n🔗 *Bound:* {matched} | ⚠️ *Conflicts:* {conflicts}",
        "groups_conflicts_head": "⚠️ *Conflict Groups Only:*",
        "groups_no_conflicts": "🎉 All active groups are successfully bound!",
        "groups_active_head": "👥 *Active Groups List:*",
        "groups_no_active": "The bot is not currently in any active group.",
        "groups_more": "\n_... and {count} more groups._",

        # Sync
        "sync_starting": "🔄 Synchronizing...",
        "sync_success": "✅ *Sync completed successfully!*\n\n🚛 *Monday Trucks:* {trucks}\n👥 *Active Telegram Groups:* {groups}\n🔗 *Bound Units:* {matched}\n⚠️ *Conflict Groups:* {conflicts}",
        "sync_failures": "❌ *Failed Chat Updates:* {count}",
        "sync_error": "❌ *Sync Error:*\n`{error}`",

        # Audits view
        "audits_empty": "📊 *COI Audits history is empty.*\n\nSend a COI insurance policy PDF file to the bot to create a new audit.",
        "audits_title": "📊 *Recent COI Audits Results:*",

        # Jobs view
        "jobs_empty": "⏰ *No scheduled broadcasts found.*\n\nUse the *Mini App* to create and schedule a new broadcast.",
        "jobs_title": "⏰ *Broadcasts & Schedule List:*",
        "job_cancelled": "✅ Job #{id} cancelled",
        "job_not_found_or_done": "Job not found or already completed",
        "job_started": "🚀 *Broadcast #{id} has started!*\n\nYou can track the results in `⏰ Scheduled Jobs`.",

        # Admins view & CRUD
        "admins_title": "👥 *Administrators List* (Total: {total}):",
        "admins_guide": "\n📌 *Command Management:*\n• Add: `/add_admin ID or @username [name] [role]`\n• Delete: `/del_admin ID or @username`\n• Edit: `/edit_admin ID New Name`",
        "admin_add_prompt_title": "✍️ *Add New Administrator:*\n\nSend the user's *Telegram ID* or *@username*:\n• Example: `123456789` or `@username`\n• With name and role: `123456789 John admin`\n\n_Roles: `admin`, `dispatcher`, `superadmin`_",
        "admin_del_confirm": "⚠️ *Are you sure you want to delete administrator #{id}?*",
        "admin_deleted": "✅ Administrator #{id} deleted",
        "admin_last_error": "Cannot delete the last administrator!",
        "admin_not_found": "Administrator `#{id}` not found.",
        "admin_added": "✅ Administrator added successfully: `{id}`",
        "admin_updated": "✅ Administrator `#{id}` updated: *{name}*",
        "admin_user_not_found": "❌ User `@{username}` not found.\nThe user must first send /start to the bot, or provide a numeric Telegram ID.",
        "admin_id_missing": "⚠️ Telegram ID or @username was not provided.",

        # Broadcast info view
        "broadcast_info_title": "📨 *Group Broadcast & Scheduling*",
        "broadcast_info_stats": "📊 *Active Groups:* {total} (Eligible: {eligible})",
        "broadcast_info_desc": "Features provided by the bot:\n• 📢 Send to *all groups* or 👥 *selected groups*\n• ⚡️ Send *immediately* or ⏰ *schedule for later*\n• 🌐 *Timezone alignment:*\n   🇺🇿 *Asia (Tashkent)* — UTC+5\n   🇺🇸 *USA Central (Chicago, Dallas)* — CT\n   🇺🇸 *USA Eastern (New York, Florida)* — ET\n   🇺🇸 *USA Pacific (Los Angeles, California)* — PT\n\n📌 *How to send:*\n1. *Via Mini App (Recommended):* Group selection, media, stickers, inline buttons, and timezone calculator.\n2. *Quick command:* `/broadcast Text` — instantly broadcast text to all active groups.",

        # Help view
        "help_title": "ℹ️ *GFS Fleet & Safety Bot — Manual*",
        "help_desc": "🤖 *Core Features:*\n• *COI VIN Check:* Simply send the COI PDF file or reply to it with `/check_coi`.\n• *Monday.com Sync:* Automatically links Telegram group titles with Monday Unit numbers.\n• *Broadcasts (Mini App):* Send text, media, stickers, and inline buttons.\n• *Scheduling:* One-time or weekly recurring broadcasts.\n• *Timezones:* Tashkent (Asia/Tashkent) and USA (Central, Eastern, Pacific) times.\n\n📌 *Commands:*\n• `/start` or `/help` — Open main menu\n• `/sync` — Synchronize Monday and groups\n• `/groups` — View group and Unit statuses\n• `/check_coi` — Audit replied PDF file\n• `/add_admin` — Add admin (ID or @username)\n• `/del_admin` — Delete admin\n• `/edit_admin` — Edit admin name\n• `/lang` — Change language (Uzbek / Русский / English)\n• `/source` — Get message IDs for copy mode",

        # Other messages
        "no_permission": "Permission denied!",
        "pdf_size_error": "PDF size must not exceed 20 MB",
        "coi_checking": "Analyzing COI…",
        "coi_failed": "COI verification failed: {error}",
        "media_saved": "📎 *Media saved!*\n\n• Type: `{kind}`\n• `file_id`: `{file_id}`\n\n_You can use this file_id when composing broadcasts in the Mini App._",
    }
}


def t(key: str, lang: str = "uz", **kwargs) -> str:
    """Retrieve translated string with interpolation; falls back to uz then en."""
    lang = (lang or "uz").lower()[:2]
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    tmpl = TRANSLATIONS.get(lang, {}).get(key)
    if tmpl is None:
        tmpl = TRANSLATIONS.get(DEFAULT_LANGUAGE, {}).get(key, key)

    if kwargs:
        try:
            return tmpl.format(**kwargs)
        except Exception:
            return tmpl
    return tmpl

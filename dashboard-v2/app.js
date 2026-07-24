const els = {
  moduleNav: document.querySelector("#moduleNav"),
  pageTitle: document.querySelector("#pageTitle"),
  scopeLine: document.querySelector("#scopeLine"),
  headerEyebrow: document.querySelector("#headerEyebrow"),
  companiesSection: document.querySelector("#companiesSection"),
  sideCompaniesTitle: document.querySelector("#sideCompaniesTitle"),
  summaryGrid: document.querySelector("#summaryGrid"),
  activeModuleEyebrow: document.querySelector("#activeModuleEyebrow"),
  activeModuleTitle: document.querySelector("#activeModuleTitle"),
  moduleContent: document.querySelector("#moduleContent"),
  detectorState: document.querySelector("#detectorState"),
  refreshBtn: document.querySelector("#refreshBtn"),
  languageToggle: document.querySelector("#languageToggle"),
  shell: document.querySelector(".v2-shell"),
  sidebarToggle: document.querySelector("#sidebarToggle"),
  brandAvatar: document.querySelector("#brandAvatar"),
  headerProfile: document.querySelector("#headerProfile"),
  sideProfile: document.querySelector("#sideProfile"),
  themeToggle: document.querySelector("#themeToggle"),
  sideCompanies: document.querySelector("#sideCompanies"),
  toast: document.querySelector("#toast"),
};

const API_BASE = (() => {
  const param = new URLSearchParams(window.location.search).get("api");
  if (param) {
    localStorage.setItem("ai_vision_v2_api_base", param.replace(/\/+$/, ""));
  }
  const saved = localStorage.getItem("ai_vision_v2_api_base");
  if (saved) return saved;
  if (window.location.hostname.endsWith("vercel.app")) {
    return "https://67-205-160-8.sslip.io";
  }
  return window.location.origin;
})();

const state = {
  role: "super_admin",
  activeModule: null,
  session: null,
  overview: null,
  streams: [],
};

const LANGUAGE_KEY = "ai_vision_v2_language";
const I18N = {
  en: {
    "actions.apply": "Apply",
    "actions.clear": "Clear",
    "actions.connect": "Connect",
    "actions.connecting": "Connecting...",
    "actions.export_excel": "Export to Excel",
    "actions.refresh": "Refresh",
    "actions.run_recognition": "Run recognition now",
    "actions.recognizing": "Recognizing...",
    "ai.add_help": "Choose at least 2 clear images from different angles.",
    "ai.add_item": "Add item to AI catalog",
    "ai.catalog_enabled": "Catalog recognition enabled",
    "ai.empty_catalog": "No catalog items yet. Add an item name and at least two images above.",
    "ai.intro": "Add only the items the AI is allowed to recognize. Every item requires multiple reference images; anything outside this catalog is ignored by scheduled recognition.",
    "ai.item_name": "Item name",
    "ai.item_placeholder": "e.g. Bread crate",
    "ai.reference_images": "Reference images",
    "analytics.catalog_note": "Operational overview with scheduled catalog recognition results below.",
    "analytics.detected_title": "Detected AI Check-in items",
    "analytics.latest_run": "Latest 12-hour recognition run: {time}",
    "analytics.next_run": "Next automatic recognition: {time}",
    "analytics.no_detected": "No checked-in AI item was recognized in the current camera images yet.",
    "camera.address": "Address:",
    "camera.channels": "Channels:",
    "camera.connected_devices": "Connected devices: {count}/{max}. Enter a device's public IP or hostname and AI Vision discovers its available services automatically - no RTSP URL, stream path, or vendor needed. The device must be reachable over the internet (public IP, port-forward, or DDNS); local-only addresses like 192.168.x.x won't connect from the cloud.",
    "camera.device_limit": "Device limit reached ({max}). Remove one to add another.",
    "camera.no_devices": "No devices connected yet - discover the first one below.",
    "camera.quality_note": "Lower quality serves video faster over slow connections.",
    "camera.quality_title": "Vision quality",
    "camera_info.empty": "No cameras connected yet. Add a device in Camera Control first.",
    "camera_info.header": "{cameras} connected cameras across {devices} NVR devices.",
    "camera_info.loading": "Loading camera device info...",
    "camera_info.models": "Models detected",
    "camera_info.nvr_devices": "NVR devices",
    "camera_info.title": "Camera Info",
    "dimension.loading": "Loading 3D recognition results...",
    "dimension.note": "3D drawings are created only for checked-in catalog items that receive a spatial measurement during recognition.",
    "dimension.empty": "No recognized item has a 3D measurement yet. The next recognition runs at {time}.",
    "discovery.available": "Available",
    "discovery.auth_hint": "This service asked for sign-in - enter the device credentials.",
    "discovery.channels_label": "Channels to connect",
    "discovery.connectable_empty": "No connectable services were exposed.",
    "discovery.discovered": "Discovered:",
    "discovery.host_placeholder": "Device IP or hostname (e.g. 87.192.242.82)",
    "discovery.name_placeholder": "Name this device (e.g. Warehouse North)",
    "discovery.needs_signin": "Needs sign-in",
    "discovery.password_placeholder": "Password (optional)",
    "discovery.progress": "Scanning {host} for available services...",
    "discovery.search": "Search",
    "discovery.searching": "Searching...",
    "discovery.select_service": "Select a service to connect to:",
    "discovery.unreachable": "Unreachable",
    "discovery.username_placeholder": "Username (optional)",
    "feed.empty": "No NVRs connected - set one up in Camera Control first.",
    "feed.default_group": "BLOCK {letter}",
    "feed.group_cameras": "{count} cameras",
    "feed.group_note": "Camera feeds are grouped automatically by room/block. Edit a group name to match your warehouse rooms.",
    "feed.group_save": "Save",
    "feed.group_saved": "Camera group name saved.",
    "feed.group_name": "Group name",
    "feed.live_note": "Live transmission at {quality} quality. This view is not recording continuous video.",
    "feed.no_signal": "No signal yet",
    "feed.readd": "Remove and re-add this NVR to reconnect it",
    "header.eyebrow": "Enterprise warehouse intelligence",
    "header.head_dashboard": "Head Dashboard",
    "header.loading_permissions": "Loading permissions...",
    "head.module": "Head module",
    "head.no_access": "This role has no access to modules on this surface.",
    "lang.switch_to_en": "Switch to English",
    "lang.switch_to_ru": "Переключить на русский",
    "menu.ai": "AI Check-in",
    "menu.analytics": "Analytics",
    "menu.camera": "Camera Control",
    "menu.camera_info": "Camera Info",
    "menu.dimension": "3D Dimensioning",
    "menu.feed": "Camera Feed",
    "menu.result_analytics": "Result Analytics",
    "menu.settings": "Settings",
    "profile.super_admin": "Super Admin",
    "quality.high.hint": "best picture",
    "quality.high.label": "High - 1080p",
    "quality.low.hint": "fastest serving",
    "quality.low.label": "Low - 480p",
    "quality.medium.hint": "balanced",
    "quality.medium.label": "Medium - 720p",
    "result.all_results": "All results",
    "result.camera_filter": "NVR or camera",
    "result.cameras_with_results": "Cameras with results",
    "result.confidence": "Confidence",
    "result.empty": "No recognition results are saved yet. Run AI Check-in first.",
    "result.item_filter": "Item",
    "result.last_hour": "Last hour",
    "result.latest_by_camera": "Latest by camera",
    "result.loading": "Loading recognition results...",
    "result.next_run": "Next run",
    "result.objects": "Objects",
    "result.object_crop": "Object crop",
    "result.recognition_runs": "Recognition runs",
    "result.scene_image": "Camera view",
    "result.table_time": "Recognition time",
    "result.this_month": "This month",
    "result.this_week": "This week",
    "result.title": "Result Analytics",
    "result.today": "Today",
    "result.total_objects": "Total objects",
    "result.subtitle": "Recognition results by NVR, camera and item.",
    "result.visual_empty": "No saved images for these results yet. Run recognition now to capture camera and object pictures.",
    "result.visual_subtitle": "Camera frame and object crop saved during recognition.",
    "result.visual_title": "Recognition images",
    "settings.loading_profile": "Loading profile...",
    "settings.title": "Settings",
    "status.connected": "Connected",
    "status.detector_running": "Detector running",
    "status.detector_stopped": "Detector stopped",
    "status.live": "Live",
    "status.not_connected": "Not connected",
    "status.offline": "Offline",
    "status.pending": "Pending",
    "status.reconnecting": "Reconnecting",
    "status.registered": "Registered",
    "status.starting": "Starting",
    "status.waiting_fresh_frame": "Waiting for a fresh camera frame",
    "status.waiting_slot": "Waiting for slot",
    "status.waiting_video": "Waiting for video",
    "status.waiting_free_slot": "Waiting for a free slot",
    "table.ai_slot": "AI slot",
    "table.camera": "Camera",
    "table.camera_objects": "Camera / objects",
    "table.count": "Count",
    "table.item": "Item",
    "table.model": "Model",
    "table.nvr_device": "NVR / Device",
    "table.objects_recognized": "Objects recognized",
    "table.stream": "Stream",
    "table.slot": "Slot",
    "table.not_assigned": "Not assigned",
    "table.channel": "channel",
    "table.channels": "channels",
    "table.channel_short": "Ch",
    "table.unknown_camera": "Unknown camera",
    "table.unknown_nvr": "Unknown NVR",
    "table.vendor": "Vendor",
    "table.host": "Host",
    "table.status": "Status",
    "table.measurement": "3D measurement",
    "summary.active_cameras": "Active cameras",
    "summary.frames_read": "Frames read",
    "summary.last_detections": "Last detections",
    "summary.stock_items": "Stock items",
    "summary.saved_cameras": "Saved cameras",
    "summary.audit_verified": "Audit verified",
    "summary.yes": "Yes",
    "summary.no": "No",
    "summary.delta_cameras": "+1 this week",
    "summary.delta_no_change": "no change",
    "summary.delta_detections": "-2 vs yesterday",
    "summary.delta_saved": "+1 this month",
    "summary.delta_normal": "all systems normal",
    "head.unavailable": "Unavailable",
    "side.companies": "Companies",
    "side.no_companies": "No companies yet",
    "device_type.nvr": "NVR / DVR",
    "device_type.camera": "IP camera",
    "device_type.unknown": "Unknown device",
    "device_type.device": "Device",
    "camera.connected_via": "Connected via {provider} - {assigned}/{total} slots assigned. Waiting for live video frames.",
    "camera.registered_no_slots": "Registered, but no slots are assigned yet.",
    "camera.slots_assigned": "slots assigned",
    "discovery.no_services": "No services found on this device.",
    "analytics.by_camera_title": "Recognized objects by NVR and camera",
    "analytics.loading_detected": "Loading detected items...",
    "ai.auto_recognition": "Automatic recognition every {hours} hours",
    "ai.last_run": "Last: {time}",
    "ai.loading": "Loading AI catalog...",
    "ai.next_run": "Next: {time}",
    "dimension.measured": "Measured:",
    "dimension.pending_measurement": "Pending 3D measurement",
    "dimension.recognized": "Recognized x{quantity}",
    "dimension.volume": "Volume:",
    "result.pending_first_run": "Pending first recognition run",
    "result.show_limit": "Show {limit}",
    "settings.confirm_password": "Confirm new password",
    "settings.credentials_updated": "Credentials updated.",
    "settings.current_login": "Current login:",
    "settings.login_password": "Login & password",
    "settings.new_login": "New login",
    "settings.new_password": "New password",
    "settings.passwords_mismatch": "Passwords do not match.",
    "settings.picture_too_large": "Picture is too large - keep it under 2 MB.",
    "settings.picture_updated": "Profile picture updated.",
    "settings.profile_picture": "Profile picture",
    "settings.remove": "Remove",
    "settings.server_note": "Stored on the server - your login and picture follow you to any device.",
    "settings.update_credentials": "Update credentials",
    "settings.upload_picture": "Upload picture",
    "user.good_morning": "Good Morning, {name} 👋",
    "user.good_afternoon": "Good Afternoon, {name} 👋",
    "user.good_evening": "Good Evening, {name} 👋",
    "user.scope_line": "{company} • login: {login}",
    "user.welcome": "Welcome, {name}",
    "toast.dashboard_refreshed": "Dashboard V2 refreshed.",
    "toast.language_updated": "Language switched to English.",
    "toast.recognition_complete": "Recognition complete.",
    "user.module": "User module",
  },
  ru: {
    "actions.apply": "Применить",
    "actions.clear": "Очистить",
    "actions.connect": "Подключить",
    "actions.connecting": "Подключение...",
    "actions.export_excel": "Экспорт в Excel",
    "actions.refresh": "Обновить",
    "actions.run_recognition": "Запустить распознавание",
    "actions.recognizing": "Распознавание...",
    "ai.add_help": "Выберите минимум 2 четких изображения с разных ракурсов.",
    "ai.add_item": "Добавить товар в AI каталог",
    "ai.catalog_enabled": "Распознавание по каталогу включено",
    "ai.empty_catalog": "В каталоге пока нет товаров. Добавьте название и минимум два изображения.",
    "ai.intro": "Добавляйте только те товары, которые AI должен распознавать. Для каждого товара нужно несколько эталонных изображений; все вне каталога будет игнорироваться.",
    "ai.item_name": "Название товара",
    "ai.item_placeholder": "например, коробка Baget",
    "ai.reference_images": "Эталонные изображения",
    "analytics.catalog_note": "Операционный обзор и ниже результаты планового распознавания каталога.",
    "analytics.detected_title": "Найденные товары AI Check-in",
    "analytics.latest_run": "Последний запуск за 12 часов: {time}",
    "analytics.next_run": "Следующее автоматическое распознавание: {time}",
    "analytics.no_detected": "В текущих кадрах камеры товары из AI Check-in пока не распознаны.",
    "camera.address": "Адрес:",
    "camera.channels": "Каналы:",
    "camera.connected_devices": "Подключенные устройства: {count}/{max}. Введите публичный IP или hostname устройства, и AI Vision сам найдет доступные сервисы - без RTSP URL, пути потока и выбора производителя. Устройство должно быть доступно из интернета; локальные адреса 192.168.x.x из облака не подключатся.",
    "camera.device_limit": "Достигнут лимит устройств ({max}). Удалите одно, чтобы добавить новое.",
    "camera.no_devices": "Устройства пока не подключены - найдите первое ниже.",
    "camera.quality_note": "Низкое качество быстрее передает видео при слабом соединении.",
    "camera.quality_title": "Качество видео",
    "camera_info.empty": "Камеры пока не подключены. Сначала добавьте устройство в Camera Control.",
    "camera_info.header": "{cameras} подключенных камер на {devices} NVR устройствах.",
    "camera_info.loading": "Загрузка информации о камерах...",
    "camera_info.models": "Найдено моделей",
    "camera_info.nvr_devices": "NVR устройства",
    "camera_info.title": "Инфо камер",
    "dimension.loading": "Загрузка результатов 3D распознавания...",
    "dimension.note": "3D чертежи создаются только для товаров AI Check-in, у которых есть пространственное измерение.",
    "dimension.empty": "Пока нет распознанных товаров с 3D измерением. Следующее распознавание: {time}.",
    "discovery.available": "Доступно",
    "discovery.auth_hint": "Сервис запросил вход - введите логин и пароль устройства.",
    "discovery.channels_label": "Количество каналов",
    "discovery.connectable_empty": "Доступные сервисы для подключения не найдены.",
    "discovery.discovered": "Найдено:",
    "discovery.host_placeholder": "IP или hostname устройства (например 87.192.242.82)",
    "discovery.name_placeholder": "Название устройства (например Склад Север)",
    "discovery.needs_signin": "Нужен вход",
    "discovery.password_placeholder": "Пароль (необязательно)",
    "discovery.progress": "Сканирование {host} на доступные сервисы...",
    "discovery.search": "Найти",
    "discovery.searching": "Поиск...",
    "discovery.select_service": "Выберите сервис для подключения:",
    "discovery.unreachable": "Недоступно",
    "discovery.username_placeholder": "Логин (необязательно)",
    "feed.empty": "NVR пока не подключены - сначала настройте устройство в Camera Control.",
    "feed.default_group": "БЛОК {letter}",
    "feed.group_cameras": "{count} камер",
    "feed.group_note": "Видеопотоки автоматически группируются по комнатам/блокам. Измените название группы под свои помещения склада.",
    "feed.group_save": "Сохранить",
    "feed.group_saved": "Название группы камер сохранено.",
    "feed.group_name": "Название группы",
    "feed.live_note": "Live видео в качестве {quality}. Эта страница не записывает постоянное видео.",
    "feed.no_signal": "Сигнала пока нет",
    "feed.readd": "Удалите и добавьте NVR заново, чтобы переподключить его",
    "header.eyebrow": "Интеллектуальный складской контроль",
    "header.head_dashboard": "Главная панель",
    "header.loading_permissions": "Загрузка прав доступа...",
    "head.module": "Главный модуль",
    "head.no_access": "У этой роли нет доступа к модулям на этой странице.",
    "lang.switch_to_en": "Switch to English",
    "lang.switch_to_ru": "Переключить на русский",
    "menu.ai": "AI Check-in",
    "menu.analytics": "Аналитика",
    "menu.camera": "Управление камерами",
    "menu.camera_info": "Инфо камер",
    "menu.dimension": "3D измерение",
    "menu.feed": "Видеопоток",
    "menu.result_analytics": "Аналитика результатов",
    "menu.settings": "Настройки",
    "profile.super_admin": "Супер админ",
    "quality.high.hint": "лучшее изображение",
    "quality.high.label": "Высокое - 1080p",
    "quality.low.hint": "самая быстрая передача",
    "quality.low.label": "Низкое - 480p",
    "quality.medium.hint": "баланс",
    "quality.medium.label": "Среднее - 720p",
    "result.all_results": "Все результаты",
    "result.camera_filter": "NVR или камера",
    "result.cameras_with_results": "Камер с результатами",
    "result.confidence": "Уверенность",
    "result.empty": "Сохраненных результатов распознавания пока нет. Сначала запустите AI Check-in.",
    "result.item_filter": "Товар",
    "result.last_hour": "За последний час",
    "result.latest_by_camera": "Последний по камере",
    "result.loading": "Загрузка результатов распознавания...",
    "result.next_run": "Следующий запуск",
    "result.objects": "Объекты",
    "result.object_crop": "Crop объекта",
    "result.recognition_runs": "Запуски распознавания",
    "result.scene_image": "Кадр камеры",
    "result.table_time": "Время распознавания",
    "result.this_month": "За месяц",
    "result.this_week": "За неделю",
    "result.title": "Аналитика результатов",
    "result.today": "За день",
    "result.total_objects": "Всего объектов",
    "result.subtitle": "Результаты распознавания по NVR, камере и товару.",
    "result.visual_empty": "Для этих результатов пока нет сохраненных картинок. Запустите распознавание, чтобы сохранить кадр камеры и объект.",
    "result.visual_subtitle": "Кадр камеры и crop объекта, сохраненные во время распознавания.",
    "result.visual_title": "Картинки распознавания",
    "settings.loading_profile": "Загрузка профиля...",
    "settings.title": "Настройки",
    "status.connected": "Подключено",
    "status.detector_running": "Детектор работает",
    "status.detector_stopped": "Детектор остановлен",
    "status.live": "Live",
    "status.not_connected": "Не подключено",
    "status.offline": "Офлайн",
    "status.pending": "Ожидание",
    "status.reconnecting": "Переподключение",
    "status.registered": "Зарегистрировано",
    "status.starting": "Запуск",
    "status.waiting_fresh_frame": "Ожидание свежего кадра камеры",
    "status.waiting_slot": "Ожидает слот",
    "status.waiting_video": "Ожидание видео",
    "status.waiting_free_slot": "Ожидает свободный слот",
    "table.ai_slot": "AI слот",
    "table.camera": "Камера",
    "table.camera_objects": "Камера / объекты",
    "table.count": "Количество",
    "table.item": "Товар",
    "table.model": "Модель",
    "table.nvr_device": "NVR / устройство",
    "table.objects_recognized": "Распознано объектов",
    "table.stream": "Поток",
    "table.slot": "Слот",
    "table.not_assigned": "Не назначен",
    "table.channel": "канал",
    "table.channels": "каналов",
    "table.channel_short": "Канал",
    "table.unknown_camera": "Неизвестная камера",
    "table.unknown_nvr": "Неизвестный NVR",
    "table.vendor": "Производитель",
    "table.host": "Host",
    "table.status": "Статус",
    "table.measurement": "3D измерение",
    "summary.active_cameras": "Активные камеры",
    "summary.frames_read": "Кадров прочитано",
    "summary.last_detections": "Последние детекции",
    "summary.stock_items": "Товары на складе",
    "summary.saved_cameras": "Сохраненные камеры",
    "summary.audit_verified": "Аудит проверен",
    "summary.yes": "Да",
    "summary.no": "Нет",
    "summary.delta_cameras": "+1 за неделю",
    "summary.delta_no_change": "без изменений",
    "summary.delta_detections": "-2 к вчера",
    "summary.delta_saved": "+1 за месяц",
    "summary.delta_normal": "системы в норме",
    "head.unavailable": "Недоступно",
    "side.companies": "Компании",
    "side.no_companies": "Компаний пока нет",
    "device_type.nvr": "NVR / DVR",
    "device_type.camera": "IP камера",
    "device_type.unknown": "Неизвестное устройство",
    "device_type.device": "Устройство",
    "camera.connected_via": "Подключено через {provider} - назначено {assigned}/{total} слотов. Ожидаем live video кадры.",
    "camera.registered_no_slots": "Зарегистрировано, но слоты пока не назначены.",
    "camera.slots_assigned": "слотов назначено",
    "discovery.no_services": "На этом устройстве сервисы не найдены.",
    "analytics.by_camera_title": "Распознанные объекты по NVR и камере",
    "analytics.loading_detected": "Загрузка найденных товаров...",
    "ai.auto_recognition": "Автоматическое распознавание каждые {hours} часов",
    "ai.last_run": "Последний: {time}",
    "ai.loading": "Загрузка AI каталога...",
    "ai.next_run": "Следующий: {time}",
    "dimension.measured": "Измерено:",
    "dimension.pending_measurement": "Ожидает 3D измерение",
    "dimension.recognized": "Распознано x{quantity}",
    "dimension.volume": "Объем:",
    "result.pending_first_run": "Первый запуск распознавания еще не выполнен",
    "result.show_limit": "Показать {limit}",
    "settings.confirm_password": "Подтвердите новый пароль",
    "settings.credentials_updated": "Логин и пароль обновлены.",
    "settings.current_login": "Текущий логин:",
    "settings.login_password": "Логин и пароль",
    "settings.new_login": "Новый логин",
    "settings.new_password": "Новый пароль",
    "settings.passwords_mismatch": "Пароли не совпадают.",
    "settings.picture_too_large": "Изображение слишком большое - максимум 2 MB.",
    "settings.picture_updated": "Фото профиля обновлено.",
    "settings.profile_picture": "Фото профиля",
    "settings.remove": "Удалить",
    "settings.server_note": "Сохранено на сервере - логин и фото доступны с любого устройства.",
    "settings.update_credentials": "Обновить данные",
    "settings.upload_picture": "Загрузить фото",
    "user.good_morning": "Доброе утро, {name} 👋",
    "user.good_afternoon": "Добрый день, {name} 👋",
    "user.good_evening": "Добрый вечер, {name} 👋",
    "user.scope_line": "{company} • логин: {login}",
    "user.welcome": "Добро пожаловать, {name}",
    "toast.dashboard_refreshed": "Dashboard V2 обновлен.",
    "toast.language_updated": "Язык переключен на русский.",
    "toast.recognition_complete": "Распознавание завершено.",
    "user.module": "Модуль пользователя",
  },
};

function currentLanguage() {
  const saved = localStorage.getItem(LANGUAGE_KEY);
  return saved === "ru" ? "ru" : "en";
}

function t(key, vars = {}) {
  const lang = currentLanguage();
  const template = I18N[lang]?.[key] || I18N.en[key] || key;
  return template.replace(/\{(\w+)\}/g, (_match, name) => String(vars[name] ?? ""));
}

function tOrNull(key) {
  return I18N[currentLanguage()]?.[key] || I18N.en[key] || null;
}

function setLanguageToggleChrome() {
  const lang = currentLanguage();
  document.documentElement.lang = lang;
  if (els.headerEyebrow) els.headerEyebrow.textContent = t("header.eyebrow");
  if (els.sideCompaniesTitle) els.sideCompaniesTitle.textContent = t("side.companies");
  if (els.refreshBtn) els.refreshBtn.textContent = t("actions.refresh");
  if (els.languageToggle) {
    els.languageToggle.innerHTML = `<span class="${lang === "ru" ? "active" : ""}">RU</span><span class="${lang === "en" ? "active" : ""}">ENG</span>`;
    els.languageToggle.title = lang === "ru" ? t("lang.switch_to_en") : t("lang.switch_to_ru");
    els.languageToggle.setAttribute("aria-label", els.languageToggle.title);
  }
}

function rerenderCurrentViewForLanguage() {
  setLanguageToggleChrome();
  renderSideCompaniesFromCache();
  if (accountState) {
    renderAccountView(accountState);
    return;
  }
  if (state.session) {
    els.pageTitle.textContent = t("header.head_dashboard");
    renderNavigation();
    renderSummary();
    renderScope();
    renderModuleContent();
  }
}

const LOAD_RETRY_DELAYS_MS = [500, 1000, 2000];
let loadRetryTimer = null;

// Each mounted camera renders a real, continuous MJPEG stream from the Stream
// Manager (`/api/live_mjpeg`) - the browser paints it as full-motion video with
// no per-frame polling. Browsers cap concurrent connections per origin (~6 in
// Chrome), so we only ever keep MAX_LIVE_STREAMS of the *visible* tiles
// connected at once; the rest are disconnected until they scroll into view.
const LIVE_FRAME_REFRESH_MS = 150;
const MAX_LIVE_STREAMS = 6;
// A stream that errors (slot has no active camera yet, or upstream dropped) is
// backed off before we spend one of the scarce connection slots retrying it.
const LIVE_STREAM_ERROR_BACKOFF_MS = 4000;
let liveFrameTimer = null;
let liveFrameVisibilityObserver = null;

function liveStreamUrl(slot) {
  const url = new URL(`${API_BASE}/api/live_mjpeg`);
  url.searchParams.set("slot", slot);
  return url.toString();
}

function liveFrameUrl(slot) {
  // Single still frame - used as the initial poster before the stream connects.
  const url = new URL(`${API_BASE}/api/live_frame`);
  url.searchParams.set("slot", slot);
  url.searchParams.set("v", Date.now());
  return url.toString();
}

function setFeedBadgeLive(image, isLive) {
  const badge = image.parentElement?.querySelector(".feed-transmitting");
  if (!badge) return;
  badge.textContent = isLive ? t("status.live") : t("status.waiting_video");
  badge.classList.toggle("feed-stale-badge", !isLive);
}

function attachLiveFrameHandlers(image) {
  if (image.dataset.liveHandlersAttached === "true") return;
  image.dataset.liveHandlersAttached = "true";
  image.addEventListener("load", () => {
    delete image.dataset.livePriming;
    delete image.dataset.liveErrorUntil;
    image.classList.remove("feed-stale");
    image.removeAttribute("title");
    image.dataset.liveLastUpdate = new Date().toISOString();
    setFeedBadgeLive(image, true);
  });
  image.addEventListener("error", () => {
    delete image.dataset.livePriming;
    // Drop the failed connection and back off so the slot is freed for another
    // visible tile instead of being held open on a dead stream.
    image.dataset.liveErrorUntil = String(Date.now() + LIVE_STREAM_ERROR_BACKOFF_MS);
    stopLiveStream(image);
    image.classList.add("feed-stale");
    image.title = t("status.waiting_fresh_frame");
    setFeedBadgeLive(image, false);
  });
  if (image.complete && image.naturalWidth > 0) {
    delete image.dataset.livePriming;
    image.classList.remove("feed-stale");
    image.removeAttribute("title");
    setFeedBadgeLive(image, true);
  }
}

function ensureLiveFrameVisibilityObserver() {
  if (!("IntersectionObserver" in window)) return null;
  if (liveFrameVisibilityObserver) return liveFrameVisibilityObserver;
  liveFrameVisibilityObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        entry.target.dataset.liveVisible = entry.isIntersecting ? "true" : "false";
      });
      reconcileLiveStreams();
    },
    { root: null, rootMargin: "300px 0px", threshold: 0.01 }
  );
  return liveFrameVisibilityObserver;
}

function observeLiveFrameImage(image) {
  attachLiveFrameHandlers(image);
  if (image.dataset.liveObserved === "true") return;
  image.dataset.liveObserved = "true";
  image.dataset.liveVisible = "true";
  ensureLiveFrameVisibilityObserver()?.observe(image);
}

function startLiveStream(image) {
  const slot = image.dataset.liveSlot;
  if (!slot) return;
  const backoffUntil = Number(image.dataset.liveErrorUntil || 0);
  if (backoffUntil && Date.now() < backoffUntil) return;
  const url = liveStreamUrl(slot);
  if (image.dataset.liveStreaming === "true" && image.dataset.liveStreamUrl === url) return;
  image.dataset.liveStreaming = "true";
  image.dataset.liveStreamUrl = url;
  // Setting src to the multipart endpoint opens one long-lived MJPEG
  // connection; the browser keeps repainting the <img> as frames arrive.
  image.src = url;
}

function stopLiveStream(image) {
  if (image.dataset.liveStreaming !== "true") return;
  delete image.dataset.liveStreaming;
  delete image.dataset.liveStreamUrl;
  // Dropping src closes the connection so the slot is available again.
  image.removeAttribute("src");
}

function reconcileLiveStreams() {
  if (document.hidden) {
    stopLiveFrameRefresh();
    return;
  }
  const images = Array.from(els.moduleContent.querySelectorAll("img[data-live-frame]"));
  images.forEach(observeLiveFrameImage);
  const visibleImages = images.filter((image) => image.dataset.liveVisible !== "false");
  const streaming = visibleImages.slice(0, MAX_LIVE_STREAMS);
  const streamingSet = new Set(streaming);
  streaming.forEach(startLiveStream);
  images.forEach((image) => {
    if (!streamingSet.has(image)) stopLiveStream(image);
  });
}

function stopLiveFrameRefresh() {
  if (liveFrameTimer !== null) {
    window.clearInterval(liveFrameTimer);
    liveFrameTimer = null;
  }
  if (liveFrameVisibilityObserver) {
    liveFrameVisibilityObserver.disconnect();
    liveFrameVisibilityObserver = null;
  }
  Array.from(els.moduleContent.querySelectorAll("img[data-live-frame]")).forEach(stopLiveStream);
}

function syncLiveFrameRefresh() {
  const hasLiveFrames = Boolean(els.moduleContent.querySelector("img[data-live-frame]"));
  if (document.hidden || !hasLiveFrames) {
    stopLiveFrameRefresh();
    return;
  }
  reconcileLiveStreams();
  if (liveFrameTimer === null) {
    // A light periodic reconcile re-arms streams that errored past their
    // backoff and picks up newly visible tiles even without an observer event.
    liveFrameTimer = window.setInterval(reconcileLiveStreams, LIVE_FRAME_REFRESH_MS);
  }
}

const HEAD_MODULE_IDS = new Set(["overview", "users"]);

const MODULE_OVERRIDES = {
  users: { label: "Company Control", subtitle: "Companies, roles & access" },
};

function moduleLabel(module) {
  return tOrNull(`menu.${module.id}`) || MODULE_OVERRIDES[module.id]?.label || module.label;
}

const permissionLabels = {
  view_dashboard: "View dashboard",
  view_organizations: "View organizations",
  manage_organizations: "Manage organizations",
  view_users: "View users",
  manage_users: "Manage users",
  view_permissions: "View permissions",
  manage_permissions: "Manage permissions",
  view_controllers: "View controllers / NVR",
  configure_cameras: "Configure cameras",
  view_cameras: "View cameras",
  view_live_monitoring: "View live monitoring",
  view_products: "View products",
  manage_products: "Manage products",
  configure_ai: "Configure AI",
  view_counts: "View counts",
  correct_counts: "Correct counts",
  view_alerts: "View alerts",
  manage_alerts: "Manage alerts",
  view_analytics: "View analytics",
  view_reports: "View reports",
  export_reports: "Export reports",
  view_system_health: "View system health",
  configure_system: "Configure system",
  view_audit_logs: "View audit logs",
  manage_integrations: "Manage integrations",
  view_settings: "View settings",
};

async function api(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "X-AI-Role": state.role,
      "X-AI-User-Name": "Dashboard V2 Preview",
      "X-AI-Company": "All Companies",
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.setTimeout(() => els.toast.classList.remove("show"), 2600);
}

const NAV_ICONS = {
  overview: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>`,
  users: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18M5 21V7l7-4 7 4v14M9 9h1M9 13h1M14 9h1M14 13h1M10 21v-4h4v4"/></svg>`,
  settings: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
  camera: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>`,
  camera_info: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M7 20h10M12 18v2M8 8h8M8 12h5"/></svg>`,
  analytics: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 3v18h18"/><path d="M7 15l4-6 4 3 5-8"/></svg>`,
  result_analytics: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/></svg>`,
  feed: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>`,
  ai: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="7" width="16" height="12" rx="2"/><path d="M12 7V4M8 4h8M9 12h.01M15 12h.01M9 16h6"/></svg>`,
  dimension: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.27 6.96 12 12.01l8.73-5.05M12 22.08V12"/></svg>`,
};

function renderNavigation() {
  const modules = (state.session?.surfaces?.head || []).filter((module) =>
    HEAD_MODULE_IDS.has(module.id)
  );
  const known =
    state.activeModule === "settings" || modules.some((module) => module.id === state.activeModule);
  if (!state.activeModule || !known) {
    state.activeModule = modules[0]?.id || "settings";
  }
  const buttons = modules.map(
    (module) => `
      <button class="${module.id === state.activeModule ? "active" : ""}" data-module="${module.id}" type="button">
        ${NAV_ICONS[module.id] || ""}
        <span>${escapeHtml(moduleLabel(module))}</span>
      </button>
    `
  );
  buttons.push(`
    <button class="${state.activeModule === "settings" ? "active" : ""}" data-module="settings" type="button">
      ${NAV_ICONS.settings}
      <span>${escapeHtml(t("settings.title"))}</span>
    </button>
  `);
  els.moduleNav.innerHTML = buttons.join("");
}

const PENCIL_SVG = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>`;

function renderSideCompaniesFromCache() {
  const companies = ccCompaniesCache || [];
  els.sideCompanies.innerHTML = companies.length
    ? companies
        .map(
          (company) => `
            <li>
              <span>${escapeHtml(company.name)}</span>
              <button type="button" data-edit-company="${company.id}" aria-label="Edit ${escapeHtml(company.name)}">${PENCIL_SVG}</button>
            </li>
          `
        )
        .join("")
    : `<li class="side-empty">${escapeHtml(t("side.no_companies"))}</li>`;
}

async function renderSideCompanies() {
  try {
    await ensureCompaniesLoaded();
  } catch {
    // Best effort — Company Control will surface the real error if opened.
  }
  renderSideCompaniesFromCache();
}

const STAT_ICONS = {
  "Active cameras": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>`,
  "Frames read": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="2" width="20" height="20" rx="2.2"/><path d="M7 2v20M17 2v20M2 12h20M2 7h5M2 17h5M17 17h5M17 7h5"/></svg>`,
  "Last detections": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 0 1 0 8.49M7.76 16.24a6 6 0 0 1 0-8.49M19.07 4.93a10 10 0 0 1 0 14.14M4.93 19.07a10 10 0 0 1 0-14.14"/></svg>`,
  "Stock items": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.27 6.96 12 12.01l8.73-5.05M12 22.08V12"/></svg>`,
  "Saved cameras": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>`,
  "Audit verified": `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>`,
};

function renderSummary() {
  const summary = state.overview?.summary || {};
  const cards = [
    ["Active cameras", "summary.active_cameras", summary.active_cameras ?? 0],
    ["Frames read", "summary.frames_read", summary.frames_read ?? 0],
    ["Last detections", "summary.last_detections", summary.last_detection_count ?? 0],
    ["Stock items", "summary.stock_items", summary.stock_items ?? 0],
    ["Saved cameras", "summary.saved_cameras", summary.saved_cameras ?? 0],
    ["Audit verified", "summary.audit_verified", summary.audit_verified ? t("summary.yes") : t("summary.no")],
  ];
  const deltas = {
    "Active cameras": { key: "summary.delta_cameras", dir: "up" },
    "Frames read": { key: "summary.delta_no_change", dir: "flat" },
    "Last detections": { key: "summary.delta_detections", dir: "down" },
    "Stock items": { key: "summary.delta_no_change", dir: "flat" },
    "Saved cameras": { key: "summary.delta_saved", dir: "up" },
    "Audit verified": { key: "summary.delta_normal", dir: "up" },
  };
  els.summaryGrid.innerHTML = cards
    .map(([iconKey, labelKey, value]) => {
      const delta = deltas[iconKey];
      return `
        <article class="stat-card">
          <div class="stat-icon">${STAT_ICONS[iconKey] || ""}</div>
          <div class="stat-body">
            <span>${escapeHtml(t(labelKey))}</span>
            <strong>${escapeHtml(value)}</strong>
            ${delta ? `<em class="stat-delta ${delta.dir}">${escapeHtml(t(delta.key))}</em>` : ""}
          </div>
        </article>
      `;
    })
    .join("");
  const running = Boolean(summary.detector_running);
  els.detectorState.textContent = running ? t("status.detector_running") : t("status.detector_stopped");
  els.detectorState.dataset.state = running ? "good" : "bad";
}

function renderScope() {
  const session = state.session;
  if (!session) return;
  const scope = session.scope || {};
  els.scopeLine.textContent = `${session.role_label} • ${scope.company} / ${scope.factory} / ${scope.warehouse}`;
}

function renderModuleContent() {
  if (state.activeModule === "settings") {
    els.activeModuleTitle.textContent = t("settings.title");
    els.activeModuleEyebrow.textContent = t("head.module");
    els.summaryGrid.hidden = true;
    renderSettings(els.moduleContent);
    return;
  }
  const modules = state.session?.surfaces?.head || [];
  const module = modules.find((item) => item.id === state.activeModule);
  els.activeModuleTitle.textContent = module ? moduleLabel(module) : t("head.unavailable");
  els.activeModuleEyebrow.textContent = t("head.module");
  els.summaryGrid.hidden = module?.id === "users";

  const summary = state.overview?.summary || {};
  const movements = state.overview?.recent_movements || [];
  const health = state.overview?.health || {};

  if (!module) {
    els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(t("head.no_access"))}</p>`;
    return;
  }

  if (module.id === "live") {
    els.moduleContent.innerHTML = `
      <div class="live-preview">
        ${Array.from({ length: Math.min(Number(summary.active_cameras || health.camera_count || 10), 10) }, (_, index) => {
          const slot = index + 1;
          return `<figure><img data-live-frame data-live-slot="${slot}" src="${API_BASE}/api/live_frame?slot=${slot}&v=${Date.now()}" loading="lazy" decoding="async" alt="Camera slot ${slot}" /><figcaption>Slot ${slot}</figcaption></figure>`;
        }).join("")}
      </div>
    `;
    return;
  }

  if (module.id === "counting" || module.id === "home" || module.id === "overview") {
    renderAnalytics(els.moduleContent);
    return;
  }

  if (module.id === "users") {
    renderCompanyControl(els.moduleContent);
    return;
  }

  if (module.id === "activity" || module.id === "reports") {
    els.moduleContent.innerHTML = movements.length
      ? `<table><tbody>${movements
          .map((item) => `<tr><td>${escapeHtml(item.product_name)}</td><td>${escapeHtml(item.direction)}</td><td>${escapeHtml(item.quantity)}</td></tr>`)
          .join("")}</tbody></table>`
      : `<p class="empty">No recent activity is available yet.</p>`;
    return;
  }

  els.moduleContent.innerHTML = `
    <div class="module-placeholder">
      <h3>${escapeHtml(module.label)} is ready for implementation</h3>
      <p>This module is registered in the V2 architecture and protected by <code>${escapeHtml(module.permission)}</code>. It can evolve independently without restructuring the dashboard.</p>
    </div>
  `;
}

// ---- Company Control --------------------------------------------------------
// Companies/roles live in localStorage for now; swap the store helpers for
// backend endpoints later.

// Companies, roles, and accounts are stored on the server (database/accounts_db.py)
// so an account link works from any browser or device, not just the one it was
// created on. `ccCompaniesCache` is a local read cache kept in sync with the API.

const ACCESS_OPTIONS = [
  { key: "camera", label: "Camera Control" },
  { key: "analytics", label: "Analytics" },
];

async function accountsApi(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      detail = (await response.text()) || detail;
    }
    throw new Error(detail || "Request failed.");
  }
  if (response.status === 204) return null;
  return response.json();
}

let ccCompaniesCache = null;
let ccEditingCompany = null;
let ccEditValues = null;
let ccPasswordEditRole = null;

// One-time recovery for companies/roles created before the server-side
// database existed (they were only ever in this browser's localStorage).
// Matches by company name / role login so re-visiting from the same browser
// doesn't create duplicates. Old account links from that era point at ids
// that only existed locally, so they can never resolve — this migration
// gives every recovered role a new, working server-backed link.
const LEGACY_COMPANIES_KEY = "ai_vision_v2_companies";
const LEGACY_MIGRATED_KEY = "ai_vision_v2_companies_migrated_at";
const LEGACY_BACKUP_KEY = "ai_vision_v2_companies_legacy_backup";

async function migrateLegacyLocalStorage() {
  const raw = localStorage.getItem(LEGACY_COMPANIES_KEY);
  if (!raw) return null;
  if (localStorage.getItem(LEGACY_MIGRATED_KEY)) {
    localStorage.removeItem(LEGACY_COMPANIES_KEY);
    return null;
  }

  let legacyCompanies;
  try {
    legacyCompanies = JSON.parse(raw);
  } catch {
    legacyCompanies = null;
  }
  if (!Array.isArray(legacyCompanies) || !legacyCompanies.length) {
    localStorage.removeItem(LEGACY_COMPANIES_KEY);
    return null;
  }

  let existing;
  try {
    existing = await ensureCompaniesLoaded();
  } catch {
    return null; // Server unreachable — leave the key in place and retry next load.
  }

  let companiesCreated = 0;
  let rolesCreated = 0;
  let failures = 0;

  for (const oldCompany of legacyCompanies) {
    const name = String(oldCompany?.name || "").trim();
    if (!name) continue;

    let company = existing.find((item) => item.name.toLowerCase() === name.toLowerCase());
    if (!company) {
      try {
        company = await accountsApi("/api/v2/companies", { method: "POST", body: JSON.stringify({ name }) });
        existing.push(company);
        companiesCreated += 1;
      } catch {
        failures += 1;
        continue;
      }
    }
    company.roles = company.roles || [];

    const oldCameraConfig = oldCompany?.cameraConfig;
    if (oldCameraConfig?.nvrs?.length && !company.cameraConfig?.nvrs?.length) {
      try {
        company.cameraConfig = await accountsApi(`/api/v2/companies/${company.id}/camera-config`, {
          method: "PUT",
          body: JSON.stringify({ cameraConfig: oldCameraConfig }),
        }).then(() => oldCameraConfig);
      } catch {
        // Non-fatal — camera setup can be redone from Company Control.
      }
    }

    for (const oldRole of oldCompany?.roles || []) {
      const roleName = String(oldRole?.name || "").trim();
      const login = String(oldRole?.login || "").trim();
      if (!roleName || !login) continue;
      if (company.roles.some((role) => role.login.toLowerCase() === login.toLowerCase())) continue;

      try {
        const role = await accountsApi(`/api/v2/companies/${company.id}/roles`, {
          method: "POST",
          body: JSON.stringify({
            name: roleName,
            login,
            password: oldRole.password || Math.random().toString(36).slice(2, 12),
            access_camera: Boolean(oldRole.access?.camera),
            access_analytics: Boolean(oldRole.access?.analytics),
          }),
        });
        company.roles.push(role);
        rolesCreated += 1;
      } catch {
        failures += 1;
      }
    }
  }

  localStorage.setItem(LEGACY_MIGRATED_KEY, new Date().toISOString());
  localStorage.setItem(LEGACY_BACKUP_KEY, raw);
  localStorage.removeItem(LEGACY_COMPANIES_KEY);

  return { companiesCreated, rolesCreated, failures };
}

async function ensureCompaniesLoaded() {
  if (ccCompaniesCache) return ccCompaniesCache;
  const payload = await accountsApi("/api/v2/companies");
  ccCompaniesCache = payload.companies || [];
  return ccCompaniesCache;
}

function ccCompanyById(id) {
  return (ccCompaniesCache || []).find((company) => company.id === id);
}

function refreshCompanyUI() {
  renderSideCompaniesFromCache();
  if (state.activeModule === "users") renderCompanyControl(els.moduleContent);
}

function accountLink(role) {
  return `${window.location.origin}/dashboard-v2#acc=${role.id}`;
}

function renderRoleView(role) {
  const changingPassword = ccPasswordEditRole === role.id;
  const passwordForm = changingPassword
    ? `
      <form class="cc-add" data-cc-form="password" data-role="${role.id}">
        <input name="password" type="password" placeholder="New password" required maxlength="120" autocomplete="new-password" />
        <button type="submit">Set password</button>
      </form>
    `
    : "";
  const link = accountLink(role);
  return `
    <div class="cc-credentials">
      <span class="cc-cred"><em>Login:</em> ${escapeHtml(role.login)}</span>
      <span class="cc-cred"><em>Password:</em> •••••••• (hashed on the server)</span>
      <button type="button" class="cc-chip cc-chip-small" data-cc-action="toggle-password-edit" data-role="${role.id}">
        ${changingPassword ? "Cancel" : "Change password"}
      </button>
    </div>
    ${passwordForm}
    <div class="cc-link">
      <a href="${escapeHtml(link)}" title="${escapeHtml(link)}">${escapeHtml(link)}</a>
      <button type="button" class="cc-chip cc-chip-small" data-cc-action="copy-link" data-link="${escapeHtml(link)}">Copy</button>
    </div>
  `;
}

function renderRoleEdit(role) {
  const edited = ccEditValues?.roles?.[role.id] || { name: role.name, login: role.login };
  return `
    <div class="cc-edit-grid">
      <input data-cc-edit="role-name" data-role="${role.id}" value="${escapeHtml(edited.name)}" placeholder="Role name" maxlength="60" />
      <input data-cc-edit="role-login" data-role="${role.id}" value="${escapeHtml(edited.login)}" placeholder="Username (login)" maxlength="60" />
    </div>
  `;
}

function renderCompanyControl(container) {
  if (!ccCompaniesCache) {
    container.innerHTML = `<p class="chart-note">Loading companies…</p>`;
    ensureCompaniesLoaded()
      .then(() => {
        if (state.activeModule === "users") renderCompanyControl(els.moduleContent);
      })
      .catch((error) => {
        if (state.activeModule === "users") {
          els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
        }
      });
    return;
  }

  const companyCards = ccCompaniesCache
    .map((company) => {
      const editing = company.id === ccEditingCompany;
      const roles = (company.roles || [])
        .map(
          (role) => `
            <div class="cc-role">
              <div class="cc-role-head">
                ${editing ? "" : `<strong>${escapeHtml(role.name)}</strong>`}
                <button type="button" class="cc-remove" data-cc-action="remove-role"
                        data-company="${company.id}" data-role="${role.id}" aria-label="Remove role">✕</button>
              </div>
              ${editing ? renderRoleEdit(role) : renderRoleView(role)}
              <div class="cc-access">
                <span>Give access:</span>
                ${ACCESS_OPTIONS.map(
                  (option) => `
                    <button type="button" class="cc-chip ${role.access?.[option.key] ? "on" : ""}"
                            data-cc-action="toggle-access" data-company="${company.id}"
                            data-role="${role.id}" data-access="${option.key}"
                            aria-pressed="${Boolean(role.access?.[option.key])}">
                      ${option.label}
                    </button>
                  `
                ).join("")}
              </div>
            </div>
          `
        )
        .join("");

      const heading = editing
        ? `<input class="cc-name-input" data-cc-edit="company-name" value="${escapeHtml(ccEditValues?.companyName ?? company.name)}" maxlength="60" aria-label="Company name" />`
        : `<h3>${escapeHtml(company.name)}</h3>`;
      const editActions = editing
        ? `
          <button type="button" class="cc-chip cc-chip-small on" data-cc-action="save-edit">Save</button>
          <button type="button" class="cc-chip cc-chip-small" data-cc-action="cancel-edit">Cancel</button>
        `
        : `<button type="button" class="cc-remove" data-cc-action="edit-company" data-company="${company.id}" aria-label="Edit ${escapeHtml(company.name)}">${PENCIL_SVG}</button>`;

      return `
        <article class="cc-company ${editing ? "editing" : ""}" data-company-card="${company.id}">
          <header class="cc-company-head">
            ${heading}
            <div class="cc-head-actions">
              ${editActions}
              <button type="button" class="cc-remove" data-cc-action="remove-company"
                      data-company="${company.id}" aria-label="Remove company">✕</button>
            </div>
          </header>
          ${roles || `<p class="empty">No roles yet.</p>`}
          <form class="cc-add cc-add-role" data-cc-form="role" data-company="${company.id}" novalidate>
            <input name="name" placeholder="Role name" required maxlength="60" autocomplete="off" />
            <input name="login" placeholder="Username (login)" required maxlength="60" autocomplete="off" />
            <input name="password" type="password" placeholder="Password" required maxlength="120" autocomplete="new-password" />
            <button type="submit">Add role</button>
          </form>
        </article>
      `;
    })
    .join("");

  container.innerHTML = `
    <p class="chart-note">Companies and accounts are stored on the server — links work on any device.</p>
    <form class="cc-add cc-add-company" data-cc-form="company" novalidate>
      <input name="name" placeholder="Company name" required maxlength="60" autocomplete="off" />
      <button type="submit">Add company</button>
    </form>
    <div class="cc-list">
      ${companyCards || `<p class="empty">No companies yet — add the first one above.</p>`}
    </div>
  `;
}

function handleCompanyInput(event) {
  const input = event.target.closest("[data-cc-edit]");
  if (!input || !ccEditValues) return;
  const field = input.dataset.ccEdit;
  if (field === "company-name") {
    ccEditValues.companyName = input.value;
  } else if (field === "role-name") {
    ccEditValues.roles[input.dataset.role] = { ...ccEditValues.roles[input.dataset.role], name: input.value };
  } else if (field === "role-login") {
    ccEditValues.roles[input.dataset.role] = { ...ccEditValues.roles[input.dataset.role], login: input.value };
  }
}

async function handleCompanySubmit(event) {
  const form = event.target.closest("[data-cc-form]");
  if (!form) return;
  event.preventDefault();
  const kind = form.dataset.ccForm;

  if (kind === "company") {
    const name = form.elements.name.value.trim();
    if (!name) {
      toast("Enter a company name.");
      form.elements.name.focus();
      return;
    }
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const company = await accountsApi("/api/v2/companies", { method: "POST", body: JSON.stringify({ name }) });
      ccCompaniesCache = [...(ccCompaniesCache || []), company];
      toast(`Company "${name}" added.`);
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
      submit.disabled = false;
    }
    return;
  }

  if (kind === "role") {
    const company = ccCompanyById(form.dataset.company);
    if (!company) return;
    const name = form.elements.name.value.trim();
    const login = form.elements.login.value.trim();
    const password = form.elements.password.value;
    if (!name || !login || !password) {
      toast("Enter a role name, login, and password.");
      (form.elements.name.value.trim() ? form.elements.login.value.trim() ? form.elements.password : form.elements.login : form.elements.name).focus();
      return;
    }
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const role = await accountsApi(`/api/v2/companies/${company.id}/roles`, {
        method: "POST",
        body: JSON.stringify({ name, login, password, access_camera: false, access_analytics: false }),
      });
      company.roles = [...(company.roles || []), role];
      toast(`"${name}" added — account link: ${accountLink(role)}`);
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
      submit.disabled = false;
    }
    return;
  }

  if (kind === "password") {
    const roleId = form.dataset.role;
    const password = form.elements.password.value;
    if (!password) return;
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      await accountsApi(`/api/v2/roles/${roleId}`, { method: "PUT", body: JSON.stringify({ password }) });
      ccPasswordEditRole = null;
      toast("Password updated.");
      renderCompanyControl(els.moduleContent);
    } catch (error) {
      toast(error.message);
      submit.disabled = false;
    }
  }
}

async function handleCompanyClick(event) {
  const button = event.target.closest("[data-cc-action]");
  if (!button) return;
  const action = button.dataset.ccAction;

  if (action === "copy-link") {
    navigator.clipboard?.writeText(button.dataset.link).then(
      () => toast("Account link copied."),
      () => toast("Could not copy — select the link manually.")
    );
    return;
  }

  if (action === "toggle-password-edit") {
    ccPasswordEditRole = ccPasswordEditRole === button.dataset.role ? null : button.dataset.role;
    renderCompanyControl(els.moduleContent);
    return;
  }

  if (action === "edit-company") {
    const company = ccCompanyById(button.dataset.company);
    if (!company) return;
    ccEditingCompany = company.id;
    ccEditValues = {
      companyName: company.name,
      roles: Object.fromEntries((company.roles || []).map((role) => [role.id, { name: role.name, login: role.login }])),
    };
    renderCompanyControl(els.moduleContent);
    return;
  }

  if (action === "cancel-edit") {
    ccEditingCompany = null;
    ccEditValues = null;
    renderCompanyControl(els.moduleContent);
    return;
  }

  if (action === "save-edit") {
    const company = ccCompanyById(ccEditingCompany);
    if (!company || !ccEditValues) return;
    button.disabled = true;
    try {
      if (ccEditValues.companyName !== company.name) {
        const updated = await accountsApi(`/api/v2/companies/${company.id}`, {
          method: "PUT",
          body: JSON.stringify({ name: ccEditValues.companyName }),
        });
        company.name = updated.name;
      }
      for (const role of company.roles || []) {
        const edited = ccEditValues.roles[role.id];
        if (!edited || (edited.name === role.name && edited.login === role.login)) continue;
        const updated = await accountsApi(`/api/v2/roles/${role.id}`, {
          method: "PUT",
          body: JSON.stringify({ name: edited.name, login: edited.login }),
        });
        role.name = updated.name;
        role.login = updated.login;
      }
      ccEditingCompany = null;
      ccEditValues = null;
      toast("Changes saved.");
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
      button.disabled = false;
    }
    return;
  }

  const company = ccCompanyById(button.dataset.company);
  if (!company) return;

  if (action === "remove-company") {
    if (!window.confirm(`Remove "${company.name}" and all of its roles? This cannot be undone.`)) return;
    try {
      await accountsApi(`/api/v2/companies/${company.id}`, { method: "DELETE" });
      ccCompaniesCache = ccCompaniesCache.filter((item) => item.id !== company.id);
      if (ccEditingCompany === company.id) {
        ccEditingCompany = null;
        ccEditValues = null;
      }
      toast(`"${company.name}" removed.`);
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
    }
    return;
  }

  if (action === "remove-role") {
    const role = (company.roles || []).find((item) => item.id === button.dataset.role);
    if (!role) return;
    if (!window.confirm(`Remove the "${role.name}" account? Its link will stop working.`)) return;
    try {
      await accountsApi(`/api/v2/roles/${role.id}`, { method: "DELETE" });
      company.roles = company.roles.filter((item) => item.id !== role.id);
      toast(`"${role.name}" removed.`);
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
    }
    return;
  }

  if (action === "toggle-access") {
    const role = (company.roles || []).find((item) => item.id === button.dataset.role);
    if (!role) return;
    const key = button.dataset.access;
    const nextValue = !role.access?.[key];
    button.disabled = true;
    try {
      const field = key === "camera" ? "access_camera" : "access_analytics";
      const updated = await accountsApi(`/api/v2/roles/${role.id}`, {
        method: "PUT",
        body: JSON.stringify({ [field]: nextValue }),
      });
      role.access = updated.access;
      refreshCompanyUI();
    } catch (error) {
      toast(error.message);
      button.disabled = false;
    }
  }
}

// ---- Settings (profile & security) ------------------------------------------
// Stored on the server (single admin profile row) so it follows you across devices.

let ccProfileCache = null;

async function ensureProfileLoaded() {
  if (ccProfileCache) return ccProfileCache;
  ccProfileCache = await accountsApi("/api/v2/admin/profile");
  return ccProfileCache;
}

function updateBrandAvatarFromCache() {
  const profile = ccProfileCache || { login: "admin", avatar: null };
  if (profile.avatar) {
    els.brandAvatar.src = profile.avatar;
    els.brandAvatar.hidden = false;
  } else {
    els.brandAvatar.hidden = true;
    els.brandAvatar.removeAttribute("src");
  }
  renderHeaderProfile();
}

async function updateBrandAvatar() {
  try {
    await ensureProfileLoaded();
  } catch {
    // Best effort — the header falls back to the "admin" placeholder.
  }
  updateBrandAvatarFromCache();
}

function renderHeaderProfile(name) {
  const profile = ccProfileCache || { login: "admin", avatar: null };
  const label = name || profile.login || "admin";
  const initial = label.slice(0, 1).toUpperCase();
  const avatar =
    !name && profile.avatar
      ? `<img src="${profile.avatar}" alt="" />`
      : `<span class="hp-initial">${escapeHtml(initial)}</span>`;
  els.headerProfile.innerHTML = `${avatar}<span class="hp-name">${escapeHtml(label)}</span>`;
  if (!name) renderSideProfile();
}

function renderSideProfile(login, subtitle) {
  const profile = ccProfileCache || { login: "admin", avatar: null };
  const label = login || profile.login || "admin";
  const sub = subtitle || t("profile.super_admin");
  const avatar =
    !login && profile.avatar
      ? `<img src="${profile.avatar}" alt="" />`
      : `<span class="hp-initial">${escapeHtml(label.slice(0, 1).toUpperCase())}</span>`;
  els.sideProfile.innerHTML = `${avatar}<div class="side-profile-text"><strong>${escapeHtml(label)}</strong><small>${escapeHtml(sub)}</small></div>`;
}

function renderSettings(container) {
  if (!ccProfileCache) {
    container.innerHTML = `<p class="chart-note">${escapeHtml(t("settings.loading_profile"))}</p>`;
    ensureProfileLoaded()
      .then(() => {
        if (state.activeModule === "settings") renderSettings(els.moduleContent);
      })
      .catch((error) => {
        if (state.activeModule === "settings") {
          els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
        }
      });
    return;
  }

  const profile = ccProfileCache;
  container.innerHTML = `
    <p class="chart-note">${escapeHtml(t("settings.server_note"))}</p>
    <div class="settings-grid">
      <section class="cc-company">
        <header class="cc-company-head"><h3>${escapeHtml(t("settings.profile_picture"))}</h3></header>
        <div class="settings-avatar-row">
          ${
            profile.avatar
              ? `<img class="settings-avatar" src="${profile.avatar}" alt="Profile picture" />`
              : `<div class="settings-avatar settings-avatar-empty">${escapeHtml((profile.login || "A").slice(0, 1).toUpperCase())}</div>`
          }
          <div class="settings-avatar-actions">
            <label class="cc-chip settings-upload">
              ${escapeHtml(t("settings.upload_picture"))}
              <input id="avatarInput" type="file" accept="image/*" hidden />
            </label>
            ${profile.avatar ? `<button type="button" class="cc-chip cc-chip-small" data-settings-action="remove-avatar">${escapeHtml(t("settings.remove"))}</button>` : ""}
          </div>
        </div>
      </section>
      <section class="cc-company">
        <header class="cc-company-head"><h3>${escapeHtml(t("settings.login_password"))}</h3></header>
        <p class="cc-cred"><em>${escapeHtml(t("settings.current_login"))}</em> ${escapeHtml(profile.login)}</p>
        <form class="cc-add cc-add-role" data-settings-form="security">
          <input name="login" placeholder="${escapeAttr(t("settings.new_login"))}" value="${escapeHtml(profile.login)}" required maxlength="60" autocomplete="username" />
          <input name="password" type="password" placeholder="${escapeAttr(t("settings.new_password"))}" required maxlength="120" autocomplete="new-password" />
          <input name="confirm" type="password" placeholder="${escapeAttr(t("settings.confirm_password"))}" required maxlength="120" autocomplete="new-password" />
          <button type="submit">${escapeHtml(t("settings.update_credentials"))}</button>
        </form>
      </section>
    </div>
  `;
}

async function handleSettingsSubmit(event) {
  const form = event.target.closest("[data-settings-form]");
  if (!form) return;
  event.preventDefault();
  const login = form.elements.login.value.trim();
  const password = form.elements.password.value;
  const confirm = form.elements.confirm.value;
  if (!login || !password) return;
  if (password !== confirm) {
    toast(t("settings.passwords_mismatch"));
    return;
  }
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    ccProfileCache = await accountsApi("/api/v2/admin/profile", {
      method: "PUT",
      body: JSON.stringify({ login, password }),
    });
    toast(t("settings.credentials_updated"));
    updateBrandAvatarFromCache();
    renderSettings(els.moduleContent);
  } catch (error) {
    toast(error.message);
    submit.disabled = false;
  }
}

async function handleSettingsChange(event) {
  if (event.target.id !== "avatarInput") return;
  const file = event.target.files?.[0];
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) {
    toast(t("settings.picture_too_large"));
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      ccProfileCache = await accountsApi("/api/v2/admin/profile", {
        method: "PUT",
        body: JSON.stringify({ avatar: String(reader.result) }),
      });
      toast(t("settings.picture_updated"));
      updateBrandAvatarFromCache();
      renderSettings(els.moduleContent);
    } catch (error) {
      toast(error.message);
    }
  };
  reader.readAsDataURL(file);
}

async function handleSettingsClick(event) {
  const button = event.target.closest("[data-settings-action]");
  if (!button) return;
  if (button.dataset.settingsAction === "remove-avatar") {
    try {
      ccProfileCache = await accountsApi("/api/v2/admin/profile", {
        method: "PUT",
        body: JSON.stringify({ remove_avatar: true }),
      });
      updateBrandAvatarFromCache();
      renderSettings(els.moduleContent);
    } catch (error) {
      toast(error.message);
    }
  }
}

// ---- User dashboard (account links) -----------------------------------------

async function resolveAccountFromHash() {
  const match = window.location.hash.match(/acc=([a-z0-9]+)/i);
  if (!match) return null;
  try {
    const response = await fetch(`${API_BASE}/api/v2/accounts/${encodeURIComponent(match[1])}`);
    if (response.status === 404) {
      return { company: null, role: null, missing: true, error: null };
    }
    if (!response.ok) {
      throw new Error(`Account lookup failed (${response.status}).`);
    }
    const payload = await response.json();
    return { company: payload.company, role: payload.role, missing: false, error: null };
  } catch (error) {
    return { company: null, role: null, missing: true, error: error instanceof Error ? error.message : String(error) };
  }
}

function livePreviewHtml(summary, health) {
  const slots = Math.min(Number(summary.active_cameras || health.camera_count || 4), 10);
  return `
    <div class="live-preview">
      ${Array.from({ length: slots }, (_, index) => {
        const slot = index + 1;
        return `<figure><img data-live-frame data-live-slot="${slot}" src="${API_BASE}/api/live_frame?slot=${slot}&v=${Date.now()}" loading="lazy" decoding="async" alt="Camera slot ${slot}" /><figcaption>Slot ${slot}</figcaption></figure>`;
      }).join("")}
    </div>
  `;
}

const MAX_NVRS = 5;
const MAX_NVR_SLOTS = 100;
let accountState = null;
let accountModule = null;

function newId() {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}

const QUALITY_OPTIONS = [
  { id: "low", label: "Low · 480p", hint: "fastest serving" },
  { id: "medium", label: "Medium · 720p", hint: "balanced" },
  { id: "high", label: "High · 1080p", hint: "best picture" },
];
const FEED_GROUP_SIZE = 8;
const FEED_GROUP_LETTERS_EN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
const FEED_GROUP_LETTERS_RU = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЭЮЯ".split("");

function companyConfig(company) {
  if (!company.cameraConfig) company.cameraConfig = { nvrs: [], quality: "high" };
  if (!company.cameraConfig.nvrs) company.cameraConfig.nvrs = [];
  if (!company.cameraConfig.feedGroups || Array.isArray(company.cameraConfig.feedGroups)) {
    company.cameraConfig.feedGroups = {};
  }
  return company;
}

async function persistAccountCompany() {
  const { company } = accountState;
  const updated = await accountsApi(`/api/v2/companies/${company.id}/camera-config`, {
    method: "PUT",
    body: JSON.stringify({ cameraConfig: company.cameraConfig }),
  });
  company.cameraConfig = updated.cameraConfig;
}

function feedGroupLetter(index) {
  const letters = currentLanguage() === "ru" ? FEED_GROUP_LETTERS_RU : FEED_GROUP_LETTERS_EN;
  return letters[index] || String(index + 1);
}

function feedDefaultGroupName(index) {
  return t("feed.default_group", { letter: feedGroupLetter(index) });
}

function feedGroupId(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9а-яё]+/gi, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "group";
}

function feedGroupFromText(value) {
  const text = String(value || "");
  const block = text.match(/(?:\bblock\b|\bblok\b|блок)\s*([a-zа-яё0-9]+)/i);
  if (block) {
    const letter = String(block[1] || "").toUpperCase();
    return { id: `named-block-${feedGroupId(letter)}`, name: t("feed.default_group", { letter }) };
  }
  const room = text.match(/(?:\broom\b|\bzone\b|комната|зона)\s*([a-zа-яё0-9]+)/i);
  if (room) {
    const name = room[0].trim();
    return { id: `named-room-${feedGroupId(name)}`, name };
  }
  return null;
}

function inferFeedGroup(nvr, nvrIndex, channel, channelIndex, nvrCount) {
  const nameText = `${nvr.name || ""} ${channel?.name || channel?.camera_name || channel?.message || ""}`;
  const named = feedGroupFromText(nameText);
  if (named) return named;
  const groupIndex = nvrCount > 1 ? nvrIndex : Math.floor(channelIndex / FEED_GROUP_SIZE);
  const idPrefix = nvrCount > 1 ? `nvr-${nvr.id || nvrIndex}` : "block";
  return { id: `auto-${idPrefix}-${groupIndex}`, name: feedDefaultGroupName(groupIndex) };
}

function renderFeedTile(nvr, channel) {
  if (!channel) {
    return `<figure class="feed-empty"><div>${escapeHtml(t("feed.readd"))}</div><figcaption>${escapeHtml(nvr.name)}</figcaption></figure>`;
  }
  if (channel.active && channel.slot_number != null) {
    return `<figure><span class="feed-transmitting feed-stale-badge">${escapeHtml(t("status.waiting_video"))}</span><img class="feed-stale" data-live-frame data-live-slot="${channel.slot_number}" data-live-priming="true" src="${liveFrameUrl(channel.slot_number)}" loading="lazy" decoding="async" alt="${escapeHtml(nvr.name)} channel ${channel.channel}" title="${escapeHtml(t("status.waiting_fresh_frame"))}" /><figcaption>${escapeHtml(nvr.name)} · ${escapeHtml(t("table.channel"))} ${channel.channel}</figcaption></figure>`;
  }
  return `<figure class="feed-empty"><div>${escapeHtml(channel.message || t("feed.no_signal"))}</div><figcaption>${escapeHtml(nvr.name)} · ${escapeHtml(t("table.channel"))} ${channel.channel}</figcaption></figure>`;
}

function feedGroups(config) {
  const groups = new Map();
  const nvrs = config.nvrs || [];
  nvrs.forEach((nvr, nvrIndex) => {
    const channels = nvr.channelsDetail || [];
    const sourceChannels = channels.length ? channels : [null];
    sourceChannels.forEach((channel, channelIndex) => {
      const channelNumber = Number(channel?.channel);
      const normalizedIndex = Number.isFinite(channelNumber) && channelNumber > 0 ? channelNumber - 1 : channelIndex;
      const meta = inferFeedGroup(nvr, nvrIndex, channel, normalizedIndex, nvrs.length);
      const name = config.feedGroups[meta.id] || meta.name;
      if (!groups.has(meta.id)) {
        groups.set(meta.id, { id: meta.id, name, tiles: [], cameraCount: 0 });
      }
      const group = groups.get(meta.id);
      group.tiles.push(renderFeedTile(nvr, channel));
      group.cameraCount += channel ? 1 : 0;
    });
  });
  return Array.from(groups.values());
}

function feedGroupsHtml(config) {
  return feedGroups(config)
    .map(
      (group) => `
        <section class="acc-block feed-group" data-feed-group="${escapeAttr(group.id)}">
          <header class="feed-group-head">
            <form class="feed-group-form" data-acc-form="feed-group" data-feed-group-id="${escapeAttr(group.id)}">
              <input name="name" value="${escapeAttr(group.name)}" maxlength="80" aria-label="${escapeAttr(t("feed.group_name"))}" />
              <button type="submit" class="cc-chip cc-chip-small">${escapeHtml(t("feed.group_save"))}</button>
            </form>
            <span>${escapeHtml(t("feed.group_cameras", { count: group.cameraCount.toLocaleString() }))}</span>
          </header>
          <div class="live-preview">${group.tiles.join("")}</div>
        </section>
      `
    )
    .join("");
}

function parseNvrConnectionInput(raw) {
  const value = raw.trim();
  const result = { host: value, port: null, username: null, password: null, path: null };
  if (!value) return result;

  if (value.includes("://")) {
    try {
      const url = new URL(value);
      result.host = url.hostname || value;
      if (url.port) result.port = Number(url.port);
      if (url.username) result.username = decodeURIComponent(url.username);
      if (url.password) result.password = decodeURIComponent(url.password);
      if (url.pathname && url.pathname !== "/") result.path = url.pathname;
      return result;
    } catch {
      return result;
    }
  }

  const hostPortMatch = value.match(/^([^:/]+):(\d{1,5})$/);
  if (hostPortMatch) {
    result.host = hostPortMatch[1];
    result.port = Number(hostPortMatch[2]);
  }
  return result;
}

async function nextAvailableCameraSlot() {
  const { cameras } = await accountsApi("/api/cameras");
  const usedSlots = (cameras || [])
    .filter((camera) => camera.is_active && camera.slot_number != null)
    .map((camera) => Number(camera.slot_number));
  // Must stay within [1, MAX_NVR_SLOTS] - the backend's start_slot field
  // rejects anything higher with a 422, even though it's perfectly able to
  // register channels beyond the free-slot budget as inactive instead of
  // failing the whole request (see _register_controller_channels). Without
  // this clamp, once every slot up to MAX_NVR_SLOTS is in use, adding any
  // new NVR fails outright instead of falling back to that behavior.
  for (let slot = 1; slot <= MAX_NVR_SLOTS; slot += 1) {
    if (!usedSlots.includes(slot)) return slot;
  }
  return MAX_NVR_SLOTS;
}

async function registerNvrController(fields) {
  const startSlot = await nextAvailableCameraSlot();
  const payload = {
    name: fields.name,
    host: fields.host,
    protocol: fields.protocol,
    channel_count: fields.channels,
    channel_start: 1,
    start_slot: startSlot,
    make_active: true,
    test_controller: true,
    test_streams: false,
  };
  if (fields.port) payload.port = fields.port;
  if (fields.username) payload.username = fields.username;
  if (fields.password) payload.password = fields.password;
  if (fields.streamPath) payload.stream_path_template = fields.streamPath;

  const response = await accountsApi("/api/camera-controller", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  return {
    port: response.controller.port,
    controllerMessage: response.controller.public_reachability_warning || response.controller.message,
    channelsDetail: response.results.map((result) => ({
      camera_id: result.camera_id,
      channel: result.channel,
      slot_number: result.slot_number,
      status: result.status,
      message: result.message,
      active: result.active,
    })),
  };
}

async function deleteNvrCameras(nvr) {
  const channels = nvr.channelsDetail || [];
  await Promise.all(
    channels.map((channel) =>
      accountsApi(`/api/cameras/${channel.camera_id}`, { method: "DELETE" }).catch(() => null)
    )
  );
}

function accountMenus(role) {
  const menus = [];
  if (role.access?.camera) menus.push({ id: "camera", label: "Camera Control", sub: "NVR & vision quality" });
  if (role.access?.camera) menus.push({ id: "camera_info", label: "Camera Info", sub: "Device models" });
  if (role.access?.analytics) menus.push({ id: "analytics", label: "Analytics", sub: "Charts & trends" });
  if (role.access?.analytics) menus.push({ id: "result_analytics", label: "Result Analytics", sub: "Recognition results" });
  if (role.access?.camera) menus.push({ id: "feed", label: "Camera Feed", sub: "Live slots" });
  menus.push({ id: "ai", label: "AI Check-in", sub: "Products to count" });
  menus.push({ id: "dimension", label: "3D Dimensioning", sub: "Item measurements" });
  return menus;
}

function accountMenuLabel(item) {
  return tOrNull(`menu.${item.id}`) || item.label;
}

function nvrControllerMessage(nvr, assigned, total) {
  const message = String(nvr.controllerMessage || "");
  if (!message || message.includes("transmitting") || message.startsWith("Connected via")) {
    return assigned > 0
      ? t("camera.connected_via", { provider: nvr.provider || "stream manager", assigned, total })
      : t("camera.registered_no_slots");
  }
  return message;
}

function streamStatusBySlot() {
  const streams = state.streams || [];
  return new Map(
    streams
      .filter((stream) => stream.slot_number != null)
      .map((stream) => [Number(stream.slot_number), stream])
  );
}

function cameraInfoDeviceMaps(devices = []) {
  const byId = new Map();
  const byHost = new Map();
  for (const device of devices || []) {
    if (!device) continue;
    if (device.id != null) byId.set(String(device.id), device);
    const host = String(device.host || "").trim().toLowerCase();
    if (host) byHost.set(host, device);
  }
  return { byId, byHost };
}

function cameraInfoChannelRows(config, devices = []) {
  const { byId, byHost } = cameraInfoDeviceMaps(devices);
  const streamsBySlot = streamStatusBySlot();
  return (config.nvrs || []).flatMap((nvr) => {
    const device =
      byId.get(String(nvr.deviceId || "")) ||
      byHost.get(String(nvr.host || "").trim().toLowerCase()) ||
      {};
    const rawChannels = Array.isArray(nvr.channelsDetail) ? nvr.channelsDetail : [];
    const channels = rawChannels.length
      ? rawChannels
      : Array.from({ length: Number(nvr.channels || 0) }, (_, index) => ({
          channel: index + 1,
          slot_number: null,
          status: "registered",
        }));
    const deviceTypeKey = nvr.deviceType || device.device_type || "nvr_or_dvr";
    const vendor = nvr.vendor || device.vendor || nvr.provider || "Unknown vendor";
    const model = nvr.model || device.model || "Unknown model";
    return channels.map((channel, index) => {
      const slotNumber = channel.slot_number != null ? Number(channel.slot_number) : null;
      const stream = slotNumber != null ? streamsBySlot.get(slotNumber) : null;
      const channelNumber = channel.channel || channel.external_channel_id || index + 1;
      const channelStatus = channel.status || "registered";
      const status = slotNumber == null && channelStatus !== "failed" ? "unassigned" : stream?.status || channelStatus;
      return {
        key: `${nvr.id || nvr.host || "nvr"}-${channelNumber}-${slotNumber ?? index}`,
        nvrName: nvr.name || device.name || "NVR",
        host: nvr.host || device.host || "Unknown host",
        vendor,
        model,
        deviceType: DEVICE_TYPE_LABELS[deviceTypeKey] ? t(DEVICE_TYPE_LABELS[deviceTypeKey]) : deviceTypeKey || t("device_type.nvr"),
        cameraName: channel.name || channel.camera_name || `Camera ${channelNumber}`,
        slotNumber,
        status,
        streamProvider: nvr.provider || "stream manager",
        detail:
          stream?.last_error ||
          channel.message ||
          channel.profile ||
          (slotNumber == null ? "Registered, but not assigned to an AI Vision live slot." : ""),
      };
    });
  });
}

function cameraInfoStatusMeta(status) {
  if (status === "online") return { label: t("status.live"), className: "online" };
  if (status === "starting") return { label: t("status.starting"), className: "pending" };
  if (status === "reconnecting") return { label: t("status.reconnecting"), className: "pending" };
  if (status === "offline" || status === "failed") return { label: t("status.offline"), className: "offline" };
  if (status === "unassigned") return { label: t("status.waiting_slot"), className: "pending" };
  if (status === "connected") return { label: t("status.connected"), className: "online" };
  return { label: t("status.registered"), className: "pending" };
}

function renderCameraInfoTable(rows) {
  if (!rows.length) {
    return `<p class="empty">${escapeHtml(t("camera_info.empty"))}</p>`;
  }
  return `
    <div class="detected-table-wrap">
      <table class="detected-table camera-info-table">
        <thead>
          <tr>
            <th>${escapeHtml(t("table.nvr_device"))}</th>
            <th>${escapeHtml(t("table.host"))}</th>
            <th>${escapeHtml(t("table.vendor"))}</th>
            <th>${escapeHtml(t("table.model"))}</th>
            <th>${escapeHtml(t("table.camera"))}</th>
            <th>${escapeHtml(t("table.ai_slot"))}</th>
            <th>${escapeHtml(t("table.status"))}</th>
            <th>${escapeHtml(t("table.stream"))}</th>
          </tr>
        </thead>
        <tbody>
          ${rows
            .map((row) => {
              const status = cameraInfoStatusMeta(row.status);
              return `
                <tr title="${escapeAttr(row.detail)}">
                  <td><strong>${escapeHtml(row.nvrName)}</strong><span class="camera-info-meta">${escapeHtml(row.deviceType)}</span></td>
                  <td>${escapeHtml(row.host)}</td>
                  <td>${escapeHtml(row.vendor)}</td>
                  <td><strong>${escapeHtml(row.model)}</strong></td>
                  <td>${escapeHtml(row.cameraName)}</td>
                  <td>${row.slotNumber != null ? `${escapeHtml(t("table.slot"))} ${row.slotNumber}` : `<span class="camera-info-meta">${escapeHtml(t("table.not_assigned"))}</span>`}</td>
                  <td><span class="camera-info-status ${status.className}">${escapeHtml(status.label)}</span></td>
                  <td>${escapeHtml(row.streamProvider)}</td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function renderCameraInfo(container) {
  const { company } = accountState;
  companyConfig(company);
  try {
    const [devicesPayload, streamsPayload] = await Promise.all([
      accountsApi("/api/v2/devices").catch(() => ({ devices: [] })),
      api("/api/v2/streams/health").catch(() => ({ streams: state.streams || [] })),
    ]);
    if (!container.isConnected || accountModule !== "camera_info") return;
    state.streams = streamsPayload.streams || state.streams || [];
    const rows = cameraInfoChannelRows(company.cameraConfig, devicesPayload.devices || []);
    const modelCount = new Set(rows.map((row) => `${row.vendor}/${row.model}`)).size;
    container.innerHTML = `
      <section class="detected-list camera-info">
        <header class="detected-list-head">
          <div>
            <h3>${escapeHtml(t("camera_info.title"))}</h3>
            <p>${escapeHtml(t("camera_info.header", { cameras: rows.length.toLocaleString(), devices: company.cameraConfig.nvrs.length.toLocaleString() }))}</p>
          </div>
          <div class="detected-list-actions">
            <button type="button" class="export-button" data-refresh-camera-info>${escapeHtml(t("actions.refresh"))}</button>
          </div>
        </header>
        <div class="camera-info-summary">
          <article><span>${escapeHtml(t("camera_info.nvr_devices"))}</span><strong>${company.cameraConfig.nvrs.length.toLocaleString()}</strong></article>
          <article><span>${escapeHtml(t("table.camera"))}</span><strong>${rows.length.toLocaleString()}</strong></article>
          <article><span>${escapeHtml(t("camera_info.models"))}</span><strong>${modelCount.toLocaleString()}</strong></article>
        </div>
        ${renderCameraInfoTable(rows)}
      </section>
    `;
    container.querySelector("[data-refresh-camera-info]")?.addEventListener("click", () => {
      container.innerHTML = `<p class="empty">${escapeHtml(t("camera_info.loading"))}</p>`;
      void renderCameraInfo(container);
    });
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function dimBoxSvg({ w, h, d }) {
  const stroke = currentTheme() === "dark" ? "#38bdf8" : "#2563eb";
  const rgb = currentTheme() === "dark" ? "56,189,248" : "37,99,235";
  const scale = 1.6;
  const bw = Math.max(30, w * scale);
  const bh = Math.max(24, h * scale);
  const bd = Math.max(16, d * scale * 0.5);
  const x = 64;
  const y = 20 + bd;
  const width = x + bw + bd + 60;
  const height = y + bh + 34;
  return `
    <svg viewBox="0 0 ${width} ${height}" class="dim-svg" role="img" aria-label="3D box ${w} by ${h} by ${d} centimeters">
      <path d="M ${x} ${y} l ${bd} ${-bd} h ${bw} l ${-bd} ${bd} Z" fill="rgba(${rgb},0.14)" stroke="${stroke}" stroke-width="1.5" />
      <rect x="${x}" y="${y}" width="${bw}" height="${bh}" fill="rgba(${rgb},0.06)" stroke="${stroke}" stroke-width="1.5" />
      <path d="M ${x + bw} ${y} l ${bd} ${-bd} v ${bh} l ${-bd} ${bd} Z" fill="rgba(${rgb},0.10)" stroke="${stroke}" stroke-width="1.5" />
      <text x="${x + bw / 2}" y="${y + bh + 18}" class="dim-label" text-anchor="middle">W ${w} cm</text>
      <text x="${x - 8}" y="${y + bh / 2}" class="dim-label" text-anchor="end">H ${h} cm</text>
      <text x="${x + bw + bd / 2 + 6}" y="${y - bd / 2}" class="dim-label">D ${d} cm</text>
    </svg>
  `;
}

function catalogScopeId() {
  return accountState?.company?.id || "default";
}

function catalogApiPath(path) {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}scope_id=${encodeURIComponent(catalogScopeId())}`;
}

async function catalogRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || "Catalog request failed.");
  }
  return response.json();
}

function formatCatalogTime(value) {
  if (!value) return t("result.pending_first_run");
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
}

function catalogDimensions(result) {
  if (!result?.width_m || !result?.height_m || !result?.depth_m) return null;
  return {
    w: Math.round(Number(result.width_m) * 1000) / 10,
    h: Math.round(Number(result.height_m) * 1000) / 10,
    d: Math.round(Number(result.depth_m) * 1000) / 10,
  };
}

function catalogCameraCountsHtml(result) {
  const cameraCounts = Array.isArray(result?.camera_counts) ? result.camera_counts : [];
  const rows = cameraCounts
    .filter((entry) => Number(entry.quantity) > 0)
    .map(
      (entry) =>
        `<span class="camera-count-pill"><strong>${escapeHtml(entry.camera_name || t("table.camera"))}</strong>${Number(entry.quantity).toLocaleString()}</span>`
    )
    .join("");
  return rows || `<span class="muted">${escapeHtml(t("table.unknown_camera"))}</span>`;
}

function catalogCameraTotals(results) {
  const totals = new Map();
  for (const result of results || []) {
    const cameraCounts = Array.isArray(result?.camera_counts) ? result.camera_counts : [];
    for (const entry of cameraCounts) {
      const quantity = Number(entry.quantity || 0);
      if (quantity <= 0) continue;
      const cameraName = String(entry.camera_name || t("table.unknown_camera"));
      totals.set(cameraName, (totals.get(cameraName) || 0) + quantity);
    }
  }
  return Array.from(totals.entries())
    .map(([cameraName, quantity]) => ({ cameraName, quantity }))
    .sort((a, b) => b.quantity - a.quantity || a.cameraName.localeCompare(b.cameraName));
}

function splitCatalogCameraName(cameraName) {
  const value = String(cameraName || t("table.unknown_camera")).trim() || t("table.unknown_camera");
  const match = value.match(/^(.*?)(?:\s+[-·]\s+|\s+)(Camera\s+\d+)$/i);
  if (!match) return { nvr: t("table.unknown_nvr"), camera: value };
  const nvr = match[1].trim() || t("table.unknown_nvr");
  const camera = match[2].trim();
  return { nvr, camera };
}

function catalogCameraTotalsTableHtml(results) {
  const totals = catalogCameraTotals(results);
  if (!totals.length) return "";
  const rows = totals
    .map((entry) => {
      const parts = splitCatalogCameraName(entry.cameraName);
      return `
        <tr>
          <td><strong>${escapeHtml(parts.nvr)}</strong></td>
          <td>${escapeHtml(parts.camera)}</td>
          <td class="count-cell">${entry.quantity.toLocaleString()}</td>
        </tr>
      `;
    })
    .join("");
  return `
    <section class="catalog-camera-breakdown">
      <h4>${escapeHtml(t("analytics.by_camera_title"))}</h4>
      <div class="detected-table-wrap">
        <table class="detected-table camera-breakdown-table">
          <thead><tr><th>NVR</th><th>${escapeHtml(t("table.camera"))}</th><th>${escapeHtml(t("table.objects_recognized"))}</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </section>
  `;
}

const RESULT_ANALYTICS_PERIODS = [
  { id: "latest", label: "Latest by camera" },
  { id: "hour", label: "Last hour" },
  { id: "day", label: "Today" },
  { id: "week", label: "This week" },
  { id: "month", label: "This month" },
  { id: "all", label: "All results" },
];

const RESULT_ANALYTICS_LIMITS = [50, 100, 250, 500];

function resultAnalyticsRows(results) {
  return (results || [])
    .flatMap((result) => {
      const cameraCounts = Array.isArray(result?.camera_counts) ? result.camera_counts : [];
      const entries = cameraCounts.some((entry) => Number(entry.quantity) > 0)
        ? cameraCounts.filter((entry) => Number(entry.quantity) > 0)
        : [{ camera_name: t("table.unknown_camera"), quantity: Number(result.quantity || 0) }];
      return entries.map((entry) => {
        const parts = splitCatalogCameraName(entry.camera_name);
        const completedAt = result.completed_at || result.created_at;
        const parsedTime = new Date(completedAt);
        const cameraName = String(entry.camera_name || t("table.unknown_camera"));
        return {
          runId: result.run_id,
          completedAt,
          timeMs: Number.isNaN(parsedTime.getTime()) ? 0 : parsedTime.getTime(),
          nvr: parts.nvr,
          camera: parts.camera,
          cameraName,
          itemName: result.item_name,
          quantity: Number(entry.quantity || 0),
          confidence: Number(result.confidence || 0),
          dimensions: catalogDimensions(result),
          frameUrl: entry.frame_url || "",
          cropUrl: entry.crop_url || "",
          className: entry.class_name || "",
          status: result.status || "completed",
        };
      });
    })
    .sort((a, b) => b.timeMs - a.timeMs || b.quantity - a.quantity || a.camera.localeCompare(b.camera));
}

function latestResultRowsByCamera(rows) {
  const latestTimeByCamera = new Map();
  for (const row of rows || []) {
    const key = `${row.nvr}/${row.camera}`.toLowerCase();
    const current = latestTimeByCamera.get(key) || 0;
    if (row.timeMs > current) latestTimeByCamera.set(key, row.timeMs);
  }
  return (rows || [])
    .filter((row) => row.timeMs === latestTimeByCamera.get(`${row.nvr}/${row.camera}`.toLowerCase()))
    .sort((a, b) => b.timeMs - a.timeMs || b.quantity - a.quantity || a.camera.localeCompare(b.camera));
}

function resultAnalyticsFilterRows(rows, filters = {}) {
  const period = filters.period || "latest";
  const limit = Number(filters.limit || 100);
  const itemNeedle = String(filters.item || "").trim().toLowerCase();
  const cameraNeedle = String(filters.camera || "").trim().toLowerCase();
  let visibleRows = period === "latest" ? latestResultRowsByCamera(rows) : [...(rows || [])];
  if (period !== "latest" && period !== "all") {
    const now = Date.now();
    const ranges = {
      hour: 60 * 60 * 1000,
      day: 24 * 60 * 60 * 1000,
      week: 7 * 24 * 60 * 60 * 1000,
      month: 30 * 24 * 60 * 60 * 1000,
    };
    const cutoff = now - (ranges[period] || ranges.day);
    visibleRows = visibleRows.filter((row) => row.timeMs >= cutoff);
  }
  if (itemNeedle) {
    visibleRows = visibleRows.filter((row) => String(row.itemName || "").toLowerCase().includes(itemNeedle));
  }
  if (cameraNeedle) {
    visibleRows = visibleRows.filter((row) =>
      `${row.nvr} ${row.camera}`.toLowerCase().includes(cameraNeedle)
    );
  }
  return visibleRows.slice(0, Math.max(1, Math.min(limit, 500)));
}

function resultAnalyticsFilterControlsHtml(filters, totalRows, visibleRows) {
  return `
    <form class="result-analytics-filters" data-result-analytics-filters>
      <select name="period" aria-label="Result period">
        ${RESULT_ANALYTICS_PERIODS.map(
          (period) =>
            `<option value="${period.id}" ${period.id === filters.period ? "selected" : ""}>${escapeHtml(t(`result.${period.id === "latest" ? "latest_by_camera" : period.id === "hour" ? "last_hour" : period.id === "day" ? "today" : period.id === "week" ? "this_week" : period.id === "month" ? "this_month" : "all_results"}`))}</option>`
        ).join("")}
      </select>
      <select name="limit" aria-label="Rows limit">
        ${RESULT_ANALYTICS_LIMITS.map(
          (limit) =>
            `<option value="${limit}" ${Number(filters.limit) === limit ? "selected" : ""}>${escapeHtml(t("result.show_limit", { limit }))}</option>`
        ).join("")}
      </select>
      <input name="item" value="${escapeAttr(filters.item || "")}" placeholder="${escapeAttr(t("result.item_filter"))}" autocomplete="off" />
      <input name="camera" value="${escapeAttr(filters.camera || "")}" placeholder="${escapeAttr(t("result.camera_filter"))}" autocomplete="off" />
      <button type="submit" class="export-button">${escapeHtml(t("actions.apply"))}</button>
      <button type="button" class="export-button muted-button" data-clear-result-filters>${escapeHtml(t("actions.clear"))}</button>
      <strong class="result-analytics-count">${currentLanguage() === "ru" ? `Показано ${visibleRows.length.toLocaleString()} из ${totalRows.toLocaleString()}` : `Shown ${visibleRows.length.toLocaleString()} of ${totalRows.toLocaleString()}`}</strong>
    </form>
  `;
}

function resultAnalyticsTableHtml(rows) {
  if (!rows.length) return `<p class="empty">${escapeHtml(t("result.empty"))}</p>`;
  return `
    <div class="detected-table-wrap">
      <table class="detected-table result-analytics-table">
        <thead>
          <tr>
            <th>${escapeHtml(t("result.table_time"))}</th>
            <th>NVR</th>
            <th>${escapeHtml(t("table.camera"))}</th>
            <th>${escapeHtml(t("table.item"))}</th>
            <th>${escapeHtml(t("result.objects"))}</th>
            <th>${escapeHtml(t("result.confidence"))}</th>
            <th>${escapeHtml(t("table.measurement"))}</th>
          </tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (row) => `
                <tr>
                  <td>${escapeHtml(formatCatalogTime(row.completedAt))}</td>
                  <td><strong>${escapeHtml(row.nvr)}</strong></td>
                  <td>${escapeHtml(row.camera)}</td>
                  <td>${escapeHtml(row.itemName)}</td>
                  <td class="count-cell">${row.quantity.toLocaleString()}</td>
                  <td>${Math.round(row.confidence * 100)}%</td>
                  <td>${row.dimensions ? `${row.dimensions.w} x ${row.dimensions.h} x ${row.dimensions.d} cm` : escapeHtml(t("status.pending"))}</td>
                </tr>
              `
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function resultAnalyticsVisualsHtml(rows) {
  const visuals = [];
  const seen = new Set();
  for (const row of rows || []) {
    if (!row.frameUrl && !row.cropUrl) continue;
    const key = `${row.runId}/${row.cameraName}/${row.itemName}/${row.frameUrl}/${row.cropUrl}`;
    if (seen.has(key)) continue;
    seen.add(key);
    visuals.push(row);
    if (visuals.length >= 24) break;
  }
  const body = visuals.length
    ? `<div class="result-visual-grid">
        ${visuals
          .map((row) => {
            const title = `${row.cameraName} - ${row.itemName}`;
            return `
              <article class="result-visual-card">
                <div class="result-visual-meta">
                  <strong>${escapeHtml(row.itemName)}</strong>
                  <span>${escapeHtml(row.cameraName)} · ${row.quantity.toLocaleString()} ${escapeHtml(t("result.objects").toLowerCase())} · ${Math.round(row.confidence * 100)}%</span>
                </div>
                <div class="result-visual-pair">
                  <figure>
                    <span>${escapeHtml(t("result.scene_image"))}</span>
                    ${row.frameUrl ? `<img src="${escapeAttr(`${API_BASE}${row.frameUrl}`)}" alt="${escapeAttr(`${title} ${t("result.scene_image")}`)}" loading="lazy" decoding="async" />` : `<div class="result-visual-missing">${escapeHtml(t("result.visual_empty"))}</div>`}
                  </figure>
                  <figure>
                    <span>${escapeHtml(t("result.object_crop"))}</span>
                    ${row.cropUrl ? `<img src="${escapeAttr(`${API_BASE}${row.cropUrl}`)}" alt="${escapeAttr(`${title} ${t("result.object_crop")}`)}" loading="lazy" decoding="async" />` : `<div class="result-visual-missing">${escapeHtml(t("result.visual_empty"))}</div>`}
                  </figure>
                </div>
              </article>
            `;
          })
          .join("")}
      </div>`
    : `<p class="empty">${escapeHtml(t("result.visual_empty"))}</p>`;
  return `
    <section class="result-visuals">
      <div class="result-visuals-head">
        <h4>${escapeHtml(t("result.visual_title"))}</h4>
        <p>${escapeHtml(t("result.visual_subtitle"))}</p>
      </div>
      ${body}
    </section>
  `;
}

function resultAnalyticsSummaryHtml(rows, schedule) {
  const totalObjects = rows.reduce((sum, row) => sum + row.quantity, 0);
  const cameras = new Set(rows.map((row) => `${row.nvr}/${row.camera}`));
  const runs = new Set((rows || []).map((row) => row.runId).filter(Boolean));
  return `
    <div class="result-analytics-summary">
      <article><span>${escapeHtml(t("result.total_objects"))}</span><strong>${totalObjects.toLocaleString()}</strong></article>
      <article><span>${escapeHtml(t("result.cameras_with_results"))}</span><strong>${cameras.size.toLocaleString()}</strong></article>
      <article><span>${escapeHtml(t("result.recognition_runs"))}</span><strong>${runs.size.toLocaleString()}</strong></article>
      <article><span>${escapeHtml(t("result.next_run"))}</span><strong>${escapeHtml(formatCatalogTime(schedule?.next_run_at))}</strong></article>
    </div>
  `;
}

function renderResultAnalyticsBody(container, payload, filters = { period: "latest", limit: 100, item: "", camera: "" }) {
  const rows = resultAnalyticsRows(payload.results);
  const visibleRows = resultAnalyticsFilterRows(rows, filters);
  container.innerHTML = `
    <section class="detected-list result-analytics">
      <header class="detected-list-head">
        <div>
          <h3>${escapeHtml(t("result.title"))}</h3>
          <p>${escapeHtml(t("result.subtitle"))}</p>
        </div>
        <div class="detected-list-actions">
          <button type="button" class="export-button" data-refresh-result-analytics>${escapeHtml(t("actions.refresh"))}</button>
          <button type="button" class="export-button" data-run-result-recognition>${escapeHtml(t("actions.run_recognition"))}</button>
          <a class="export-button" href="${API_BASE}${catalogApiPath("/api/catalog/results/export.xlsx")}">${escapeHtml(t("actions.export_excel"))}</a>
        </div>
      </header>
      ${resultAnalyticsFilterControlsHtml(filters, rows.length, visibleRows)}
      ${resultAnalyticsSummaryHtml(visibleRows, payload.schedule)}
      ${resultAnalyticsTableHtml(visibleRows)}
      ${resultAnalyticsVisualsHtml(visibleRows)}
    </section>
  `;
  container.querySelector("[data-result-analytics-filters]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const nextFilters = {
      period: form.period.value,
      limit: Number(form.limit.value),
      item: form.item.value,
      camera: form.camera.value,
    };
    renderResultAnalyticsBody(container, payload, nextFilters);
  });
  container.querySelector("[data-clear-result-filters]")?.addEventListener("click", () => {
    renderResultAnalyticsBody(container, payload, { period: "latest", limit: 100, item: "", camera: "" });
  });
  container.querySelector("[data-refresh-result-analytics]")?.addEventListener("click", () => {
    container.innerHTML = `<p class="empty">${escapeHtml(t("result.loading"))}</p>`;
    void renderResultAnalytics(container);
  });
  container.querySelector("[data-run-result-recognition]")?.addEventListener("click", (event) => {
    void runResultAnalyticsRecognition(container, event.currentTarget, filters);
  });
}

async function runResultAnalyticsRecognition(container, button, filters) {
  button.disabled = true;
  button.textContent = t("actions.recognizing");
  try {
    await catalogRequest(catalogApiPath("/api/catalog/recognition/run"), { method: "POST" });
    const payload = await catalogRequest(catalogApiPath("/api/catalog/results/history?limit=500"));
    if (container.isConnected && accountModule === "result_analytics") {
      renderResultAnalyticsBody(container, payload, filters);
    }
    toast(t("toast.recognition_complete"));
  } catch (error) {
    button.disabled = false;
    button.textContent = t("actions.run_recognition");
    toast(error.message);
  }
}

async function renderResultAnalytics(container) {
  try {
    const payload = await catalogRequest(catalogApiPath("/api/catalog/results/history?limit=500"));
    if (!container.isConnected || accountModule !== "result_analytics") return;
    renderResultAnalyticsBody(container, payload);
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

async function renderCatalogEnrollment(container) {
  try {
    const payload = await catalogRequest(catalogApiPath("/api/catalog/items"));
    if (!container.isConnected || accountModule !== "ai") return;
    const rows = payload.items
      .map(
        (item) => `
          <article class="cc-role ai-product catalog-product">
            <div class="cc-role-head">
              <div><strong>${escapeHtml(item.name)}</strong><small>${item.image_count} ${escapeHtml(t("ai.reference_images").toLowerCase())}</small></div>
              <button type="button" class="cc-remove" data-acc-action="remove-catalog-item" data-product="${item.id}" aria-label="Remove ${escapeHtml(item.name)}">✕</button>
            </div>
            <div class="catalog-thumbs">
              ${item.images.map((image) => `<img src="${API_BASE}${image.url}" alt="${escapeHtml(item.name)} reference" />`).join("")}
            </div>
            <span class="cc-chip cc-chip-small on">${escapeHtml(t("ai.catalog_enabled"))}</span>
          </article>
        `
      )
      .join("");
    container.innerHTML = `
      <p class="chart-note">${escapeHtml(t("ai.intro"))}</p>
      <form class="catalog-form" data-acc-form="catalog-product">
        <label class="catalog-name-field">
          <span>${escapeHtml(t("ai.item_name"))}</span>
          <input name="name" placeholder="${escapeAttr(t("ai.item_placeholder"))}" required maxlength="60" autocomplete="off" />
        </label>
        <label class="catalog-upload">
          <span>${escapeHtml(t("ai.reference_images"))}</span>
          <input name="images" type="file" accept="image/*" multiple required />
        </label>
        <small class="catalog-upload-help" data-image-count>${escapeHtml(t("ai.add_help"))}</small>
        <button type="submit">${escapeHtml(t("ai.add_item"))}</button>
      </form>
      <div class="recognition-schedule">
        <strong>${escapeHtml(t("ai.auto_recognition", { hours: payload.schedule.interval_hours }))}</strong>
        <span>${escapeHtml(t("ai.last_run", { time: formatCatalogTime(payload.schedule.last_run_at) }))}</span>
        <span>${escapeHtml(t("ai.next_run", { time: formatCatalogTime(payload.schedule.next_run_at) }))}</span>
      </div>
      <div class="cc-list ai-list">${rows || `<p class="empty">${escapeHtml(t("ai.empty_catalog"))}</p>`}</div>
    `;
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function catalogResultsTableHtml(results) {
  const rows = (results || [])
    .map((result) => {
      const dims = catalogDimensions(result);
      return `
        <tr>
          <td><strong>${escapeHtml(result.item_name)}</strong></td>
          <td class="count-cell">${Number(result.quantity).toLocaleString()}</td>
          <td><div class="camera-count-list">${catalogCameraCountsHtml(result)}</div></td>
          <td>${Math.round(Number(result.confidence) * 100)}%</td>
          <td>${dims ? `${dims.w} × ${dims.h} × ${dims.d} cm` : escapeHtml(t("dimension.pending_measurement"))}</td>
        </tr>
      `;
    })
    .join("");
  return rows
    ? `<div class="detected-table-wrap"><table class="detected-table"><thead><tr><th>${escapeHtml(t("table.item"))}</th><th>${escapeHtml(t("table.count"))}</th><th>${escapeHtml(t("table.camera_objects"))}</th><th>${escapeHtml(t("result.confidence"))}</th><th>${escapeHtml(t("table.measurement"))}</th></tr></thead><tbody>${rows}</tbody></table></div>`
    : `<p class="empty">${escapeHtml(t("analytics.no_detected"))}</p>`;
}

async function refreshCatalogResultsTable(container, results = []) {
  const table = container.querySelector("[data-catalog-table]");
  if (!table) return;
  if (!container.isConnected) return;
  const breakdown = container.querySelector("[data-catalog-camera-breakdown]");
  if (breakdown) breakdown.innerHTML = catalogCameraTotalsTableHtml(results);
  table.innerHTML = catalogResultsTableHtml(results);
}

async function renderCatalogResults(container) {
  try {
    const payload = await catalogRequest(catalogApiPath("/api/catalog/results"));
    if (!container.isConnected || accountModule !== "analytics") return;
    container.innerHTML = `
      <section class="detected-list">
        <header class="detected-list-head">
          <div>
            <h3>${escapeHtml(t("analytics.detected_title"))}</h3>
            <p>${escapeHtml(t("analytics.latest_run", { time: formatCatalogTime(payload.run?.completed_at) }))}</p>
          </div>
          <div class="detected-list-actions">
            <button type="button" class="export-button" data-run-live-recognition>${escapeHtml(t("actions.run_recognition"))}</button>
            <a class="export-button" href="${API_BASE}${catalogApiPath("/api/catalog/results/export.xlsx")}">${escapeHtml(t("actions.export_excel"))}</a>
          </div>
        </header>
        <div data-catalog-table>${catalogResultsTableHtml(payload.results)}</div>
        <div data-catalog-camera-breakdown>${catalogCameraTotalsTableHtml(payload.results)}</div>
        <p class="catalog-next-run">${escapeHtml(t("analytics.next_run", { time: formatCatalogTime(payload.schedule.next_run_at) }))}</p>
      </section>
    `;
    const button = container.querySelector("[data-run-live-recognition]");
    button?.addEventListener("click", () => startLiveCatalogRecognition(container, button));
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

// Recognition runs immediately against items enrolled via AI Check-in. The
// backend compares the current YOLO detection crops to those catalog reference
// images, so generic objects are ignored unless they match a checked-in item.
async function startLiveCatalogRecognition(container, button) {
  button.disabled = true;
  button.textContent = t("actions.recognizing");
  try {
    const payload = await catalogRequest(catalogApiPath("/api/catalog/recognition/run"), { method: "POST" });
    await refreshCatalogResultsTable(container, payload.results || []);
    button.disabled = false;
    button.textContent = t("actions.run_recognition");
    toast(t("toast.recognition_complete"));
  } catch (error) {
    button.disabled = false;
    button.textContent = t("actions.run_recognition");
    toast(error.message);
  }
}

async function renderCatalogDimensions(container) {
  try {
    const [catalog, recognition] = await Promise.all([
      catalogRequest(catalogApiPath("/api/catalog/items")),
      catalogRequest(catalogApiPath("/api/catalog/results")),
    ]);
    if (!container.isConnected || accountModule !== "dimension") return;
    const items = new Map(catalog.items.map((item) => [item.id, item]));
    const cards = recognition.results
      .map((result) => {
        const dims = catalogDimensions(result);
        if (!dims) return "";
        const item = items.get(result.item_id);
        return `
          <article class="cc-company dim-card">
            <header class="cc-company-head"><h3>${escapeHtml(result.item_name)}</h3><span class="cc-chip cc-chip-small on">${escapeHtml(t("dimension.recognized", { quantity: result.quantity }))}</span></header>
            <div class="dimension-visual">
              ${item?.images?.[0] ? `<img src="${API_BASE}${item.images[0].url}" alt="${escapeHtml(result.item_name)} reference" />` : ""}
              ${dimBoxSvg(dims)}
            </div>
            <p class="cc-cred"><em>${escapeHtml(t("dimension.measured"))}</em> ${dims.w} × ${dims.h} × ${dims.d} cm</p>
            <p class="cc-cred"><em>${escapeHtml(t("dimension.volume"))}</em> ${((dims.w * dims.h * dims.d) / 1000).toFixed(1)} L · ${escapeHtml(result.measurement_method || "3D vision")}</p>
          </article>
        `;
      })
      .join("");
    container.innerHTML = `
      <p class="chart-note">${escapeHtml(t("dimension.note"))}</p>
      ${cards ? `<div class="cc-list dim-list">${cards}</div>` : `<p class="empty">${escapeHtml(t("dimension.empty", { time: formatCatalogTime(recognition.schedule.next_run_at) }))}</p>`}
    `;
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function renderAccountModule() {
  const { company, role } = accountState;
  companyConfig(company);
  const menus = accountMenus(role);
  const menu = menus.find((item) => item.id === accountModule) || menus[0];
  accountModule = menu?.id || null;

  els.moduleNav.innerHTML = menus
    .map(
      (item) => `
        <button class="${item.id === accountModule ? "active" : ""}" data-acc-module="${item.id}" type="button">
          ${NAV_ICONS[item.id] || ""}
          <span>${escapeHtml(accountMenuLabel(item))}</span>
        </button>
      `
    )
    .join("");

  els.activeModuleEyebrow.textContent = t("user.module");
  els.activeModuleTitle.textContent = menu ? accountMenuLabel(menu) : t("user.welcome", { name: role.name });

  if (!menu) {
    els.moduleContent.innerHTML = `<p class="empty">No modules have been granted to this account yet. Ask your administrator for access.</p>`;
    return;
  }

  const config = company.cameraConfig;

  if (menu.id === "camera") {
    const atLimit = config.nvrs.length >= MAX_NVRS;
    const streamsBySlot = streamStatusBySlot();
    const nvrCards = config.nvrs
      .map((nvr) => {
        const channels = nvr.channelsDetail || [];
        const assigned = channels.filter((channel) => channel.slot_number != null).length;
        const totalChannels = channels.length || nvr.channels || 0;
        const overallOk = channels.length > 0 && assigned > 0;
        const channelRows = channels.length
          ? `<ul class="nvr-channels">${channels
              .map((channel) => {
                const hasSlot = channel.slot_number != null;
                const stream = hasSlot ? streamsBySlot.get(Number(channel.slot_number)) : null;
                const isLive = stream?.status === "online";
                const isStarting = stream?.status === "starting";
                const isReconnecting = stream?.status === "reconnecting";
                const stateClass = isLive
                  ? "ok"
                  : isReconnecting || stream?.status === "offline" || channel.status === "failed"
                    ? "bad"
                    : hasSlot || channel.status === "connected"
                      ? "pending"
                      : "bad";
                const label = isLive
                  ? t("status.live")
                  : isReconnecting
                    ? t("status.reconnecting")
                    : isStarting
                      ? t("status.starting")
                  : hasSlot
                    ? t("status.waiting_video")
                    : channel.status === "connected"
                    ? t("status.waiting_free_slot")
                    : t("status.not_connected");
                const detail = stream?.last_error || channel.message || "";
                const slotLabel = channel.slot_number != null ? `${t("table.slot")} ${channel.slot_number}` : t("table.not_assigned");
                return `
                  <li class="nvr-channel ${stateClass}" title="${escapeHtml(detail)}">
                    <span>${escapeHtml(t("table.channel_short"))} ${channel.channel} · ${escapeHtml(slotLabel)}</span>
                    <span class="nvr-channel-status">${label}</span>
                  </li>
                `;
              })
              .join("")}</ul>`
          : "";
        return `
          <article class="cc-company">
            <header class="cc-company-head">
              <h3>${escapeHtml(nvr.name)}</h3>
              <button type="button" class="cc-remove" data-acc-action="remove-nvr" data-nvr="${nvr.id}" aria-label="Remove NVR">✕</button>
            </header>
            <p class="cc-cred"><em>${escapeHtml(t("camera.address"))}</em> <span class="nvr-rtsp" title="${escapeHtml(nvr.protocol)}://${escapeHtml(nvr.host)}:${nvr.port}">${escapeHtml(nvr.protocol)}://${escapeHtml(nvr.host)}:${nvr.port}</span></p>
            <p class="cc-cred"><em>${escapeHtml(t("camera.channels"))}</em> ${assigned}/${totalChannels} ${escapeHtml(t("camera.slots_assigned"))}</p>
            <p class="nvr-status ${overallOk ? "ok" : "bad"}">${escapeHtml(nvrControllerMessage(nvr, assigned, totalChannels))}</p>
            ${channelRows}
          </article>
        `;
      })
      .join("");
    els.moduleContent.innerHTML = `
      <p class="chart-note">${escapeHtml(t("camera.connected_devices", { count: config.nvrs.length, max: MAX_NVRS }))}</p>
      <div class="cc-list">${nvrCards || `<p class="empty">${escapeHtml(t("camera.no_devices"))}</p>`}</div>
      ${atLimit ? `<p class="empty">${escapeHtml(t("camera.device_limit", { max: MAX_NVRS }))}</p>` : `<div class="discovery-panel" data-discovery-panel></div>`}
      <section class="acc-block quality-block">
        <h3>${escapeHtml(t("camera.quality_title"))}</h3>
        <p class="chart-note">${escapeHtml(t("camera.quality_note"))}</p>
        <div class="cc-access">
          ${QUALITY_OPTIONS.map(
            (option) => `
              <button type="button" class="cc-chip ${config.quality === option.id ? "on" : ""}"
                      data-acc-action="quality" data-quality="${option.id}">
                ${escapeHtml(t(`quality.${option.id}.label`))} <small>· ${escapeHtml(t(`quality.${option.id}.hint`))}</small>
              </button>
            `
          ).join("")}
        </div>
      </section>
    `;
    const discoveryPanel = els.moduleContent.querySelector("[data-discovery-panel]");
    if (discoveryPanel) renderDiscoveryPanel(discoveryPanel);
    return;
  }

  if (menu.id === "camera_info") {
    els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(t("camera_info.loading"))}</p>`;
    void renderCameraInfo(els.moduleContent);
    return;
  }

  if (menu.id === "analytics") {
    els.moduleContent.innerHTML = `<div id="accCharts"></div><div id="catalogResults" class="catalog-results-loading"><p class="empty">${escapeHtml(t("analytics.loading_detected"))}</p></div>`;
    renderAnalytics(els.moduleContent.querySelector("#accCharts"), true);
    void renderCatalogResults(els.moduleContent.querySelector("#catalogResults"));
    return;
  }

  if (menu.id === "result_analytics") {
    els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(t("result.loading"))}</p>`;
    void renderResultAnalytics(els.moduleContent);
    return;
  }

  if (menu.id === "feed") {
    if (!config.nvrs.length) {
      els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(t("feed.empty"))}</p>`;
      return;
    }
    els.moduleContent.innerHTML = `
      <p class="chart-note">${escapeHtml(t("feed.live_note", { quality: t(`quality.${(QUALITY_OPTIONS.find((option) => option.id === config.quality) || QUALITY_OPTIONS[2]).id}.label`) }))}</p>
      <p class="chart-note">${escapeHtml(t("feed.group_note"))}</p>
      ${feedGroupsHtml(config)}
    `;
    return;
  }

  if (menu.id === "ai") {
    els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(t("ai.loading"))}</p>`;
    void renderCatalogEnrollment(els.moduleContent);
    return;
  }

  if (menu.id === "dimension") {
    els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(t("dimension.loading"))}</p>`;
    void renderCatalogDimensions(els.moduleContent);
    return;
  }
}

// ---- Device-first discovery flow -------------------------------------------
// State for the multi-step discovery interaction lives here so the panel can
// re-render itself (search -> services -> auth-if-needed -> connect) without a
// full module re-render wiping progress between steps.
let discoveryState = {
  host: "",
  scanning: false,
  result: null,
  selectedPort: null,
  selectedProtocol: null,
  selectedRequiresAuth: false,
  deviceId: null,
  connecting: false,
  error: null,
};

function resetDiscoveryState() {
  discoveryState = {
    host: "",
    scanning: false,
    result: null,
    selectedPort: null,
    selectedProtocol: null,
    selectedRequiresAuth: false,
    deviceId: null,
    connecting: false,
    error: null,
  };
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll('"', "&quot;");
}

const DEVICE_TYPE_LABELS = {
  nvr_or_dvr: "device_type.nvr",
  ip_camera: "device_type.camera",
  unknown: "device_type.unknown",
};

function discoveryConnectFormHtml(isNvr) {
  // Credentials are always enterable (optional): auth detection from an RTSP
  // OPTIONS probe is unreliable - it can report "Available" for a stream that
  // actually needs a password - so we never hide the fields behind it. The
  // sign-in hint just clarifies why they matter for this service.
  const authHint = discoveryState.selectedRequiresAuth
    ? `<p class="discovery-auth-hint">${escapeHtml(t("discovery.auth_hint"))}</p>`
    : "";
  return `
    ${authHint}
    <div class="discovery-connect">
      <input placeholder="${escapeAttr(t("discovery.name_placeholder"))}" maxlength="60" autocomplete="off" data-discovery-name />
      <input placeholder="${escapeAttr(t("discovery.username_placeholder"))}" autocomplete="off" data-discovery-username />
      <input type="password" placeholder="${escapeAttr(t("discovery.password_placeholder"))}" autocomplete="new-password" data-discovery-password />
      ${isNvr
        ? `<input type="number" min="1" max="${MAX_NVR_SLOTS}" value="4" data-discovery-channels aria-label="${escapeAttr(t("discovery.channels_label"))}" title="${escapeAttr(t("discovery.channels_label"))}" />`
        : ""}
      <button type="button" data-discovery-connect ${discoveryState.connecting ? "disabled" : ""}>
        ${escapeHtml(discoveryState.connecting ? t("actions.connecting") : t("actions.connect"))}
      </button>
    </div>
  `;
}

function discoveryResultsHtml(result) {
  const services = result.services || [];
  const vendor = result.fingerprint?.vendor;
  const isNvr = result.fingerprint?.device_type === "nvr_or_dvr";
  const typeLabel = t(DEVICE_TYPE_LABELS[result.fingerprint?.device_type] || "device_type.device");
  const serviceButtons = services
    .map((svc) => {
      const protocol = String(svc.protocol || "").toLowerCase();
      const selected =
        discoveryState.selectedPort === svc.port && discoveryState.selectedProtocol === protocol;
      const badge =
        svc.status === "available"
          ? t("discovery.available")
          : svc.status === "requires_auth"
            ? t("discovery.needs_signin")
            : t("discovery.unreachable");
      return `
        <button type="button" class="discovery-service ${selected ? "selected" : ""} ${svc.status}"
                data-discovery-service data-port="${svc.port}" data-protocol="${escapeAttr(protocol)}"
                data-requires-auth="${svc.requires_auth ? "true" : "false"}"
                ${svc.status === "unreachable" ? "disabled" : ""}>
          <span class="discovery-service-proto">${escapeHtml(svc.protocol)}</span>
          <span class="discovery-service-port">Port ${svc.port}</span>
          <span class="discovery-service-status">${badge}</span>
        </button>
      `;
    })
    .join("");
  return `
    <div class="discovery-device">
      <p class="cc-cred"><em>${escapeHtml(t("discovery.discovered"))}</em> ${escapeHtml(typeLabel)}${vendor ? ` · ${escapeHtml(vendor)}` : ""}</p>
      <p class="chart-note">${escapeHtml(t("discovery.select_service"))}</p>
      <div class="discovery-services">${serviceButtons || `<p class="empty">${escapeHtml(t("discovery.connectable_empty"))}</p>`}</div>
      ${discoveryState.selectedPort ? discoveryConnectFormHtml(isNvr) : ""}
    </div>
  `;
}

function renderDiscoveryPanel(container) {
  const st = discoveryState;
  const result = st.result;
  container.innerHTML = `
    <form class="discovery-search" data-discovery-search>
      <input name="host" value="${escapeAttr(st.host)}" placeholder="${escapeAttr(t("discovery.host_placeholder"))}"
             required maxlength="255" autocomplete="off" ${st.scanning ? "disabled" : ""} />
      <button type="submit" ${st.scanning ? "disabled" : ""}>${escapeHtml(st.scanning ? t("discovery.searching") : t("discovery.search"))}</button>
    </form>
    ${st.scanning ? `<p class="discovery-progress">${escapeHtml(t("discovery.progress", { host: st.host }))}</p>` : ""}
    ${st.error ? `<p class="nvr-status bad">${escapeHtml(st.error)}</p>` : ""}
    ${result && !result.reachable && !st.scanning ? `<p class="nvr-status bad">${escapeHtml(result.error || t("discovery.no_services"))}</p>` : ""}
    ${result && result.reachable ? discoveryResultsHtml(result) : ""}
  `;

  container.querySelector("[data-discovery-search]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    discoverySearch(container, event.target.elements.host.value);
  });
  container.querySelectorAll("[data-discovery-service]").forEach((btn) =>
    btn.addEventListener("click", () => discoverySelectService(container, btn))
  );
  container.querySelector("[data-discovery-connect]")?.addEventListener("click", () =>
    discoveryConnect(container)
  );
}

async function discoverySearch(container, hostValue) {
  const host = (hostValue || "").trim();
  if (!host) return;
  discoveryState = {
    ...discoveryState,
    host,
    scanning: true,
    result: null,
    error: null,
    selectedPort: null,
    selectedProtocol: null,
    selectedRequiresAuth: false,
    deviceId: null,
  };
  renderDiscoveryPanel(container);
  try {
    const response = await accountsApi("/api/v2/devices/discover", {
      method: "POST",
      body: JSON.stringify({ host, name: host }),
    });
    discoveryState = {
      ...discoveryState,
      scanning: false,
      result: response.discovery,
      deviceId: response.device?.id,
    };
  } catch (error) {
    discoveryState = { ...discoveryState, scanning: false, error: error.message };
  }
  if (container.isConnected) renderDiscoveryPanel(container);
}

function discoverySelectService(container, btn) {
  discoveryState = {
    ...discoveryState,
    selectedPort: Number(btn.dataset.port),
    selectedProtocol: btn.dataset.protocol,
    selectedRequiresAuth: btn.dataset.requiresAuth === "true",
  };
  renderDiscoveryPanel(container);
}

async function discoveryConnect(container) {
  const st = discoveryState;
  const name = container.querySelector("[data-discovery-name]")?.value.trim() || st.host;
  const username = container.querySelector("[data-discovery-username]")?.value.trim() || "";
  const password = container.querySelector("[data-discovery-password]")?.value || "";
  const channels = Math.min(
    MAX_NVR_SLOTS,
    Math.max(1, Number(container.querySelector("[data-discovery-channels]")?.value) || 1)
  );
  discoveryState = { ...discoveryState, connecting: true };
  renderDiscoveryPanel(container);

  const payload = {
    protocol: st.selectedProtocol,
    port: st.selectedPort,
    channel_count: channels,
    make_active: true,
    test_streams: false,
  };
  if (username) {
    payload.username = username;
    payload.password = password;
  }

  try {
    const response = await accountsApi(`/api/v2/devices/${st.deviceId}/authenticate`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await persistDiscoveredDevice({
      name,
      host: st.host,
      protocol: st.selectedProtocol,
      port: st.selectedPort,
      channels,
      response,
    });
    resetDiscoveryState();
    renderAccountModule();
  } catch (error) {
    discoveryState = { ...discoveryState, connecting: false };
    toast(error.message);
    if (container.isConnected) renderDiscoveryPanel(container);
  }
}

async function persistDiscoveredDevice({ name, host, protocol, port, channels, response }) {
  const { company } = accountState;
  const responseChannels = response.channels || response.results || [];
  const channelsDetail = responseChannels.map((result) => ({
    camera_id: result.camera_id,
    channel_id: result.id,
    channel: result.external_channel_id || result.channel,
    name: result.name,
    profile: result.profile,
    slot_number: result.slot_number,
    status: result.slot_number != null ? "connected" : result.status || "registered",
    message: result.masked_stream_reference || result.message || "Stream managed by AI Vision.",
    active: result.slot_number != null,
  }));
  const assigned = channelsDetail.filter((channel) => channel.slot_number != null).length;
  const previousNvrs = company.cameraConfig.nvrs;
  const newNvr = {
    id: newId(),
    name,
    host,
    protocol,
    port,
    channels,
    deviceId: response.device?.id,
    vendor: response.device?.vendor || response.discovery?.fingerprint?.vendor || response.provider,
    model: response.device?.model || response.discovery?.fingerprint?.model,
    deviceType: response.device?.device_type || response.discovery?.fingerprint?.device_type,
    provider: response.provider,
    controllerMessage: `Connected via ${response.provider} — ${assigned}/${channelsDetail.length} slot${assigned === 1 ? "" : "s"} assigned. Waiting for live video frames.`,
    channelsDetail,
  };
  company.cameraConfig.nvrs = [...previousNvrs, newNvr];
  try {
    await persistAccountCompany();
    if (assigned > 0) {
      toast(`"${name}" connected — ${assigned}/${channelsDetail.length} slot${assigned === 1 ? "" : "s"} assigned. Waiting for video.`);
    } else {
      toast(`"${name}" registered, but no slots are assigned yet.`);
    }
  } catch (error) {
    company.cameraConfig.nvrs = previousNvrs;
    await deleteNvrCameras(newNvr);
    toast(error.message);
  }
}

async function handleAccountSubmit(event) {
  const form = event.target.closest("[data-acc-form]");
  if (!form || !accountState) return;
  event.preventDefault();
  const { company } = accountState;
  companyConfig(company);

  if (form.dataset.accForm === "feed-group") {
    const groupId = form.dataset.feedGroupId;
    const name = form.elements.name.value.trim();
    if (!groupId || !name) return;
    const previousGroups = { ...company.cameraConfig.feedGroups };
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    company.cameraConfig.feedGroups = { ...previousGroups, [groupId]: name };
    try {
      await persistAccountCompany();
      toast(t("feed.group_saved"));
      renderAccountModule();
    } catch (error) {
      company.cameraConfig.feedGroups = previousGroups;
      toast(error.message);
      submit.disabled = false;
    }
    return;
  }

  if (form.dataset.accForm === "catalog-product") {
    const name = form.elements.name.value.trim();
    const files = Array.from(form.elements.images.files || []);
    if (!name || files.length < 2) {
      toast("Add an item name and at least two reference images.");
      return;
    }
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    submit.textContent = "Adding item…";
    const payload = new FormData();
    payload.append("scope_id", catalogScopeId());
    payload.append("name", name);
    files.forEach((file) => payload.append("files", file));
    try {
      await catalogRequest("/api/catalog/items", { method: "POST", body: payload });
      toast(`"${name}" added with ${files.length} reference images.`);
      renderAccountModule();
    } catch (error) {
      toast(error.message);
      submit.disabled = false;
      submit.textContent = "Add item to AI catalog";
    }
    return;
  }

  if (form.dataset.accForm !== "nvr") return;
  if (company.cameraConfig.nvrs.length >= MAX_NVRS) return;
  const name = form.elements.name.value.trim();
  const channels = Math.min(MAX_NVR_SLOTS, Math.max(1, Number(form.elements.channels.value) || 1));
  // The host field also accepts "host:port" or a full rtsp://user:pass@host:port/path
  // URL pasted straight from an NVR's spec sheet, so a port typed there (instead of the
  // dedicated Port field) doesn't silently fall back to the protocol default.
  const parsedHost = parseNvrConnectionInput(form.elements.host.value);
  const host = parsedHost.host;
  const protocol = form.elements.protocol.value;
  const port = Number(form.elements.port.value) || parsedHost.port || null;
  const username = form.elements.username.value.trim() || parsedHost.username || "";
  const password = form.elements.password.value || parsedHost.password || "";
  const streamPath =
    form.elements.streamPath.value.trim() || (channels === 1 && parsedHost.path) || "";
  if (!name || !host) return;

  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  submit.textContent = "Connecting…";
  try {
    const registration = await registerNvrController({
      name,
      host,
      protocol,
      port,
      username,
      password,
      channels,
      streamPath,
    });
    const previousNvrs = company.cameraConfig.nvrs;
    const newNvr = {
      id: newId(),
      name,
      host,
      protocol,
      port: registration.port,
      channels,
      controllerMessage: registration.controllerMessage,
      channelsDetail: registration.channelsDetail,
    };
    company.cameraConfig.nvrs = [...previousNvrs, newNvr];
    try {
      await persistAccountCompany();
      const transmitting = registration.channelsDetail.filter((channel) => channel.active).length;
      const waiting = registration.channelsDetail.filter(
        (channel) => !channel.active && channel.status === "connected"
      ).length;
      if (transmitting > 0 && waiting > 0) {
        toast(
          `NVR "${name}" connected — ${transmitting}/${channels} channels transmitting, ` +
            `${waiting} registered but waiting for a free slot.`
        );
      } else if (transmitting > 0) {
        toast(`NVR "${name}" connected — ${transmitting}/${channels} channels transmitting.`);
      } else if (waiting > 0) {
        toast(
          `NVR "${name}" reachable, but no free camera slots are available right now — ` +
            `${waiting} channels are registered and will activate once a slot frees up.`
        );
      } else {
        toast(`NVR "${name}" saved but not reachable: ${registration.controllerMessage}`);
      }
    } catch (error) {
      company.cameraConfig.nvrs = previousNvrs;
      await deleteNvrCameras(newNvr);
      toast(error.message);
    }
  } catch (error) {
    toast(error.message);
  } finally {
    submit.disabled = false;
    submit.textContent = "Add NVR";
  }
  renderAccountModule();
}

async function handleAccountClick(event) {
  const button = event.target.closest("[data-acc-action]");
  if (!button || !accountState) return;
  const { company } = accountState;
  companyConfig(company);
  const action = button.dataset.accAction;

  if (action === "remove-catalog-item") {
    button.disabled = true;
    try {
      await catalogRequest(catalogApiPath(`/api/catalog/items/${encodeURIComponent(button.dataset.product)}`), {
        method: "DELETE",
      });
      toast("Catalog item removed.");
      renderAccountModule();
    } catch (error) {
      toast(error.message);
      button.disabled = false;
    }
    return;
  }

  if (action !== "remove-nvr" && action !== "quality") return;
  const previousConfig = { ...company.cameraConfig, nvrs: [...company.cameraConfig.nvrs] };
  let removedNvr = null;
  if (action === "remove-nvr") {
    removedNvr = company.cameraConfig.nvrs.find((nvr) => nvr.id === button.dataset.nvr) || null;
    company.cameraConfig.nvrs = company.cameraConfig.nvrs.filter((nvr) => nvr.id !== button.dataset.nvr);
  } else {
    company.cameraConfig.quality = button.dataset.quality;
  }
  try {
    await persistAccountCompany();
    if (removedNvr) await deleteNvrCameras(removedNvr);
  } catch (error) {
    company.cameraConfig = previousConfig;
    toast(error.message);
  }
  renderAccountModule();
}

function handleCatalogImageChange(event) {
  const input = event.target.closest('input[name="images"][multiple]');
  if (!input) return;
  const label = input.closest("label")?.querySelector("[data-image-count]");
  if (!label) return;
  const count = input.files?.length || 0;
  label.textContent = count ? `${count} images selected${count < 2 ? " — add at least one more" : " ✓"}` : "Choose at least 2 clear images from different angles.";
}

function renderAccountView({ company, role, missing, error }) {
  els.pageTitle.textContent = "User Dashboard";
  els.companiesSection.hidden = true;
  els.summaryGrid.hidden = true;
  els.activeModuleEyebrow.textContent = t("user.module");

  const summary = state.overview?.summary || {};
  const running = Boolean(summary.detector_running);
  els.detectorState.textContent = running ? t("status.detector_running") : t("status.detector_stopped");
  els.detectorState.dataset.state = running ? "good" : "bad";

  if (missing) {
    els.moduleNav.innerHTML = "";
    els.scopeLine.textContent = "Account access";
    if (error) {
      els.activeModuleTitle.textContent = "Couldn't load this account";
      els.moduleContent.innerHTML = `
        <p class="empty">${escapeHtml(error)} Check your connection and try refreshing — this is not
        the same as the account being deleted.</p>
        <button type="button" data-retry-dashboard>Try again</button>
      `;
    } else {
      els.activeModuleTitle.textContent = "Account not found";
      els.moduleContent.innerHTML = `
        <p class="empty">This account link doesn't match any saved account. It may have been deleted,
        mistyped, or created before this dashboard moved account storage to the server — ask an admin
        to open Company Control and copy the current link for this account.</p>
      `;
    }
    return;
  }

  accountState = { company, role };
  if (!accountModule && role.access?.camera) accountModule = "feed";
  const hour = new Date().getHours();
  const greetingKey = hour < 12 ? "user.good_morning" : hour < 18 ? "user.good_afternoon" : "user.good_evening";
  els.pageTitle.textContent = t(greetingKey, { name: role.name });
  els.scopeLine.textContent = t("user.scope_line", { company: company.name, login: role.login });
  renderHeaderProfile(role.login);
  renderSideProfile(role.login, `${role.name} @ ${company.name}`);
  renderAccountModule();
}

// ---- Analytics charts -------------------------------------------------------
// Sample data for now; swap sampleAnalytics() for a backend endpoint later.

const THEME_KEY = "ai_vision_v2_theme";

function currentTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

// Both palettes validated against their own surface (light: #ffffff, dark: #0f172a).
function chartColors() {
  return currentTheme() === "dark"
    ? { blue: "#0284c7", green: "#15803d" }
    : { blue: "#2a78d6", green: "#008300" };
}
const CHART_W = 960;
const CHART_H = 250;
const CHART_PAD = { top: 22, right: 14, bottom: 30, left: 50 };
const chartRegistry = new Map();

function mulberry32(seed) {
  let a = seed | 0;
  return function () {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function lastDays(count) {
  const days = [];
  const now = new Date();
  for (let i = count - 1; i >= 0; i -= 1) {
    const day = new Date(now);
    day.setDate(now.getDate() - i);
    days.push(day);
  }
  return days;
}

function shortDate(day) {
  return day.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function sampleAnalytics() {
  const rand = mulberry32(20260717);
  const companies = lastDays(30).map((date, index) => ({
    date,
    value: Math.max(0, Math.round(rand() * 3 + index / 14 - 0.4)),
  }));
  const uptime = lastDays(7).map((date) => ({
    date,
    value: Math.round((88 + rand() * 11.5) * 10) / 10,
  }));
  const movements = lastDays(14).map((date) => ({
    date,
    in: Math.round(22 + rand() * 38),
    out: Math.round(16 + rand() * 36),
  }));
  return { companies, uptime, movements };
}

function emptyMovements() {
  return lastDays(14).map((date) => ({ date, in: 0, out: 0 }));
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

// /api/warehouse/movements returns YOLO warehouse ledger rows. In appearance
// mode, an IN row is created when a tracked item is first recognized, even if
// it stays still in the frame.
function aggregateMovements(movements) {
  const days = emptyMovements();
  for (const movement of movements || []) {
    const at = new Date(movement.created_at);
    if (Number.isNaN(at.getTime())) continue;
    const bucket = days.find((day) => sameDay(day.date, at));
    if (!bucket) continue;
    if (movement.direction === "IN") bucket.in += Number(movement.quantity || 1);
  }
  return days;
}

function timeAgo(timestamp) {
  const at = new Date(timestamp);
  if (Number.isNaN(at.getTime())) return "";
  const seconds = Math.max(0, Math.round((Date.now() - at.getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function movementDimensionsText(movement) {
  const width = Number(movement.estimated_width_m);
  const height = Number(movement.estimated_height_m);
  const depth = Number(movement.estimated_depth_m);
  if (![width, height, depth].every(Number.isFinite)) return "";
  return `${width.toFixed(2)} x ${height.toFixed(2)} x ${depth.toFixed(2)} m`;
}

function checkInCameraTotals(movements) {
  const totals = new Map();
  for (const movement of movements || []) {
    if (movement.direction !== "IN") continue;
    const cameraName = String(movement.camera_id || "Unknown camera");
    const quantity = Math.max(1, Number(movement.quantity || 1));
    totals.set(cameraName, (totals.get(cameraName) || 0) + quantity);
  }
  return Array.from(totals.entries())
    .map(([cameraName, quantity]) => ({ cameraName, quantity }))
    .sort((a, b) => b.quantity - a.quantity || a.cameraName.localeCompare(b.cameraName));
}

function checkInCameraTotalsHtml(movements) {
  const totals = checkInCameraTotals(movements);
  if (!totals.length) return "";
  return `
    <div class="camera-total-list" aria-label="Recognized objects by camera">
      ${totals
        .map(
          (entry) => `
            <div class="camera-total-row">
              <span>${escapeHtml(entry.cameraName)}</span>
              <strong>${entry.quantity.toLocaleString()} objects</strong>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function recentActivityHtml(movements) {
  const checkIns = (movements || []).filter((movement) => movement.direction === "IN");
  if (!checkIns.length) {
    return `<div class="alert-empty-state">
      <span class="alert-dot" style="background:var(--good)"></span>
      <div class="alert-main"><strong>No AI Check-ins yet</strong><small>YOLO will add items here when it recognizes stock in view, even if the item stays still.</small></div>
    </div>`;
  }
  const cameraTotals = checkInCameraTotalsHtml(checkIns);
  const recentRows = checkIns
    .slice(0, 10)
    .map((movement) => {
      const quantity = Number(movement.quantity || 1);
      const quantityLabel = quantity > 1 ? `${quantity}x ` : "";
      const dimensions = movementDimensionsText(movement);
      const meta = [movement.camera_id, timeAgo(movement.created_at), dimensions || null]
        .filter(Boolean)
        .join(" - ");
      return `
        <div class="alert-row">
          <span class="alert-dot" style="background:var(--good)"></span>
          <div class="alert-main"><strong>AI Check in: ${escapeHtml(quantityLabel)}${escapeHtml(movement.product_name)}</strong><small>${escapeHtml(meta)}</small></div>
        </div>
      `;
    })
    .join("");
  return `${cameraTotals}${recentRows}`;
}
function axisMax(value) {
  const candidates = [2, 4, 5, 8, 10, 20, 30, 40, 50, 60, 80, 100, 200, 500, 1000];
  return candidates.find((candidate) => candidate >= value) || Math.ceil(value / 1000) * 1000;
}

function axisTicks(max, min = 0) {
  const span = max - min;
  let step;
  if (span <= 6) step = 1;
  else step = [4, 3, 2].map((parts) => span / parts).find((candidate) => Number.isInteger(candidate)) || span / 4;
  const ticks = [];
  for (let v = min; v <= max + 1e-9; v += step) ticks.push(+v.toFixed(2));
  return ticks;
}

function chartScales({ count, yMin, yMax }) {
  const plotW = CHART_W - CHART_PAD.left - CHART_PAD.right;
  const plotH = CHART_H - CHART_PAD.top - CHART_PAD.bottom;
  return {
    plotW,
    plotH,
    slotW: plotW / count,
    x: (index) => CHART_PAD.left + (plotW / count) * index,
    xCenter: (index) => CHART_PAD.left + (plotW / count) * (index + 0.5),
    y: (value) => CHART_PAD.top + plotH * (1 - (value - yMin) / (yMax - yMin)),
  };
}

function gridSvg(ticks, yMin, yMax, scale, formatTick) {
  return ticks
    .map((tick) => {
      const y = scale.y(tick);
      const isBase = tick === yMin;
      return `
        <line x1="${CHART_PAD.left}" x2="${CHART_W - CHART_PAD.right}" y1="${y}" y2="${y}"
              class="${isBase ? "chart-baseline" : "chart-gridline"}" />
        <text x="${CHART_PAD.left - 8}" y="${y + 3.5}" class="chart-tick" text-anchor="end">${formatTick(tick)}</text>
      `;
    })
    .join("");
}

function xLabelIndexes(count, want) {
  if (count <= want) return Array.from({ length: count }, (_, index) => index);
  const step = (count - 1) / (want - 1);
  return Array.from({ length: want }, (_, index) => Math.round(index * step));
}

function xLabelsSvg(points, scale, want = 5) {
  return xLabelIndexes(points.length, want)
    .map((index) => `<text x="${scale.xCenter(index)}" y="${CHART_H - 8}" class="chart-tick" text-anchor="middle">${shortDate(points[index].date)}</text>`)
    .join("");
}

function roundedBarPath(x, yTop, width, yBase) {
  const height = yBase - yTop;
  if (height <= 0) return "";
  const r = Math.min(4, height, width / 2);
  return `M ${x} ${yBase}
          L ${x} ${yTop + r}
          Q ${x} ${yTop} ${x + r} ${yTop}
          L ${x + width - r} ${yTop}
          Q ${x + width} ${yTop} ${x + width} ${yTop + r}
          L ${x + width} ${yBase} Z`;
}

function barChartSvg(id, points, { color, formatValue }) {
  const dataMax = Math.max(...points.map((point) => point.value));
  const yMax = axisMax(dataMax || 1);
  const scale = chartScales({ count: points.length, yMin: 0, yMax });
  const yBase = scale.y(0);
  const barW = Math.max(3, scale.slotW * 0.62);
  const maxIndex = points.reduce((best, point, index) => (point.value > points[best].value ? index : best), 0);

  const bars = points
    .map((point, index) => {
      const x = scale.xCenter(index) - barW / 2;
      const yTop = scale.y(point.value);
      const label =
        index === maxIndex && point.value > 0
          ? `<text x="${scale.xCenter(index)}" y="${yTop - 6}" class="chart-value" text-anchor="middle">${formatValue(point.value)}</text>`
          : "";
      return `
        <g class="chart-slot" data-index="${index}">
          <rect x="${scale.x(index)}" y="${CHART_PAD.top}" width="${scale.slotW}" height="${scale.plotH}" fill="transparent" />
          <path d="${roundedBarPath(x, yTop, barW, yBase)}" fill="${color}" />
          ${label}
        </g>
      `;
    })
    .join("");

  return `
    <svg viewBox="0 0 ${CHART_W} ${CHART_H}" role="img" aria-label="Bar chart" data-chart-svg="${id}">
      ${gridSvg(axisTicks(yMax), 0, yMax, scale, formatValue)}
      ${bars}
      ${xLabelsSvg(points, scale)}
    </svg>
  `;
}

function lineChartSvg(id, points, { color, yMin, yMax, formatValue }) {
  const scale = chartScales({ count: points.length, yMin, yMax });
  const coords = points.map((point, index) => [scale.xCenter(index), scale.y(point.value)]);
  const path = coords.map(([x, y], index) => `${index ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const [lastX, lastY] = coords[coords.length - 1];
  const areaPath = `${path} L ${lastX.toFixed(1)} ${scale.y(yMin)} L ${coords[0][0].toFixed(1)} ${scale.y(yMin)} Z`;

  return `
    <svg viewBox="0 0 ${CHART_W} ${CHART_H}" role="img" aria-label="Line chart" data-chart-svg="${id}">
      ${gridSvg(axisTicks(yMax, yMin), yMin, yMax, scale, formatValue)}
      <path d="${areaPath}" fill="${color}" opacity="0.14" />
      <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
      <line class="chart-crosshair" x1="0" x2="0" y1="${CHART_PAD.top}" y2="${CHART_PAD.top + scale.plotH}" hidden />
      <circle class="chart-focus" r="4.5" fill="${color}" stroke="var(--panel-strong)" stroke-width="2" hidden />
      <text x="${lastX - 8}" y="${lastY - 10}" class="chart-value" text-anchor="end">${formatValue(points[points.length - 1].value)}</text>
      ${xLabelsSvg(points, scale, points.length)}
    </svg>
  `;
}

function groupedBarChartSvg(id, points, { seriesKeys, seriesLabels, colors, formatValue }) {
  const dataMax = Math.max(...points.flatMap((point) => seriesKeys.map((key) => point[key])));
  const yMax = axisMax(dataMax || 1);
  const scale = chartScales({ count: points.length, yMin: 0, yMax });
  const yBase = scale.y(0);
  const gap = 2;
  const barW = Math.max(3, (scale.slotW * 0.66 - gap) / seriesKeys.length);

  const groups = points
    .map((point, index) => {
      const groupW = barW * seriesKeys.length + gap;
      const startX = scale.xCenter(index) - groupW / 2;
      const bars = seriesKeys
        .map((key, keyIndex) => {
          const x = startX + keyIndex * (barW + gap);
          const yTop = scale.y(point[key]);
          return `<path d="${roundedBarPath(x, yTop, barW, yBase)}" fill="${colors[keyIndex]}" />`;
        })
        .join("");
      return `
        <g class="chart-slot" data-index="${index}">
          <rect x="${scale.x(index)}" y="${CHART_PAD.top}" width="${scale.slotW}" height="${scale.plotH}" fill="transparent" />
          ${bars}
        </g>
      `;
    })
    .join("");

  return `
    <svg viewBox="0 0 ${CHART_W} ${CHART_H}" role="img" aria-label="Grouped bar chart" data-chart-svg="${id}">
      ${gridSvg(axisTicks(yMax), 0, yMax, scale, formatValue)}
      ${groups}
      ${xLabelsSvg(points, scale)}
    </svg>
  `;
}

function chartTableHtml(spec) {
  const header = `<tr><th>Date</th>${spec.series.map((series) => `<th>${escapeHtml(series.label)}</th>`).join("")}</tr>`;
  const rows = spec.points
    .map(
      (point) =>
        `<tr><td>${shortDate(point.date)}</td>${spec.series
          .map((series) => `<td>${spec.formatValue(point[series.key])}</td>`)
          .join("")}</tr>`
    )
    .join("");
  return `<div class="chart-table-wrap"><table class="chart-table"><thead>${header}</thead><tbody>${rows}</tbody></table></div>`;
}

function chartCardHtml(spec) {
  const legend =
    spec.series.length > 1
      ? `<div class="chart-legend">${spec.series
          .map((series, index) => `<span><i style="background:${spec.colors[index]}"></i>${escapeHtml(series.label)}</span>`)
          .join("")}</div>`
      : "";
  return `
    <article class="chart-card" data-chart="${spec.id}">
      <header class="chart-head">
        <div>
          <h3>${escapeHtml(spec.title)}</h3>
          <p class="chart-sub">${escapeHtml(spec.subtitle)}</p>
        </div>
        <button type="button" class="chart-toggle" data-chart-toggle="${spec.id}">Table</button>
      </header>
      ${legend}
      <div class="chart-body" data-chart-body="${spec.id}">${spec.svg}<div class="chart-tip" hidden></div></div>
    </article>
  `;
}

function tipHtml(spec, index) {
  const point = spec.points[index];
  const rows = spec.series
    .map(
      (series, seriesIndex) =>
        `<div><i style="background:${spec.colors[seriesIndex]}"></i>${escapeHtml(series.label)}: <strong>${spec.formatValue(point[series.key])}</strong></div>`
    )
    .join("");
  return `<em>${shortDate(point.date)}</em>${rows}`;
}

function moveTip(tip, body, clientX) {
  const rect = body.getBoundingClientRect();
  const x = clientX - rect.left;
  tip.style.left = `${Math.min(Math.max(x, 70), rect.width - 70)}px`;
}

function wireCharts(root) {
  root.querySelectorAll("[data-chart]").forEach((card) => {
    const spec = chartRegistry.get(card.dataset.chart);
    if (!spec) return;
    const body = card.querySelector("[data-chart-body]");
    const tip = () => card.querySelector(".chart-tip");

    card.querySelector("[data-chart-toggle]").addEventListener("click", (event) => {
      spec.showTable = !spec.showTable;
      event.target.textContent = spec.showTable ? "Chart" : "Table";
      body.innerHTML = spec.showTable ? chartTableHtml(spec) : `${spec.svg}<div class="chart-tip" hidden></div>`;
    });

    body.addEventListener("pointerleave", () => {
      const tipEl = tip();
      if (tipEl) tipEl.hidden = true;
      const svg = body.querySelector("svg");
      svg?.querySelector(".chart-crosshair")?.setAttribute("hidden", "");
      svg?.querySelector(".chart-focus")?.setAttribute("hidden", "");
    });

    body.addEventListener("pointermove", (event) => {
      const svg = body.querySelector("svg");
      const tipEl = tip();
      if (!svg || !tipEl || spec.showTable) return;
      const svgRect = svg.getBoundingClientRect();
      const xRatio = (event.clientX - svgRect.left) / svgRect.width;
      const plotStart = CHART_PAD.left / CHART_W;
      const plotEnd = (CHART_W - CHART_PAD.right) / CHART_W;
      if (xRatio < plotStart || xRatio > plotEnd) return;
      const index = Math.min(
        spec.points.length - 1,
        Math.max(0, Math.floor(((xRatio - plotStart) / (plotEnd - plotStart)) * spec.points.length))
      );
      tipEl.innerHTML = tipHtml(spec, index);
      tipEl.hidden = false;
      moveTip(tipEl, body, event.clientX);

      if (spec.type === "line") {
        const scale = chartScales({ count: spec.points.length, yMin: spec.yMin, yMax: spec.yMax });
        const crosshair = svg.querySelector(".chart-crosshair");
        const focus = svg.querySelector(".chart-focus");
        const cx = scale.xCenter(index);
        crosshair.setAttribute("x1", cx);
        crosshair.setAttribute("x2", cx);
        crosshair.removeAttribute("hidden");
        focus.setAttribute("cx", cx);
        focus.setAttribute("cy", scale.y(spec.points[index].value));
        focus.removeAttribute("hidden");
      }
    });
  });
}

function currentOperationalAlerts() {
  const summary = state.overview?.summary || {};
  const health = state.overview?.health || {};
  const cameraCount = Number(health.camera_count || 0);

  if (health.error) {
    return [{ title: "Detector error", where: String(health.error), sev: "critical", color: "#dc2626" }];
  }
  if (!summary.detector_running) {
    return [{ title: "Detector stopped", where: "Camera processing is not running", sev: "critical", color: "#dc2626" }];
  }
  if (cameraCount === 0) {
    return [{ title: "No camera feeds connected", where: "Detector is running without an active feed", sev: "high", color: "var(--bad)" }];
  }
  if (!health.last_frame_at) {
    return [{ title: "Waiting for camera frames", where: `${cameraCount} camera feed${cameraCount === 1 ? "" : "s"} connecting`, sev: "medium", color: "var(--warn)" }];
  }
  return [];
}

function renderAnalytics(container, catalogMode = false) {
  const data = sampleAnalytics();
  const count = (value) => String(Math.round(value));
  const pct = (value) => `${value}%`;

  const specs = [
    {
      id: "companies",
      type: "bar",
      title: "Companies activated",
      subtitle: "New companies per day — past 30 days",
      points: data.companies,
      series: [{ key: "value", label: "Companies" }],
      colors: [chartColors().blue],
      formatValue: count,
      svg: null,
    },
    {
      id: "uptime",
      type: "line",
      title: "Active cameras",
      subtitle: "Share of cameras online — past 7 days",
      points: data.uptime,
      series: [{ key: "value", label: "Online" }],
      colors: [chartColors().blue],
      formatValue: pct,
      yMin: 80,
      yMax: 100,
      svg: null,
    },
    {
      id: "movements",
      type: "grouped",
      title: "AI Check-ins",
      subtitle: "YOLO-recognized item entries per day - past 14 days (live)",
      points: emptyMovements(),
      series: [
        { key: "in", label: "AI Check in" },
      ],
      colors: [chartColors().blue],
      formatValue: count,
      svg: null,
    },
  ];

  specs.forEach((spec) => {
    if (spec.type === "bar") {
      spec.svg = barChartSvg(spec.id, spec.points, { color: spec.colors[0], formatValue: spec.formatValue });
    } else if (spec.type === "line") {
      spec.svg = lineChartSvg(spec.id, spec.points, {
        color: spec.colors[0],
        yMin: spec.yMin,
        yMax: spec.yMax,
        formatValue: spec.formatValue,
      });
    } else {
      spec.svg = groupedBarChartSvg(spec.id, spec.points, {
        seriesKeys: spec.series.map((series) => series.key),
        seriesLabels: spec.series.map((series) => series.label),
        colors: spec.colors,
        formatValue: spec.formatValue,
      });
    }
    spec.showTable = false;
    chartRegistry.set(spec.id, spec);
  });

  const alerts = currentOperationalAlerts();
  const health = state.overview?.health || {};
  const cameraCount = Number(health.camera_count || 0);
  const resources = [
    { name: "CPU Usage", pct: 42, color: "#2a78d6" },
    { name: "GPU Usage", pct: 67, color: "#7c3aed" },
    { name: "Storage Usage", pct: 58, color: "#0891b2" },
    { name: "Memory Usage", pct: 71, color: "#db2777" },
  ];
  container.innerHTML = `
    <p class="chart-note">${catalogMode ? "Operational overview with scheduled catalog recognition results below." : "Companies/uptime are sample data - AI Check-ins below are live."}</p>
    <div class="chart-grid">${specs.map(chartCardHtml).join("")}</div>
    <div class="ov-grid">
      <section class="ov-card">
        <h3>Active Alerts</h3>
        ${alerts.length
          ? alerts
              .map(
                (alert) => `
              <div class="alert-row">
                <span class="alert-dot" style="background:${alert.color}"></span>
                <div class="alert-main"><strong>${escapeHtml(alert.title)}</strong><small>${escapeHtml(alert.where)}</small></div>
                <span class="sev-chip ${alert.sev}">${alert.sev.charAt(0).toUpperCase() + alert.sev.slice(1)}</span>
              </div>
            `
              )
              .join("")
          : `<div class="alert-empty-state">
              <span class="alert-dot" style="background:var(--good)"></span>
              <div class="alert-main">
                <strong>No active alerts</strong>
                <small>Detector running · ${cameraCount} camera feed${cameraCount === 1 ? "" : "s"} connected</small>
              </div>
            </div>`}
      </section>
      <section class="ov-card">
        <h3>System Resources</h3>
        ${resources
          .map(
            (res) => `
              <div class="res-row">
                <div class="res-head"><strong>${res.name}</strong><span>${res.pct}%</span></div>
                <div class="res-bar"><i style="width:${res.pct}%;background:${res.color}"></i></div>
              </div>
            `
          )
          .join("")}
      </section>
      <section class="ov-card" data-recent-activity>
        <h3>AI Check in</h3>
        <div class="alert-empty-state">
          <span class="alert-dot" style="background:var(--good)"></span>
          <div class="alert-main"><strong>Loading…</strong></div>
        </div>
      </section>
    </div>
  `;
  wireCharts(container);
  void loadLiveWarehouseActivity(container);
}

async function loadLiveWarehouseActivity(container) {
  try {
    const { movements } = await accountsApi("/api/warehouse/movements?limit=200");
    if (!container.isConnected) return;

    const movementsSpec = chartRegistry.get("movements");
    if (movementsSpec) {
      movementsSpec.points = aggregateMovements(movements);
      movementsSpec.svg = groupedBarChartSvg("movements", movementsSpec.points, {
        seriesKeys: movementsSpec.series.map((series) => series.key),
        seriesLabels: movementsSpec.series.map((series) => series.label),
        colors: movementsSpec.colors,
        formatValue: movementsSpec.formatValue,
      });
      const body = container.querySelector('[data-chart-body="movements"]');
      if (body && !movementsSpec.showTable) {
        body.innerHTML = `${movementsSpec.svg}<div class="chart-tip" hidden></div>`;
      }
    }

    const activityCard = container.querySelector("[data-recent-activity]");
    if (activityCard) {
      activityCard.innerHTML = `<h3>AI Check in</h3>${recentActivityHtml(movements)}`;
    }
  } catch {
    const activityCard = container.querySelector("[data-recent-activity]");
    if (activityCard) {
      activityCard.innerHTML = `<h3>AI Check in</h3><div class="alert-empty-state">
        <span class="alert-dot" style="background:var(--bad)"></span>
        <div class="alert-main"><strong>Couldn't load activity</strong></div>
      </div>`;
    }
  }
}

async function load() {
  setLanguageToggleChrome();
  const [session, overview, streamsHealth] = await Promise.all([
    api("/api/v2/rbac/me"),
    api("/api/v2/head/overview"),
    api("/api/v2/streams/health").catch(() => ({ streams: [] })),
  ]);
  state.session = session;
  state.overview = overview;
  state.streams = streamsHealth.streams || [];
  const account = await resolveAccountFromHash();
  if (account) {
    renderAccountView(account);
    return;
  }
  els.pageTitle.textContent = t("header.head_dashboard");
  els.companiesSection.hidden = false;
  renderNavigation();
  renderSummary();
  renderScope();
  renderModuleContent();
}

function renderLoadFailure(error, retrying) {
  const message = error instanceof Error ? error.message : String(error || "Unknown error");
  els.scopeLine.textContent = retrying ? "Dashboard service connection interrupted — retrying…" : "Unable to load dashboard data";
  els.detectorState.textContent = retrying ? "Reconnecting…" : "Connection failed";
  els.detectorState.dataset.state = retrying ? "" : "bad";
  els.moduleContent.innerHTML = retrying
    ? `<div class="module-placeholder"><h3>Reconnecting to the dashboard service…</h3><p>The dashboard will resume automatically.</p></div>`
    : `<div class="module-placeholder">
        <h3>Dashboard data could not be loaded</h3>
        <p>${escapeHtml(message)}</p>
        <button type="button" data-retry-dashboard>Try again</button>
      </div>`;
}

async function loadDashboard(attempt = 0) {
  if (loadRetryTimer !== null) {
    window.clearTimeout(loadRetryTimer);
    loadRetryTimer = null;
  }
  try {
    await load();
    return true;
  } catch (error) {
    const retrying = attempt < LOAD_RETRY_DELAYS_MS.length;
    renderLoadFailure(error, retrying);
    if (retrying) {
      loadRetryTimer = window.setTimeout(() => loadDashboard(attempt + 1), LOAD_RETRY_DELAYS_MS[attempt]);
    } else {
      toast(error instanceof Error ? error.message : String(error));
    }
    return false;
  }
}

els.moduleContent.addEventListener("submit", (event) => {
  handleCompanySubmit(event);
  handleSettingsSubmit(event);
  handleAccountSubmit(event);
});
els.moduleContent.addEventListener("click", (event) => {
  if (event.target.closest("[data-retry-dashboard]")) {
    loadDashboard();
    return;
  }
  handleCompanyClick(event);
  handleSettingsClick(event);
  handleAccountClick(event);
});
els.moduleContent.addEventListener("input", handleCompanyInput);
els.moduleContent.addEventListener("change", handleSettingsChange);
els.moduleContent.addEventListener("change", handleCatalogImageChange);

els.sideCompanies.addEventListener("click", (event) => {
  const button = event.target.closest("[data-edit-company]");
  if (!button) return;
  const company = ccCompanyById(button.dataset.editCompany);
  if (!company) return;
  ccEditingCompany = company.id;
  ccEditValues = {
    companyName: company.name,
    roles: Object.fromEntries((company.roles || []).map((role) => [role.id, { name: role.name, login: role.login }])),
  };
  state.activeModule = "users";
  renderNavigation();
  renderModuleContent();
  els.moduleContent
    .querySelector(`[data-company-card="${ccEditingCompany}"]`)
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
});

els.moduleNav.addEventListener("click", (event) => {
  const accButton = event.target.closest("[data-acc-module]");
  if (accButton && accountState) {
    accountModule = accButton.dataset.accModule;
    renderAccountModule();
    return;
  }
  const button = event.target.closest("[data-module]");
  if (!button) return;
  state.activeModule = button.dataset.module;
  renderNavigation();
  renderModuleContent();
});

const SUN_SVG = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>`;
const MOON_SVG = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  els.themeToggle.innerHTML = theme === "dark" ? SUN_SVG : MOON_SVG;
  els.themeToggle.title = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
}

applyTheme(localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light");
setLanguageToggleChrome();

els.themeToggle.addEventListener("click", () => {
  const next = currentTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  localStorage.setItem(THEME_KEY, next);
  if (accountState) renderAccountModule();
  else renderModuleContent();
});

function applySidebarState(collapsed) {
  els.shell.classList.toggle("sidebar-collapsed", collapsed);
  els.sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
}

applySidebarState(localStorage.getItem("ai_vision_v2_sidebar") === "collapsed");

els.sidebarToggle.addEventListener("click", () => {
  const collapsed = !els.shell.classList.contains("sidebar-collapsed");
  applySidebarState(collapsed);
  localStorage.setItem("ai_vision_v2_sidebar", collapsed ? "collapsed" : "open");
});

els.languageToggle.addEventListener("click", () => {
  const next = currentLanguage() === "ru" ? "en" : "ru";
  localStorage.setItem(LANGUAGE_KEY, next);
  rerenderCurrentViewForLanguage();
  toast(t("toast.language_updated"));
});

els.refreshBtn.addEventListener("click", () => {
  loadDashboard().then((loaded) => {
    if (loaded) toast(t("toast.dashboard_refreshed"));
  });
});

window.addEventListener("hashchange", () => window.location.reload());

// setFeedBadgeLive() sets badge.textContent, which is itself a childList
// mutation on the badge - without filtering, that retriggers this observer,
// which calls reconcileLiveStreams() immediately, which sets the badge again,
// forming a tight loop. Only structural changes (feed elements added/removed)
// should resync; badge text updates are just a symptom of a reconcile already
// run.
const liveFrameObserver = new MutationObserver((mutations) => {
  const structuralChange = mutations.some((mutation) => {
    const target = mutation.target;
    return !(target instanceof Element && target.closest(".feed-transmitting"));
  });
  if (structuralChange) syncLiveFrameRefresh();
});
liveFrameObserver.observe(els.moduleContent, { childList: true, subtree: true });
document.addEventListener("visibilitychange", syncLiveFrameRefresh);
window.addEventListener("beforeunload", stopLiveFrameRefresh);

migrateLegacyLocalStorage()
  .then((result) => {
    if (!result) return;
    if (result.companiesCreated || result.rolesCreated) {
      const companyWord = result.companiesCreated === 1 ? "company" : "companies";
      const accountWord = result.rolesCreated === 1 ? "account" : "accounts";
      toast(
        `Recovered ${result.companiesCreated} ${companyWord} and ${result.rolesCreated} ${accountWord} from this browser onto the server — open Company Control for the new links.`
      );
    } else if (result.failures) {
      toast(`Could not automatically recover ${result.failures} saved item(s) from this browser. Recreate them in Company Control.`);
    }
  })
  .catch(() => {})
  .finally(() => {
    renderSideCompanies();
    updateBrandAvatar();
    loadDashboard();
  });

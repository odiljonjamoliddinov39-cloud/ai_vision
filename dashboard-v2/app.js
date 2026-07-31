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
  systemConfig: null,
};

const readCache = new Map();

function readCacheKey(scope, path) {
  return `${scope}:${path}`;
}

function clearReadCache(...prefixes) {
  if (!prefixes.length) {
    readCache.clear();
    return;
  }
  for (const key of Array.from(readCache.keys())) {
    if (prefixes.some((prefix) => key.startsWith(prefix))) {
      readCache.delete(key);
    }
  }
}

function cachedRead(key, loader, force = false) {
  if (!force && readCache.has(key)) {
    const cached = readCache.get(key);
    return cached instanceof Promise ? cached : Promise.resolve(cached);
  }
  const request = loader()
    .then((value) => {
      readCache.set(key, value);
      return value;
    })
    .catch((error) => {
      readCache.delete(key);
      throw error;
    });
  readCache.set(key, request);
  return request;
}

function invalidateDashboardReads() {
  clearReadCache();
  ccCompaniesCache = null;
  aiModulesCatalogCache = null;
  state.systemConfig = null;
}

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
    "menu.enterprise": "Enterprise Map",
    "menu.events": "Events",
    "menu.feed": "Camera Feed",
    "menu.ai_models": "AI Models",
    "menu.integrations": "Integrations",
    "menu.logs": "Logs",
    "menu.ai_modules": "AI Modules",
    "menu.result_analytics": "Result Analytics",
    "menu.zones": "Zones & Safety",
    "menu.settings": "Settings",
    "modules.count": "{count} functions",
    "modules.current_note": "Current baseline covers camera/NVR streaming, Stream Manager, catalog recognition, result analytics, exports and training tools. Remaining items are tracked as roadmap modules.",
    "modules.empty": "No functions match these filters.",
    "modules.feature": "Function",
    "modules.functions": "Functions",
    "modules.implemented": "Implemented",
    "modules.loading": "Loading AI video analytics modules...",
    "modules.partial": "Partial",
    "modules.planned": "Planned",
    "modules.search": "Search function",
    "modules.section": "Section",
    "modules.section_all": "All sections",
    "modules.sections": "Sections",
    "modules.source": "Spec version: 25 July 2026",
    "modules.status": "Status",
    "modules.status_all": "All statuses",
    "modules.status_done": "Implemented",
    "modules.status_partial": "Partial",
    "modules.status_planned": "Planned",
    "modules.shown": "Shown {visible} of {total}",
    "modules.subtitle": "Specification-driven roadmap for factory, production line, machine and warehouse video analytics.",
    "modules.title": "AI Video Analytics Modules",
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
    "result.ai_prediction": "AI prediction",
    "result.correct_name": "Correct name",
    "result.correct_name_ph": "What is it really?",
    "result.prompt_label": "Prompt",
    "result.prompt_ph": "Describe this object...",
    "result.save_correction": "Save",
    "result.correction_saved": "Saved - the system will learn this object.",
    "result.correct_name_required": "Enter the correct name first.",
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
    "menu.enterprise": "Структура",
    "menu.events": "События",
    "menu.feed": "Видеопоток",
    "menu.ai_models": "AI модели",
    "menu.integrations": "Интеграции",
    "menu.logs": "Журнал действий",
    "menu.ai_modules": "AI модули",
    "menu.result_analytics": "Аналитика результатов",
    "menu.zones": "Зоны и безопасность",
    "menu.settings": "Настройки",
    "modules.count": "{count} функций",
    "modules.current_note": "Текущая база уже покрывает камеры/NVR, Stream Manager, распознавание каталога, аналитику результатов, экспорт и инструменты обучения. Остальные пункты ведутся как roadmap-модули.",
    "modules.empty": "По этим фильтрам функции не найдены.",
    "modules.feature": "Функция",
    "modules.functions": "Функции",
    "modules.implemented": "Реализовано",
    "modules.loading": "Загрузка AI модулей видеоаналитики...",
    "modules.partial": "Частично",
    "modules.planned": "План",
    "modules.search": "Поиск функции",
    "modules.section": "Раздел",
    "modules.section_all": "Все разделы",
    "modules.sections": "Разделы",
    "modules.source": "Версия ТЗ: 25 июля 2026",
    "modules.status": "Статус",
    "modules.status_all": "Все статусы",
    "modules.status_done": "Реализовано",
    "modules.status_partial": "Частично",
    "modules.status_planned": "План",
    "modules.shown": "Показано {visible} из {total}",
    "modules.subtitle": "Roadmap по ТЗ для завода, производственных линий, станков и складов.",
    "modules.title": "AI модули видеоаналитики",
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
    "result.ai_prediction": "Прогноз ИИ",
    "result.correct_name": "Правильное название",
    "result.correct_name_ph": "Что это на самом деле?",
    "result.prompt_label": "Подсказка",
    "result.prompt_ph": "Опишите этот объект...",
    "result.save_correction": "Сохранить",
    "result.correction_saved": "Сохранено - система запомнит этот объект.",
    "result.correct_name_required": "Сначала введите правильное название.",
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

// One WebSocket multiplexes every mounted camera. The connection stays alive
// regardless of scroll position and avoids the browser's per-origin limit on
// separate long-lived MJPEG requests.
const LIVE_STREAM_RECONNECT_MS = 1500;
const LIVE_DETECTION_REFRESH_MS = 3000;
let liveFrameSocket = null;
let liveFrameSocketSlots = "";
let liveFrameReconnectTimer = null;
let liveDetectionTimer = null;
let liveDetectionLoading = false;
const liveFrameGenerations = new Map();
const liveFrameCache = new Map();
const liveDetectionsByCamera = new Map();
const liveDetectionsBySlot = new Map();

function setFeedBadgeLive(image, isLive) {
  const badge = image.parentElement?.querySelector(".feed-transmitting");
  if (!badge) return;
  badge.textContent = isLive ? t("status.live") : t("status.waiting_video");
  badge.classList.toggle("feed-stale-badge", !isLive);
}

function liveWebSocketUrl(slots) {
  const url = new URL(`${API_BASE}/api/live_ws`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("slots", slots);
  return url.toString();
}

function normalizeLiveCameraKey(value) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function uniqueLiveCameraAliases(values) {
  const seen = new Set();
  return values
    .map((value) => String(value || "").trim())
    .filter((value) => {
      const key = normalizeLiveCameraKey(value);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function liveDetectionBox(detection) {
  const bbox = detection?.bbox || detection?.box;
  if (Array.isArray(bbox) && bbox.length >= 4) {
    return { x1: Number(bbox[0]), y1: Number(bbox[1]), x2: Number(bbox[2]), y2: Number(bbox[3]) };
  }
  if (bbox && typeof bbox === "object") {
    return {
      x1: Number(bbox.x1 ?? bbox.left),
      y1: Number(bbox.y1 ?? bbox.top),
      x2: Number(bbox.x2 ?? bbox.right),
      y2: Number(bbox.y2 ?? bbox.bottom),
    };
  }
  return null;
}

function liveDetectionLabel(detection) {
  const name = detection?.inventory_name || detection?.class_name || detection?.label || detection?.name || "object";
  const quantity = Number(detection?.quantity || 0);
  const confidence = Number(detection?.confidence);
  const parts = [quantity > 1 ? `${quantity}x ${name}` : name];
  if (Number.isFinite(confidence) && confidence > 0) parts.push(`${Math.round(confidence * 100)}%`);
  return parts.join(" · ");
}

function liveDetectionAliasesForCanvas(canvas) {
  const slot = Number(canvas.dataset.liveSlot);
  const stream = slot ? streamStatusBySlot().get(slot) : null;
  return uniqueLiveCameraAliases([
    canvas.dataset.liveCamera,
    ...(canvas.dataset.liveCameraAliases || "").split("||"),
    stream?.name,
    stream?.camera_name,
    slot ? `slot-${slot}` : "",
    slot ? `Slot ${slot}` : "",
    slot ? `Camera ${slot}` : "",
    slot ? `NVR Camera ${slot}` : "",
  ]);
}

function liveDetectionsForCanvas(canvas) {
  const slot = Number(canvas.dataset.liveSlot);
  if (slot && liveDetectionsBySlot.has(slot)) return liveDetectionsBySlot.get(slot) || [];
  for (const alias of liveDetectionAliasesForCanvas(canvas)) {
    const detections = liveDetectionsByCamera.get(normalizeLiveCameraKey(alias));
    if (detections) return detections;
  }
  return [];
}

function liveDetectionOverlayForCanvas(canvas) {
  return canvas.parentElement?.querySelector("[data-live-detection-overlay]") || null;
}

function drawLiveDetectionOverlay(canvas, detections) {
  const overlay = liveDetectionOverlayForCanvas(canvas);
  if (!overlay || !canvas.width || !canvas.height) {
    if (overlay) overlay.dataset.liveDetectionCount = "0";
    return;
  }
  if (overlay.width !== canvas.width || overlay.height !== canvas.height) {
    overlay.width = canvas.width;
    overlay.height = canvas.height;
  }
  const ctx = overlay.getContext("2d");
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  if (!detections?.length) {
    overlay.dataset.liveDetectionCount = "0";
    return;
  }
  const width = canvas.width;
  const height = canvas.height;
  const lineWidth = Math.max(2, Math.round(width / 520));
  const fontSize = Math.max(13, Math.round(width / 88));
  let drawn = 0;
  ctx.save();
  ctx.lineWidth = lineWidth;
  ctx.font = `700 ${fontSize}px Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
  ctx.textBaseline = "top";
  detections.slice(0, 80).forEach((detection, index) => {
    const box = liveDetectionBox(detection);
    if (!box || [box.x1, box.y1, box.x2, box.y2].some((value) => !Number.isFinite(value))) return;
    const sourceWidth = Number(detection.frame_width || detection.frameWidth || detection.image_width || width) || width;
    const sourceHeight = Number(detection.frame_height || detection.frameHeight || detection.image_height || height) || height;
    const scaleX = width / sourceWidth;
    const scaleY = height / sourceHeight;
    const x = Math.max(0, Math.min(box.x1, box.x2) * scaleX);
    const y = Math.max(0, Math.min(box.y1, box.y2) * scaleY);
    const x2 = Math.min(width, Math.max(box.x1, box.x2) * scaleX);
    const y2 = Math.min(height, Math.max(box.y1, box.y2) * scaleY);
    const boxWidth = Math.max(0, x2 - x);
    const boxHeight = Math.max(0, y2 - y);
    if (boxWidth < 3 || boxHeight < 3) return;

    const color = index % 2 === 0 ? "#ef4444" : "#38bdf8";
    ctx.strokeStyle = color;
    ctx.shadowColor = "rgba(15, 23, 42, 0.5)";
    ctx.shadowBlur = lineWidth * 1.5;
    ctx.strokeRect(x, y, boxWidth, boxHeight);
    ctx.shadowBlur = 0;

    const label = liveDetectionLabel(detection);
    const labelWidth = Math.min(ctx.measureText(label).width + 14, width - 8);
    const labelHeight = fontSize + 8;
    const labelX = Math.min(Math.max(4, x), Math.max(4, width - labelWidth - 4));
    const labelY = y - labelHeight - 4 >= 4 ? y - labelHeight - 4 : Math.min(height - labelHeight - 4, y + 4);
    ctx.fillStyle = "rgba(15, 23, 42, 0.88)";
    ctx.fillRect(labelX, labelY, labelWidth, labelHeight);
    ctx.fillStyle = "#ffffff";
    ctx.fillText(label, labelX + 7, labelY + 4, labelWidth - 14);
    drawn += 1;
  });
  ctx.restore();
  overlay.dataset.liveDetectionCount = String(drawn);
}

function updateLiveDetectionCache(payload) {
  liveDetectionsByCamera.clear();
  liveDetectionsBySlot.clear();
  const byCamera = payload?.detections || payload?.spatial || {};
  Object.entries(byCamera).forEach(([cameraName, detections]) => {
    if (!Array.isArray(detections)) return;
    liveDetectionsByCamera.set(normalizeLiveCameraKey(cameraName), detections);
  });
  (payload?.cameras || []).forEach((camera) => {
    const slot = Number(camera?.slot_number ?? camera?.slotNumber);
    const cameraName = normalizeLiveCameraKey(camera?.name || camera?.camera_name);
    if (!slot || !cameraName) return;
    const detections = liveDetectionsByCamera.get(cameraName);
    if (detections) liveDetectionsBySlot.set(slot, detections);
  });
}

function redrawVisibleDetectionOverlays() {
  const surfaces = Array.from(els.moduleContent.querySelectorAll("[data-live-frame]"));
  surfaces.forEach((canvas) => {
    drawLiveDetectionOverlay(canvas, liveDetectionsForCanvas(canvas));
  });
}

async function refreshLiveDetections() {
  const hasLiveFrames = Boolean(els.moduleContent.querySelector("[data-live-frame]"));
  if (!hasLiveFrames) {
    stopLiveDetectionRefresh();
    return;
  }
  if (liveDetectionLoading) return;
  liveDetectionLoading = true;
  try {
    const payload = await api("/api/v2/detections/latest", { force: true });
    updateLiveDetectionCache(payload);
    redrawVisibleDetectionOverlays();
  } catch {
    // Live video must continue even if detector health is temporarily unavailable.
  } finally {
    liveDetectionLoading = false;
  }
}

function syncLiveDetectionRefresh() {
  const hasLiveFrames = Boolean(els.moduleContent.querySelector("[data-live-frame]"));
  if (!hasLiveFrames) {
    stopLiveDetectionRefresh();
    return;
  }
  if (liveDetectionTimer === null) {
    refreshLiveDetections();
    liveDetectionTimer = window.setInterval(refreshLiveDetections, LIVE_DETECTION_REFRESH_MS);
  } else {
    redrawVisibleDetectionOverlays();
  }
}

function stopLiveDetectionRefresh() {
  if (liveDetectionTimer !== null) {
    window.clearInterval(liveDetectionTimer);
    liveDetectionTimer = null;
  }
}

function renderLiveSocketFrame(slot, jpegBytes, cacheFrame = true) {
  if (cacheFrame) liveFrameCache.set(slot, jpegBytes);
  const generation = (liveFrameGenerations.get(slot) || 0) + 1;
  liveFrameGenerations.set(slot, generation);
  createImageBitmap(new Blob([jpegBytes], { type: "image/jpeg" }))
    .then((bitmap) => {
      if (liveFrameGenerations.get(slot) !== generation) {
        bitmap.close();
        return;
      }
      const canvases = Array.from(
        els.moduleContent.querySelectorAll(`[data-live-frame][data-live-slot="${slot}"]`)
      );
      canvases.forEach((canvas) => {
        const resized = canvas.width !== bitmap.width || canvas.height !== bitmap.height;
        if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
          canvas.width = bitmap.width;
          canvas.height = bitmap.height;
        }
        canvas.getContext("2d", { alpha: false }).drawImage(bitmap, 0, 0);
        if (resized) drawLiveDetectionOverlay(canvas, liveDetectionsForCanvas(canvas));
        delete canvas.dataset.livePriming;
        canvas.classList.remove("feed-stale");
        canvas.removeAttribute("title");
        canvas.dataset.liveLastUpdate = new Date().toISOString();
        setFeedBadgeLive(canvas, true);
      });
      bitmap.close();
    })
    .catch(() => {});
}

function scheduleLiveSocketReconnect() {
  if (liveFrameReconnectTimer !== null) return;
  liveFrameReconnectTimer = window.setTimeout(() => {
    liveFrameReconnectTimer = null;
    syncLiveFrameRefresh();
  }, LIVE_STREAM_RECONNECT_MS);
}

function reconcileLiveStreams() {
  const surfaces = Array.from(els.moduleContent.querySelectorAll("[data-live-frame]"));
  const slotNumbers = [...new Set(
    surfaces.map((surface) => Number(surface.dataset.liveSlot)).filter(Boolean)
  )].sort((left, right) => left - right);
  const slots = slotNumbers.join(",");
  if (!slots) {
    // Leaving the feed view must not behave like switching the cameras off.
    // Keep the multiplexed browser connection alive so the current frames are
    // ready when the operator returns. The server-side Stream Manager remains
    // the permanent RTSP owner independently of this connection.
    return;
  }

  // Paint the most recently received frame synchronously with mounting the
  // feed grid. A fresh WebSocket frame will replace it on the next server tick.
  slotNumbers.forEach((slot) => {
    const cachedFrame = liveFrameCache.get(slot);
    if (cachedFrame) renderLiveSocketFrame(slot, cachedFrame, false);
  });
  if (
    liveFrameSocket
    && liveFrameSocketSlots === slots
    && (liveFrameSocket.readyState === WebSocket.OPEN
      || liveFrameSocket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  stopLiveFrameRefresh();
  liveFrameSocketSlots = slots;
  const socket = new WebSocket(liveWebSocketUrl(slots));
  socket.binaryType = "arraybuffer";
  liveFrameSocket = socket;
  socket.addEventListener("message", (event) => {
    const payload = new Uint8Array(event.data);
    if (payload.byteLength <= 2) return;
    const slot = new DataView(payload.buffer, payload.byteOffset, 2).getUint16(0);
    renderLiveSocketFrame(slot, payload.slice(2));
  });
  socket.addEventListener("close", () => {
    if (liveFrameSocket !== socket) return;
    liveFrameSocket = null;
    scheduleLiveSocketReconnect();
  });
  socket.addEventListener("error", () => socket.close());
}

function stopLiveFrameRefresh() {
  if (liveFrameReconnectTimer !== null) {
    window.clearTimeout(liveFrameReconnectTimer);
    liveFrameReconnectTimer = null;
  }
  const socket = liveFrameSocket;
  liveFrameSocket = null;
  liveFrameSocketSlots = "";
  if (socket && socket.readyState < WebSocket.CLOSING) socket.close();
}

function syncLiveFrameRefresh() {
  const hasLiveFrames = Boolean(els.moduleContent.querySelector("[data-live-frame]"));
  if (!hasLiveFrames) {
    stopLiveDetectionRefresh();
    return;
  }
  reconcileLiveStreams();
  syncLiveDetectionRefresh();
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

async function api(path, options = {}) {
  const { force = false, ...fetchOptions } = options;
  const method = String(fetchOptions.method || "GET").toUpperCase();
  if (!force && method === "GET" && !fetchOptions.body) {
    return cachedRead(readCacheKey("api", path), () => api(path, { ...fetchOptions, force: true }), force);
  }
  const headers = {
    "Content-Type": "application/json",
    "X-AI-Role": state.role,
    "X-AI-User-Name": "Dashboard V2 Preview",
    "X-AI-Company": "All Companies",
    ...(fetchOptions.headers || {}),
  };
  if (fetchOptions.body instanceof FormData) delete headers["Content-Type"];
  const response = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  if (method !== "GET") clearReadCache();
  if (response.status === 204) return null;
  const payload = await response.json();
  if (method === "GET" && !fetchOptions.body) readCache.set(readCacheKey("api", path), payload);
  return payload;
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
  enterprise: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18M5 21V7l7-4 7 4v14M9 9h1M9 13h1M14 9h1M14 13h1M10 21v-4h4v4"/></svg>`,
  analytics: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 3v18h18"/><path d="M7 15l4-6 4 3 5-8"/></svg>`,
  events: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></svg>`,
  result_analytics: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/></svg>`,
  ai_modules: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16v16H4z"/><path d="M9 4v16M15 4v16M4 9h16M4 15h16"/></svg>`,
  ai_models: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 15h3M1 9h3M1 15h3M10 10h4v4h-4z"/></svg>`,
  integrations: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 7H7a5 5 0 0 0 0 10h2M15 7h2a5 5 0 0 1 0 10h-2M8 12h8"/></svg>`,
  zones: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3V6z"/><path d="M9 3v15M15 6v15"/></svg>`,
  feed: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>`,
  ai: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="7" width="16" height="12" rx="2"/><path d="M12 7V4M8 4h8M9 12h.01M15 12h.01M9 16h6"/></svg>`,
  dimension: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.27 6.96 12 12.01l8.73-5.05M12 22.08V12"/></svg>`,
  logs: `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12a2 2 0 0 1 2 2v16l-4-2-4 2-4-2-4 2V5a2 2 0 0 1 2-2z"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>`,
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
          return `<figure><canvas data-live-frame data-live-slot="${slot}" role="img" aria-label="Camera slot ${slot}" style="display:block;width:100%;aspect-ratio:16/9"></canvas><figcaption>Slot ${slot}</figcaption></figure>`;
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
  const { force = false, ...fetchOptions } = options;
  const method = String(fetchOptions.method || "GET").toUpperCase();
  if (!force && method === "GET" && !fetchOptions.body) {
    return cachedRead(readCacheKey("accounts", path), () => accountsApi(path, { ...fetchOptions, force: true }), force);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(fetchOptions.headers || {}) },
    ...fetchOptions,
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
  if (method !== "GET") clearReadCache();
  if (response.status === 204) return null;
  const payload = await response.json();
  if (method === "GET" && !fetchOptions.body) readCache.set(readCacheKey("accounts", path), payload);
  return payload;
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
let systemConfigLoading = null;

async function ensureProfileLoaded() {
  if (ccProfileCache) return ccProfileCache;
  ccProfileCache = await accountsApi("/api/v2/admin/profile");
  return ccProfileCache;
}

async function ensureSystemConfigLoaded(force = false) {
  if (!force && state.systemConfig) return state.systemConfig;
  if (!force && systemConfigLoading) return systemConfigLoading;
  systemConfigLoading = api("/api/config", { force })
    .then((config) => {
      state.systemConfig = config || {};
      return state.systemConfig;
    })
    .finally(() => {
      systemConfigLoading = null;
    });
  return systemConfigLoading;
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
  if (!ccProfileCache || !state.systemConfig) {
    container.innerHTML = `<p class="chart-note">${escapeHtml(uiText("Loading settings...", "Загрузка настроек..."))}</p>`;
    Promise.all([ensureProfileLoaded(), ensureSystemConfigLoaded()])
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
  const config = state.systemConfig || {};
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
    ${systemSettingsHtml(config)}
  `;
}

function configPathValue(config, path, fallback = "") {
  let cursor = config || {};
  for (const part of path.split(".")) {
    if (!cursor || typeof cursor !== "object" || !(part in cursor)) return fallback;
    cursor = cursor[part];
  }
  return cursor ?? fallback;
}

function configNumber(config, path, fallback) {
  const value = Number(configPathValue(config, path, fallback));
  return Number.isFinite(value) ? value : fallback;
}

function configBool(config, path, fallback = false) {
  const value = configPathValue(config, path, fallback);
  return value === true || value === "true" || value === 1;
}

function configListText(config, path) {
  const value = configPathValue(config, path, []);
  return Array.isArray(value) ? value.join("\n") : "";
}

function settingsInputHtml({ label, name, value, type = "text", min = "", max = "", step = "", required = true }) {
  const attrs = [
    `name="${escapeAttr(name)}"`,
    `type="${escapeAttr(type)}"`,
    `value="${escapeAttr(value)}"`,
    min !== "" ? `min="${escapeAttr(min)}"` : "",
    max !== "" ? `max="${escapeAttr(max)}"` : "",
    step !== "" ? `step="${escapeAttr(step)}"` : "",
    required ? "required" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return `
    <label class="settings-field">
      <span>${escapeHtml(label)}</span>
      <input ${attrs} />
    </label>
  `;
}

function settingsTextareaHtml(label, name, value) {
  return `
    <label class="settings-field settings-field-wide">
      <span>${escapeHtml(label)}</span>
      <textarea name="${escapeAttr(name)}" rows="4">${escapeHtml(value)}</textarea>
    </label>
  `;
}

function settingsCheckboxHtml(label, name, checked) {
  return `
    <label class="settings-check">
      <input name="${escapeAttr(name)}" type="checkbox" ${checked ? "checked" : ""} />
      <span>${escapeHtml(label)}</span>
    </label>
  `;
}

function systemSettingsHtml(config) {
  return `
    <form class="settings-config-form" data-settings-form="system-config">
      <div class="settings-form-head">
        <div>
          <h3>${escapeHtml(uiText("System / AI settings", "Системные / AI настройки"))}</h3>
          <p>${escapeHtml(uiText("Saved to server config. Restart detector after changing model or YOLO runtime values.", "Сохраняется в конфиг сервера. После изменения модели или YOLO-параметров перезапустите детектор."))}</p>
        </div>
        <button type="button" class="cc-chip" data-settings-action="reload-config">${escapeHtml(uiText("Reload", "Обновить"))}</button>
      </div>

      <section class="settings-section">
        <h4>${escapeHtml(uiText("YOLO detection", "YOLO детекция"))}</h4>
        <div class="settings-field-grid">
          ${settingsInputHtml({ label: uiText("Model path", "Путь модели"), name: "model_path", value: configPathValue(config, "detection.model_path", "yoloe-26s-seg.pt") })}
          ${settingsInputHtml({ label: uiText("Fallback model", "Резервная модель"), name: "fallback_model_path", value: configPathValue(config, "detection.fallback_model_path", "yolov8s-worldv2.pt") })}
          ${settingsInputHtml({ label: uiText("Device", "Устройство"), name: "device", value: configPathValue(config, "detection.device", "auto") })}
          ${settingsInputHtml({ label: uiText("Confidence threshold", "Порог confidence"), name: "confidence_threshold", type: "number", value: configNumber(config, "detection.confidence_threshold", 0.4), min: 0, max: 1, step: 0.01 })}
          ${settingsInputHtml({ label: uiText("IoU threshold", "Порог IoU"), name: "iou_threshold", type: "number", value: configNumber(config, "detection.iou_threshold", 0.55), min: 0, max: 1, step: 0.01 })}
          ${settingsInputHtml({ label: uiText("Max detections", "Макс. детекций"), name: "max_detections", type: "number", value: configNumber(config, "detection.max_detections", 300), min: 1, max: 3000, step: 1 })}
          ${settingsInputHtml({ label: uiText("Image size", "Размер кадра"), name: "image_size", type: "number", value: configNumber(config, "detection.image_size", 640), min: 320, max: 1920, step: 32 })}
          ${settingsInputHtml({ label: uiText("Target FPS", "Целевой FPS"), name: "target_fps", type: "number", value: configNumber(config, "detection.target_fps", 2), min: 0.1, max: 60, step: 0.1 })}
          ${settingsInputHtml({ label: uiText("Stale frame ms", "Устаревший кадр, ms"), name: "stale_after_ms", type: "number", value: configNumber(config, "detection.stale_after_ms", 3000), min: 250, max: 60000, step: 50 })}
          ${settingsInputHtml({ label: uiText("Concurrent cameras", "Параллельные камеры"), name: "max_concurrent_cameras", type: "number", value: configNumber(config, "detection.max_concurrent_cameras", 0), min: 0, max: 100, step: 1 })}
          ${settingsCheckboxHtml(uiText("Class-agnostic NMS", "Class-agnostic NMS"), "class_agnostic_nms", configBool(config, "detection.class_agnostic_nms", false))}
          ${settingsTextareaHtml(uiText("Classes", "Классы"), "classes", configListText(config, "detection.classes"))}
          ${settingsTextareaHtml(uiText("Class prompts", "Prompts классов"), "class_prompts", configListText(config, "detection.class_prompts"))}
        </div>
      </section>

      <section class="settings-section">
        <h4>${escapeHtml(uiText("Recognition", "Распознавание"))}</h4>
        <div class="settings-field-grid">
          ${settingsCheckboxHtml(uiText("Recognition enabled", "Распознавание включено"), "recognition_enabled", configBool(config, "recognition.enabled", true))}
          ${settingsInputHtml({ label: uiText("Provider", "Провайдер"), name: "recognition_provider", value: configPathValue(config, "recognition.provider", "gemini") })}
          ${settingsInputHtml({ label: uiText("Recognition model", "Модель распознавания"), name: "recognition_model", value: configPathValue(config, "recognition.model", "gemini-3.1-flash-lite") })}
          ${settingsInputHtml({ label: uiText("Confidence threshold", "Порог confidence"), name: "recognition_confidence_threshold", type: "number", value: configNumber(config, "recognition.confidence_threshold", 0.9), min: 0, max: 1, step: 0.01 })}
          ${settingsInputHtml({ label: uiText("Similarity threshold", "Порог similarity"), name: "recognition_similarity_threshold", type: "number", value: configNumber(config, "recognition.similarity_threshold", 0.62), min: 0, max: 1, step: 0.01 })}
          ${settingsInputHtml({ label: uiText("Cache expiration, sec", "Кеш, секунд"), name: "recognition_cache_expiration", type: "number", value: configNumber(config, "recognition.cache_expiration", 1800), min: 0, max: 86400, step: 60 })}
          ${settingsInputHtml({ label: uiText("Timeout, sec", "Таймаут, секунд"), name: "recognition_timeout", type: "number", value: configNumber(config, "recognition.timeout", 30), min: 1, max: 300, step: 1 })}
          ${settingsInputHtml({ label: uiText("Retries", "Повторы"), name: "recognition_retries", type: "number", value: configNumber(config, "recognition.retries", 2), min: 0, max: 10, step: 1 })}
          ${settingsInputHtml({ label: uiText("Max workers", "Max workers"), name: "recognition_max_workers", type: "number", value: configNumber(config, "recognition.max_workers", 2), min: 1, max: 32, step: 1 })}
          ${settingsCheckboxHtml(uiText("Cache enabled", "Кеш включен"), "recognition_cache_enabled", configBool(config, "recognition.cache_enabled", true))}
          ${settingsCheckboxHtml(uiText("Catalog only", "Только каталог"), "recognition_catalog_only", configBool(config, "recognition.catalog_only", true))}
        </div>
      </section>

      <section class="settings-section">
        <h4>${escapeHtml(uiText("Live video", "Live видео"))}</h4>
        <div class="settings-field-grid">
          ${settingsCheckboxHtml(uiText("Show FPS", "Показывать FPS"), "show_fps", configBool(config, "display.show_fps", true))}
          ${settingsCheckboxHtml(uiText("Live feed enabled", "Live поток включен"), "live_feed_enabled", configBool(config, "display.live_feed_enabled", true))}
          ${settingsInputHtml({ label: uiText("Frame width", "Ширина кадра"), name: "live_frame_width", type: "number", value: configNumber(config, "display.live_frame_width", 1280), min: 160, max: 3840, step: 16 })}
          ${settingsInputHtml({ label: uiText("JPEG quality", "JPEG качество"), name: "live_frame_jpeg_quality", type: "number", value: configNumber(config, "display.live_frame_jpeg_quality", 85), min: 30, max: 100, step: 1 })}
        </div>
      </section>

      <section class="settings-section">
        <h4>${escapeHtml(uiText("Spatial / 3D", "Spatial / 3D"))}</h4>
        <div class="settings-field-grid">
          ${settingsCheckboxHtml(uiText("Spatial analysis enabled", "Spatial анализ включен"), "spatial_enabled", configBool(config, "spatial_analysis.enabled", true))}
          ${settingsInputHtml({ label: uiText("Horizontal FOV", "Горизонтальный FOV"), name: "horizontal_fov_degrees", type: "number", value: configNumber(config, "spatial_analysis.horizontal_fov_degrees", 90), min: 20, max: 160, step: 0.1 })}
          ${settingsInputHtml({ label: uiText("Camera height, m", "Высота камеры, м"), name: "camera_height_m", type: "number", value: configNumber(config, "spatial_analysis.camera_height_m", 1.2), min: 0.1, max: 20, step: 0.1 })}
          ${settingsInputHtml({ label: uiText("Horizon Y ratio", "Горизонт Y ratio"), name: "horizon_y_ratio", type: "number", value: configNumber(config, "spatial_analysis.horizon_y_ratio", 0.28), min: 0, max: 1, step: 0.01 })}
          ${settingsInputHtml({ label: uiText("Min distance, m", "Мин. дистанция, м"), name: "min_distance_m", type: "number", value: configNumber(config, "spatial_analysis.min_distance_m", 0.5), min: 0.1, max: 100, step: 0.1 })}
          ${settingsInputHtml({ label: uiText("Max distance, m", "Макс. дистанция, м"), name: "max_distance_m", type: "number", value: configNumber(config, "spatial_analysis.max_distance_m", 50), min: 0.1, max: 500, step: 0.1 })}
          ${settingsInputHtml({ label: uiText("Max units per detection", "Макс. единиц на детекцию"), name: "max_units_per_detection", type: "number", value: configNumber(config, "spatial_analysis.max_units_per_detection", 200), min: 1, max: 10000, step: 1 })}
          ${settingsCheckboxHtml(uiText("Estimate depth layers", "Оценивать слои глубины"), "estimate_depth_layers", configBool(config, "spatial_analysis.estimate_depth_layers", false))}
        </div>
      </section>

      <section class="settings-section">
        <h4>${escapeHtml(uiText("Tracking / counting", "Tracking / counting"))}</h4>
        <div class="settings-field-grid">
          ${settingsCheckboxHtml(uiText("Tracking enabled", "Tracking включен"), "tracking_enabled", configBool(config, "tracking.enabled", true))}
          ${settingsInputHtml({ label: uiText("Grace period, sec", "Grace period, секунд"), name: "tracking_grace_period_seconds", type: "number", value: configNumber(config, "tracking.grace_period_seconds", 5), min: 0, max: 600, step: 0.1 })}
          ${settingsCheckboxHtml(uiText("Warehouse counting enabled", "Складской подсчет включен"), "warehouse_counting_enabled", configBool(config, "warehouse_counting.enabled", true))}
          ${settingsInputHtml({ label: uiText("Counting confidence", "Confidence подсчета"), name: "warehouse_confidence_threshold", type: "number", value: configNumber(config, "warehouse_counting.confidence_threshold", 0.55), min: 0, max: 1, step: 0.01 })}
          ${settingsCheckboxHtml(uiText("Low confidence as unknown", "Низкий confidence как unknown"), "count_low_confidence_as_unknown", configBool(config, "warehouse_counting.count_low_confidence_as_unknown", false))}
        </div>
      </section>

      <section class="settings-section">
        <h4>${escapeHtml(uiText("Snapshots / logging", "Snapshots / logging"))}</h4>
        <div class="settings-field-grid">
          ${settingsCheckboxHtml(uiText("Snapshots enabled", "Snapshots включены"), "snapshots_enabled", configBool(config, "snapshots.enabled", true))}
          ${settingsInputHtml({ label: uiText("Snapshot cooldown, sec", "Cooldown snapshots, секунд"), name: "snapshot_cooldown_seconds", type: "number", value: configNumber(config, "snapshots.cooldown_seconds", 5), min: 0, max: 86400, step: 1 })}
          ${settingsCheckboxHtml(uiText("Logging enabled", "Логи включены"), "logging_enabled", configBool(config, "logging.enabled", true))}
          ${settingsTextareaHtml(uiText("Snapshot trigger classes", "Классы для snapshots"), "snapshot_trigger_classes", configListText(config, "snapshots.trigger_classes"))}
        </div>
      </section>

      <div class="settings-actions">
        <button type="submit">${escapeHtml(uiText("Save system settings", "Сохранить системные настройки"))}</button>
      </div>
    </form>
  `;
}

function settingsNumber(form, name) {
  return Number(form.elements[name]?.value || 0);
}

function settingsList(form, name) {
  return String(form.elements[name]?.value || "")
    .split(/\n|,/)
    .map((value) => value.trim())
    .filter(Boolean);
}

function readSystemSettingsForm(form) {
  return {
    model_path: form.elements.model_path.value.trim(),
    fallback_model_path: form.elements.fallback_model_path.value.trim(),
    device: form.elements.device.value.trim() || "auto",
    confidence_threshold: settingsNumber(form, "confidence_threshold"),
    iou_threshold: settingsNumber(form, "iou_threshold"),
    max_detections: settingsNumber(form, "max_detections"),
    image_size: settingsNumber(form, "image_size"),
    target_fps: settingsNumber(form, "target_fps"),
    stale_after_ms: settingsNumber(form, "stale_after_ms"),
    max_concurrent_cameras: settingsNumber(form, "max_concurrent_cameras"),
    class_agnostic_nms: form.elements.class_agnostic_nms.checked,
    classes: settingsList(form, "classes"),
    class_prompts: settingsList(form, "class_prompts"),
    recognition_enabled: form.elements.recognition_enabled.checked,
    recognition_provider: form.elements.recognition_provider.value.trim(),
    recognition_model: form.elements.recognition_model.value.trim(),
    recognition_confidence_threshold: settingsNumber(form, "recognition_confidence_threshold"),
    recognition_similarity_threshold: settingsNumber(form, "recognition_similarity_threshold"),
    recognition_cache_expiration: settingsNumber(form, "recognition_cache_expiration"),
    recognition_timeout: settingsNumber(form, "recognition_timeout"),
    recognition_retries: settingsNumber(form, "recognition_retries"),
    recognition_max_workers: settingsNumber(form, "recognition_max_workers"),
    recognition_cache_enabled: form.elements.recognition_cache_enabled.checked,
    recognition_catalog_only: form.elements.recognition_catalog_only.checked,
    show_fps: form.elements.show_fps.checked,
    live_feed_enabled: form.elements.live_feed_enabled.checked,
    live_frame_width: settingsNumber(form, "live_frame_width"),
    live_frame_jpeg_quality: settingsNumber(form, "live_frame_jpeg_quality"),
    spatial_enabled: form.elements.spatial_enabled.checked,
    horizontal_fov_degrees: settingsNumber(form, "horizontal_fov_degrees"),
    camera_height_m: settingsNumber(form, "camera_height_m"),
    horizon_y_ratio: settingsNumber(form, "horizon_y_ratio"),
    min_distance_m: settingsNumber(form, "min_distance_m"),
    max_distance_m: settingsNumber(form, "max_distance_m"),
    max_units_per_detection: settingsNumber(form, "max_units_per_detection"),
    estimate_depth_layers: form.elements.estimate_depth_layers.checked,
    tracking_enabled: form.elements.tracking_enabled.checked,
    tracking_grace_period_seconds: settingsNumber(form, "tracking_grace_period_seconds"),
    warehouse_counting_enabled: form.elements.warehouse_counting_enabled.checked,
    warehouse_confidence_threshold: settingsNumber(form, "warehouse_confidence_threshold"),
    count_low_confidence_as_unknown: form.elements.count_low_confidence_as_unknown.checked,
    snapshots_enabled: form.elements.snapshots_enabled.checked,
    snapshot_cooldown_seconds: settingsNumber(form, "snapshot_cooldown_seconds"),
    logging_enabled: form.elements.logging_enabled.checked,
    snapshot_trigger_classes: settingsList(form, "snapshot_trigger_classes"),
  };
}

async function handleSettingsSubmit(event) {
  const form = event.target.closest("[data-settings-form]");
  if (!form) return;
  event.preventDefault();
  if (form.dataset.settingsForm === "system-config") {
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      state.systemConfig = await api("/api/config", {
        method: "PATCH",
        body: JSON.stringify(readSystemSettingsForm(form)),
      });
      toast(uiText("System settings saved.", "Системные настройки сохранены."));
      renderSettings(els.moduleContent);
    } catch (error) {
      toast(error.message);
      submit.disabled = false;
    }
    return;
  }
  if (form.dataset.settingsForm !== "security") return;
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
  if (button.dataset.settingsAction === "reload-config") {
    button.disabled = true;
    try {
      await ensureSystemConfigLoaded(true);
      renderSettings(els.moduleContent);
      toast(uiText("Settings reloaded.", "Настройки обновлены."));
    } catch (error) {
      toast(error.message);
      button.disabled = false;
    }
    return;
  }
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
        return `<figure><canvas data-live-frame data-live-slot="${slot}" role="img" aria-label="Camera slot ${slot}" style="display:block;width:100%;aspect-ratio:16/9"></canvas><figcaption>Slot ${slot}</figcaption></figure>`;
      }).join("")}
    </div>
  `;
}

const MAX_NVRS = 5;
const MAX_NVR_SLOTS = 100;
const FEATURE_CATALOG_PATH = "/dashboard-v2/assets/video-analytics-functions.json";
let accountState = null;
let accountModule = null;
let aiModulesCatalogCache = null;

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

function feedCameraAliases(nvr, channel) {
  const channelNumber = channel?.channel || channel?.external_channel_id || "";
  const slotNumber = channel?.slot_number || "";
  const nvrName = nvr?.name || "NVR";
  return uniqueLiveCameraAliases([
    channel?.name,
    channel?.camera_name,
    channel?.cameraName,
    channelNumber ? `${nvrName} Camera ${channelNumber}` : "",
    channelNumber ? `${nvrName} Channel ${channelNumber}` : "",
    channelNumber ? `NVR Camera ${channelNumber}` : "",
    channelNumber ? `Camera ${channelNumber}` : "",
    slotNumber ? `slot-${slotNumber}` : "",
    slotNumber ? `Slot ${slotNumber}` : "",
    slotNumber ? `Camera ${slotNumber}` : "",
    slotNumber ? `NVR Camera ${slotNumber}` : "",
  ]);
}

function feedCameraDisplayName(nvr, channel) {
  return feedCameraAliases(nvr, channel)[0] || `${nvr?.name || "NVR"} ${t("table.channel")} ${channel?.channel || ""}`.trim();
}

function renderFeedTile(nvr, channel) {
  if (!channel) {
    return `<figure class="feed-empty"><div>${escapeHtml(t("feed.readd"))}</div><figcaption>${escapeHtml(nvr.name)}</figcaption></figure>`;
  }
  if (channel.active && channel.slot_number != null) {
    const cameraName = feedCameraDisplayName(nvr, channel);
    const aliases = feedCameraAliases(nvr, channel).join("||");
    return `<figure><span class="feed-transmitting feed-stale-badge">${escapeHtml(t("status.waiting_video"))}</span><div class="feed-frame"><canvas class="feed-stale" data-live-frame data-live-slot="${channel.slot_number}" data-live-camera="${escapeAttr(cameraName)}" data-live-camera-aliases="${escapeAttr(aliases)}" data-live-priming="true" role="img" aria-label="${escapeAttr(cameraName)}" title="${escapeHtml(t("status.waiting_fresh_frame"))}" style="display:block;width:100%;aspect-ratio:16/9"></canvas><canvas class="feed-detection-layer" data-live-detection-overlay data-live-slot="${channel.slot_number}" aria-hidden="true"></canvas></div><figcaption>${escapeHtml(nvr.name)} · ${escapeHtml(t("table.channel"))} ${channel.channel}</figcaption></figure>`;
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
  if (role.access?.camera) menus.push({ id: "enterprise", label: "Enterprise Map", sub: "Blocks, zones & cameras" });
  if (role.access?.camera) menus.push({ id: "feed", label: "Camera Feed", sub: "Live slots" });
  menus.push({ id: "ai", label: "AI Check-in", sub: "Products to count" });
  menus.push({ id: "ai_models", label: "AI Models", sub: "YOLOE & training" });
  if (role.access?.analytics) menus.push({ id: "analytics", label: "Analytics", sub: "Charts & trends" });
  if (role.access?.analytics) menus.push({ id: "result_analytics", label: "Result Analytics", sub: "Recognition results" });
  if (role.access?.analytics) menus.push({ id: "events", label: "Events", sub: "Incidents & alerts" });
  if (role.access?.analytics) menus.push({ id: "zones", label: "Zones & Safety", sub: "Rules by camera group" });
  menus.push({ id: "dimension", label: "3D Dimensioning", sub: "Item measurements" });
  if (role.access?.analytics) menus.push({ id: "integrations", label: "Integrations", sub: "NVR, API & systems" });
  if (role.access?.analytics) menus.push({ id: "ai_modules", label: "AI Modules", sub: "270-function roadmap" });
  if (role.access?.analytics) menus.push({ id: "logs", label: "Logs", sub: "Engine actions" });
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

function cameraInfoNumber(...values) {
  for (const value of values) {
    if (value == null || value === "") continue;
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function cameraInfoFrameAge(stream) {
  const reported = cameraInfoNumber(stream?.frame_age_ms, stream?.frameAgeMs, stream?.age_ms);
  if (reported != null) return reported;
  const lastFrameAt = stream?.last_frame_at || stream?.lastFrameAt;
  if (!lastFrameAt) return null;
  const parsed = new Date(lastFrameAt).getTime();
  return Number.isFinite(parsed) ? Math.max(0, Date.now() - parsed) : null;
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
      const lastError = stream?.last_error || stream?.lastError || "";
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
        streamSeen: Boolean(stream),
        streamProvider: stream?.provider || stream?.stream_provider || nvr.provider || "stream manager",
        streamPath: stream?.stream_path || stream?.path || channel.stream_path || channel.profile || "",
        lastError,
        lastFrameAt: stream?.last_frame_at || stream?.lastFrameAt || "",
        frameAgeMs: stream ? cameraInfoFrameAge(stream) : null,
        reconnectCount: cameraInfoNumber(stream?.reconnect_count, stream?.reconnectCount) || 0,
        decodeErrors: cameraInfoNumber(stream?.decode_errors, stream?.decodeErrors) || 0,
        detail:
          lastError ||
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

function cameraInfoDuration(ms) {
  const value = Number(ms);
  if (!Number.isFinite(value)) return "";
  if (value < 1000) return `${Math.max(0, Math.round(value))} ms`;
  const seconds = Math.round(value / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  return `${hours}h`;
}

function cameraInfoTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
}

function cameraInfoPrimaryIssue(row) {
  if (row.slotNumber == null) return uiText("No AI slot assigned", "AI слот не назначен");
  if (!row.streamSeen) return uiText("No stream health received yet", "Данные health по потоку еще не получены");
  if (row.lastError) return row.lastError;
  if (row.status === "online") return uiText("Frames are live", "Кадры поступают");
  if (row.status === "starting") return uiText("Stream is starting", "Поток запускается");
  if (row.status === "reconnecting") return uiText("Stream Manager is reconnecting", "Stream Manager переподключается");
  if (row.status === "offline" || row.status === "failed") return uiText("Stream is offline", "Поток отключен");
  return row.detail || uiText("Waiting for stream data", "Ожидание данных потока");
}

function cameraInfoDiagnosticsText(row) {
  const parts = [cameraInfoPrimaryIssue(row)];
  if (row.frameAgeMs != null) {
    parts.push(`${uiText("Last frame", "Последний кадр")}: ${cameraInfoDuration(row.frameAgeMs)} ${uiText("ago", "назад")}`);
  } else if (row.lastFrameAt) {
    parts.push(`${uiText("Last frame", "Последний кадр")}: ${cameraInfoTime(row.lastFrameAt)}`);
  }
  if (row.reconnectCount > 0) {
    parts.push(`${uiText("Reconnects", "Переподключений")}: ${row.reconnectCount.toLocaleString()}`);
  }
  if (row.decodeErrors > 0) {
    parts.push(`${uiText("Decode errors", "Ошибок декодирования")}: ${row.decodeErrors.toLocaleString()}`);
  }
  return parts.filter(Boolean).join(" · ");
}

function cameraInfoDiagnosticsHtml(row) {
  const primary = cameraInfoPrimaryIssue(row);
  const details = [];
  if (row.frameAgeMs != null) {
    details.push(`${uiText("Last frame", "Последний кадр")}: ${cameraInfoDuration(row.frameAgeMs)} ${uiText("ago", "назад")}`);
  } else if (row.lastFrameAt) {
    details.push(`${uiText("Last frame", "Последний кадр")}: ${cameraInfoTime(row.lastFrameAt)}`);
  }
  if (row.reconnectCount > 0) details.push(`${uiText("Reconnects", "Переподключений")}: ${row.reconnectCount.toLocaleString()}`);
  if (row.decodeErrors > 0) details.push(`${uiText("Decode errors", "Ошибок декодирования")}: ${row.decodeErrors.toLocaleString()}`);
  return `
    <div class="camera-info-diagnostics">
      <strong>${escapeHtml(primary)}</strong>
      ${details.map((detail) => `<span>${escapeHtml(detail)}</span>`).join("")}
    </div>
  `;
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
            <th>${escapeHtml(uiText("Diagnostics", "Диагностика"))}</th>
          </tr>
        </thead>
        <tbody>
          ${rows
            .map((row) => {
              const status = cameraInfoStatusMeta(row.status);
              return `
                <tr title="${escapeAttr(cameraInfoDiagnosticsText(row))}">
                  <td><strong>${escapeHtml(row.nvrName)}</strong><span class="camera-info-meta">${escapeHtml(row.deviceType)}</span></td>
                  <td>${escapeHtml(row.host)}</td>
                  <td>${escapeHtml(row.vendor)}</td>
                  <td><strong>${escapeHtml(row.model)}</strong></td>
                  <td>${escapeHtml(row.cameraName)}</td>
                  <td>${row.slotNumber != null ? `${escapeHtml(t("table.slot"))} ${row.slotNumber}` : `<span class="camera-info-meta">${escapeHtml(t("table.not_assigned"))}</span>`}</td>
                  <td><span class="camera-info-status ${status.className}">${escapeHtml(status.label)}</span></td>
                  <td><strong>${escapeHtml(row.streamProvider)}</strong>${row.streamPath ? `<span class="camera-info-meta">${escapeHtml(row.streamPath)}</span>` : ""}</td>
                  <td>${cameraInfoDiagnosticsHtml(row)}</td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function renderCameraInfo(container, force = false) {
  const { company } = accountState;
  companyConfig(company);
  try {
    const [devicesPayload, streamsPayload] = await Promise.all([
      accountsApi("/api/v2/devices", { force }).catch(() => ({ devices: [] })),
      api("/api/v2/streams/health", { force }).catch(() => ({ streams: state.streams || [] })),
    ]);
    if (!container.isConnected || accountModule !== "camera_info") return;
    state.streams = streamsPayload.streams || state.streams || [];
    const rows = cameraInfoChannelRows(company.cameraConfig, devicesPayload.devices || []);
    const modelCount = new Set(rows.map((row) => `${row.vendor}/${row.model}`)).size;
    const liveCount = rows.filter((row) => row.status === "online").length;
    const attentionCount = rows.filter((row) => row.slotNumber != null && row.status !== "online").length;
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
          <article><span>${escapeHtml(uiText("Live streams", "Live потоки"))}</span><strong>${liveCount.toLocaleString()} / ${rows.length.toLocaleString()}</strong></article>
          <article><span>${escapeHtml(uiText("Need attention", "Требуют внимания"))}</span><strong>${attentionCount.toLocaleString()}</strong></article>
        </div>
        ${renderCameraInfoTable(rows)}
      </section>
    `;
    container.querySelector("[data-refresh-camera-info]")?.addEventListener("click", () => {
      container.innerHTML = `<p class="empty">${escapeHtml(t("camera_info.loading"))}</p>`;
      void renderCameraInfo(container, true);
    });
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function localizedText(value) {
  if (typeof value === "string") return value;
  if (!value || typeof value !== "object") return "";
  const lang = currentLanguage();
  return value[lang] || value.en || value.ru || "";
}

async function loadAiModulesCatalog(force = false) {
  if (aiModulesCatalogCache && !force) return aiModulesCatalogCache;
  const response = await fetch(`${API_BASE}${FEATURE_CATALOG_PATH}`);
  if (!response.ok) throw new Error(response.statusText || "Feature catalog request failed.");
  aiModulesCatalogCache = await response.json();
  return aiModulesCatalogCache;
}

function aiModulesRows(catalog) {
  return (catalog.sections || []).flatMap((section) =>
    (section.features || []).map((feature) => ({
      id: feature.id,
      sectionId: section.id,
      sectionNumber: section.number,
      sectionTitle: section.title,
      featureTitle: feature.title,
      status: feature.status || "planned",
    }))
  );
}

function aiModulesStatusCounts(rows) {
  return (rows || []).reduce(
    (counts, row) => {
      const status = row.status || "planned";
      counts[status] = (counts[status] || 0) + 1;
      counts.total += 1;
      return counts;
    },
    { total: 0, done: 0, partial: 0, planned: 0 }
  );
}

function aiModuleStatusLabel(status) {
  return t(`modules.status_${status || "planned"}`);
}

function aiModulesFilterRows(rows, filters = {}) {
  const section = filters.section || "all";
  const status = filters.status || "all";
  const query = String(filters.search || "").trim().toLowerCase();
  return (rows || []).filter((row) => {
    if (section !== "all" && row.sectionId !== section) return false;
    if (status !== "all" && row.status !== status) return false;
    if (!query) return true;
    return `${localizedText(row.sectionTitle)} ${localizedText(row.featureTitle)} ${row.status}`
      .toLowerCase()
      .includes(query);
  });
}

function aiModulesFilterControlsHtml(catalog, filters, totalRows, visibleRows) {
  return `
    <form class="ai-modules-filters" data-ai-modules-filters>
      <select name="section" aria-label="${escapeAttr(t("modules.section"))}">
        <option value="all">${escapeHtml(t("modules.section_all"))}</option>
        ${(catalog.sections || [])
          .map(
            (section) =>
              `<option value="${escapeAttr(section.id)}" ${filters.section === section.id ? "selected" : ""}>${section.number}. ${escapeHtml(localizedText(section.title))}</option>`
          )
          .join("")}
      </select>
      <select name="status" aria-label="${escapeAttr(t("modules.status"))}">
        <option value="all">${escapeHtml(t("modules.status_all"))}</option>
        ${["done", "partial", "planned"]
          .map(
            (status) =>
              `<option value="${status}" ${filters.status === status ? "selected" : ""}>${escapeHtml(aiModuleStatusLabel(status))}</option>`
          )
          .join("")}
      </select>
      <input name="search" value="${escapeAttr(filters.search || "")}" placeholder="${escapeAttr(t("modules.search"))}" autocomplete="off" />
      <button type="submit" class="export-button">${escapeHtml(t("actions.apply"))}</button>
      <button type="button" class="export-button muted-button" data-clear-ai-module-filters>${escapeHtml(t("actions.clear"))}</button>
      <strong class="result-analytics-count">${escapeHtml(t("modules.shown", { visible: visibleRows.length.toLocaleString(), total: totalRows.toLocaleString() }))}</strong>
    </form>
  `;
}

function aiModulesSummaryHtml(catalog, rows) {
  const counts = aiModulesStatusCounts(rows);
  return `
    <div class="ai-modules-summary">
      <article><span>${escapeHtml(t("modules.sections"))}</span><strong>${Number(catalog.meta?.sections_total || catalog.sections?.length || 0).toLocaleString()}</strong></article>
      <article><span>${escapeHtml(t("modules.functions"))}</span><strong>${Number(catalog.meta?.features_total || counts.total).toLocaleString()}</strong></article>
      <article><span>${escapeHtml(t("modules.implemented"))}</span><strong>${counts.done.toLocaleString()}</strong></article>
      <article><span>${escapeHtml(t("modules.partial"))}</span><strong>${counts.partial.toLocaleString()}</strong></article>
      <article><span>${escapeHtml(t("modules.planned"))}</span><strong>${counts.planned.toLocaleString()}</strong></article>
    </div>
  `;
}

function aiModuleSectionCounts(section) {
  return aiModulesStatusCounts(
    (section.features || []).map((feature) => ({ status: feature.status || "planned" }))
  );
}

function aiModuleSectionCardsHtml(catalog) {
  return `
    <div class="ai-module-section-grid">
      ${(catalog.sections || [])
        .map((section) => {
          const counts = aiModuleSectionCounts(section);
          const complete = counts.total ? Math.round(((counts.done + counts.partial * 0.5) / counts.total) * 100) : 0;
          return `
            <article class="ai-module-section-card">
              <div>
                <strong>${section.number}. ${escapeHtml(localizedText(section.title))}</strong>
                <span>${escapeHtml(t("modules.count", { count: counts.total.toLocaleString() }))}</span>
              </div>
              <div class="ai-module-progress" aria-label="${escapeAttr(`${complete}%`)}"><span style="width: ${complete}%"></span></div>
              <p>
                <em class="ai-module-status done">${counts.done.toLocaleString()}</em>
                <em class="ai-module-status partial">${counts.partial.toLocaleString()}</em>
                <em class="ai-module-status planned">${counts.planned.toLocaleString()}</em>
              </p>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function aiModulesTableHtml(rows) {
  if (!rows.length) return `<p class="empty">${escapeHtml(t("modules.empty"))}</p>`;
  return `
    <div class="detected-table-wrap">
      <table class="detected-table ai-modules-table">
        <thead>
          <tr>
            <th>${escapeHtml(t("modules.section"))}</th>
            <th>${escapeHtml(t("modules.feature"))}</th>
            <th>${escapeHtml(t("modules.status"))}</th>
          </tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (row) => `
                <tr>
                  <td><strong>${row.sectionNumber}. ${escapeHtml(localizedText(row.sectionTitle))}</strong></td>
                  <td>${escapeHtml(localizedText(row.featureTitle))}</td>
                  <td><span class="ai-module-status ${escapeAttr(row.status)}">${escapeHtml(aiModuleStatusLabel(row.status))}</span></td>
                </tr>
              `
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderAiModulesBody(container, catalog, filters = { section: "all", status: "all", search: "" }) {
  const rows = aiModulesRows(catalog);
  const visibleRows = aiModulesFilterRows(rows, filters);
  container.innerHTML = `
    <section class="detected-list ai-modules">
      <header class="detected-list-head">
        <div>
          <h3>${escapeHtml(t("modules.title"))}</h3>
          <p>${escapeHtml(t("modules.subtitle"))} ${escapeHtml(t("modules.source"))}</p>
        </div>
        <div class="detected-list-actions">
          <button type="button" class="export-button" data-refresh-ai-modules>${escapeHtml(t("actions.refresh"))}</button>
        </div>
      </header>
      ${aiModulesFilterControlsHtml(catalog, filters, rows.length, visibleRows)}
      ${aiModulesSummaryHtml(catalog, rows)}
      <p class="ai-modules-note">${escapeHtml(t("modules.current_note"))}</p>
      ${aiModuleSectionCardsHtml(catalog)}
      ${aiModulesTableHtml(visibleRows)}
    </section>
  `;
  container.querySelector("[data-ai-modules-filters]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    renderAiModulesBody(container, catalog, {
      section: form.section.value,
      status: form.status.value,
      search: form.search.value,
    });
  });
  container.querySelector("[data-clear-ai-module-filters]")?.addEventListener("click", () => {
    renderAiModulesBody(container, catalog, { section: "all", status: "all", search: "" });
  });
  container.querySelector("[data-refresh-ai-modules]")?.addEventListener("click", async () => {
    aiModulesCatalogCache = null;
    container.innerHTML = `<p class="empty">${escapeHtml(t("modules.loading"))}</p>`;
    await renderAiModules(container, filters);
  });
}

async function renderAiModules(container, filters = { section: "all", status: "all", search: "" }) {
  try {
    const catalog = await loadAiModulesCatalog();
    if (!container.isConnected || accountModule !== "ai_modules") return;
    renderAiModulesBody(container, catalog, filters);
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function uiText(en, ru) {
  return currentLanguage() === "ru" ? ru : en;
}

function platformStatusHtml(status, label) {
  const normalized = status || "planned";
  return `<span class="platform-status ${escapeAttr(normalized)}">${escapeHtml(label)}</span>`;
}

function platformSummaryHtml(cards) {
  return `
    <div class="platform-summary">
      ${cards
        .map(
          (card) => `
            <article>
              <span>${escapeHtml(card.label)}</span>
              <strong>${escapeHtml(card.value)}</strong>
              ${card.note ? `<em>${escapeHtml(card.note)}</em>` : ""}
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function feedGroupRecords(config) {
  const groups = new Map();
  const nvrs = config.nvrs || [];
  nvrs.forEach((nvr, nvrIndex) => {
    const channels = nvr.channelsDetail?.length
      ? nvr.channelsDetail
      : Array.from({ length: Number(nvr.channels || 0) }, (_, index) => ({
          channel: index + 1,
          slot_number: null,
          status: "registered",
        }));
    channels.forEach((channel, channelIndex) => {
      const channelNumber = Number(channel?.channel);
      const normalizedIndex = Number.isFinite(channelNumber) && channelNumber > 0 ? channelNumber - 1 : channelIndex;
      const meta = inferFeedGroup(nvr, nvrIndex, channel, normalizedIndex, nvrs.length);
      const name = config.feedGroups?.[meta.id] || meta.name;
      if (!groups.has(meta.id)) {
        groups.set(meta.id, { id: meta.id, name, cameras: [], nvrs: new Set() });
      }
      const group = groups.get(meta.id);
      group.nvrs.add(nvr.name || "NVR");
      group.cameras.push({
        nvrName: nvr.name || "NVR",
        cameraName: channel?.name || channel?.camera_name || `${t("table.camera")} ${channel?.channel || channelIndex + 1}`,
        channel: channel?.channel || channelIndex + 1,
        slotNumber: channel?.slot_number ?? null,
        active: channel?.active !== false && channel?.slot_number != null,
        status: channel?.status || "registered",
      });
    });
  });
  return Array.from(groups.values()).map((group) => ({
    ...group,
    nvrCount: group.nvrs.size,
  }));
}

function renderEnterprisePage(container) {
  const { company } = accountState;
  companyConfig(company);
  const config = company.cameraConfig;
  const groups = feedGroupRecords(config);
  const cameraRows = cameraInfoChannelRows(config, []);
  const assignedSlots = cameraRows.filter((row) => row.slotNumber != null).length;
  const groupRows = groups
    .flatMap((group) =>
      group.cameras.map((camera) => ({ ...camera, groupName: group.name, nvrCount: group.nvrCount }))
    )
    .map(
      (row) => `
        <tr>
          <td><strong>${escapeHtml(row.groupName)}</strong></td>
          <td>${escapeHtml(row.nvrName)}</td>
          <td>${escapeHtml(row.cameraName)}</td>
          <td>${row.slotNumber != null ? `${escapeHtml(t("table.slot"))} ${row.slotNumber}` : escapeHtml(t("table.not_assigned"))}</td>
          <td>${platformStatusHtml(row.active ? "done" : "partial", row.active ? t("status.live") : t("status.pending"))}</td>
        </tr>
      `
    )
    .join("");
  const groupCards = groups
    .map(
      (group) => `
        <article class="platform-card">
          <div>
            <strong>${escapeHtml(group.name)}</strong>
            <span>${escapeHtml(uiText("Camera group", "Группа камер"))}</span>
          </div>
          <p>${escapeHtml(uiText("NVR devices", "NVR устройств"))}: ${group.nvrCount.toLocaleString()}</p>
          <p>${escapeHtml(t("table.camera"))}: ${group.cameras.length.toLocaleString()}</p>
          <div class="platform-flow">${group.cameras
            .slice(0, 6)
            .map((camera) => `<span>${escapeHtml(camera.cameraName)}</span>`)
            .join("")}</div>
        </article>
      `
    )
    .join("");
  container.innerHTML = `
    <section class="detected-list platform-page">
      <header class="detected-list-head">
        <div>
          <h3>${escapeHtml(uiText("Enterprise Structure", "Структура предприятия"))}</h3>
          <p>${escapeHtml(uiText("Company, NVR, camera groups and live slot coverage in one place.", "Компания, NVR, группы камер и live-слоты в одном месте."))}</p>
        </div>
      </header>
      ${platformSummaryHtml([
        { label: uiText("Company", "Компания"), value: company.name || "AI Vision" },
        { label: uiText("NVR devices", "NVR устройств"), value: config.nvrs.length.toLocaleString() },
        { label: t("table.camera"), value: cameraRows.length.toLocaleString() },
        { label: uiText("Groups / blocks", "Группы / блоки"), value: groups.length.toLocaleString() },
        { label: uiText("Assigned slots", "Назначено слотов"), value: assignedSlots.toLocaleString() },
      ])}
      <div class="platform-flow platform-chain">
        <span>${escapeHtml(company.name || "Company")}</span>
        <span>${escapeHtml(uiText("Warehouse / site", "Склад / объект"))}</span>
        <span>${escapeHtml(uiText("Blocks and zones", "Блоки и зоны"))}</span>
        <span>${escapeHtml(uiText("NVR / cameras", "NVR / камеры"))}</span>
        <span>Stream Manager</span>
        <span>YOLOE</span>
      </div>
      <div class="platform-card-grid">${groupCards || `<p class="empty">${escapeHtml(t("feed.empty"))}</p>`}</div>
      <div class="detected-table-wrap">
        <table class="detected-table platform-table">
          <thead><tr><th>${escapeHtml(uiText("Block / room", "Блок / комната"))}</th><th>NVR</th><th>${escapeHtml(t("table.camera"))}</th><th>${escapeHtml(t("table.slot"))}</th><th>${escapeHtml(t("table.status"))}</th></tr></thead>
          <tbody>${groupRows || `<tr><td colspan="5">${escapeHtml(t("feed.empty"))}</td></tr>`}</tbody>
        </table>
      </div>
    </section>
  `;
}

function eventSeverity(event) {
  const text = `${event.event_type || ""} ${event.action || ""} ${event.level || ""}`.toLowerCase();
  if (text.includes("violation") || text.includes("failed") || text.includes("error") || text.includes("alarm")) return "bad";
  if (Number(event.inventory_delta || 0) !== 0 || text.includes("warn") || text.includes("zone")) return "partial";
  return "done";
}

function eventRowsFromPayloads(enginePayload, auditPayload, logPayload) {
  const engineRows = (enginePayload.events || []).map((event) => ({
    time: event.timestamp,
    source: "AI Engine",
    type: String(event.event_type || "event").replaceAll("_", " "),
    camera: event.camera_id || "-",
    object: event.product_name || event.object_id || "-",
    status: Number(event.inventory_delta || 0) !== 0 ? uiText("Action", "Действие") : uiText("Recorded", "Записано"),
    severity: eventSeverity(event),
  }));
  const auditRows = (auditPayload.events || []).map((event) => ({
    time: event.created_at || event.timestamp,
    source: "Security Audit",
    type: String(event.action || event.event_type || "audit").replaceAll("_", " "),
    camera: event.path || "-",
    object: event.actor || event.user || "-",
    status: String(event.status_code || event.status || "OK"),
    severity: eventSeverity(event),
  }));
  const logRows = (logPayload.logs || []).slice(0, 80).map((line) => ({
    time: "",
    source: "Server Log",
    type: String(line).slice(0, 80),
    camera: "-",
    object: "-",
    status: uiText("Log", "Лог"),
    severity: String(line).toLowerCase().includes("error") ? "bad" : "done",
  }));
  return [...engineRows, ...auditRows, ...logRows].sort((a, b) => new Date(b.time || 0) - new Date(a.time || 0));
}

function eventsTableHtml(rows) {
  if (!rows.length) return `<p class="empty">${escapeHtml(uiText("No events recorded yet.", "Событий пока нет."))}</p>`;
  return `
    <div class="detected-table-wrap">
      <table class="detected-table platform-table">
        <thead><tr><th>${escapeHtml(uiText("Time", "Время"))}</th><th>${escapeHtml(uiText("Source", "Источник"))}</th><th>${escapeHtml(uiText("Event", "Событие"))}</th><th>${escapeHtml(t("table.camera"))}</th><th>${escapeHtml(uiText("Object / actor", "Объект / пользователь"))}</th><th>${escapeHtml(t("table.status"))}</th></tr></thead>
        <tbody>${rows
          .slice(0, 250)
          .map(
            (row) => `
              <tr>
                <td>${escapeHtml(row.time ? formatCatalogTime(row.time) : "-")}</td>
                <td><strong>${escapeHtml(row.source)}</strong></td>
                <td>${escapeHtml(row.type)}</td>
                <td>${escapeHtml(row.camera)}</td>
                <td>${escapeHtml(row.object)}</td>
                <td>${platformStatusHtml(row.severity, row.status)}</td>
              </tr>
            `
          )
          .join("")}</tbody>
      </table>
    </div>
  `;
}

async function renderEventsPage(container, force = false) {
  try {
    const [enginePayload, auditPayload, logPayload] = await Promise.all([
      catalogRequest("/api/warehouse-engine/events?limit=500", { force }).catch(() => ({ events: [] })),
      catalogRequest("/api/security/audit?limit=200", { force }).catch(() => ({ events: [] })),
      catalogRequest("/api/logs?limit=80", { force }).catch(() => ({ logs: [] })),
    ]);
    if (!container.isConnected || accountModule !== "events") return;
    const rows = eventRowsFromPayloads(enginePayload, auditPayload, logPayload);
    const high = rows.filter((row) => row.severity === "bad").length;
    container.innerHTML = `
      <section class="detected-list platform-page">
        <header class="detected-list-head">
          <div>
            <h3>${escapeHtml(uiText("Events and Incidents", "События и инциденты"))}</h3>
            <p>${escapeHtml(uiText("A single journal for AI actions, camera events, security audit and server logs.", "Единый журнал для AI действий, камер, аудита безопасности и логов сервера."))}</p>
          </div>
          <button type="button" class="export-button" data-refresh-events>${escapeHtml(t("actions.refresh"))}</button>
        </header>
        ${platformSummaryHtml([
          { label: uiText("Total records", "Всего записей"), value: rows.length.toLocaleString() },
          { label: uiText("Critical", "Критические"), value: high.toLocaleString() },
          { label: uiText("AI engine", "AI engine"), value: (enginePayload.events || []).length.toLocaleString() },
          { label: uiText("Audit", "Аудит"), value: (auditPayload.events || []).length.toLocaleString() },
        ])}
        ${eventsTableHtml(rows)}
      </section>
    `;
    container.querySelector("[data-refresh-events]")?.addEventListener("click", () => {
      container.innerHTML = `<p class="empty">${escapeHtml(uiText("Refreshing events...", "Обновление событий..."))}</p>`;
      void renderEventsPage(container, true);
    });
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function renderSafetyZonesPage(container) {
  const { company } = accountState;
  companyConfig(company);
  const groups = feedGroupRecords(company.cameraConfig);
  const ruleCards = [
    { name: uiText("Person in danger zone", "Человек в опасной зоне"), status: groups.length ? "partial" : "planned", note: uiText("Needs zone polygon per group", "Нужен контур зоны для группы") },
    { name: uiText("Line crossing", "Пересечение линии"), status: groups.length ? "partial" : "planned", note: uiText("Ready for camera calibration", "Готово к калибровке камеры") },
    { name: uiText("PPE control", "Контроль СИЗ"), status: "planned", note: uiText("Requires PPE model weights", "Нужны веса PPE модели") },
    { name: uiText("Blocked exits", "Заблокированные выходы"), status: "planned", note: uiText("Use safety camera groups", "Использовать группы камер безопасности") },
  ];
  const groupRows = groups
    .map(
      (group) => `
        <tr>
          <td><strong>${escapeHtml(group.name)}</strong></td>
          <td>${group.cameras.length.toLocaleString()}</td>
          <td>${group.cameras.filter((camera) => camera.active).length.toLocaleString()}</td>
          <td>${platformStatusHtml(group.cameras.some((camera) => camera.active) ? "partial" : "planned", group.cameras.some((camera) => camera.active) ? uiText("Ready for rules", "Готово для правил") : uiText("Needs live camera", "Нужна live камера"))}</td>
        </tr>
      `
    )
    .join("");
  container.innerHTML = `
    <section class="detected-list platform-page">
      <header class="detected-list-head">
        <div>
          <h3>${escapeHtml(uiText("Zones and Safety", "Зоны и безопасность"))}</h3>
          <p>${escapeHtml(uiText("Safety rules are organized by editable camera groups and blocks.", "Правила безопасности организованы по редактируемым группам камер и блокам."))}</p>
        </div>
      </header>
      ${platformSummaryHtml([
        { label: uiText("Controlled zones", "Контролируемые зоны"), value: groups.length.toLocaleString() },
        { label: uiText("Cameras in zones", "Камер в зонах"), value: groups.reduce((sum, group) => sum + group.cameras.length, 0).toLocaleString() },
        { label: uiText("Safety rules", "Правила безопасности"), value: ruleCards.length.toLocaleString() },
      ])}
      <div class="platform-card-grid">${ruleCards
        .map(
          (rule) => `
            <article class="platform-card">
              <div><strong>${escapeHtml(rule.name)}</strong>${platformStatusHtml(rule.status, rule.status === "planned" ? t("modules.status_planned") : t("modules.status_partial"))}</div>
              <p>${escapeHtml(rule.note)}</p>
            </article>
          `
        )
        .join("")}</div>
      <div class="detected-table-wrap">
        <table class="detected-table platform-table">
          <thead><tr><th>${escapeHtml(uiText("Zone / block", "Зона / блок"))}</th><th>${escapeHtml(t("table.camera"))}</th><th>Live</th><th>${escapeHtml(t("table.status"))}</th></tr></thead>
          <tbody>${groupRows || `<tr><td colspan="4">${escapeHtml(t("feed.empty"))}</td></tr>`}</tbody>
        </table>
      </div>
    </section>
  `;
}

async function renderAiModelsPage(container, force = false) {
  try {
    const [catalogPayload, statusPayload, healthPayload] = await Promise.all([
      catalogRequest(catalogApiPath("/api/catalog/items"), { force }).catch(() => ({ items: [] })),
      api("/api/status", { force }).catch(() => ({})),
      api("/api/v2/analytics/health", { force }).catch(() => ({})),
    ]);
    if (!container.isConnected || accountModule !== "ai_models") return;
    const items = catalogPayload.items || [];
    const promptCount = items.reduce((sum, item) => sum + Number(item.detection_prompts?.length || 0), 0);
    const detectorRunning = Boolean(statusPayload.detector_running || healthPayload.running || healthPayload.status === "running");
    const models = [
      { name: "YOLOE Detector", status: detectorRunning ? "done" : "partial", note: uiText("Live object proposals from Stream Manager frames.", "Live object proposals из кадров Stream Manager.") },
      { name: "Catalog Matcher", status: items.length ? "done" : "partial", note: uiText("Reference images and prompts for exact products.", "Эталонные фото и prompts для точных товаров.") },
      { name: "Product Learning", status: "partial", note: uiText("One-click learning from a live camera is available in AI Check-in.", "One-click обучение с live камеры доступно в AI Check-in.") },
      { name: "3D Spatial Measurement", status: "partial", note: uiText("Uses recognized catalog items with spatial calibration.", "Использует распознанные товары с пространственной калибровкой.") },
    ];
    const itemRows = items
      .map(
        (item) => `
          <tr>
            <td><strong>${escapeHtml(item.name)}</strong></td>
            <td>${Number(item.image_count || item.images?.length || 0).toLocaleString()}</td>
            <td>${escapeHtml((item.detection_prompts || []).join(", ") || uiText("No prompts", "Нет prompts"))}</td>
            <td>${platformStatusHtml("done", t("ai.catalog_enabled"))}</td>
          </tr>
        `
      )
      .join("");
    container.innerHTML = `
      <section class="detected-list platform-page">
        <header class="detected-list-head">
          <div>
            <h3>${escapeHtml(uiText("AI Models", "AI модели"))}</h3>
            <p>${escapeHtml(uiText("Detector, catalog matching, training readiness and product prompts.", "Детектор, catalog matching, готовность обучения и product prompts."))}</p>
          </div>
          <button type="button" class="export-button" data-run-ai-model-recognition>${escapeHtml(t("actions.run_recognition"))}</button>
        </header>
        ${platformSummaryHtml([
          { label: uiText("Detector", "Детектор"), value: detectorRunning ? t("status.detector_running") : t("status.detector_stopped") },
          { label: uiText("Catalog items", "Товаров в каталоге"), value: items.length.toLocaleString() },
          { label: "YOLO prompts", value: promptCount.toLocaleString() },
          { label: uiText("Model family", "Семейство модели"), value: "YOLOE" },
        ])}
        <div class="platform-card-grid">${models
          .map(
            (model) => `
              <article class="platform-card">
                <div><strong>${escapeHtml(model.name)}</strong>${platformStatusHtml(model.status, model.status === "done" ? t("modules.status_done") : t("modules.status_partial"))}</div>
                <p>${escapeHtml(model.note)}</p>
              </article>
            `
          )
          .join("")}</div>
        <div class="detected-table-wrap">
          <table class="detected-table platform-table">
            <thead><tr><th>${escapeHtml(t("table.item"))}</th><th>${escapeHtml(t("ai.reference_images"))}</th><th>YOLO prompts</th><th>${escapeHtml(t("table.status"))}</th></tr></thead>
            <tbody>${itemRows || `<tr><td colspan="4">${escapeHtml(t("ai.empty_catalog"))}</td></tr>`}</tbody>
          </table>
        </div>
      </section>
    `;
    container.querySelector("[data-run-ai-model-recognition]")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = t("actions.recognizing");
      try {
        await catalogRequest(catalogApiPath("/api/catalog/recognition/run"), { method: "POST" });
        toast(t("toast.recognition_complete"));
        await renderAiModelsPage(container);
      } catch (error) {
        toast(error.message);
        button.disabled = false;
        button.textContent = t("actions.run_recognition");
      }
    });
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

async function renderIntegrationsPage(container, force = false) {
  try {
    const [devicesPayload, streamsPayload] = await Promise.all([
      accountsApi("/api/v2/devices", { force }).catch(() => ({ devices: [] })),
      api("/api/v2/streams/health", { force }).catch(() => ({ streams: state.streams || [] })),
    ]);
    if (!container.isConnected || accountModule !== "integrations") return;
    const devices = devicesPayload.devices || [];
    const streams = streamsPayload.streams || [];
    const liveStreams = streams.filter((stream) => stream.status === "online").length;
    const connectors = [
      { name: "RTSP", status: devices.length ? "done" : "partial", note: uiText("Camera transport through Stream Manager.", "Транспорт камер через Stream Manager.") },
      { name: "ONVIF", status: "partial", note: uiText("Discovery and vendor fingerprinting layer.", "Слой discovery и vendor fingerprinting.") },
      { name: "Hikvision / Dahua", status: devices.some((device) => /hikvision|dahua/i.test(`${device.vendor || ""}`)) ? "done" : "partial", note: uiText("Vendor-aware discovery is enabled.", "Vendor-aware discovery включен.") },
      { name: "REST API", status: "done", note: "/api/*" },
      { name: "WebSocket / SSE", status: "done", note: "/api/logs/stream" },
      { name: "WMS / ERP / 1C", status: "planned", note: uiText("Roadmap integration connector.", "Roadmap-коннектор интеграции.") },
      { name: "Webhook", status: "planned", note: uiText("External incident delivery.", "Передача инцидентов во внешние системы.") },
    ];
    const deviceRows = devices
      .map(
        (device) => `
          <tr>
            <td><strong>${escapeHtml(device.name || device.host || "Device")}</strong></td>
            <td>${escapeHtml(device.host || "-")}</td>
            <td>${escapeHtml(device.vendor || t("device_type.unknown"))}</td>
            <td>${escapeHtml(device.model || "-")}</td>
            <td>${platformStatusHtml("done", t("status.registered"))}</td>
          </tr>
        `
      )
      .join("");
    container.innerHTML = `
      <section class="detected-list platform-page">
        <header class="detected-list-head">
          <div>
            <h3>${escapeHtml(uiText("Integrations", "Интеграции"))}</h3>
            <p>${escapeHtml(uiText("Camera vendors, internal APIs and external system connectors.", "Вендоры камер, внутренние API и коннекторы внешних систем."))}</p>
          </div>
          <button type="button" class="export-button" data-refresh-integrations>${escapeHtml(t("actions.refresh"))}</button>
        </header>
        ${platformSummaryHtml([
          { label: uiText("Connected devices", "Подключено устройств"), value: devices.length.toLocaleString() },
          { label: uiText("Live streams", "Live потоков"), value: liveStreams.toLocaleString() },
          { label: uiText("Connectors", "Коннекторы"), value: connectors.length.toLocaleString() },
        ])}
        <div class="platform-card-grid">${connectors
          .map(
            (connector) => `
              <article class="platform-card">
                <div><strong>${escapeHtml(connector.name)}</strong>${platformStatusHtml(connector.status, connector.status === "done" ? t("modules.status_done") : connector.status === "planned" ? t("modules.status_planned") : t("modules.status_partial"))}</div>
                <p>${escapeHtml(connector.note)}</p>
              </article>
            `
          )
          .join("")}</div>
        <div class="detected-table-wrap">
          <table class="detected-table platform-table">
            <thead><tr><th>${escapeHtml(uiText("Device", "Устройство"))}</th><th>${escapeHtml(t("table.host"))}</th><th>${escapeHtml(t("table.vendor"))}</th><th>${escapeHtml(t("table.model"))}</th><th>${escapeHtml(t("table.status"))}</th></tr></thead>
            <tbody>${deviceRows || `<tr><td colspan="5">${escapeHtml(t("camera.no_devices"))}</td></tr>`}</tbody>
          </table>
        </div>
      </section>
    `;
    container.querySelector("[data-refresh-integrations]")?.addEventListener("click", () => {
      container.innerHTML = `<p class="empty">${escapeHtml(uiText("Refreshing integrations...", "Обновление интеграций..."))}</p>`;
      void renderIntegrationsPage(container, true);
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
  const { force = false, ...fetchOptions } = options;
  const method = String(fetchOptions.method || "GET").toUpperCase();
  if (!force && method === "GET" && !fetchOptions.body) {
    return cachedRead(readCacheKey("catalog", path), () => catalogRequest(path, { ...fetchOptions, force: true }), force);
  }
  const response = await fetch(`${API_BASE}${path}`, fetchOptions);
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
  if (method !== "GET") clearReadCache();
  if (response.status === 204) return null;
  const payload = await response.json();
  if (method === "GET" && !fetchOptions.body) readCache.set(readCacheKey("catalog", path), payload);
  return payload;
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
        `<span class="camera-count-pill">
          ${entry.crop_url ? `<img src="${escapeAttr(`${API_BASE}${entry.crop_url}`)}" alt="${escapeAttr(`${result.item_name || "Item"} from ${entry.camera_name || "camera"}`)}" style="width:72px;height:52px;object-fit:cover;border-radius:7px;border:1px solid #cbd5e1;margin-right:8px;vertical-align:middle" />` : ""}
          <strong>${escapeHtml(entry.camera_name || t("table.camera"))}</strong>
          ${Number(entry.quantity).toLocaleString()}
          ${entry.detected_at ? `<small style="display:block;margin-left:8px;color:#64748b">${escapeHtml(formatCatalogTime(entry.detected_at))}</small>` : ""}
        </span>`
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
        const completedAt = entry.detected_at || result.completed_at || result.created_at;
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
                ${row.cropUrl ? `
                <form class="result-correction" data-correct-form data-crop-url="${escapeAttr(row.cropUrl)}" data-predicted="${escapeAttr(row.itemName || "")}">
                  <p class="result-correction-ai">${escapeHtml(t("result.ai_prediction"))}: <strong>${escapeHtml(row.itemName)} (${Math.round(row.confidence * 100)}%)</strong></p>
                  <label>${escapeHtml(t("result.correct_name"))}
                    <input type="text" name="correct_name" maxlength="60" autocomplete="off" placeholder="${escapeAttr(t("result.correct_name_ph"))}" />
                  </label>
                  <label>${escapeHtml(t("result.prompt_label"))}
                    <textarea name="prompt" rows="2" maxlength="500" placeholder="${escapeAttr(t("result.prompt_ph"))}"></textarea>
                  </label>
                  <button type="submit" class="result-correction-save">${escapeHtml(t("result.save_correction"))}</button>
                </form>` : ""}
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
    void renderResultAnalytics(container, true);
  });
  container.querySelector("[data-run-result-recognition]")?.addEventListener("click", (event) => {
    void runResultAnalyticsRecognition(container, event.currentTarget, filters);
  });
  container.querySelectorAll("[data-correct-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const correctName = form.querySelector("[name=correct_name]").value.trim();
      if (!correctName) {
        toast(t("result.correct_name_required"));
        return;
      }
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      try {
        await catalogRequest(catalogApiPath("/api/catalog/results/correct"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            correct_name: correctName,
            prompt: form.querySelector("[name=prompt]").value.trim() || null,
            crop_url: form.dataset.cropUrl,
            predicted_name: form.dataset.predicted || null,
          }),
        });
        toast(t("result.correction_saved"));
        container.innerHTML = `<p class="empty">${escapeHtml(t("result.loading"))}</p>`;
        void renderResultAnalytics(container);
      } catch (error) {
        toast(error.message || "Failed to save correction.");
        button.disabled = false;
      }
    });
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

async function renderResultAnalytics(container, force = false) {
  try {
    const payload = await catalogRequest(catalogApiPath("/api/catalog/results/history?limit=500"), { force });
    if (!container.isConnected || accountModule !== "result_analytics") return;
    renderResultAnalyticsBody(container, payload);
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

let productLearningSessionId = null;

function productLearningPanelHtml(session) {
  if (!session) {
    return `<div class="module-placeholder"><h3>One Click Product Learning</h3><p>Press the button, then hold one product in view of a camera and slowly rotate or move it for 10–20 seconds.</p></div>`;
  }
  if (session.status === "failed") {
    return `<div class="module-placeholder"><h3>Learning could not finish</h3><p>${escapeHtml(session.error || "No stable product views were found.")}</p><button type="button" data-acc-action="learn-product">Try again</button></div>`;
  }
  const existing = session.existing_match;
  const matchingViewIndices = new Set(existing?.matching_view_indices || []);
  const previews = (session.views || [])
    .map((view) => `
      <label style="display:block;cursor:pointer;border:2px solid #2563eb;border-radius:10px;padding:5px">
        <img src="${API_BASE}${view.url}" alt="Learned product view" style="display:block;width:110px;height:90px;object-fit:cover;border-radius:7px" />
        <span style="display:flex;gap:5px;align-items:center;font-size:11px;margin-top:5px">
          <input type="checkbox" name="learned-view" value="${Number(view.index)}" ${existing ? (matchingViewIndices.has(Number(view.index)) ? "checked" : "") : "checked"} />
          Use this view
        </span>
      </label>`)
    .join("");
  if (session.status === "ready") {
    return `
      <div class="module-placeholder">
        <h3>${Number(session.view_count || 0)} reusable product views captured</h3>
        <p>Select only the pictures that clearly contain the product. Deselect warehouse background or the wrong object. At least two views are required.</p>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin:12px 0">${previews}</div>
        <form data-acc-form="learned-product-save" data-session-id="${escapeAttr(session.session_id)}">
          ${existing ? `
            <label style="display:flex;gap:8px;align-items:center;padding:12px;background:#ecfdf5;border:1px solid #86efac;border-radius:9px;margin-bottom:12px">
              <input type="checkbox" name="use-existing-product" value="${escapeAttr(existing.item_id)}" checked />
              <span><strong>Existing manual product found: ${escapeHtml(existing.name)}</strong><br><small>${Math.round(Number(existing.confidence) * 100)}% multi-view match across ${Number(existing.matching_view_count)} pictures. This product is already in the AI Check-in list; saving adds the selected views to it.</small></span>
            </label>` : ""}
          <div style="display:flex;gap:10px;align-items:end">
          <label style="flex:1"><span style="display:block;font-weight:700;margin-bottom:5px">Product Name</span><input name="name" required maxlength="60" placeholder="Baget Box" value="${escapeAttr(existing?.name || "")}" autocomplete="off" style="width:100%" /></label>
          <button type="button" data-acc-action="learn-product">Retake pictures</button>
          <button type="submit">Save to base</button>
          </div>
        </form>
      </div>`;
  }
  if (session.status === "saved") {
    return `<div class="module-placeholder"><h3>${escapeHtml(session.product_name || "Product")} is learned and active</h3><p>The fingerprint is saved and counting can begin immediately. No restart is required.</p></div>`;
  }
  return `
    <div class="module-placeholder">
      <h3>Learning from live cameras… ${Number(session.remaining_seconds || 0)}s</h3>
      <p>Keep the product visible and slowly show different sides. ${Number(session.frames_seen || 0).toLocaleString()} frames inspected; ${Number(session.proposal_count || 0).toLocaleString()} candidate views found.</p>
    </div>`;
}

async function startProductLearning(container, button, cameraName) {
  button.disabled = true;
  try {
    let session = await catalogRequest(catalogApiPath("/api/catalog/learning/start"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ duration_seconds: 12, camera_name: cameraName }),
    });
    productLearningSessionId = session.session_id;
    const panel = container.querySelector("[data-product-learning-panel]");
    if (panel) panel.innerHTML = productLearningPanelHtml(session);
    while (session.status === "capturing" || session.status === "processing") {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      if (!container.isConnected || accountModule !== "ai") return;
      session = await catalogRequest(catalogApiPath(`/api/catalog/learning/${encodeURIComponent(productLearningSessionId)}`));
      if (panel) panel.innerHTML = productLearningPanelHtml(session);
    }
  } catch (error) {
    toast(error.message);
    button.disabled = false;
  }
}

async function renderCatalogEnrollment(container, force = false) {
  try {
    const payload = await catalogRequest(catalogApiPath("/api/catalog/items"), { force });
    if (!container.isConnected || accountModule !== "ai") return;
    const cameraOptions = (accountState?.company?.cameraConfig?.nvrs || [])
      .flatMap((nvr) => (nvr.channelsDetail || []).map((channel) => ({
        name: channel.name || `${nvr.name} Channel ${channel.channel}`,
        active: channel.active !== false && channel.slot_number != null,
      })))
      .filter((camera) => camera.active);
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
            <form data-acc-form="catalog-prompts" data-item-id="${escapeAttr(item.id)}" style="display:flex;gap:8px;align-items:end;margin-top:12px">
              <label style="flex:1">
                <span style="display:block;font-size:12px;font-weight:700;margin-bottom:5px">YOLO detection prompts</span>
                <input name="prompts" value="${escapeAttr((item.detection_prompts || []).join(", "))}" placeholder="baget box, long carton, bakery package" autocomplete="off" style="width:100%" />
              </label>
              <button type="submit">Save prompts</button>
            </form>
            <span class="cc-chip cc-chip-small on">${escapeHtml(t("ai.catalog_enabled"))}</span>
          </article>
        `
      )
      .join("");
    container.innerHTML = `
      <p class="chart-note">${escapeHtml(t("ai.intro"))}</p>
      <section class="detected-list" style="margin-bottom:18px">
        <header class="detected-list-head">
          <div><h3>Learn New Product</h3><p>Show the product to a live camera. AI Vision captures its views and builds the reusable fingerprint automatically.</p></div>
          <div style="display:flex;gap:8px;align-items:end">
            <label><span style="display:block;font-size:12px;font-weight:700;margin-bottom:5px">Camera showing the product</span>
              <select data-learning-camera style="min-width:260px">
                ${cameraOptions.map((camera) => `<option value="${escapeAttr(camera.name)}">${escapeHtml(camera.name)}</option>`).join("")}
              </select>
            </label>
            <button type="button" class="export-button" data-acc-action="learn-product" ${cameraOptions.length ? "" : "disabled"}>Learn New Product</button>
          </div>
        </header>
        ${cameraOptions.length ? "" : '<p class="empty">Connect an active camera before starting product learning.</p>'}
        <div data-product-learning-panel>${productLearningPanelHtml(null)}</div>
      </section>
      <details>
        <summary style="cursor:pointer;font-weight:700;margin-bottom:12px">Manual image upload</summary>
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
      </details>
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

function warehouseEngineOverviewHtml(engine) {
  const zoneRows = Object.entries(engine.zone_statistics || {})
    .map(([zone, count]) => `<span class="camera-count-pill"><strong>${escapeHtml(zone)}</strong>${Number(count).toLocaleString()}</span>`)
    .join("");
  const events = (engine.events || []).slice(0, 20)
    .map((event) => `
      <tr>
        <td>${escapeHtml(formatCatalogTime(event.timestamp))}</td>
        <td><strong>${escapeHtml(String(event.event_type || "").replaceAll("_", " "))}</strong></td>
        <td>${escapeHtml(event.object_id || "")}</td>
        <td>${escapeHtml(event.camera_id || "")}</td>
        <td>${escapeHtml(event.zone || "Unassigned")}</td>
        <td class="count-cell">${Number(event.inventory_delta || 0).toLocaleString()}</td>
      </tr>`)
    .join("");
  return `
    <section class="detected-list" style="margin-top:20px">
      <header class="detected-list-head">
        <div><h3>Warehouse Intelligence Engine</h3><p>Inventory is driven by persistent identity, movement, zones, and rules—not raw YOLO frames.</p></div>
      </header>
      <div class="result-analytics-summary">
        <article><span>Detected objects</span><strong>${Number(engine.detected_objects || 0).toLocaleString()}</strong></article>
        <article><span>Tracked objects</span><strong>${Number(engine.tracked_objects || 0).toLocaleString()}</strong></article>
        <article><span>Inventory objects</span><strong>${Number(engine.inventory_objects || 0).toLocaleString()}</strong></article>
        <article><span>Active events</span><strong>${Number(engine.active_events || 0).toLocaleString()}</strong></article>
      </div>
      <div class="camera-count-list" style="margin:14px 0">${zoneRows || '<span class="muted">No active zones yet</span>'}</div>
      <form data-warehouse-task-builder style="display:flex;gap:10px;align-items:end;margin:18px 0">
        <label style="flex:1"><span style="display:block;font-weight:700;margin-bottom:6px">AI Task Builder</span><input name="prompt" required value="Count all baget boxes entering warehouse." style="width:100%" /></label>
        <button type="submit" class="export-button">Build task</button>
      </form>
      <pre data-warehouse-task-output style="display:none;white-space:pre-wrap;background:#f8fafc;padding:12px;border-radius:8px"></pre>
      <h4>Movement timeline</h4>
      ${events ? `<div class="detected-table-wrap"><table class="detected-table"><thead><tr><th>Time</th><th>Event</th><th>Object ID</th><th>Camera</th><th>Zone</th><th>Inventory Δ</th></tr></thead><tbody>${events}</tbody></table></div>` : '<p class="empty">No engine events yet.</p>'}
    </section>
  `;
}

async function renderCatalogResults(container, force = false) {
  try {
    const [payload, engine] = await Promise.all([
      catalogRequest(catalogApiPath("/api/catalog/results"), { force }),
      catalogRequest("/api/warehouse-engine/overview?limit=100", { force }),
    ]);
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
      ${warehouseEngineOverviewHtml(engine)}
    `;
    const button = container.querySelector("[data-run-live-recognition]");
    button?.addEventListener("click", () => startLiveCatalogRecognition(container, button));
    container.querySelector("[data-warehouse-task-builder]")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const output = container.querySelector("[data-warehouse-task-output]");
      try {
        const task = await catalogRequest("/api/warehouse-engine/tasks/parse", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt: event.currentTarget.elements.prompt.value }),
        });
        output.style.display = "block";
        output.textContent = JSON.stringify(task.task, null, 2);
      } catch (error) {
        toast(error.message);
      }
    });
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
    let status = await catalogRequest(catalogApiPath("/api/catalog/recognition/run-live"), { method: "POST" });
    while (status.running) {
      if (!container.isConnected || accountModule !== "analytics") return;
      if ((status.results || []).length) {
        await refreshCatalogResultsTable(container, status.results);
      } else {
        const table = container.querySelector("[data-catalog-table]");
        if (table) {
          const scan = status.yolo_scan;
          const detail = scan
            ? ` YOLO scanned ${Number(scan.camera_count || 0).toLocaleString()} camera feeds and produced ${Number(scan.detection_count || 0).toLocaleString()} fresh detections; ${Number(scan.cached_candidate_count || 0).toLocaleString()} existing detector crops were also checked.${Number(scan.proposal_count || 0) > 0 ? ` The class-agnostic fallback generated ${Number(scan.proposal_count).toLocaleString()} object proposals for reference matching.` : ""}${scan.catalog_scores ? ` Best catalog similarity: ${Object.entries(scan.catalog_scores).map(([name, score]) => `${name} ${Math.round(Number(score) * 100)}%`).join(", ")}.` : ""}${scan.error ? ` YOLO error: ${scan.error}; fallback proposals were still evaluated.` : ""}`
            : "";
          table.innerHTML = `<p class="empty">Scanning all live feeds… matched items, quantities, cameras, and crops will appear here during this countdown.${escapeHtml(detail)}</p>`;
        }
      }
      button.textContent = `${t("actions.recognizing")} ${Number(status.remaining_seconds || 0).toLocaleString()}s`;
      await new Promise((resolve) => setTimeout(resolve, 1000));
      status = await catalogRequest(catalogApiPath("/api/catalog/recognition/run-live/status"));
    }
    const payload = await catalogRequest(catalogApiPath("/api/catalog/results"));
    if (container.isConnected && accountModule === "analytics") {
      await refreshCatalogResultsTable(container, payload.results || []);
      button.disabled = false;
      button.textContent = t("actions.run_recognition");
      toast(t("toast.recognition_complete"));
    }
  } catch (error) {
    button.disabled = false;
    button.textContent = t("actions.run_recognition");
    toast(error.message);
  }
}

async function renderCatalogDimensions(container, force = false) {
  try {
    const [catalog, recognition] = await Promise.all([
      catalogRequest(catalogApiPath("/api/catalog/items"), { force }),
      catalogRequest(catalogApiPath("/api/catalog/results"), { force }),
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

function warehouseLogAction(event) {
  const type = String(event.event_type || "event").replaceAll("_", " ");
  const delta = Number(event.inventory_delta || 0);
  if (delta > 0) return `Added ${delta} to inventory`;
  if (delta < 0) return `Removed ${Math.abs(delta)} from inventory`;
  if (event.previous_zone && event.zone && event.previous_zone !== event.zone) {
    return `Moved from ${event.previous_zone} to ${event.zone}`;
  }
  return type.charAt(0).toUpperCase() + type.slice(1);
}

function warehouseLogsHtml(events) {
  if (!events.length) return `<p class="empty">No engine actions have been recorded yet.</p>`;
  return `
    <div class="detected-table-wrap">
      <table class="detected-table">
        <thead><tr><th>Time</th><th>Action</th><th>Camera</th><th>Object</th><th>Product</th><th>Zone</th><th>Confidence</th><th>Inventory Δ</th></tr></thead>
        <tbody>${events.map((event) => `
          <tr>
            <td>${escapeHtml(formatCatalogTime(event.timestamp))}</td>
            <td><strong>${escapeHtml(warehouseLogAction(event))}</strong><br><small>${escapeHtml(String(event.event_type || "").replaceAll("_", " "))}</small></td>
            <td>${escapeHtml(event.camera_id || "—")}</td>
            <td>${escapeHtml(event.object_id || "—")}</td>
            <td>${escapeHtml(event.product_name || "Unidentified")}</td>
            <td>${escapeHtml(event.zone || "Unassigned")}</td>
            <td>${Math.round(Number(event.confidence || 0) * 100)}%</td>
            <td class="count-cell">${Number(event.inventory_delta || 0) > 0 ? "+" : ""}${Number(event.inventory_delta || 0).toLocaleString()}</td>
          </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
}

async function renderWarehouseLogs(container, force = false) {
  try {
    const payload = await catalogRequest("/api/warehouse-engine/events?limit=500", { force });
    if (!container.isConnected || accountModule !== "logs") return;
    const events = payload.events || [];
    container.innerHTML = `
      <section class="detected-list">
        <header class="detected-list-head">
          <div><h3>Warehouse action logs</h3><p>Every detection, movement, zone transition, rule decision, and inventory change recorded by the engine.</p></div>
          <button type="button" class="export-button" data-refresh-warehouse-logs>Refresh logs</button>
        </header>
        <p class="chart-note">Showing the latest ${events.length.toLocaleString()} actions, newest first.</p>
        ${warehouseLogsHtml(events)}
      </section>`;
    container.querySelector("[data-refresh-warehouse-logs]")?.addEventListener("click", () => {
      container.innerHTML = `<p class="empty">Refreshing action logs…</p>`;
      void renderWarehouseLogs(container, true);
    });
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
                const health = [];
                const frameAge = stream ? cameraInfoFrameAge(stream) : null;
                if (frameAge != null) health.push(`${uiText("Last frame", "Последний кадр")}: ${cameraInfoDuration(frameAge)} ${uiText("ago", "назад")}`);
                if (Number(stream?.reconnect_count || 0) > 0) health.push(`${uiText("Reconnects", "Переподключений")}: ${Number(stream.reconnect_count).toLocaleString()}`);
                if (Number(stream?.decode_errors || 0) > 0) health.push(`${uiText("Decode errors", "Ошибок декодирования")}: ${Number(stream.decode_errors).toLocaleString()}`);
                const detailLine = [detail, ...health].filter(Boolean).join(" · ");
                const slotLabel = channel.slot_number != null ? `${t("table.slot")} ${channel.slot_number}` : t("table.not_assigned");
                return `
                  <li class="nvr-channel ${stateClass}" title="${escapeHtml(detailLine)}">
                    <span>${escapeHtml(t("table.channel_short"))} ${channel.channel} · ${escapeHtml(slotLabel)}</span>
                    <span class="nvr-channel-status">${label}</span>
                    ${detailLine ? `<small class="nvr-channel-detail">${escapeHtml(detailLine)}</small>` : ""}
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

  if (menu.id === "enterprise") {
    renderEnterprisePage(els.moduleContent);
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

  if (menu.id === "events") {
    els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(uiText("Loading events...", "Загрузка событий..."))}</p>`;
    void renderEventsPage(els.moduleContent);
    return;
  }

  if (menu.id === "zones") {
    renderSafetyZonesPage(els.moduleContent);
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

  if (menu.id === "ai_models") {
    els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(uiText("Loading AI models...", "Загрузка AI моделей..."))}</p>`;
    void renderAiModelsPage(els.moduleContent);
    return;
  }

  if (menu.id === "ai_modules") {
    els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(t("modules.loading"))}</p>`;
    void renderAiModules(els.moduleContent);
    return;
  }

  if (menu.id === "dimension") {
    els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(t("dimension.loading"))}</p>`;
    void renderCatalogDimensions(els.moduleContent);
    return;
  }

  if (menu.id === "integrations") {
    els.moduleContent.innerHTML = `<p class="empty">${escapeHtml(uiText("Loading integrations...", "Загрузка интеграций..."))}</p>`;
    void renderIntegrationsPage(els.moduleContent);
    return;
  }

  if (menu.id === "logs") {
    els.moduleContent.innerHTML = `<p class="empty">Loading warehouse action logs…</p>`;
    void renderWarehouseLogs(els.moduleContent);
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
        ? `<input type="number" min="1" max="${MAX_NVR_SLOTS}" value="26" data-discovery-channels aria-label="${escapeAttr(t("discovery.channels_label"))}" title="${escapeAttr(t("discovery.channels_label"))}" />`
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

  if (form.dataset.accForm === "catalog-prompts") {
    const itemId = form.dataset.itemId;
    const prompts = form.elements.prompts.value
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    submit.textContent = "Saving…";
    try {
      await catalogRequest(catalogApiPath(`/api/catalog/items/${encodeURIComponent(itemId)}/prompts`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompts }),
      });
      toast("YOLO prompts saved. They will be used in the next recognition run.");
      renderAccountModule();
    } catch (error) {
      toast(error.message);
      submit.disabled = false;
      submit.textContent = "Save prompts";
    }
    return;
  }

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

  if (form.dataset.accForm === "learned-product-save") {
    const productName = form.elements.name.value.trim();
    if (!productName) return;
    const viewIndices = Array.from(form.querySelectorAll('input[name="learned-view"]:checked'))
      .map((input) => Number(input.value));
    const existingItemId = form.querySelector('input[name="use-existing-product"]:checked')?.value || null;
    if (viewIndices.length < 1) {
      toast("Select at least one clear picture of the product.");
      return;
    }
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    submit.textContent = "Saving to base…";
    try {
      await catalogRequest(catalogApiPath("/api/catalog/learning/save"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: form.dataset.sessionId,
          product_name: productName,
          view_indices: viewIndices,
          existing_item_id: existingItemId,
        }),
      });
      productLearningSessionId = null;
      toast(`"${productName}" learned and activated. Counting can start now.`);
      renderAccountModule();
    } catch (error) {
      toast(error.message);
      submit.disabled = false;
      submit.textContent = "Save to base";
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

  if (action === "learn-product") {
    const cameraName = els.moduleContent.querySelector("[data-learning-camera]")?.value;
    if (!cameraName) {
      toast("Select the camera where you will show the product.");
      return;
    }
    const panel = els.moduleContent.querySelector("[data-product-learning-panel]");
    if (panel) panel.innerHTML = `<div class="module-placeholder"><h3>Starting live capture…</h3><p>Place the product clearly in view of a camera now.</p></div>`;
    void startProductLearning(els.moduleContent, button, cameraName);
    return;
  }

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
    if (accountModule === accButton.dataset.accModule) return;
    accountModule = accButton.dataset.accModule;
    renderAccountModule();
    return;
  }
  const button = event.target.closest("[data-module]");
  if (!button) return;
  if (state.activeModule === button.dataset.module) return;
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
  invalidateDashboardReads();
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

# AI Vision Warehouse — To‘liq hujjat

Bu hujjat loyiha qanday ishlashini oddiy tilda tushuntiradi. Uni texnik odam ham, texnik bo‘lmagan rahbar/operator ham o‘qib tushuna olishi uchun yozildi.

## 1. Loyiha nima qiladi?

AI Vision Warehouse — bu ombor yoki do‘kon kameralarini bitta dashboardga ulab, kamera tasvirlarida ko‘rinayotgan buyumlarni aniqlash, sanash va nazorat qilish tizimi.

Hozirgi holatda tizim:

- 10 ta NVR kamera kanalini bitta serverga ulaydi.
- Har bir kamerani alohida slot sifatida ko‘rsatadi.
- Dashboardda kameralarni grid ko‘rinishida chiqaradi.
- Kameradan kelgan tasvirlarga AI ishlov beradi.
- Buyum aniqlanganda uni ombor hisobiga yozadi.
- Masalan, “cardboard box” ko‘rinsa, tizim uni kirim sifatida yozadi.
- Har bir aniqlangan buyum uchun kamera nomi, vaqt, obyekt turi, taxminiy o‘lcham va masofa saqlanadi.
- Ma’lumotlar server o‘chib-yonib ketsa ham yo‘qolmasligi uchun PostgreSQL bazasida saqlanadi.

## 2. Hozir ishlab turgan qismlar

### Dashboard

Dashboard foydalanuvchi ko‘radigan asosiy sahifa.

Manzil:

[https://ai-vision-dashboard-phi.vercel.app](https://ai-vision-dashboard-phi.vercel.app)

Dashboardda quyidagilar bor:

- Start / Stop detection tugmalari
- Camera Settings sahifasi
- 10 ta kamera grid ko‘rinishi
- Warehouse Events sahifasi
- Aniqlangan buyumlar jadvali
- Ombor kirim/chiqim statistikasi
- 3D/spatial taxminiy obyekt ma’lumotlari

### Backend server

Backend — bu dashboard ortida ishlaydigan “miya”. U kameralarni ulaydi, detection jarayonini yuritadi, ma’lumotlarni bazaga yozadi.

Manzil:

[https://ai-vision-backend-nasoe.ondigitalocean.app](https://ai-vision-backend-nasoe.ondigitalocean.app)

Foydali tekshiruv linklari:

- Status: [https://ai-vision-backend-nasoe.ondigitalocean.app/api/status](https://ai-vision-backend-nasoe.ondigitalocean.app/api/status)
- Kameralar: [https://ai-vision-backend-nasoe.ondigitalocean.app/api/cameras](https://ai-vision-backend-nasoe.ondigitalocean.app/api/cameras)
- Ombor stock: [https://ai-vision-backend-nasoe.ondigitalocean.app/api/warehouse/stock](https://ai-vision-backend-nasoe.ondigitalocean.app/api/warehouse/stock)
- Harakatlar: [https://ai-vision-backend-nasoe.ondigitalocean.app/api/warehouse/movements](https://ai-vision-backend-nasoe.ondigitalocean.app/api/warehouse/movements)

### Ma’lumotlar bazasi

Oldin tizim SQLite ishlatardi. SQLite kichik testlar uchun qulay, lekin server qayta deploy bo‘lsa yoki fayl o‘chsa, kamera sozlamalari yo‘qolib qolishi mumkin edi.

Hozir PostgreSQL qo‘shildi.

Bu nimani beradi?

- Kamera sozlamalari server restart bo‘lsa ham saqlanadi.
- Ombor harakatlari yo‘qolmaydi.
- Xavfsizlik audit yozuvlari saqlanadi.
- Deploy qilingandan keyin demo kamera holatiga qaytib ketish xavfi kamayadi.

DigitalOcean’da PostgreSQL komponent nomi:

`ai-vision-postgres`

Backend `DATABASE_URL` orqali shu bazaga ulanadi.

## 3. Kamera tizimi qanday ulangan?

Kameralar alohida-alohida IP kamera sifatida emas, NVR/controller orqali ulangan.

Oddiy tushuntirish:

- NVR — kameralarni bitta joyga yig‘ib turadigan qurilma.
- Kamera 1, Kamera 2, Kamera 3 va hokazo kanallar NVR ichida turadi.
- Server NVR’ga internet orqali ulanadi.
- Har bir kanal alohida RTSP stream sifatida olinadi.

Hozir 10 ta kamera sloti ishlayapti:

| Slot | Nomi |
|---:|---|
| 1 | Warehouse NVR Main Camera 1 |
| 2 | Warehouse NVR Main Camera 2 |
| 3 | Warehouse NVR Main Camera 3 |
| 4 | Warehouse NVR Main Camera 4 |
| 5 | Warehouse NVR Main Camera 5 |
| 6 | Warehouse NVR Main Camera 6 |
| 7 | Warehouse NVR Main Camera 7 |
| 8 | Warehouse NVR Main Camera 8 |
| 9 | Warehouse NVR Main Camera 9 |
| 10 | Warehouse NVR Main Camera 10 |

Dashboarddagi Camera Settings sahifasida shu slotlar ko‘rinadi. Detection boshlanganda har bir slotdan tasvir olinadi.

## 4. “Detection” qanday ishlaydi?

Detection — kamera tasvirini AI orqali tekshirish jarayoni.

Jarayon oddiy qilib shunday:

1. NVR’dan kamera tasviri keladi.
2. Backend har bir kameradan frame oladi.
3. AI/detector frame ichida buyum bor-yo‘qligini tekshiradi.
4. Aniqlangan buyum live feed ustida ko‘rsatiladi.
5. Buyum stock/movement jadvaliga yoziladi.
6. Dashboard bu ma’lumotlarni foydalanuvchiga chiqaradi.

Hozirgi live holatda tekshirilgan natija:

- 10 ta kamera ulangan.
- Detection running holatida.
- 10 ta kamera bo‘yicha frame o‘qilyapti.
- Har bir slot uchun live MJPEG feed ishlaydi.
- Warehouse stock’da “cardboard box” yozuvi bor.
- Movement log’da har bir kameradan bittadan box aniqlangani saqlangan.

## 5. Muhim: lightweight detector va full YOLO farqi

Hozir tizim 10 ta kamera bilan barqaror ishlashi uchun lightweight/instant detector rejimida ishlayapti.

Bu nimani anglatadi?

- Tizim tez ishga tushadi.
- 10 ta kamera bilan server yiqilib qolmasligi uchun yengil rejim ishlatiladi.
- Buyum sanash va dashboard oqimi ishlaydi.
- 3D/spatial taxminiy o‘lchamlar ham chiqadi.

Full YOLO modeli nima?

Full YOLO — og‘irroq, aniqroq AI model. U real obyektlarni yanada kuchliroq aniqlaydi, lekin ko‘proq CPU/RAM/GPU talab qiladi.

Nega hozir full YOLO doimiy yoqilmagan?

DigitalOcean’dagi hozirgi server 10 ta kamera + og‘ir YOLO modelni bir vaqtda barqaror ko‘tarishi qiyin. Oldingi testlarda og‘ir model 10 stream bilan server jarayonini o‘ldirishi yoki restart qildirishi mumkinligi ko‘rindi.

Eng to‘g‘ri yo‘l:

- Hozir: 10 kamera uchun stable lightweight mode.
- Keyingi bosqich: kuchliroq server/GPU yoki kamroq kamera bilan full YOLO.
- Production uchun: real obyekt aniqlash sifati kerak bo‘lsa, server planini kattalashtirish kerak.

## 6. 3D/spatial analysis nima?

Tizim kamera tasviridan buyumning taxminiy shakli, o‘lchami va masofasini hisoblaydi.

Masalan:

- object type: `cuboid`
- inventory name: `cardboard box`
- width / height / depth: taxminiy o‘lchamlar
- distance: kameradan taxminiy masofa
- method: `monocular_ground_plane`

Oddiy qilib: bitta oddiy kamera bilan “haqiqiy 3D skaner” kabi mukammal o‘lchash imkoni yo‘q. Lekin tizim kamera balandligi, ko‘rish burchagi va obyekt joylashuviga qarab foydali taxmin beradi.

Aniq o‘lcham kerak bo‘lsa:

- kamera balandligini aniq kiritish kerak;
- kamera burchagini kalibrlash kerak;
- obyektning real standart o‘lchamlari kiritilishi kerak;
- eng aniq yechim uchun stereo/depth kamera kerak bo‘ladi.

## 7. Ombor hisob-kitobi qanday yuradi?

Warehouse module buyumlar kirim/chiqimini yozadi.

Hozir tizim “appearance mode” ishlatadi. Ya’ni kamera tasvirida buyum ko‘rinsa, tizim uni stock harakati sifatida qayd qiladi.

Saqlanadigan ma’lumotlar:

- buyum nomi;
- yo‘nalish: IN yoki OUT;
- quantity;
- kamera nomi;
- tracking ID;
- confidence;
- taxminiy o‘lcham;
- taxminiy masofa;
- vaqt.

Misol:

`Warehouse NVR Main Camera 9` kamerasi `cardboard box` ko‘rsa, movement log’da shu kamera nomi bilan yozuv paydo bo‘ladi.

## 8. Dashboarddan qanday foydalaniladi?

### Detection boshlash

1. Dashboardga kiring.
2. Start Detection tugmasini bosing.
3. Bir necha soniya kuting.
4. Status running bo‘lishi kerak.
5. Camera grid’da har bir kamera alohida ko‘rinishi kerak.

### Detection to‘xtatish

1. Stop Detection tugmasini bosing.
2. Status running false bo‘ladi.
3. Kamera feed yangilanishi to‘xtaydi.

### Kamera sozlamalari

Camera Settings sahifasida:

- mavjud kameralar ro‘yxati;
- qaysi kamera qaysi slotda turgani;
- NVR/controller ulash formasi;
- individual RTSP kamera qo‘shish formasi bor.

### Warehouse Events

Bu sahifada:

- stock;
- kirim/chiqim;
- aniqlangan buyumlar;
- suspicious yoki alohida voqealar ko‘rsatiladi.

## 9. Server va hosting arxitekturasi

Tizim uch asosiy qismdan iborat:

| Qism | Qayerda joylashgan | Vazifasi |
|---|---|---|
| Dashboard | Vercel | Foydalanuvchi ko‘radigan web sahifa |
| Backend | DigitalOcean App Platform | Kameralar, detection, API |
| PostgreSQL | DigitalOcean | Kamera sozlamalari va ombor ma’lumotlari |

Oddiy oqim:

```text
Foydalanuvchi
   ↓
Vercel Dashboard
   ↓
DigitalOcean Backend API
   ↓
NVR / Kameralar
   ↓
Detection + Warehouse counting
   ↓
PostgreSQL database
```

## 10. Auto-deploy qanday ishlaydi?

GitHub `main` branch’ga kod push bo‘lsa, GitHub Actions avtomatik DigitalOcean backend deploy qiladi.

Mavjud workflow:

- `.github/workflows/digitalocean-deploy.yml`

PostgreSQL qo‘shish uchun alohida helper workflow ham bor:

- `.github/workflows/digitalocean-add-postgres.yml`

Bu workflow DigitalOcean app spec’ga PostgreSQL komponent qo‘shish va backendga `DATABASE_URL` ulash uchun ishlatilgan.

## 11. Xavfsizlik choralari

Tizimga quyidagi xavfsizlik elementlari qo‘shilgan:

### 1. Kamera parollari dashboardda yashiriladi

RTSP URL ichida username/password bo‘lsa ham, API javobida parol `****` qilib ko‘rsatiladi.

Masalan:

`rtsp://admin:****@server:554/...`

### 2. PostgreSQL serverda saqlaydi

Kamera sozlamalari oddiy lokal faylda emas, PostgreSQL’da saqlanadi. Bu production uchun xavfsizroq va ishonchliroq.

### 3. Security audit log

Tizimda tamper-evident audit log mavjud. Bu blockchain’ga o‘xshash hash-chain prinsipi bilan ishlaydi.

Oddiy tushuntirish:

- Har bir audit yozuvi o‘zidan oldingi yozuv hash’iga bog‘lanadi.
- Kimdir eski yozuvni o‘zgartirsa, zanjir buziladi.
- Bu public blockchain emas, lekin ichki audit uchun juda foydali.

### 4. CORS cheklovi

Backend faqat ruxsat berilgan frontend manzillaridan ishlashga moslangan.

### 5. Browser permissions policy

Backend javoblarida brauzerga kamera/mikrofon/geolocation kabi ruxsatlar bloklanadi. Bu dashboardning ortiqcha brauzer ruxsatlarini so‘ramasligiga yordam beradi.

### 6. API key rejimi mavjud

`ADMIN_API_KEY` qo‘yilsa, backend endpointlari API key talab qiladi. Hozirgi statusda `api_key_required: false`, ya’ni bu qatlam hali majburiy yoqilmagan.

Production uchun tavsiya:

- `ADMIN_API_KEY` yoqish;
- dashboard token bilan ishlashi;
- DigitalOcean tokenni rotate qilish;
- kamera parollarini faqat env/secrets ichida saqlash;
- Vercel va DO access’larni faqat kerakli odamlarga berish.

## 12. Muhim operational tavsiyalar

### Har kuni tekshirish

Operator quyidagilarni tekshirishi kerak:

1. Dashboard ochilyaptimi?
2. Backend `/api/status` running holatidami?
3. `camera_count` 10 ko‘rsatyaptimi?
4. Camera grid’da hamma slotlar chiqyaptimi?
5. Warehouse stock yangilanyaptimi?

### Kamera ishlamay qolsa

Agar bir kamera qora ekran bo‘lsa:

1. Camera Settings’da statusni tekshiring.
2. NVR internetga chiqqanini tekshiring.
3. RTSP port ochiq ekanini tekshiring.
4. NVR ichida kanal raqami o‘zgarmaganini tekshiring.
5. Detection’ni restart qiling.

### Backend sekinlashsa

Sabablar:

- 10 kamera juda ko‘p CPU ishlatyapti;
- NVR HEVC stream yuboryapti;
- server plan kichik;
- full YOLO yoqilgan bo‘lsa, model og‘irlik qilyapti.

Yechimlar:

- substream ishlatish;
- kamera resolution/FPS pasaytirish;
- server planini kattalashtirish;
- GPU serverga o‘tish;
- full YOLO’ni kamroq kamera bilan test qilish.

## 13. Hozirgi cheklovlar

Bu juda muhim:

1. Hozir real-time 10 kamera barqarorligi lightweight detector bilan tasdiqlangan.
2. Full YOLO real detection uchun kuchliroq server kerak bo‘lishi mumkin.
3. Bitta oddiy kamera orqali 3D o‘lchash taxminiy bo‘ladi, laboratoriya aniqligidagi o‘lchov emas.
4. HEVC streamlarda `PPS id out of range` kabi FFmpeg ogohlantirishlari chiqishi mumkin. Bu NVR codec/stream xususiyati bilan bog‘liq. Feed baribir ishlasa, bu fatal xato emas.
5. Xavfsizlik uchun API key hali majburiy yoqilmagan. Production’da yoqish kerak.

## 14. Ertangi demo uchun qisqa tekshiruv ro‘yxati

Demo boshlashdan oldin:

- Dashboard ochiladi.
- Backend status ochiladi.
- `/api/cameras` 10 active camera ko‘rsatadi.
- Start Detection bosiladi.
- 30–60 soniya kutiladi.
- `/api/status` ichida:
  - `running: true`
  - `state: running`
  - `camera_count: 10`
  - `frames_read` oshib boradi
- Camera grid’da 10 feed ko‘rinadi.
- Warehouse stock’da `cardboard box` yoki boshqa aniqlangan item ko‘rinadi.
- Movements jadvalida kamera nomlari bilan yozuvlar paydo bo‘ladi.

## 15. Keyingi eng muhim ishlar

1. API key security’ni production uchun yoqish.
2. Full YOLO uchun server resursini oshirish yoki GPU plan tanlash.
3. Har bir kamera uchun haqiqiy zone/line sozlash.
4. Box, sack, pallet kabi real ombor obyektlari ro‘yxatini aniq belgilash.
5. Operator uchun login tizimi qo‘shish.
6. Alertlar: after-hours, suspicious removal, camera offline.
7. Backup/recovery tartibini yozib qo‘yish.

## 16. Oddiy xulosa

Tizim hozir quyidagi asosiy vazifani bajaryapti:

“NVR’dagi 10 ta kamerani internet orqali olib, dashboardda alohida ko‘rsatadi, detection ishlatadi, buyumlarni sanaydi va natijalarni PostgreSQL bazaga yozadi.”

Bu endi demo uchun ishlaydigan asosiy mahsulot holatiga keldi. Keyingi katta sakrash — real YOLO modelni 10 kamera bilan barqaror ishlatish uchun server quvvatini oshirish.

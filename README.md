# الحجز الآلي للوجبات — PROGRES WebEtu

أداة بايثون تحجز وجباتك الجامعية تلقائيا كل يوم، قبل إغلاق الحجز منتصف الليل (الحد الأقصى 3 أيام مسبقا حسب بلاغ الديوان).

**كل الملفات في مجلد واحد:**
`progres_auto_booking.py` · `config.json` · `requirements.txt` · `README.md`

## ⚠️ مهم قبل البدء
- مسار تسجيل الدخول (`/api/authentication/v1/`) مأخوذ من معرفتي بالمنصة وقد يختلف.
- **مسار الحجز نفسه غير منشور**، ولم أستطع اختباره (لا اتصال من بيئتي). لذلك تركته `TODO`، وستستخرجه مرة واحدة من متصفحك (الخطوة 2).
- استعمله لحسابك الشخصي فقط، وبوتيرة معقولة (مرة يوميا).

## 1) التثبيت
```
pip install -r requirements.txt
```
ضع في `config.json` اسم المستخدم، وكلمة السر الأفضل عبر متغير بيئة:
```
export PROGRES_PASSWORD="كلمة_السر"        # Windows: set PROGRES_PASSWORD=...
```

## 2) استخراج مسار الحجز (مرة واحدة)
1. افتح `https://progres.mesrs.dz/webetu/` في Chrome وسجّل الدخول.
2. اضغط F12 ← تبويب **Network** ← فعّل **Preserve log**.
3. احجز وجبة يدويا لليوم التالي.
4. كليك يمين على أي طلب ← **Save all as HAR with content** ← احفظه في هذا المجلد باسم `capture.har`.
5. شغّل:
   ```
   python progres_auto_booking.py --har capture.har
   ```
   سيعرض طلبات الحجز (الطريقة + الرابط + الجسم).
6. انسخ في `config.json`:
   - `endpoints.book.path` = المسار بعد `progres.mesrs.dz`
   - `endpoints.book.body` = شكل الجسم، واستبدل التاريخ بـ `{date}` والوجبة بـ `{meal}`
   - `meals` = قيم الوجبات كما تظهر في الجسم (فطور/غداء/عشاء)
   - إن ظهرت معرّفات من تسجيل الدخول مثل `uuid` أو `userId` فاستعملها هكذا: `{uuid}`

> إن كان الحجز يمر عبر الرابط بدل الجسم، ضع `{date}` و`{meal}` داخل `path` أو `params`.

## 3) التشغيل
```
python progres_auto_booking.py --dry-run   # معاينة بدون اتصال
python progres_auto_booking.py             # تنفيذ مرة واحدة
python progres_auto_booking.py --daemon    # خدمة يومية عند run_at (افتراضي 20:00)
```
السجل في `booking.log`.

## 4) الجدولة التلقائية
- **Linux/Mac (cron):** `0 20 * * * cd /المسار && PROGRES_PASSWORD=xxx python3 progres_auto_booking.py`
- **Windows:** Task Scheduler ← مهمة يومية 20:00 تشغّل الأمر نفسه.
- **الهاتف (Android):** تطبيق Termux + `--daemon`.

## الإعدادات
| المفتاح | المعنى |
|---|---|
| `meals` | قيم الوجبات المراد حجزها |
| `weekdays` | أيام الحجز (`sun`…`sat`) |
| `days_ahead` | عدد الأيام القادمة (أقصاه 3) |
| `run_at` | وقت التنفيذ اليومي في وضع `--daemon` |
| `auth_header_format` | شكل ترويسة Authorization (`{token}` أو `Bearer {token}`) |

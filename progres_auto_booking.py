#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
الحجز الآلي للوجبات الجامعية عبر PROGRES WebEtu
Auto-booking of university meals on PROGRES WebEtu (ONOU)

الاستعمال / Usage:
    python progres_auto_booking.py --dry-run          # معاينة بدون أي اتصال
    python progres_auto_booking.py                    # تنفيذ مرة واحدة
    python progres_auto_booking.py --daemon           # يبقى يعمل ويحجز يوميا في الوقت run_at
    python progres_auto_booking.py --har capture.har  # استخراج مسارات الحجز من تسجيل المتصفح

كل الإعدادات في config.json (نفس المجلد).
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    sys.exit("ثبّت المكتبة أولا:  pip install -r requirements.txt")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "config.json")
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
MAX_DAYS_AHEAD = 3  # حد الديوان: 3 أيام كحد أقصى

log = logging.getLogger("progres")


# ----------------------------------------------------------------- helpers
def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    # يُفضَّل وضع كلمة السر في متغير بيئة بدل الملف
    cfg["username"] = os.environ.get("PROGRES_USERNAME", cfg.get("username", ""))
    cfg["password"] = os.environ.get("PROGRES_PASSWORD", cfg.get("password", ""))
    return cfg


def fill(obj, ctx):
    """يستبدل {name} داخل النصوص (متداخلة) بقيم من ctx."""
    if isinstance(obj, str):
        for k, v in ctx.items():
            obj = obj.replace("{" + k + "}", str(v))
        return obj
    if isinstance(obj, dict):
        return {k: fill(v, ctx) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fill(v, ctx) for v in obj]
    return obj


def target_dates(cfg):
    days = min(int(cfg.get("days_ahead", MAX_DAYS_AHEAD)), MAX_DAYS_AHEAD)
    allowed = {WEEKDAYS[d.lower()] for d in cfg.get("weekdays", list(WEEKDAYS))}
    today = datetime.now().date()
    out = []
    for i in range(1, days + 1):  # الحجز دائما لأيام قادمة، يغلق منتصف الليل
        d = today + timedelta(days=i)
        if d.weekday() in allowed:
            out.append(d)
    return out


def seconds_until(hhmm):
    h, m = map(int, hhmm.split(":"))
    now = datetime.now()
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t <= now:
        t += timedelta(days=1)
    return (t - now).total_seconds()


# ------------------------------------------------------------------ client
class Progres:
    def __init__(self, cfg):
        self.cfg = cfg
        self.base = cfg["base_url"].rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) ProgresAutoBooking/1.0",
            "Accept": "application/json, text/plain, */*",
        })
        self.ctx = {}

    def call(self, name, extra=None):
        ep = self.cfg["endpoints"][name]
        if "TODO" in json.dumps(ep):
            sys.exit(
                f"المسار '{name}' في config.json لم يُملأ بعد (TODO).\n"
                "اتبع خطوات README.md لاستخراجه من المتصفح (--har)."
            )
        ctx = {**self.ctx, **(extra or {})}
        kwargs = {"timeout": 30}
        if "body" in ep:
            kwargs["json"] = fill(ep["body"], ctx)
        if ep.get("params"):
            kwargs["params"] = fill(ep["params"], ctx)
        return self.s.request(ep.get("method", "POST"), self.base + fill(ep["path"], ctx), **kwargs)

    def login(self):
        r = self.call("login", {
            "username": self.cfg["username"],
            "password": self.cfg["password"],
        })
        r.raise_for_status()
        data = r.json()
        token = data.get("token")
        if not token:
            raise RuntimeError("لم يُرجع الخادم token — تحقق من اسم المستخدم وكلمة السر")
        self.ctx["token"] = token
        for k, v in data.items():  # uuid, userId, id ... متاحة كـ {uuid} في القوالب
            if isinstance(v, (str, int)):
                self.ctx.setdefault(k, v)
        self.s.headers["Authorization"] = fill(
            self.cfg.get("auth_header_format", "{token}"), self.ctx
        )
        log.info("تم تسجيل الدخول")

    def book(self, day, meal):
        fmt = self.cfg.get("date_format", "%Y-%m-%d")
        r = self.call("book", {"date": day.strftime(fmt), "meal": meal})
        ok = 200 <= r.status_code < 300
        snippet = r.text[:160].replace("\n", " ")
        log.log(logging.INFO if ok else logging.WARNING,
                "%s | %s | %s %s", day, meal, r.status_code, snippet)
        return ok


# ------------------------------------------------------------------- tasks
def run_once(cfg, dry_run=False):
    dates = target_dates(cfg)
    meals = cfg.get("meals", [])
    if not dates or not meals:
        log.info("لا شيء للحجز (تحقق من weekdays / meals)")
        return
    plan = [(d, m) for d in dates for m in meals]
    if dry_run:
        for d, m in plan:
            print(f"[DRY] سيتم حجز: {d} ({d.strftime('%A')}) — {m}")
        return
    client = Progres(cfg)
    client.login()
    done = sum(client.book(d, m) for d, m in plan)
    log.info("اكتمل: %d/%d", done, len(plan))


def daemon(cfg):
    run_at = cfg.get("run_at", "20:00")
    log.info("وضع الخدمة: التنفيذ يوميا عند %s", run_at)
    while True:
        wait = seconds_until(run_at)
        log.info("الانتظار %.0f دقيقة", wait / 60)
        time.sleep(wait)
        try:
            run_once(cfg)
        except Exception as e:  # لا نوقف الخدمة بسبب خطأ عابر
            log.error("فشل التنفيذ: %s", e)


def discover_har(path):
    """يعرض الطلبات المرشحة للحجز من ملف HAR مسجَّل من المتصفح."""
    with open(path, encoding="utf-8") as f:
        har = json.load(f)
    kws = ("repas", "reserv", "restau", "meal", "book", "menu",
           "wallet", "portefeuille", "cantine", "restauration")
    found = 0
    for e in har["log"]["entries"]:
        req, res = e["request"], e["response"]
        url = req["url"]
        if "progres.mesrs.dz" not in url:
            continue
        is_write = req["method"] in ("POST", "PUT", "PATCH") and "/api/" in url
        if is_write or any(k in url.lower() for k in kws):
            found += 1
            print(f"{req['method']} {url}  ->  {res['status']}")
            body = (req.get("postData") or {}).get("text")
            if body and "password" not in body.lower():
                print(f"    body: {body[:300]}")
    if not found:
        print("لم أجد طلبات مرشحة. سجّل عملية حجز كاملة ثم صدّر HAR.")


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="حجز آلي للوجبات — PROGRES WebEtu")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--dry-run", action="store_true", help="معاينة بدون اتصال")
    ap.add_argument("--daemon", action="store_true", help="تشغيل يومي مستمر")
    ap.add_argument("--har", help="ملف HAR لاستخراج مسارات الحجز")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(HERE, "booking.log"), encoding="utf-8"),
        ],
    )

    if args.har:
        return discover_har(args.har)

    cfg = load_config(args.config)
    if args.daemon:
        daemon(cfg)
    else:
        run_once(cfg, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

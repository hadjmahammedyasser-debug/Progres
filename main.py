# -*- coding: utf-8 -*-
"""
Progres Repas — application Android (Kivy) pour la réservation automatique
des repas universitaires sur PROGRES WebEtu.

Point d'entrée de Buildozer. Réutilise la logique de progres_auto_booking.py
(même dossier). L'interface est en français : Kivy n'embarque pas de police arabe.
"""
import json
import logging
import os
import threading
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput

from progres_auto_booking import Progres, target_dates

HERE = os.path.dirname(os.path.abspath(__file__))


class UiLogHandler(logging.Handler):
    """Envoie les logs du client vers l'écran."""

    def __init__(self, fn):
        super().__init__(logging.INFO)
        self.fn = fn

    def emit(self, record):
        self.fn(record.getMessage())


class ProgresApp(App):
    title = "Progres Repas"

    # ------------------------------------------------------------ settings
    def load_defaults(self):
        with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
            return json.load(f)

    def load_settings(self):
        try:
            with open(self.settings_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_settings(self, *_):
        self.settings.update(
            username=self.user.text.strip(),
            password=self.pwd.text,
            meals=self.meals.text.strip(),
            auto=self.auto.active,
        )
        os.makedirs(self.user_data_dir, exist_ok=True)
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f)
        self.log("Paramètres enregistrés.")

    # ------------------------------------------------------------------ UI
    def build(self):
        Window.softinput_mode = "below_target"
        self.cfg = self.load_defaults()
        self.settings_path = os.path.join(self.user_data_dir, "settings.json")
        self.settings = self.load_settings()
        self.busy = False

        default_meals = ", ".join(
            m for m in self.cfg.get("meals", []) if "TODO" not in m
        )
        field_h = dp(46)

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        root.add_widget(Label(text="Réservation auto des repas", size_hint_y=None,
                              height=dp(36), font_size="18sp", bold=True))

        self.user = TextInput(
            text=self.settings.get("username", ""), hint_text="Identifiant PROGRES",
            multiline=False, size_hint_y=None, height=field_h)
        self.pwd = TextInput(
            text=self.settings.get("password", ""), hint_text="Mot de passe",
            password=True, multiline=False, size_hint_y=None, height=field_h)
        self.meals = TextInput(
            text=self.settings.get("meals", default_meals),
            hint_text="Repas (valeurs séparées par des virgules)",
            multiline=False, size_hint_y=None, height=field_h)
        for w in (self.user, self.pwd, self.meals):
            root.add_widget(w)

        row = BoxLayout(size_hint_y=None, height=field_h)
        row.add_widget(Label(text="Réserver auto à l'ouverture", halign="left"))
        self.auto = Switch(active=self.settings.get("auto", False),
                           size_hint_x=None, width=dp(90))
        row.add_widget(self.auto)
        root.add_widget(row)

        btns = BoxLayout(size_hint_y=None, height=field_h, spacing=dp(8))
        btns.add_widget(Button(text="Enregistrer", on_release=self.save_settings))
        btns.add_widget(Button(text="Réserver maintenant", on_release=self.book_now))
        root.add_widget(btns)

        self.out = Label(text="", size_hint_y=None, halign="left", valign="top")
        self.out.bind(
            width=lambda *_: setattr(self.out, "text_size", (self.out.width, None)),
            texture_size=lambda *_: setattr(self.out, "height", self.out.texture_size[1]),
        )
        scroll = ScrollView()
        scroll.add_widget(self.out)
        root.add_widget(scroll)

        logging.getLogger("progres").addHandler(UiLogHandler(self.log))
        logging.getLogger("progres").setLevel(logging.INFO)
        return root

    def on_start(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self.settings.get("auto") and self.settings.get("last_run") != today:
            Clock.schedule_once(self.book_now, 1)

    def log(self, msg):
        Clock.schedule_once(lambda dt: self._append(msg))

    def _append(self, msg):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.out.text = f"[{stamp}] {msg}\n" + self.out.text

    # ------------------------------------------------------------- booking
    def book_now(self, *_):
        if self.busy:
            return
        self.save_settings()
        self.busy = True
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            meals = [m.strip() for m in self.meals.text.split(",") if m.strip()]
            cfg = dict(self.cfg)
            cfg.update(username=self.user.text.strip(), password=self.pwd.text,
                       meals=meals)
            dates = target_dates(cfg)
            if not dates or not meals:
                self.log("Rien à réserver (vérifiez les repas et les jours).")
                return
            if not cfg["username"] or not cfg["password"]:
                self.log("Renseignez l'identifiant et le mot de passe.")
                return
            client = Progres(cfg)
            client.login()
            plan = [(d, m) for d in dates for m in meals]
            done = sum(client.book(d, m) for d, m in plan)
            self.log(f"Terminé : {done}/{len(plan)} réservations.")
            if done == len(plan):
                self.settings["last_run"] = datetime.now().strftime("%Y-%m-%d")
                self.save_settings()
        except BaseException as e:  # SystemExit (TODO) incluse
            self.log(f"Erreur : {e}")
        finally:
            self.busy = False


if __name__ == "__main__":
    ProgresApp().run()

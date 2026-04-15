#!/usr/bin/env python3
"""
Home Monitor - macOS Menu Bar App
Displays real-time data from Solarman, Tesla, ROTEX and Netatmo
"""

import rumps
import requests
import hashlib
import threading
import time
import json
import os
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────────────────
CONFIG_FILE = os.path.expanduser("~/.home_monitor_config.json")

DEFAULT_CONFIG = {
    "solarman": {
        "email": "",
        "password": "",
        "token": "",
        "plant_id": ""
    },
    "rotex": {
        "username": "",
        "password": "",
        "heating_circuit_id": 16443
    },
    "tesla": {
        "access_token": "",
        "refresh_token": "",
        "client_id": "",
        "client_secret": "",
        "vin": "",
        "region": "EU"
    },
    "poll_intervals": {
        "solarman": 60,
        "rotex": 60,
        "tesla": 300
    }
}

FLEET_API_HOSTS = {
    "EU": "fleet-api.prd.eu.vn.cloud.tesla.com",
    "NA": "fleet-api.prd.na.vn.cloud.tesla.com",
    "CN": "fleet-api.prd.cn.vn.cloud.tesla.com"
}

MODE_NAMES = {1: "Standby", 3: "Calefaccion", 5: "Verano", 17: "Refrigeracion"}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            # Merge with defaults for missing keys
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
                elif isinstance(v, dict):
                    for k2, v2 in v.items():
                        if k2 not in cfg[k]:
                            cfg[k][k2] = v2
            return cfg
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ─── API Clients ─────────────────────────────────────────────────────────────

class SolarmanClient:
    BASE = "https://globalpro.solarmanpv.com"

    def __init__(self, cfg):
        self.email = cfg.get("email", "")
        self.password = cfg.get("password", "")
        self.token = cfg.get("token", "")
        self.plant_id = cfg.get("plant_id", "")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def login(self):
        if self.token:
            return
        pwd_hash = hashlib.sha256(self.password.encode()).hexdigest()
        r = self.session.post(f"{self.BASE}/maintain-s/simple/login", json={
            "identity": self.email,
            "secret": pwd_hash,
            "grant_type": "password"
        })
        r.raise_for_status()
        self.token = r.json().get("data", {}).get("access_token", "")

    def get_data(self):
        if not self.token:
            self.login()
        self.session.headers["Authorization"] = f"Bearer {self.token}"
        r = self.session.post(f"{self.BASE}/maintain-s/operating/station/search",
                              json={"page": 1, "size": 10},
                              params={"token": self.token})
        if r.status_code == 401:
            self.token = ""
            self.login()
            return self.get_data()
        r.raise_for_status()
        plant = r.json().get("data", [{}])[0]
        gen = (plant.get("generationPower") or 0) / 1000
        use = (plant.get("usePower") or 0) / 1000
        soc = plant.get("batterySoc") or 0
        grid = (plant.get("gridPower") or 0) / 1000
        surplus = max(0, gen - use)
        bat_calc = round(gen - use - grid, 2)
        return {
            "generation": round(gen, 2),
            "consumption": round(use, 2),
            "battery_soc": soc,
            "surplus": round(surplus, 2),
            "grid": round(grid, 2),
            "bat_power": round(abs(bat_calc), 2),
            "charging": round(bat_calc, 2) if bat_calc > 0 else 0,
            "discharging": round(abs(bat_calc), 2) if bat_calc < 0 else 0,
        }


class RotexClient:
    BASE = "https://api.rotex-control.com"

    def __init__(self, cfg):
        self.username = cfg.get("username", "")
        self.password = cfg.get("password", "")
        self.circuit_id = cfg.get("heating_circuit_id", 16443)
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        self.authenticated = False

    def login(self):
        r = self.session.post(f"{self.BASE}/login", json={
            "username": self.username,
            "password": self.password,
            "deviceInformation": {
                "deviceName": "HomeMonitor",
                "softwareVersion": "1.0.0"
            }
        })
        r.raise_for_status()
        self.authenticated = True

    def _extract_value(self, data, path):
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                if part in current:
                    val = current[part]
                    if isinstance(val, dict) and "value" in val:
                        current = val["value"]
                    else:
                        current = val
                else:
                    return None
            else:
                return None
        return current

    def get_status(self):
        if not self.authenticated:
            self.login()
        try:
            r = self.session.get(f"{self.BASE}/mobile/heatingcircuit/{self.circuit_id}")
            if r.status_code == 401:
                self.authenticated = False
                self.login()
                r = self.session.get(f"{self.BASE}/mobile/heatingcircuit/{self.circuit_id}")
            r.raise_for_status()
            data = r.json()
            mode_val = self._extract_value(data, "operationMode.type")
            return {
                "mode": mode_val if isinstance(mode_val, int) else 0,
                "mode_name": MODE_NAMES.get(mode_val, "Desconocido") if isinstance(mode_val, int) else "Desconocido",
                "boost_acs": self._extract_value(data, "onetimeHeatupActive") == True,
                "temp_acs": self._extract_number(data, "boilerActualTemperature"),
                "temp_room": self._extract_number(data, "actualTemperature"),
                "temp_outside": self._extract_number(data, "outsideTemperature"),
                "temp_boiler": self._extract_number(data, "tvbhMix"),
                "temp_acs_target": self._extract_number(data, "boilerSetTemperature"),
            }
        except Exception as e:
            return None

    def _extract_number(self, data, key):
        val = self._extract_value(data, key)
        if val is None:
            return 0.0
        try:
            return round(float(val), 1)
        except (ValueError, TypeError):
            return 0.0


class TeslaClient:
    def __init__(self, cfg):
        self.access_token = cfg.get("access_token", "")
        self.refresh_token = cfg.get("refresh_token", "")
        self.client_id = cfg.get("client_id", "")
        self.client_secret = cfg.get("client_secret", "")
        self.vin = cfg.get("vin", "")
        self.region = cfg.get("region", "EU")
        self.base_host = FLEET_API_HOSTS.get(self.region, FLEET_API_HOSTS["EU"])
        self.vehicle_id = None

    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    def _refresh_tokens(self):
        try:
            r = requests.post("https://auth.tesla.com/oauth2/v3/token", json={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token
            })
            r.raise_for_status()
            data = r.json()
            self.access_token = data.get("access_token", self.access_token)
            self.refresh_token = data.get("refresh_token", self.refresh_token)
        except:
            pass

    def get_vehicle_id(self):
        if self.vehicle_id:
            return self.vehicle_id
        try:
            r = requests.get(f"https://{self.base_host}/api/1/vehicles",
                           headers=self._headers())
            if r.status_code == 401:
                self._refresh_tokens()
                r = requests.get(f"https://{self.base_host}/api/1/vehicles",
                               headers=self._headers())
            r.raise_for_status()
            vehicles = r.json().get("response", [])
            for v in vehicles:
                if not self.vin or v.get("vin") == self.vin:
                    self.vehicle_id = v["id"]
                    return self.vehicle_id
        except:
            pass
        return None

    def get_data(self):
        vid = self.get_vehicle_id()
        if not vid:
            return None
        try:
            r = requests.get(
                f"https://{self.base_host}/api/1/vehicles/{vid}/vehicle_data"
                f"?endpoints=charge_state%3Bclimate_state%3Bvehicle_state",
                headers=self._headers()
            )
            if r.status_code == 401:
                self._refresh_tokens()
                r = requests.get(
                    f"https://{self.base_host}/api/1/vehicles/{vid}/vehicle_data"
                    f"?endpoints=charge_state%3Bclimate_state%3Bvehicle_state",
                    headers=self._headers()
                )
            if r.status_code == 408:
                return {"battery": None, "charging": "Dormido", "inside_temp": None, "locked": None}
            r.raise_for_status()
            resp = r.json().get("response", {})
            cs = resp.get("charge_state", {})
            cl = resp.get("climate_state", {})
            vs = resp.get("vehicle_state", {})
            return {
                "battery": cs.get("battery_level"),
                "charging": cs.get("charging_state", "Unknown"),
                "charge_limit": cs.get("charge_limit_soc"),
                "inside_temp": cl.get("inside_temp"),
                "outside_temp": cl.get("outside_temp"),
                "locked": vs.get("locked"),
                "sentry": vs.get("sentry_mode"),
            }
        except:
            return None


# ─── Menu Bar App ────────────────────────────────────────────────────────────

class HomeMonitorApp(rumps.App):
    def __init__(self):
        super().__init__("🏠", quit_button=None)
        self.cfg = load_config()

        # Data state
        self.solar_data = None
        self.rotex_data = None
        self.tesla_data = None
        self.last_update = {}

        # Build menu
        self.menu_title = rumps.MenuItem("Home Monitor", callback=None)
        self.menu_title.set_callback(None)

        self.sep1 = rumps.separator

        # Solar section
        self.solar_header = rumps.MenuItem("━━━ ☀️ SOLAR ━━━")
        self.solar_gen = rumps.MenuItem("  Generacion: --")
        self.solar_use = rumps.MenuItem("  Consumo: --")
        self.solar_bat = rumps.MenuItem("  Bateria Solar: --")
        self.solar_surplus = rumps.MenuItem("  Excedente: --")
        self.solar_charge = rumps.MenuItem("  Carga/Descarga: --")
        self.solar_grid = rumps.MenuItem("  Red: --")

        self.sep2 = rumps.separator

        # ROTEX section
        self.rotex_header = rumps.MenuItem("━━━ 🔥 CALEFACCION ━━━")
        self.rotex_mode = rumps.MenuItem("  Modo: --")
        self.rotex_acs = rumps.MenuItem("  ACS: --")
        self.rotex_boost = rumps.MenuItem("  Boost ACS: --")
        self.rotex_boiler = rumps.MenuItem("  Caldera: --")
        self.rotex_outside = rumps.MenuItem("  Exterior: --")

        self.sep3 = rumps.separator

        # Tesla section
        self.tesla_header = rumps.MenuItem("━━━ 🚗 TESLA ━━━")
        self.tesla_bat = rumps.MenuItem("  Bateria: --")
        self.tesla_charging = rumps.MenuItem("  Carga: --")
        self.tesla_temp = rumps.MenuItem("  Temp Interior: --")
        self.tesla_locked = rumps.MenuItem("  Cerrado: --")
        self.tesla_sentry = rumps.MenuItem("  Sentry: --")

        self.sep4 = rumps.separator
        self.last_update_item = rumps.MenuItem("Ultima actualizacion: --")
        self.refresh_btn = rumps.MenuItem("🔄 Actualizar ahora", callback=self.manual_refresh)
        self.quit_btn = rumps.MenuItem("Salir", callback=self.quit_app)

        self.menu = [
            self.solar_header,
            self.solar_gen,
            self.solar_use,
            self.solar_bat,
            self.solar_surplus,
            self.solar_charge,
            self.solar_grid,
            None,  # separator
            self.rotex_header,
            self.rotex_mode,
            self.rotex_acs,
            self.rotex_boost,
            self.rotex_boiler,
            self.rotex_outside,
            None,
            self.tesla_header,
            self.tesla_bat,
            self.tesla_charging,
            self.tesla_temp,
            self.tesla_locked,
            self.tesla_sentry,
            None,
            self.last_update_item,
            self.refresh_btn,
            self.quit_btn,
        ]

        # Start polling threads
        self._start_polling()

    def _start_polling(self):
        intervals = self.cfg.get("poll_intervals", {})
        threading.Thread(target=self._poll_loop, args=("solarman", intervals.get("solarman", 60)), daemon=True).start()
        threading.Thread(target=self._poll_loop, args=("rotex", intervals.get("rotex", 60)), daemon=True).start()
        threading.Thread(target=self._poll_loop, args=("tesla", intervals.get("tesla", 300)), daemon=True).start()

    def _poll_loop(self, source, interval):
        time.sleep(2)  # initial delay
        while True:
            try:
                if source == "solarman":
                    self._fetch_solar()
                elif source == "rotex":
                    self._fetch_rotex()
                elif source == "tesla":
                    self._fetch_tesla()
                self._update_menubar_title()
            except Exception as e:
                print(f"[{source}] Error: {e}")
            time.sleep(interval)

    def _fetch_solar(self):
        cfg = self.cfg.get("solarman", {})
        if not cfg.get("token") and not cfg.get("email"):
            return
        client = SolarmanClient(cfg)
        data = client.get_data()
        if data:
            self.solar_data = data
            self.last_update["solarman"] = datetime.now()
            self._update_solar_menu()

    def _fetch_rotex(self):
        cfg = self.cfg.get("rotex", {})
        if not cfg.get("username"):
            return
        client = RotexClient(cfg)
        data = client.get_status()
        if data:
            self.rotex_data = data
            self.last_update["rotex"] = datetime.now()
            self._update_rotex_menu()

    def _fetch_tesla(self):
        cfg = self.cfg.get("tesla", {})
        if not cfg.get("access_token"):
            return
        client = TeslaClient(cfg)
        data = client.get_data()
        if data:
            self.tesla_data = data
            self.last_update["tesla"] = datetime.now()
            self._update_tesla_menu()

    def _update_menubar_title(self):
        parts = []
        if self.solar_data:
            parts.append(f"☀️{self.solar_data['generation']}kW")
            parts.append(f"🏠{self.solar_data['consumption']}kW")
            parts.append(f"🔋{self.solar_data['battery_soc']}%")
        if self.tesla_data and self.tesla_data.get("battery") is not None:
            parts.append(f"🚗{self.tesla_data['battery']}%")
        if self.rotex_data:
            parts.append(f"🌡️{self.rotex_data['temp_acs']}°")
        if parts:
            self.title = " ".join(parts)
        else:
            self.title = "🏠 --"

    def _update_solar_menu(self):
        d = self.solar_data
        if not d:
            return
        self.solar_gen.title = f"  ☀️ Generacion: {d['generation']} kW"
        self.solar_use.title = f"  🏠 Consumo: {d['consumption']} kW"
        self.solar_bat.title = f"  🔋 Bateria Solar: {d['battery_soc']}%"
        self.solar_surplus.title = f"  💰 Excedente: {d['surplus']} kW"
        if d['charging'] > 0:
            self.solar_charge.title = f"  ⚡ Cargando Bat: +{d['charging']} kW"
        elif d['discharging'] > 0:
            self.solar_charge.title = f"  ⚡ Descargando Bat: -{d['discharging']} kW"
        else:
            self.solar_charge.title = f"  ⚡ Bateria: Inactiva"
        self.solar_grid.title = f"  🔌 Red: {d['grid']} kW"

    def _update_rotex_menu(self):
        d = self.rotex_data
        if not d:
            return
        mode_icon = {"Calefaccion": "🔥", "Verano": "☀️", "Standby": "⏸️", "Refrigeracion": "❄️"}.get(d['mode_name'], "❓")
        self.rotex_mode.title = f"  {mode_icon} Modo: {d['mode_name']}"
        self.rotex_acs.title = f"  🚿 ACS: {d['temp_acs']}° (objetivo: {d['temp_acs_target']}°)"
        self.rotex_boost.title = f"  🔥 Boost ACS: {'SI' if d['boost_acs'] else 'No'}"
        self.rotex_boiler.title = f"  🌡️ Caldera: {d['temp_boiler']}°"
        self.rotex_outside.title = f"  🌤️ Exterior: {d['temp_outside']}°"

    def _update_tesla_menu(self):
        d = self.tesla_data
        if not d:
            return
        bat = d.get("battery")
        self.tesla_bat.title = f"  🔋 Bateria: {bat}%" if bat is not None else "  🔋 Bateria: Dormido"
        charging = d.get("charging", "Unknown")
        charge_icons = {"Charging": "⚡", "Complete": "✅", "Disconnected": "🔌", "Stopped": "⏸️", "Dormido": "😴"}
        ci = charge_icons.get(charging, "❓")
        self.tesla_charging.title = f"  {ci} Carga: {charging}"
        temp = d.get("inside_temp")
        self.tesla_temp.title = f"  🌡️ Interior: {temp}°C" if temp is not None else "  🌡️ Interior: --"
        locked = d.get("locked")
        self.tesla_locked.title = f"  {'🔒' if locked else '🔓'} {'Cerrado' if locked else 'Abierto'}" if locked is not None else "  🔒 Cerrado: --"
        sentry = d.get("sentry")
        self.tesla_sentry.title = f"  🛡️ Sentry: {'Activo' if sentry else 'Inactivo'}" if sentry is not None else "  🛡️ Sentry: --"

    @rumps.clicked("🔄 Actualizar ahora")
    def manual_refresh(self, _):
        self.title = "🏠 Actualizando..."
        threading.Thread(target=self._refresh_all, daemon=True).start()

    def _refresh_all(self):
        self._fetch_solar()
        self._fetch_rotex()
        self._fetch_tesla()
        self._update_menubar_title()
        now = datetime.now().strftime("%H:%M:%S")
        self.last_update_item.title = f"Ultima actualizacion: {now}"

    def quit_app(self, _):
        rumps.quit_application()


if __name__ == "__main__":
    HomeMonitorApp().run()

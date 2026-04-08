#!/usr/bin/env python3
"""Table Saw Fence Controller — NiceGUI touchscreen app for Raspberry Pi."""

import time

from nicegui import app, ui
import paho.mqtt.client as mqtt

# ── Configuration ──────────────────────────────────────────────────────────────
MQTT_BROKER  = "stepperpi.local"
MQTT_PORT    = 1883
MAX_POS_MM = 1200.0   # safety: refuse moves beyond this distance


# ── Motor state (written by MQTT thread, read by UI timer) ────────────────────
class MotorState:
    position_mm: float = 0.0
    state: str = "disconnected"
    last_seen: float = 0.0

    def driver_online(self) -> bool:
        return time.monotonic() - self.last_seen < 2.0

motor = MotorState()


# ── MQTT client ────────────────────────────────────────────────────────────────
_mqtt = mqtt.Client()

def _on_connect(client, _userdata, _flags, rc):
    motor.state = "idle" if rc == 0 else "disconnected"
    if rc == 0:
        client.subscribe([
            ("stepper/status/position", 0),
            ("stepper/status/state", 0),
        ])

def _on_disconnect(_client, _userdata, _rc):
    motor.state = "disconnected"

def _on_message(_client, _userdata, msg):
    payload = msg.payload.decode().strip()
    motor.last_seen = time.monotonic()
    if msg.topic == "stepper/status/position":
        try:
            motor.position_mm = float(payload)
        except ValueError:
            pass
    elif msg.topic == "stepper/status/state":
        motor.state = payload

_mqtt.on_connect    = _on_connect
_mqtt.on_disconnect = _on_disconnect
_mqtt.on_message    = _on_message

def start_mqtt():
    try:
        _mqtt.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        _mqtt.loop_start()
    except Exception as e:
        print(f"MQTT connection error: {e}")

def send_move(mm: float):
    _mqtt.publish("stepper/command/position", f"{mm:.4f}")

def send_reset_position():
    _mqtt.publish("stepper/command/reset_position", "0")


# ── Box joint logic ────────────────────────────────────────────────────────────
class BoxJoint:
    """Tracks cut sequence for a box joint operation.

    Piece A cuts: positions 0, step_a, 2*step_a, ...   step_a = pin_a + kerf
    Piece B cuts: positions pin_a, pin_a+step_b, ...   step_b = pin_b + kerf
    """

    def __init__(self):
        s = app.storage.general.get("boxjoint", {})
        self.kerf:  float = s.get("kerf",  3.0)
        self.pin_a: float = s.get("pin_a", 10.0)
        self.pin_b: float = s.get("pin_b", 10.0)
        self.piece: str   = "A"
        self.cut_index: int = 0

        self._cut_lbl: ui.label
        self._pos_lbl: ui.label
        self._piece_a_btn: ui.button
        self._piece_b_btn: ui.button

    def _save(self):
        app.storage.general["boxjoint"] = {
            "kerf": self.kerf, "pin_a": self.pin_a, "pin_b": self.pin_b
        }

    def _step(self) -> float:
        return (self.pin_a if self.piece == "A" else self.pin_b) + self.kerf

    def _offset(self) -> float:
        return 0.0 if self.piece == "A" else self.pin_a

    def current_position(self) -> float:
        return round(self._offset() + self.cut_index * self._step(), 4)

    def _refresh(self):
        self._cut_lbl.set_text(f"Cut {self.cut_index + 1}  —  piece {self.piece}")
        self._pos_lbl.set_text(f"{self.current_position():.2f} mm")

    def _require_driver(self) -> bool:
        if not motor.driver_online():
            ui.notify("Driver offline", type="negative", position="top")
            return False
        return True

    def go_home(self):
        if not self._require_driver():
            return
        self.cut_index = 0
        send_move(self.current_position())
        self._refresh()

    def advance(self):
        if not self._require_driver():
            return
        self.cut_index += 1
        send_move(self.current_position())
        self._refresh()

    def select_piece(self, piece: str):
        self.piece = piece
        self.cut_index = 0
        self._refresh()
        if piece == "A":
            self._piece_a_btn.props("color=blue-8")
            self._piece_b_btn.props("color=grey-8")
        else:
            self._piece_a_btn.props("color=grey-8")
            self._piece_b_btn.props("color=blue-8")

    def build_tab(self):
        with ui.column().classes("w-full gap-3 p-2"):

            # ── Settings ──────────────────────────────────────────────────
            ui.label("Settings").classes("text-grey-5 text-xs uppercase tracking-widest")
            with ui.grid(columns=3).classes("w-full gap-2"):
                for label, attr in [("Kerf", "kerf"), ("Pin A", "pin_a"), ("Pin B", "pin_b")]:
                    with ui.column().classes("gap-0"):
                        ui.label(label).classes("text-grey-5 text-xs")
                        def _make_input(a=attr):
                            inp = (ui.number(value=getattr(self, a), format="%.2f",
                                             min=0.1, max=50, step=0.1)
                                   .classes("w-full bg-grey-9 rounded")
                                   .props("dense outlined dark suffix=mm"))
                            def _update(e, _a=a):
                                setattr(self, _a, e.value)
                                self._save()
                                self._refresh()
                            inp.on("update:model-value", _update)
                        _make_input()

            # ── Piece selector ────────────────────────────────────────────
            ui.label("Piece").classes("text-grey-5 text-xs uppercase tracking-widest")
            with ui.row().classes("gap-2 w-full"):
                self._piece_a_btn = (
                    ui.button("Piece A", on_click=lambda: self.select_piece("A"))
                    .classes("grow h-12 text-lg font-bold")
                    .props("unelevated color=blue-8 text-color=white")
                )
                self._piece_b_btn = (
                    ui.button("Piece B", on_click=lambda: self.select_piece("B"))
                    .classes("grow h-12 text-lg font-bold")
                    .props("unelevated color=grey-8 text-color=white")
                )

            # ── Current cut display ───────────────────────────────────────
            with ui.column().classes("w-full bg-grey-9 rounded px-4 py-3 gap-0"):
                self._cut_lbl = ui.label("Cut 1  —  piece A").classes(
                    "text-grey-5 text-sm"
                )
                self._pos_lbl = ui.label("0.00 mm").classes(
                    "font-mono text-5xl text-white font-bold"
                )

            # ── Home / Advance buttons ────────────────────────────────────
            with ui.row().classes("gap-2 w-full"):
                (ui.button(icon="home", on_click=self.go_home)
                 .classes("grow h-16 text-2xl font-bold")
                 .props("unelevated color=grey-7 text-color=white"))
                (ui.button("ADVANCE", icon="arrow_forward", on_click=self.advance)
                 .classes("grow h-16 text-2xl font-bold")
                 .props("unelevated color=green-8 text-color=white"))


# ── App ────────────────────────────────────────────────────────────────────────
class FenceApp:
    def __init__(self):
        self.entry: str = ""
        self.relative: bool = False
        self.history: list[float] = list(app.storage.general.get("history", []))

        # UI element references — assigned in build()
        self.display_lbl: ui.label
        self.mode_btn: ui.button
        self.history_col: ui.column
        self._reset_dialog: ui.dialog
        self.pos_lbl: ui.label
        self.state_lbl: ui.label
        self._last_state_color: str = "text-red-5"

    # ── Numpad ────────────────────────────────────────────────────────────────

    def press(self, key: str):
        v = self.entry
        match key:
            case "C":
                self.entry = ""
            case "←":
                self.entry = v[:-1]
            case "±":
                self.entry = v[1:] if v.startswith("-") else ("-" + v if v else "")
            case ".":
                if "." not in v:
                    self.entry = v + "."
            case _:  # digit 0–9
                # limit to 2 decimal places
                if "." in v and len(v.split(".")[1]) >= 2:
                    return
                self.entry = v + key
        self._refresh_display()

    def _refresh_display(self):
        v = self.entry or "0.00"
        prefix = "+" if self.relative and v and not v.startswith("-") and v != "0.00" else ""
        self.display_lbl.set_text(f"{prefix}{v}")

    def toggle_mode(self):
        self.relative = not self.relative
        if self.relative:
            self.mode_btn.set_text("REL")
            self.mode_btn.props("color=orange-8 text-color=white")
        else:
            self.mode_btn.set_text("ABS")
            self.mode_btn.props("color=grey-7 text-color=white")
        self._refresh_display()

    # ── Movement ──────────────────────────────────────────────────────────────

    def _require_driver(self) -> bool:
        if not motor.driver_online():
            ui.notify("Driver offline", type="negative", position="top")
            return False
        return True

    def go(self):
        if not self._require_driver():
            return
        if self.entry in ("-", "."):
            ui.notify("Invalid value", type="warning", position="top")
            return
        try:
            val = float(self.entry) if self.entry else 0.0
        except ValueError:
            ui.notify("Invalid value", type="negative", position="top")
            return

        target = round(motor.position_mm + val if self.relative else val, 2)

        if target < -MAX_POS_MM:
            ui.notify(f"Exceeds limit ({-MAX_POS_MM:.0f} mm)", type="warning", position="top")
            return
        if target > MAX_POS_MM:
            ui.notify(f"Exceeds limit ({MAX_POS_MM:.0f} mm)", type="warning", position="top")
            return

        send_move(target)
        self._add_history(target)
        self.entry = ""
        self._refresh_display()

    def _nudge(self, delta_mm: float):
        if not self._require_driver():
            return
        target = round(motor.position_mm + delta_mm, 2)
        if target < -MAX_POS_MM or target > MAX_POS_MM:
            ui.notify(f"Exceeds limit ({MAX_POS_MM:.0f} mm)", type="warning", position="top")
            return
        send_move(target)

    # ── History ───────────────────────────────────────────────────────────────

    def _add_history(self, pos: float):
        if pos not in self.history:
            self.history.append(pos)
        self.history.sort()
        app.storage.general["history"] = self.history
        self._rebuild_history()

    def _remove_history(self, pos: float):
        if pos in self.history:
            self.history.remove(pos)
        app.storage.general["history"] = self.history
        self._rebuild_history()

    def _go_from_history(self, pos: float):
        send_move(pos)

    def _rebuild_history(self):
        self.history_col.clear()
        with self.history_col:
            if not self.history:
                ui.label("No history yet").classes("text-grey-6 italic p-3")
                return
            for pos in self.history:
                with ui.row().classes("w-full items-center border-b border-grey-8"):
                    (ui.button(
                        f"{pos:.2f} mm",
                        on_click=lambda p=pos: self._go_from_history(p),
                    )
                    .classes("grow text-left font-mono text-lg")
                    .props("flat dense align=left text-color=white"))
                    (ui.button(
                        icon="delete_outline",
                        on_click=lambda p=pos: self._remove_history(p),
                    )
                    .classes("text-grey-5")
                    .props("flat dense round"))

    # ── Status timer ──────────────────────────────────────────────────────────

    _STATE_COLOR = {
        "idle":            "text-green-5",
        "moving":          "text-yellow-5",
        "homing":          "text-blue-4",
        "disconnected":    "text-red-5",
        "error":           "text-red-5",
        "driver offline":  "text-red-5",
    }

    def _refresh_status(self):
        self.pos_lbl.set_text(f"{motor.position_mm:.2f} mm")
        s = motor.state if motor.driver_online() else "driver offline"
        new_color = self._STATE_COLOR.get(s, "text-grey-5")
        if new_color != self._last_state_color:
            self.state_lbl.classes(remove=self._last_state_color)
            self.state_lbl.classes(add=new_color)
            self._last_state_color = new_color
        self.state_lbl.set_text(f"● {s}")

    # ── Reset position ────────────────────────────────────────────────────────

    def _confirm_reset(self):
        self._reset_dialog.open()

    def _do_reset(self):
        if not self._require_driver():
            self._reset_dialog.close()
            return
        send_reset_position()
        self._reset_dialog.close()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def build(self):
        # Confirmation dialog for position reset
        with ui.dialog() as self._reset_dialog, ui.card().classes("bg-grey-9 text-white"):
            ui.label("Reset position to 0?").classes("text-lg font-bold")
            ui.label("This will not move the stepper.").classes("text-grey-4 text-sm")
            with ui.row().classes("gap-2 w-full mt-2"):
                (ui.button("Reset", on_click=self._do_reset)
                 .classes("grow")
                 .props("unelevated color=deep-orange-9 text-color=white"))
                (ui.button("Cancel", on_click=self._reset_dialog.close)
                 .classes("grow")
                 .props("unelevated color=grey-7 text-color=white"))

        # Header
        with ui.header().classes("bg-grey-10 items-center px-4 gap-4 min-h-0 py-2"):
            self.pos_lbl = ui.label("0.00 mm").classes("text-white font-mono text-2xl font-bold")
            ui.space()
            self.state_lbl = ui.label("● disconnected").classes("text-red-5 text-sm")
            ui.button(icon="close", on_click=app.shutdown).props("flat round dense text-color=grey-5")

        # Tabs: Position | Box Joint | History
        with ui.tabs().classes("w-full bg-grey-9") as tabs:
            tab_pos  = ui.tab("Position",  icon="straighten")
            tab_bj   = ui.tab("Box Joint", icon="grid_on")
            tab_hist = ui.tab("History",   icon="history")

        with ui.tab_panels(tabs, value=tab_pos).classes("w-full grow bg-grey-10"):

            # ── Position tab ───────────────────────────────────────────────
            with ui.tab_panel(tab_pos).classes("p-2 flex flex-col gap-2"):

                # Entry display
                with ui.row().classes("items-baseline gap-1 bg-grey-9 rounded px-3 py-1 w-full"):
                    self.display_lbl = ui.label("0.00").classes(
                        "font-mono text-5xl text-white grow text-right"
                    )
                    ui.label("mm").classes("text-grey-5 text-xl self-end mb-1")

                # Digit grid — buttons grow to fill the row
                for row_keys in [["7","8","9"],["4","5","6"],["1","2","3"],[".","0","←"]]:
                    with ui.row().classes("gap-2 w-full"):
                        for k in row_keys:
                            (ui.button(k, on_click=lambda _k=k: self.press(_k))
                             .classes("grow h-14 text-2xl font-bold")
                             .props("unelevated color=grey-8 text-color=white"))

                # Control row
                with ui.row().classes("gap-2 w-full"):
                    (ui.button("C", on_click=lambda: self.press("C"))
                     .classes("grow h-12 text-lg font-bold")
                     .props("unelevated color=deep-orange-9 text-color=white"))
                    (ui.button("±", on_click=lambda: self.press("±"))
                     .classes("grow h-12 text-lg font-bold")
                     .props("unelevated color=grey-8 text-color=white"))
                    self.mode_btn = (
                        ui.button("ABS", on_click=self.toggle_mode)
                        .classes("grow h-12 text-lg font-bold")
                        .props("unelevated color=grey-7 text-color=white")
                    )

                # GO button
                (ui.button("GO", on_click=self.go)
                 .classes("w-full h-16 text-4xl font-bold")
                 .props("unelevated color=green-8 text-color=white"))

                # Nudge buttons
                with ui.row().classes("gap-2 w-full"):
                    for delta, label in [(-1, "-1"), (-0.1, "-0.1"), (0.1, "0.1"), (1, "1")]:
                        (ui.button(f"{label} mm", on_click=lambda d=delta: self._nudge(d))
                         .classes("grow h-11 text-base font-bold")
                         .props("unelevated color=blue-grey-8 text-color=white"))

                # Reset position button
                (ui.button("Reset position to 0", icon="restart_alt", on_click=self._confirm_reset)
                 .classes("w-full h-10 text-sm")
                 .props("unelevated color=grey-8 text-color=grey-4"))

            # ── Box joint tab ──────────────────────────────────────────────
            with ui.tab_panel(tab_bj).classes("p-0"):
                BoxJoint().build_tab()

            # ── History tab ────────────────────────────────────────────────
            with ui.tab_panel(tab_hist).classes("p-2"):
                with ui.scroll_area().classes("w-full").style("height: calc(100vh - 120px)"):
                    self.history_col = ui.column().classes("w-full")
                    with self.history_col:
                        ui.label("No history yet").classes("text-grey-6 italic p-3")

        ui.timer(0.5, self._refresh_status)


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    start_mqtt()
    FenceApp().build()

    # PWA meta tags — lets phones install via "Add to Home Screen" for fullscreen
    ui.add_head_html('''
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <meta name="apple-mobile-web-app-title" content="Fence">
        <link rel="manifest" href="/manifest.json">
    ''')

    @app.get("/manifest.json")
    async def manifest():
        from fastapi.responses import JSONResponse
        return JSONResponse({
            "name": "Fence Controller",
            "short_name": "Fence",
            "display": "standalone",
            "background_color": "#111",
            "theme_color": "#111",
            "start_url": "/",
            "icons": [],
        })

    ui.run(
        title="Fence Controller",
        dark=True,
        reload=False,
        host="0.0.0.0",
        port=8080,
        storage_secret="fence-controller",
    )


if __name__ == "__main__":
    main()

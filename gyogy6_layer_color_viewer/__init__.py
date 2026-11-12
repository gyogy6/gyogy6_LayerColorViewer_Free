"""
gyogy6 Layer Color Viewer for Substance 3D Painter.

Adds a "gyogy6 Layer Colors" dock that lists the colors used by the visible
layers of every Texture Set (fill colors and .sbsar color parameters) with a
swatch and #RRGGBB, so they can be copied and pasted into other layers.
"""

import substance_painter as sp

_widgets = []
_panel = None
_connections = []


def _on_stack_changed(_event):
    if _panel is not None:
        _panel.schedule_refresh()


def _on_project_closed(_event):
    if _panel is not None:
        _panel.clear()


def _connect(event_type, callback):
    sp.event.DISPATCHER.connect(event_type, callback)
    _connections.append((event_type, callback))


def start_plugin():
    global _panel  # pylint: disable=global-statement
    from .ui import LayerColorPanel  # pylint: disable=import-outside-toplevel

    _panel = LayerColorPanel()
    dock = sp.ui.add_dock_widget(_panel)
    _widgets.append(dock if dock is not None else _panel)

    # events that exist in every Python-enabled Painter version
    for name in ("ProjectOpened", "ProjectEditionEntered", "LayerStacksModelDataChanged"):
        ev = getattr(sp.event, name, None)
        if ev is not None:
            _connect(ev, _on_stack_changed)
    ev = getattr(sp.event, "ProjectAboutToClose", None)
    if ev is not None:
        _connect(ev, _on_project_closed)

    sp.logging.info("[LayerColor] plugin started")


def close_plugin():
    global _panel  # pylint: disable=global-statement
    for event_type, callback in _connections:
        try:
            sp.event.DISPATCHER.disconnect(event_type, callback)
        except Exception:  # pylint: disable=broad-except
            pass
    _connections.clear()
    for w in _widgets:
        sp.ui.delete_ui_element(w)
    _widgets.clear()
    _panel = None


if __name__ == "__main__":
    start_plugin()

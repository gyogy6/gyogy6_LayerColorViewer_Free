"""Dock panel for the gyogy6 Layer Color Viewer."""

from __future__ import annotations

from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

import substance_painter as sp

from . import core
from .i18n import tr
from .colorutil import clamp01, parse_color, to_float_text, to_hex, to_rgb255_text

COL_LAYER, COL_VALUE, COL_SWATCH, COL_HEX = range(4)
ROLE_ENTRY = QtCore.Qt.UserRole + 1


def _swatch_icon(rgb, size=16) -> QtGui.QIcon:
    pix = QtGui.QPixmap(size * 2, size)
    pix.fill(QtGui.QColor.fromRgbF(*[clamp01(c) for c in rgb]))
    p = QtGui.QPainter(pix)
    p.setPen(QtGui.QColor("#555"))
    p.drawRect(0, 0, size * 2 - 1, size - 1)
    p.end()
    return QtGui.QIcon(pix)


class LayerColorPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gyogy6LayerColorViewer")
        self.setWindowTitle("gyogy6 Layer Colors")
        self._entries: List[core.ColorEntry] = []
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(400)
        self._refresh_timer.timeout.connect(self.refresh)
        self._build()

    # ------------------------------------------------------------------ layout
    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)

        top = QtWidgets.QHBoxLayout()
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_refresh.setToolTip(tr("Read the layer colors again", "レイヤーの色を読み直します"))
        self.btn_refresh.clicked.connect(self.refresh)
        self.chk_auto = QtWidgets.QCheckBox("Auto")
        self.chk_auto.setToolTip(tr("Read again automatically whenever the layers change", "レイヤーが変わるたびに自動で読み直します"))
        self.chk_auto.setChecked(True)
        self.filter = QtWidgets.QLineEdit()
        self.filter.setPlaceholderText("Filter (layer / value / #hex)")
        self.filter.textChanged.connect(self._apply_filter)
        top.addWidget(self.btn_refresh)
        top.addWidget(self.chk_auto)
        top.addWidget(self.filter, 1)
        lay.addLayout(top)

        opts = QtWidgets.QHBoxLayout()
        self.chk_active = QtWidgets.QCheckBox("Active set only")
        self.chk_active.setToolTip(tr("Show only the selected Texture Set", "選択中のテクスチャセットだけを表示します"))
        self.chk_hidden = QtWidgets.QCheckBox("Hidden layers")
        self.chk_hidden.setToolTip(tr("Also show hidden layers", "非表示のレイヤーも表示します"))
        self.chk_masks = QtWidgets.QCheckBox("Masks")
        self.chk_masks.setToolTip(tr("Also show generators and other effects inside masks", "マスクの中のジェネレーターなども表示します"))
        self.chk_allch = QtWidgets.QCheckBox("All channels")
        self.chk_allch.setToolTip(tr("Also show non-color channels such as Roughness", "Roughness など、色以外のチャンネルの値も表示します"))
        for w in (self.chk_active, self.chk_hidden, self.chk_masks, self.chk_allch):
            w.toggled.connect(self.refresh)
            opts.addWidget(w)
        opts.addStretch(1)
        lay.addLayout(opts)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Layer", "Value", "Color", "HEX"])
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setIconSize(QtCore.QSize(32, 16))
        hdr = self.tree.header()
        hdr.setSectionResizeMode(COL_LAYER, QtWidgets.QHeaderView.Interactive)
        hdr.setSectionResizeMode(COL_VALUE, QtWidgets.QHeaderView.Interactive)
        hdr.setSectionResizeMode(COL_SWATCH, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(COL_HEX, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.setColumnWidth(COL_LAYER, 170)
        self.tree.setColumnWidth(COL_VALUE, 170)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        lay.addWidget(self.tree, 1)

        # clipboard row
        clip = QtWidgets.QHBoxLayout()
        self.clip_swatch = QtWidgets.QLabel()
        self.clip_swatch.setFixedSize(32, 18)
        self.clip_text = QtWidgets.QLineEdit()
        self.clip_text.setPlaceholderText("#RRGGBB")
        self.clip_text.setToolTip(
            tr("The color to paste. Copying a row puts its color here; you can also type one.\n"
               "Accepted: #RRGGBB / #RGB / 255, 128, 0 / 1.0, 0.5, 0.0",
               "貼り付ける色です。コピーするとここに入ります。直接入力もできます。\n"
               "#RRGGBB / #RGB / 255, 128, 0 / 1.0, 0.5, 0.0 の形に対応しています。"))
        self.clip_text.textChanged.connect(self._update_clip_swatch)
        clip.addWidget(QtWidgets.QLabel("Paste color"))
        clip.addWidget(self.clip_swatch)
        clip.addWidget(self.clip_text, 1)
        lay.addLayout(clip)

        btns = QtWidgets.QGridLayout()
        self.btn_copy = QtWidgets.QPushButton("Copy HEX")
        self.btn_copy.setToolTip(tr("Copy the color of the selected row as #RRGGBB (or double-click the row)", "選んだ行の色を #RRGGBB でコピーします（ダブルクリックでも同じ）"))
        self.btn_copy.clicked.connect(lambda: self._copy_selected("hex"))
        self.btn_paste_rows = QtWidgets.QPushButton("Paste to selected rows")
        self.btn_paste_rows.setToolTip(tr("Write the Paste color into the rows selected in this list", "Paste color の色を、この一覧で選んだ行に書き込みます"))
        self.btn_paste_rows.clicked.connect(self._paste_rows)
        self.btn_paste_layer = QtWidgets.QPushButton("Paste to selected layer (Base Color)")
        self.btn_paste_layer.setToolTip(
            tr("Write the Paste color into the Base Color of the Fill layers\n"
               "selected in Painter's Layers panel",
               "Paste color の色を、Painter のレイヤーパネルで選んでいる\n"
               "Fill レイヤーの Base Color に書き込みます"))
        self.btn_paste_layer.clicked.connect(self._paste_layer)
        self.btn_copy_all = QtWidgets.QPushButton("Copy list")
        self.btn_copy_all.setToolTip(tr("Copy the shown list as tab-separated text", "表示中の一覧をテキスト（タブ区切り）でコピーします"))
        self.btn_copy_all.clicked.connect(self._copy_list)
        btns.addWidget(self.btn_copy, 0, 0)
        btns.addWidget(self.btn_copy_all, 0, 1)
        btns.addWidget(self.btn_paste_rows, 1, 0)
        btns.addWidget(self.btn_paste_layer, 1, 1)
        lay.addLayout(btns)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self._update_clip_swatch()

    # ------------------------------------------------------------------ data
    def _options(self) -> core.ScanOptions:
        return core.ScanOptions(
            active_set_only=self.chk_active.isChecked(),
            include_hidden=self.chk_hidden.isChecked(),
            include_masks=self.chk_masks.isChecked(),
            all_channels=self.chk_allch.isChecked(),
        )

    def schedule_refresh(self):
        if self.chk_auto.isChecked() and self.isVisible():
            self._refresh_timer.start()

    def clear(self):
        self._entries = []
        self.tree.clear()
        self.status.setText(tr("No project is open", "プロジェクトが開かれていません"))

    def refresh(self, *_):
        if not sp.project.is_open():
            self.clear()
            return
        try:
            self._entries = core.scan(self._options())
        except Exception as e:  # pylint: disable=broad-except
            self._entries = []
            self.status.setText(tr("Could not read the layers: ", "読み込みに失敗しました: ") + str(e))
            sp.logging.error(f"{core.LOG_TAG} scan failed: {e}")
            return
        self._populate()

    def _populate(self):
        expanded = {self.tree.topLevelItem(i).text(0)
                    for i in range(self.tree.topLevelItemCount())
                    if self.tree.topLevelItem(i).isExpanded()}
        first = self.tree.topLevelItemCount() == 0
        selected = {self._key(e) for e in self._selected_entries()}
        self.tree.clear()
        groups = {}
        for e in self._entries:
            key = e.set_label
            parent = groups.get(key)
            if parent is None:
                parent = QtWidgets.QTreeWidgetItem([key])
                f = parent.font(0)
                f.setBold(True)
                parent.setFont(0, f)
                self.tree.addTopLevelItem(parent)
                parent.setFirstColumnSpanned(True)
                parent.setExpanded(first or key in expanded)
                groups[key] = parent
            label = e.value_label if e.where == "Fill" else f"[{e.where}] {e.value_label}"
            it = QtWidgets.QTreeWidgetItem(["", label, "", e.hex])
            it.setText(COL_LAYER, e.layer_path)
            it.setIcon(COL_SWATCH, _swatch_icon(e.rgb))
            it.setData(COL_LAYER, ROLE_ENTRY, e)
            tip = (f"{e.set_label}\n{e.layer_path}\n{e.value_label}"
                   + (f"  ({e.note})" if e.note else "")
                   + f"\nHEX {e.hex}\nRGB {to_rgb255_text(e.rgb)}\nFloat {to_float_text(e.rgb)}")
            if not e.exact:
                tip += tr("\n* Color space unknown (the .sbsar value is shown as it is)", "\n※ 色空間を確認できない値です（.sbsar の数値をそのまま表示）")
            if not e.writable:
                tip += tr("\n* Read only", "\n※ 読み取り専用")
            for c in range(4):
                it.setToolTip(c, tip)
            mono = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
            it.setFont(COL_HEX, mono)
            if not e.exact:
                it.setForeground(COL_HEX, QtGui.QBrush(QtGui.QColor("#d9a441")))
            parent.addChild(it)
            if self._key(e) in selected:
                it.setSelected(True)
        n_sets = len(groups)
        self.status.setText(f"{len(self._entries)} colors / {n_sets} texture set(s)"
                            if self._entries else tr("No colored layers found", "色の付いたレイヤーが見つかりません"))
        self._apply_filter(self.filter.text())

    @staticmethod
    def _key(e: core.ColorEntry):
        return (e.set_label, e.layer_path, e.where, e.value_label)

    def _apply_filter(self, text: str):
        t = (text or "").strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            shown = 0
            for j in range(top.childCount()):
                ch = top.child(j)
                hay = " ".join(ch.text(c) for c in range(4)).lower()
                hide = bool(t) and t not in hay
                ch.setHidden(hide)
                shown += 0 if hide else 1
            top.setHidden(shown == 0 and bool(t))

    def _selected_entries(self) -> List[core.ColorEntry]:
        out = []
        for it in self.tree.selectedItems():
            e = it.data(COL_LAYER, ROLE_ENTRY)
            if e is not None:
                out.append(e)
        return out

    # ------------------------------------------------------------------ clipboard
    def _set_clipboard(self, text: str):
        QtGui.QGuiApplication.clipboard().setText(text)

    def _copy_entry(self, e: core.ColorEntry, fmt: str = "hex"):
        text = {"hex": e.hex, "rgb": to_rgb255_text(e.rgb),
                "float": to_float_text(e.rgb)}[fmt]
        self._set_clipboard(text)
        self.clip_text.setText(e.hex)
        self.status.setText(f"Copied {text}  ({e.layer_path} – {e.value_label})")

    def _copy_selected(self, fmt="hex"):
        sel = self._selected_entries()
        if not sel:
            self.status.setText(tr("Select a row to copy", "コピーする行を選んでください"))
            return
        if len(sel) == 1:
            self._copy_entry(sel[0], fmt)
            return
        self._set_clipboard("\n".join(e.hex for e in sel))
        self.clip_text.setText(sel[0].hex)
        self.status.setText(f"Copied {len(sel)} colors")

    def _copy_list(self):
        lines = ["Texture Set\tLayer\tValue\tHEX\tRGB"]
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                ch = top.child(j)
                if ch.isHidden():
                    continue
                e = ch.data(COL_LAYER, ROLE_ENTRY)
                lines.append(f"{e.set_label}\t{e.layer_path}\t{e.value_label}\t{e.hex}\t"
                             f"{to_rgb255_text(e.rgb)}")
        self._set_clipboard("\n".join(lines))
        self.status.setText(f"Copied {len(lines) - 1} rows")

    def _update_clip_swatch(self, *_):
        rgb = parse_color(self.clip_text.text())
        if rgb is None:
            self.clip_swatch.setStyleSheet("border: 1px dashed #777;")
        else:
            self.clip_swatch.setStyleSheet(
                f"background-color: {to_hex(rgb)}; border: 1px solid #555;")

    def _paste_color(self) -> Optional[tuple]:
        rgb = parse_color(self.clip_text.text())
        if rgb is None:
            rgb = parse_color(QtGui.QGuiApplication.clipboard().text())
            if rgb is not None:
                self.clip_text.setText(to_hex(rgb))
        if rgb is None:
            self.status.setText(tr("No color to paste (type #RRGGBB or copy a row)", "貼り付ける色がありません（#RRGGBB を入力するか、行をコピーしてください）"))
        return rgb

    # ------------------------------------------------------------------ paste
    def _report(self, done: int, errors: List[str]):
        msg = f"Pasted to {done} item(s)"
        if errors:
            msg += f" / {len(errors)} skipped: " + "; ".join(errors[:3])
            if len(errors) > 3:
                msg += tr(" …(see the Log)", " …(Log を確認)")
        self.status.setText(msg)
        self.refresh()

    def _paste_rows(self):
        rgb = self._paste_color()
        if rgb is None:
            return
        sel = self._selected_entries()
        if not sel:
            self.status.setText(tr("Select the rows to paste into", "貼り付け先の行を選んでください"))
            return
        self._report(*core.apply_color(sel, rgb))

    def _paste_layer(self):
        rgb = self._paste_color()
        if rgb is None:
            return
        try:
            self._report(*core.apply_to_selected_layers(rgb))
        except Exception as e:  # pylint: disable=broad-except
            self.status.setText(tr("Paste failed: ", "貼り付けに失敗しました: ") + str(e))

    # ------------------------------------------------------------------ interaction
    def _on_double_click(self, item, column):
        e = item.data(COL_LAYER, ROLE_ENTRY)
        if e is None:
            return
        if column == COL_LAYER:
            core.select_node(e.node_uid)
            self.status.setText(f"Selected {e.layer_path}")
        else:
            self._copy_entry(e, "hex")

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        e = item.data(COL_LAYER, ROLE_ENTRY) if item else None
        if e is None:
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction(f"Copy HEX  {e.hex}", lambda: self._copy_entry(e, "hex"))
        menu.addAction(f"Copy RGB  {to_rgb255_text(e.rgb)}", lambda: self._copy_entry(e, "rgb"))
        menu.addAction(f"Copy float  {to_float_text(e.rgb)}", lambda: self._copy_entry(e, "float"))
        menu.addSeparator()
        act = menu.addAction("Paste color here", self._paste_rows)
        act.setEnabled(e.writable)
        menu.addAction("Select layer in Layers panel", lambda: core.select_node(e.node_uid))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def showEvent(self, event):  # noqa: N802 (Qt naming)
        super().showEvent(event)
        if sp.project.is_open() and not self._entries:
            self.refresh()

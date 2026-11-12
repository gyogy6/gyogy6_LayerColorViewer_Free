"""
gyogy6 Layer Color Viewer - reads (and writes) the colors of the layer stack.

What is collected, per Texture Set / stack, walking the layer tree top -> bottom:

  * Fill layers and fill effects
      - split mode    : every channel whose source is a uniform color
                        (Base Color, Emissive, ... ; other channels on request)
      - material mode : color parameters of the material (.sbsar)
      - channel sources that are a .sbsar (generator / material per channel):
                        its color parameters
      - text (font) sources: text color and background color
  * Generator / filter effects (content stack; mask stack on request):
      color parameters of the .sbsar
  * Inputs of a .sbsar that are set to a uniform color

What cannot be read through the Python API (so it never appears in the list):
  * painted pixels (paint layers / paint effects), bitmap and vectorial sources
  * the final, blended color shown in the viewport (opacity, blending modes,
    masks and the layers below are not taken into account)
"""

from __future__ import annotations

import dataclasses
import functools
import warnings
from typing import Any, Callable, Iterable, List, Optional, Tuple

import substance_painter as sp
from substance_painter import layerstack as ls
from substance_painter import source as src_mod
from substance_painter.colormanagement import Color
from substance_painter.textureset import ChannelType

from .colorutil import RGB, clamp01, to_hex

LOG_TAG = "[LayerColor]"

# Channels that hold a color (others, such as Roughness, are grey values).
COLOR_CHANNEL_NAMES = {
    "BaseColor", "Diffuse", "Specular", "SpecularEdgeColor", "Emissive",
    "Transmissive", "Reflection", "ScatterColor", "SheenColor", "CoatColor",
    "AbsorptionColor",
}


def _attr(obj, name: str):
    """Read `obj.name` on any Painter version.

    Painter 11 turned some getters (TextureSet.name, Stack.name, uid, ...) into
    properties; calling them as methods still works but logs a deprecation
    warning. Values that are already plain data are returned as they are.
    """
    v = getattr(obj, name)
    if isinstance(v, (str, int, float, tuple)) or not callable(v):
        return v
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*deprecated.*")
        return v()


def _quiet(func):
    """Hide 'method is deprecated, use the property' warnings from Painter's own
    getters (they became properties in Painter 11) while `func` runs."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*deprecated.*property.*")
            return func(*args, **kwargs)
    return wrapper


def _log(msg: str) -> None:
    sp.logging.info(f"{LOG_TAG} {msg}")


def _warn(msg: str) -> None:
    sp.logging.warning(f"{LOG_TAG} {msg}")


# ----------------------------------------------------------------------------- data
@dataclasses.dataclass
class ColorEntry:
    texture_set: str
    stack: str
    layer_path: str              # "Group / Layer"
    where: str                   # "Fill", "Content", "Mask"
    value_label: str             # "Base Color", "Skin Color", ...
    rgb: RGB                     # 0..1, display (sRGB) values
    exact: bool                  # False when the API gave raw floats (color space unknown)
    node_uid: int
    writable: bool
    # how to write the value back: called with an sRGB tuple
    writer: Optional[Callable[[RGB], None]] = dataclasses.field(default=None, repr=False)
    note: str = ""

    @property
    def hex(self) -> str:
        return to_hex(self.rgb)

    @property
    def set_label(self) -> str:
        return self.texture_set if not self.stack else f"{self.texture_set} / {self.stack}"


# ----------------------------------------------------------------------------- color conversion
def color_to_rgb(color: Color) -> RGB:
    """Painter Color -> sRGB 0..1."""
    for getter in (lambda c: c.sRGB, lambda c: c.convert(_srgb_space()), lambda c: c.value):
        try:
            v = getter(color)
            if v is not None:
                return tuple(float(x) for x in tuple(v)[:3])  # type: ignore[return-value]
        except Exception:  # pylint: disable=broad-except
            continue
    raise ValueError("cannot read Color")


def _srgb_space():
    from substance_painter.colormanagement import GenericColorSpace  # pylint: disable=import-outside-toplevel
    return GenericColorSpace.sRGB


def rgb_to_color(rgb: RGB) -> Color:
    """sRGB 0..1 -> Painter Color tagged as sRGB."""
    r, g, b = (clamp01(c) for c in rgb[:3])
    try:
        return Color(r, g, b, _srgb_space())
    except Exception:  # pylint: disable=broad-except
        c = Color(r, g, b)
        try:
            c.sRGB = (r, g, b)
        except Exception:  # pylint: disable=broad-except
            pass
        return c


def _is_float_tuple(v: Any, sizes=(3, 4)) -> bool:
    return (isinstance(v, (tuple, list)) and len(v) in sizes
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v))


def _value_rgb(value: Any) -> Optional[Tuple[RGB, bool]]:
    """(rgb, exact) for a property value that looks like a color, else None."""
    if isinstance(value, Color):
        return color_to_rgb(value), True
    if (isinstance(value, (tuple, list)) and len(value) == 2
            and isinstance(value[0], Color)):
        return color_to_rgb(value[0]), True
    if _is_float_tuple(value):
        return tuple(float(x) for x in value[:3]), False  # type: ignore[return-value]
    return None


def _new_value_like(old: Any, rgb: RGB) -> Any:
    """Build a new property value with the same shape as the old one."""
    if isinstance(old, Color):
        return rgb_to_color(rgb)
    if isinstance(old, (tuple, list)) and len(old) == 2 and isinstance(old[0], Color):
        return (rgb_to_color(rgb), old[1])
    if _is_float_tuple(old, (4,)):
        return (clamp01(rgb[0]), clamp01(rgb[1]), clamp01(rgb[2]), float(old[3]))
    return (clamp01(rgb[0]), clamp01(rgb[1]), clamp01(rgb[2]))


# ----------------------------------------------------------------------------- scanning
@dataclasses.dataclass
class ScanOptions:
    active_set_only: bool = False
    include_hidden: bool = False
    include_masks: bool = False
    all_channels: bool = False   # also uniform colors of non-color channels (Roughness ...)


def _channel_name(ch) -> str:
    return getattr(ch, "name", str(ch))


def _is_color_channel(ch) -> bool:
    name = _channel_name(ch)
    return name in COLOR_CHANNEL_NAMES or "Color" in name


def _stacks(active_only: bool) -> List[Tuple[str, str, Any]]:
    """[(texture set name, stack name, stack)]"""
    out = []
    if active_only:
        stack = sp.textureset.get_active_stack()
        ts = _attr(stack, "material")
        out.append((_attr(ts, "name"), _attr(stack, "name"), stack))
        return out
    for ts in sp.textureset.all_texture_sets():
        for stack in ts.all_stacks():
            out.append((_attr(ts, "name"), _attr(stack, "name"), stack))
    return out


def _substance_label(source) -> str:
    try:
        rid = source.resource_id
        res = sp.resource.Resource.retrieve(rid)
        if res:
            return _attr(res[0] if isinstance(res, list) else res, "gui_name")
    except Exception:  # pylint: disable=broad-except
        pass
    try:
        return source.resource_id.name
    except Exception:  # pylint: disable=broad-except
        return "Substance"


class _Ctx:
    def __init__(self, ts_name, stack_name, opts: ScanOptions):
        self.ts = ts_name
        self.stack = stack_name
        self.opts = opts
        self.entries: List[ColorEntry] = []

    def add(self, node, path, where, label, rgb_exact, writer, note=""):
        rgb, exact = rgb_exact
        self.entries.append(ColorEntry(
            texture_set=self.ts, stack=self.stack, layer_path=path, where=where,
            value_label=label, rgb=rgb, exact=exact, node_uid=_attr(node, "uid"),
            writable=writer is not None, writer=writer, note=note))


def _collect_substance(ctx: _Ctx, node, path, where, source, prefix: str) -> None:
    """Color parameters (and uniform-color image inputs) of a SourceSubstance."""
    if source is None:
        return
    try:
        props = source.get_properties()
    except Exception as e:  # pylint: disable=broad-except
        _warn(f"{path}: cannot read parameters ({e})")
        props = {}
    for key, prop in props.items():
        try:
            value = prop.value()
        except Exception:  # pylint: disable=broad-except
            continue
        try:
            widget = (_attr(prop, "widget_type") or "").lower()
        except Exception:  # pylint: disable=broad-except
            widget = ""
        got = _value_rgb(value)
        if got is None:
            continue
        # raw float3/float4 are only colors when the .sbsar says so (color widget)
        if not got[1] and "color" not in widget:
            continue
        try:
            label = _attr(prop, "label") or key
        except Exception:  # pylint: disable=broad-except
            label = key

        def writer(rgb, _src=source, _key=key):
            old = _src.get_parameters().get(_key)
            _src.set_parameters({_key: _new_value_like(old, rgb)})

        ctx.add(node, path, where, f"{prefix}{label}", got, writer, note=key)

    # inputs of the substance that are plugged to a uniform color
    try:
        inputs = list(source.image_inputs)
    except Exception:  # pylint: disable=broad-except
        inputs = []
    for ident in inputs:
        try:
            inner = source.get_source(ident)
        except Exception:  # pylint: disable=broad-except
            continue
        if isinstance(inner, src_mod.SourceUniformColor):
            def writer(rgb, _inner=inner):
                _inner.set_color(rgb_to_color(rgb))
            ctx.add(node, path, where, f"{prefix}{ident} (input)",
                    (color_to_rgb(inner.get_color()), True), writer)


def _collect_source(ctx: _Ctx, node, path, where, source, label: str,
                    color_channel: bool) -> None:
    if source is None:
        return
    if isinstance(source, src_mod.SourceUniformColor):
        if not (color_channel or ctx.opts.all_channels):
            return

        def writer(rgb, _s=source):
            _s.set_color(rgb_to_color(rgb))
        ctx.add(node, path, where, label, (color_to_rgb(source.get_color()), True), writer)
    elif isinstance(source, src_mod.SourceSubstance):
        _collect_substance(ctx, node, path, where, source,
                           f"{label}: {_substance_label(source)} / ")
    elif isinstance(source, src_mod.SourceFont):
        params = source.get_parameters()
        for attr, text in (("color", "Text Color"), ("background_color", "Text Background")):
            col = getattr(params, attr, None)
            if not isinstance(col, Color):
                continue

            def writer(rgb, _s=source, _attr=attr):
                p = _s.get_parameters()
                setattr(p, _attr, rgb_to_color(rgb))
                _s.set_parameters(p)
            ctx.add(node, path, where, f"{label}: {text}", (color_to_rgb(col), True), writer)
    # SourceBitmap / SourceVectorial / SourceReference: no single color to read


def _collect_fill_like(ctx: _Ctx, node, path, where) -> None:
    """FillLayerNode or FillEffectNode (both are SourceEditorMixin)."""
    mode = getattr(node, "source_mode", None)
    mode_name = getattr(mode, "name", str(mode))
    if mode_name == "Material":
        try:
            mat = node.get_material_source()
        except Exception:  # pylint: disable=broad-except
            mat = None
        if isinstance(mat, src_mod.SourceSubstance):
            _collect_substance(ctx, node, path, where, mat, f"{_substance_label(mat)} / ")
        return
    try:
        channels = sorted(node.active_channels, key=_channel_name)
    except Exception:  # pylint: disable=broad-except
        channels = []
    # Base Color first, it is the one people look for
    channels.sort(key=lambda c: 0 if _channel_name(c) == "BaseColor" else 1)
    for ch in channels:
        try:
            s = node.get_source(ch)
        except Exception:  # pylint: disable=broad-except
            continue
        _collect_source(ctx, node, path, where, s, _pretty_channel(ch), _is_color_channel(ch))


def _pretty_channel(ch) -> str:
    name = _channel_name(ch)
    out = ""
    for i, c in enumerate(name):
        if c.isupper() and i and not name[i - 1].isupper():
            out += " "
        out += c
    return out


def _collect_effects(ctx: _Ctx, effects: Iterable, path: str, where: str) -> None:
    for eff in effects:
        if not ctx.opts.include_hidden and not _visible(eff):
            continue
        epath = f"{path} › {eff.get_name()}"
        if isinstance(eff, ls.FillEffectNode):
            _collect_fill_like(ctx, eff, epath, where)
        elif isinstance(eff, (ls.GeneratorEffectNode, ls.FilterEffectNode)):
            try:
                s = eff.get_source()
            except Exception:  # pylint: disable=broad-except
                s = None
            if isinstance(s, src_mod.SourceSubstance):
                _collect_substance(ctx, eff, epath, where, s, f"{_substance_label(s)} / ")


def _visible(node) -> bool:
    try:
        return bool(node.is_visible())
    except Exception:  # pylint: disable=broad-except
        return True


def _walk(ctx: _Ctx, nodes, parent_path: str) -> None:
    for node in nodes:
        if not ctx.opts.include_hidden and not _visible(node):
            continue  # hidden layers (and everything inside a hidden group) are skipped
        name = node.get_name()
        path = f"{parent_path} / {name}" if parent_path else name
        if isinstance(node, ls.GroupLayerNode):
            _walk(ctx, node.sub_layers(), path)
        elif isinstance(node, ls.FillLayerNode):
            _collect_fill_like(ctx, node, path, "Fill")
        if isinstance(node, ls.LayerNode):
            try:
                _collect_effects(ctx, node.content_effects(), path, "Content")
            except Exception:  # pylint: disable=broad-except
                pass
            if ctx.opts.include_masks:
                try:
                    if node.has_mask():
                        _collect_effects(ctx, node.mask_effects(), path, "Mask")
                except Exception:  # pylint: disable=broad-except
                    pass


@_quiet
def scan(opts: ScanOptions) -> List[ColorEntry]:
    if not sp.project.is_open():
        return []
    entries: List[ColorEntry] = []
    _scan_into(entries, opts)
    return entries


def _scan_into(entries: List[ColorEntry], opts: ScanOptions) -> None:
    for ts_name, stack_name, stack in _stacks(opts.active_set_only):
        ctx = _Ctx(ts_name, stack_name, opts)
        try:
            _walk(ctx, ls.get_root_layer_nodes(stack), "")
        except Exception as e:  # pylint: disable=broad-except
            _warn(f"{ts_name}: scan failed ({e})")
        entries.extend(ctx.entries)


# ----------------------------------------------------------------------------- writing
@_quiet
def apply_color(entries: List[ColorEntry], rgb: RGB) -> Tuple[int, List[str]]:
    """Write one color into several entries (one undo step). Returns (count, errors)."""
    done, errors = 0, []
    with ls.ScopedModification("gyogy6 Layer Color: paste"):
        for e in entries:
            if e.writer is None:
                errors.append(f"{e.layer_path} – {e.value_label}: read only")
                continue
            try:
                e.writer(rgb)
                done += 1
            except Exception as ex:  # pylint: disable=broad-except
                errors.append(f"{e.layer_path} – {e.value_label}: {ex}")
    for msg in errors:
        _warn(msg)
    return done, errors


@_quiet
def apply_to_selected_layers(rgb: RGB) -> Tuple[int, List[str]]:
    """Set Base Color of the fill layers / fill effects selected in Painter's Layers panel."""
    stack = sp.textureset.get_active_stack()
    nodes = ls.get_selected_nodes(stack)
    done, errors = 0, []
    with ls.ScopedModification("gyogy6 Layer Color: paste to layer"):
        for node in nodes:
            if not isinstance(node, (ls.FillLayerNode, ls.FillEffectNode)):
                errors.append(f"{node.get_name()}: not a fill layer / fill effect")
                continue
            mode = getattr(getattr(node, "source_mode", None), "name", "")
            if mode == "Material":
                errors.append(f"{node.get_name()}: uses a material, paste into its parameter row instead")
                continue
            try:
                active = set(node.active_channels)
                if ChannelType.BaseColor not in active:
                    active.add(ChannelType.BaseColor)
                    node.active_channels = active
                s = node.get_source(ChannelType.BaseColor)
                if isinstance(s, src_mod.SourceUniformColor):
                    s.set_color(rgb_to_color(rgb))
                else:
                    node.set_source(ChannelType.BaseColor, rgb_to_color(rgb))
                done += 1
            except Exception as ex:  # pylint: disable=broad-except
                errors.append(f"{node.get_name()}: {ex}")
    if not nodes:
        errors.append("No layer selected in the Layers panel")
    for msg in errors:
        _warn(msg)
    return done, errors


@_quiet
def select_node(uid: int) -> bool:
    """Select the layer / effect in Painter's Layers panel."""
    try:
        found = ls.get_node_by_uid(uid)
        node = found[0] if isinstance(found, list) else found
        if node is None:
            return False
        try:
            sp.textureset.set_active_stack(node.get_stack())
        except Exception:  # pylint: disable=broad-except
            pass
        ls.set_selected_nodes([node])
        return True
    except Exception as e:  # pylint: disable=broad-except
        _warn(f"cannot select node {uid} ({e})")
        return False

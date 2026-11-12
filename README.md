# gyogy6 Layer Color Viewer (Free)

**English** / [日本語](README.ja.md) / [简体中文](README.zh-CN.md) / [한국어](README.ko.md)

A Python plugin for Substance 3D Painter.
It lists the colors used by your layers, Texture Set by Texture Set, so you can check them at a glance.
Copy a color with a double-click and paste it into other layers.

- Version: 1.0.0
- Price: Free (commercial use allowed, credit optional)
- Terms of use: [LICENSE.md](LICENSE.md) (**by downloading or using this product, you agree to these terms**)

| Feature | Description |
|---|---|
| **Color list** | For the visible layers: layer name, which value, a color swatch and the HEX code (#RRGGBB). |
| **Copy** | Double-click a row to copy its HEX. Right-click to copy as RGB (0–255) or float (0–1). |
| **Paste** | Write a copied color into other rows of the list, or into the Base Color of the Fill layer selected in the Layers panel. |

Besides Fill layer colors, the color parameters of .sbsar materials, generators and filters are also listed.

---

## 1. Included files

| File | Description |
|---|---|
| `gyogy6_layer_color_viewer/` | The plugin (use the whole folder) |
| `README.md` and others | This manual (English, Japanese, Chinese, Korean) |
| `LICENSE.md` | Terms of use |

## 2. Requirements

- Adobe Substance 3D Painter 10 or later (versions whose Python plugins run on PySide6)
- Tested with Painter 11.1.3

The panel's tooltips and messages are shown in Japanese when Painter runs in Japanese, and in English otherwise.

## 3. Installation

1. Start Substance 3D Painter.
2. From the top menu, choose **Python → Plugins Folder**. The plugin folder opens.
   (Usually `Documents/Adobe/Adobe Substance 3D Painter/python`.)
3. Copy the **whole** `gyogy6_layer_color_viewer` folder into the `plugins` folder inside it.
4. Choose **Python → Reload Plugins Folder**, or restart Painter.

## 4. Usage

### 4-1. Show the panel

1. Open the **Python** menu and check **gyogy6_layer_color_viewer**.
2. The **gyogy6 Layer Colors** panel appears.
   If you cannot find it, look in **Window → Views**.

### 4-2. Read the color list

When a project is open, the list appears automatically, grouped by Texture Set.

| Column | Content |
|---|---|
| **Layer** | Layer name. Inside a group: `Group / Layer`. For an effect: `Layer › Effect`. |
| **Value** | Which value the color belongs to (see below). |
| **Color** | Color swatch. |
| **HEX** | Color code as `#RRGGBB`. |

**What the Value column shows**

| Shown as | Meaning |
|---|---|
| `Base Color`, `Emissive`, ... | A channel color of a Fill layer (uniform color) |
| `Material / Parameter` | A color parameter of the .sbsar material in a Fill layer |
| `Base Color: Generator / Parameter` | A color parameter of a .sbsar used for one channel |
| `[Content] …` | Colors of Fill effects, generators and filters added inside a layer |
| `[Mask] …` | Colors of effects inside a mask (only with **Masks** checked) |
| `Text Color`, ... | Text and background colors of text (font) layers |

**Options at the top of the panel**

| Option | Effect |
|---|---|
| **Refresh** | Reads the list again. |
| **Auto** | Reads the list again whenever the layers change (on by default). |
| **Filter** | Shows only rows containing the text: a layer name, a value name, or part of a HEX code such as `#FFE3`. |
| **Active set only** | Shows only the Texture Set selected in the Layers panel. |
| **Hidden layers** | Also shows hidden layers. By default, layers whose eye icon is off (and the contents of hidden groups) are not listed. |
| **Masks** | Also shows the colors of effects inside masks. |
| **All channels** | Also shows non-color channel values (gray), such as Roughness. |

### 4-3. Copy a color

- **Double-click a row** (Value, Color or HEX column) to copy its HEX to the clipboard.
- Or select rows and click **Copy HEX**. With several rows selected, one HEX per line is copied.
- **Right-click** a row to copy in other formats:

  | Menu | Copied text |
  |---|---|
  | Copy HEX | `#FFE3D1` |
  | Copy RGB | `255, 227, 209` |
  | Copy float | `1.0000, 0.8902, 0.8196` |

- **Copy list** copies the shown list as tab-separated text, ready to paste into a spreadsheet.

> **Tip:** Double-clicking the **Layer** column selects that layer in Painter's Layers panel. The right-click menu item **Select layer in Layers panel** does the same.

### 4-4. Paste a color

A copied color goes into the **Paste color** field at the bottom of the panel. You can also type a color there.
Accepted forms: `#RRGGBB`, `#RGB`, `rgb(255, 128, 0)`, `255, 128, 0`, `1.0, 0.5, 0.0`.
(For 0–1 values, include a decimal point such as `1.0`. Numbers without a decimal point are read as 0–255.)

| Button | Effect |
|---|---|
| **Paste to selected rows** | Writes the color into the rows selected in the list (several allowed). The right-click item **Paste color here** does the same. |
| **Paste to selected layer (Base Color)** | Writes the color into the **Base Color** of the Fill layers selected in Painter's Layers panel. Turns Base Color on if it is off. |

A paste can be undone with **Ctrl+Z** (one undo, however many rows were pasted).

**Example: match the skin color of the face to the body**

1. In the list, double-click the face material's skin color row to copy it.
2. Select the body material's skin color row in the other Texture Set.
3. Click **Paste to selected rows**.

## 5. What can and cannot be listed

Only values that Painter's Python API can read are listed.

| Kind | Listed | Paste |
|---|---|---|
| Uniform colors of Fill layers and Fill effects (Base Color, etc.) | Yes | Yes |
| Color parameters of a .sbsar material in a Fill layer | Yes | Yes |
| Color parameters of a .sbsar used for one channel (generators, etc.) | Yes | Yes |
| Color parameters of generators and filters inside a layer | Yes | Yes |
| Image inputs of a .sbsar set to a uniform color | Yes (`… (input)`) | Yes |
| Text (font) color and background color | Yes | Yes |
| Smart materials | As the Fill layers and effects inside them | Yes |
| Colors painted with paint layers or paint effects | **No** (painted pixels cannot be read through the API) | — |
| Colors of bitmaps and vector images | **No** (not a single color) | — |
| Anchor (reference) colors | **No** | — |
| The final color shown on screen | **No** (see below) | — |

> **Note:** The listed color is the value **set on that layer**.
> Opacity, blending modes, masks and the layers below are not taken into account,
> so it can differ from the color you see on screen.

A HEX shown in **yellow** is a .sbsar value returned without color space information; it is shown as stored in the .sbsar.

## 6. Troubleshooting

| Problem | What to check |
|---|---|
| The plugin is not in the Python menu | Make sure the **whole** `gyogy6_layer_color_viewer` folder is in the `plugins` folder, then run **Python → Reload Plugins Folder**. |
| The list is empty | Make sure a project is open. The list is also empty when the visible layers have no color values (paint-only layers, etc.). |
| The list does not update when layers change | Check **Auto**, or click **Refresh**. |
| A .sbsar color parameter is missing | The parameter must use a **color widget** in the .sbsar. Number (slider) parameters are not listed. |
| A paste says "read only" | That value cannot be written. |

Error details are written to **Window → Views → Log** with the tag `[LayerColor]`.

## 7. Limitations

- Only the values marked "Yes" in section 5 are listed.
- **Paste to selected layer (Base Color)** works only on Fill layers and Fill effects. For a Fill layer with a material, paste into the parameter rows of the list instead.
- Non-color parameters (opacity, angle, etc.) cannot be copied.

## 8. Terms of use: key points

Please read [LICENSE.md](LICENSE.md) for the full terms. This is only a summary.

**You may**
- Use it as an individual or a company, for commercial or non-commercial purposes
- Sell or distribute works made with it (textures, VRChat avatars, games, illustrations, etc.). Credit is optional.
- Read the source code to run it or to understand how it works

**You may not**
- Redistribute or sell the plugin (even for free, even unmodified)
- Modify the source code, use a modified version, or distribute code that reuses it
- Use it as AI training data, or issue it as an NFT

If you want to introduce this product to others, please share the URL of the download page, not the files.

## 9. Contact

Bug reports are welcome via GitHub Issues (a response is not guaranteed).

---

Adobe and Substance 3D Painter are trademarks or registered trademarks of Adobe. This product is not affiliated with or endorsed by Adobe.
© 2026 gyogy6

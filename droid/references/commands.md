# Droid Command Reference

Complete documentation for all droid commands.

## Command Index

| Command | Purpose |
|---------|---------|
| [screenshot](#screenshot) | Capture screenshot + UI elements |
| [tap](#tap) | Tap by coordinates or text |
| [fill](#fill) | Fill text field (tap + clear + type) |
| [wait-for](#wait-for) | Wait for element to appear |
| [type](#type) | Type text into focused field |
| [clear](#clear) | Clear focused text field |
| [hide-keyboard](#hide-keyboard) | Dismiss on-screen keyboard |
| [key](#key) | Send key event |
| [swipe](#swipe) | Swipe gesture for scrolling |
| [longpress](#longpress) | Long press at coordinates |
| [launch](#launch) | Launch app by package name |
| [current](#current) | Get current activity |
| [info](#info) | Get device information |
| [wait](#wait) | Wait milliseconds |
| [select-all](#select-all) | Select all text in field |

---

## screenshot

Capture screenshot AND UI elements in one call. Returns the screenshot path and all UI elements with their coordinates.

```bash
droid screenshot
# {"ok":true,"screenshot":"/tmp/screenshot_20240115_143022.png","elements":[...]}

# Filter clickable elements only
droid screenshot --clickable

# Filter by text
droid screenshot -t "Settings"

# Fast screenshot without UI dump
droid screenshot --no-ui
```

**Options:**
- `-c, --clickable` - Only return clickable elements
- `-t, --text <text>` - Filter elements by text
- `--no-ui` - Skip UI hierarchy dump (faster)
- `-d, --dir <path>` - Output directory

**Response fields:**
- `screenshot`: Path to PNG file
- `elements[]`: Array of UI elements
  - `text`: Display text
  - `class`: View class name (Button, EditText, etc.)
  - `id`: Resource ID
  - `desc`: Content description
  - `clickable`: Boolean
  - `x`, `y`: Center tap coordinates
  - `bounds`: [x1, y1, x2, y2] bounding box

---

## tap

Tap at coordinates or by text match.

```bash
# By coordinates
droid tap 540 960
# {"ok":true,"action":"tap","x":540,"y":960}

# By text (finds element and taps center)
droid tap -t "Book Now"
# {"ok":true,"action":"tap","x":540,"y":350,"matched":"Book Now"}

# If multiple matches, use index
droid tap -t "Button" -i 2

# Prefer input fields over labels
droid tap -t "State" --prefer-input

# Only match clickable elements
droid tap -t "Submit" --clickable
```

**Options:**
- `-t, --text <text>` - Find element by text
- `-i, --index <n>` - Index if multiple matches (default: 0)
- `-w, --wait <ms>` - Wait after tap
- `--prefer-input` - Prefer EditText fields over labels
- `--clickable` - Only match clickable elements

---

## fill

Fill a text field in one command. Combines: tap + clear + type + hide-keyboard.

```bash
droid fill "Enter your email" "user@example.com"
# {"ok":true,"action":"fill","field":"Enter your email","value":"user@example.com","x":540,"y":980,"matched":"Enter your email"}
```

**Arguments:**
- `field` - Text to find the field
- `value` - Value to type

**Options:**
- `-w, --wait <ms>` - Wait after action

**Note:** Automatically prefers input fields over labels.

---

## wait-for

Wait for an element to appear on screen with timeout.

```bash
droid wait-for -t "Welcome" -s 10
# {"ok":true,"action":"wait_for","found":true,"element":{...},"elapsed_ms":1500}

# Timeout returns found:false
# {"ok":true,"action":"wait_for","found":false,"timeout":true,"searched":"Welcome","elapsed_ms":10000}
```

**Options:**
- `-t, --text <text>` - Text to wait for (required)
- `-s, --timeout <seconds>` - Timeout in seconds (default: 10)

---

## type

Type text into the currently focused input field.

```bash
droid type "hello@example.com"
# {"ok":true,"action":"type","text":"hello@example.com"}
```

**Options:**
- `-w, --wait <ms>` - Wait after typing

**Note:** Spaces are handled automatically.

---

## clear

Clear the currently focused text field.

```bash
droid clear
# {"ok":true,"action":"clear"}
```

**Options:**
- `-w, --wait <ms>` - Wait after action

**Note:** Uses repeated backspace keys. Works reliably up to ~200 characters.

---

## hide-keyboard

Dismiss the on-screen keyboard without navigating back.

```bash
droid hide-keyboard
# {"ok":true,"action":"hide_keyboard"}
```

**Options:**
- `-w, --wait <ms>` - Wait after action

**Important:** Use this instead of `key back` when keyboard is showing. `key back` may dismiss the entire screen/form.

---

## key

Send key events.

```bash
droid key back
# {"ok":true,"action":"key","key":"back","keycode":4}
```

**Options:**
- `-w, --wait <ms>` - Wait after key

**Available keys:**

| Category | Keys |
|----------|------|
| Navigation | `back`, `app_home` (or `home`), `menu`, `search` |
| Text cursor | `move_home`, `move_end`, `page_up`, `page_down` |
| Text editing | `enter`, `tab`, `delete`, `del`, `space` |
| D-pad | `up`, `down`, `left`, `right` |
| System | `volup`, `voldown`, `power`, `escape`, `esc` |

**Note:** `move_home` moves cursor to start of text. `app_home` goes to Android home screen.

---

## swipe

Swipe gestures for scrolling.

```bash
droid swipe up      # Scroll content down
droid swipe down    # Scroll content up
droid swipe left    # Next page
droid swipe right   # Previous page
# {"ok":true,"action":"swipe","direction":"up"}
```

**Options:**
- `-d, --duration <ms>` - Swipe duration (default: 300)
- `-w, --wait <ms>` - Wait after swipe

---

## longpress

Long press at coordinates or by text.

```bash
# By coordinates
droid longpress 540 960
# {"ok":true,"action":"longpress","x":540,"y":960,"duration":1000}

# By text
droid longpress -t "Item"
# {"ok":true,"action":"longpress","x":540,"y":350,"matched":"Item","duration":1000}
```

**Options:**
- `-t, --text <text>` - Find element by text
- `-i, --index <n>` - Index if multiple matches
- `-d, --duration <ms>` - Press duration (default: 1000)
- `-w, --wait <ms>` - Wait after action

---

## launch

Launch an app by package name.

```bash
droid launch com.example.app
# {"ok":true,"action":"launch","package":"com.example.app"}
```

**Options:**
- `-w, --wait <ms>` - Wait after launch

---

## current

Get the currently visible activity.

```bash
droid current
# {"ok":true,"action":"current","activity":"com.example.app/.MainActivity","package":"com.example.app"}
```

---

## info

Get device information.

```bash
droid info
# {"ok":true,"device":"emulator-5554","model":"sdk_gphone64_x86_64","brand":"google","android":"14","sdk":"34","width":1080,"height":2400,"density":420}
```

---

## wait

Wait for specified milliseconds.

```bash
droid wait 1000
# {"ok":true,"action":"wait","ms":1000}
```

**Note:** Prefer `wait-for` to wait for specific UI state instead of blind waits.

---

## select-all

Select all text in the currently focused field.

```bash
droid select-all
# {"ok":true,"action":"select_all"}
```

**Options:**
- `-w, --wait <ms>` - Wait after action

**Note:** May not work on all Android versions due to ADB limitations with modifier keys. For reliable text replacement, use `clear` + `type` instead.

---

## Common Options

All action commands support:
- `-w, --wait <ms>` - Wait after action completes

```bash
droid tap -t "Submit" -w 2000  # Tap and wait 2 seconds
```

---

## Error Handling

All errors return JSON with `"ok":false`:

```bash
droid tap -t "NonexistentButton"
# {"ok":false,"error":"No element found matching 'NonexistentButton'"}

droid info  # No device connected
# {"ok":false,"error":"No Android device connected. Run 'adb devices' to check."}
```

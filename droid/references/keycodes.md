# Android Keycodes Reference

Common keycodes for use with `adb shell input keyevent`.

## Navigation & System

| Keycode | Name | Description |
|---------|------|-------------|
| 3 | KEYCODE_HOME | Go to home screen |
| 4 | KEYCODE_BACK | Navigate back |
| 82 | KEYCODE_MENU | Open menu |
| 84 | KEYCODE_SEARCH | Open search |
| 187 | KEYCODE_APP_SWITCH | Recent apps |

## D-Pad / Arrow Keys

| Keycode | Name | Description |
|---------|------|-------------|
| 19 | KEYCODE_DPAD_UP | Move up |
| 20 | KEYCODE_DPAD_DOWN | Move down |
| 21 | KEYCODE_DPAD_LEFT | Move left |
| 22 | KEYCODE_DPAD_RIGHT | Move right |
| 23 | KEYCODE_DPAD_CENTER | Select/confirm |

## Input / Editing

| Keycode | Name | Description |
|---------|------|-------------|
| 66 | KEYCODE_ENTER | Enter/confirm |
| 61 | KEYCODE_TAB | Tab to next field |
| 67 | KEYCODE_DEL | Backspace/delete |
| 112 | KEYCODE_FORWARD_DEL | Forward delete |
| 62 | KEYCODE_SPACE | Space character |
| 111 | KEYCODE_ESCAPE | Escape/cancel |

## Volume & Power

| Keycode | Name | Description |
|---------|------|-------------|
| 24 | KEYCODE_VOLUME_UP | Increase volume |
| 25 | KEYCODE_VOLUME_DOWN | Decrease volume |
| 164 | KEYCODE_VOLUME_MUTE | Mute volume |
| 26 | KEYCODE_POWER | Power button |

## Media

| Keycode | Name | Description |
|---------|------|-------------|
| 85 | KEYCODE_MEDIA_PLAY_PAUSE | Play/pause media |
| 86 | KEYCODE_MEDIA_STOP | Stop media |
| 87 | KEYCODE_MEDIA_NEXT | Next track |
| 88 | KEYCODE_MEDIA_PREVIOUS | Previous track |

## Numbers (0-9)

| Keycode | Name |
|---------|------|
| 7-16 | KEYCODE_0 through KEYCODE_9 |

## Letters (A-Z)

| Keycode | Name |
|---------|------|
| 29-54 | KEYCODE_A through KEYCODE_Z |

## Function Keys

| Keycode | Name |
|---------|------|
| 131-142 | KEYCODE_F1 through KEYCODE_F12 |

## Shortcuts in droid CLI

The `droid key` command supports these shortcuts:

- `back` - Navigate back (KEYCODE_BACK)
- `home`, `app_home` - Go home (KEYCODE_HOME)
- `enter` - Confirm/submit (KEYCODE_ENTER)
- `tab` - Next field (KEYCODE_TAB)
- `delete`, `del` - Backspace (KEYCODE_DEL)
- `menu` - Open menu (KEYCODE_MENU)
- `search` - Open search (KEYCODE_SEARCH)
- `up`, `down`, `left`, `right` - D-pad navigation
- `volup`, `voldown` - Volume controls
- `power` - Power button
- `space` - Space character
- `escape`, `esc` - Escape key
- `move_home` - Cursor to start of text (KEYCODE_MOVE_HOME)
- `move_end` - Cursor to end of text (KEYCODE_MOVE_END)
- `page_up`, `page_down` - Page navigation

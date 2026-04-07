import { defineCommand, runMain } from "citty";
import pkg from "../package.json" with { type: "json" };
import { clearCommand } from "./commands/clear.ts";
import { currentCommand } from "./commands/current.ts";
import { fillCommand } from "./commands/fill.ts";
import { hideKeyboardCommand } from "./commands/hide-keyboard.ts";
import { infoCommand } from "./commands/info.ts";
import { keyCommand } from "./commands/key.ts";
import { launchCommand } from "./commands/launch.ts";
import { longpressCommand } from "./commands/longpress.ts";
import { screenshotCommand } from "./commands/screenshot.ts";
import { selectAllCommand } from "./commands/select-all.ts";
import { swipeCommand } from "./commands/swipe.ts";
import { tapCommand } from "./commands/tap.ts";
import { typeCommand } from "./commands/type.ts";
import { waitForCommand } from "./commands/wait-for.ts";
import { waitCommand } from "./commands/wait.ts";

const main = defineCommand({
	meta: {
		name: "droid",
		version: pkg.version,
		description: "Android device automation and UI testing via ADB",
	},
	subCommands: {
		// Device info
		info: infoCommand,

		// Screenshot and UI
		screenshot: screenshotCommand,
		ss: screenshotCommand,
		screen: screenshotCommand,

		// Tap
		tap: tapCommand,
		click: tapCommand,

		// Swipe
		swipe: swipeCommand,
		scroll: swipeCommand,

		// Type text
		type: typeCommand,
		text: typeCommand,
		input: typeCommand,

		// Key events
		key: keyCommand,
		keyevent: keyCommand,

		// Wait
		wait: waitCommand,
		sleep: waitCommand,

		// Keyboard
		"hide-keyboard": hideKeyboardCommand,
		hidekb: hideKeyboardCommand,
		"dismiss-keyboard": hideKeyboardCommand,

		// Clear field
		clear: clearCommand,
		"clear-field": clearCommand,

		// Fill form field
		fill: fillCommand,

		// Select all
		"select-all": selectAllCommand,
		selectall: selectAllCommand,
		select: selectAllCommand,

		// Launch app
		launch: launchCommand,
		start: launchCommand,
		open: launchCommand,

		// Current activity
		current: currentCommand,
		activity: currentCommand,
		foreground: currentCommand,

		// Wait for element
		"wait-for": waitForCommand,
		waitfor: waitForCommand,
		await: waitForCommand,

		// Long press
		longpress: longpressCommand,
		hold: longpressCommand,
		"long-press": longpressCommand,
	},
});

runMain(main);

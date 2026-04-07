#!/usr/bin/env bun
import { defineCommand, runMain } from "citty";
import pkg from "../package.json";
import { clearCommand } from "./commands/clear";
import { currentCommand } from "./commands/current";
import { fillCommand } from "./commands/fill";
import { hideKeyboardCommand } from "./commands/hide-keyboard";
import { infoCommand } from "./commands/info";
import { keyCommand } from "./commands/key";
import { launchCommand } from "./commands/launch";
import { longpressCommand } from "./commands/longpress";
import { screenshotCommand } from "./commands/screenshot";
import { selectAllCommand } from "./commands/select-all";
import { swipeCommand } from "./commands/swipe";
import { tapCommand } from "./commands/tap";
import { typeCommand } from "./commands/type";
import { waitCommand } from "./commands/wait";
import { waitForCommand } from "./commands/wait-for";

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

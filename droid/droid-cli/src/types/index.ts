// Error codes
export type ErrorCode =
	| "ADB_NOT_FOUND"
	| "NO_DEVICE"
	| "ADB_ERROR"
	| "ELEMENT_NOT_FOUND"
	| "INVALID_DIRECTION"
	| "INVALID_KEY"
	| "INVALID_ARGS"
	| "UI_DUMP_FAILED"
	| "SCREENSHOT_FAILED"
	| "ACTIVITY_NOT_FOUND"
	| "LAUNCH_FAILED"
	| "PREREQ_MISSING";

// Base response types
export interface SuccessResponse<T = Record<string, unknown>> {
	ok: true;
	action?: string;
	[key: string]: unknown;
}

export interface ErrorResponse {
	ok: false;
	error: string;
	code?: ErrorCode;
	hint?: string;
}

export type Response<T = Record<string, unknown>> =
	| SuccessResponse<T>
	| ErrorResponse;

// UI Element data
export interface UIElementData {
	text: string;
	class: string;
	id: string;
	desc: string;
	clickable: boolean;
	x: number;
	y: number;
	bounds: [number, number, number, number];
}

// Device info
export interface DeviceInfo {
	device: string;
	model: string;
	brand: string;
	android: string;
	sdk: string;
	width: number;
	height: number;
	density: number;
}

// Screenshot response
export interface ScreenshotResponse {
	screenshot: string;
	elements: UIElementData[];
}

// Tap response
export interface TapResponse {
	action: "tap";
	x: number;
	y: number;
	matched?: string;
}

// Swipe response
export interface SwipeResponse {
	action: "swipe";
	direction: string;
}

// Type response
export interface TypeResponse {
	action: "type";
	text: string;
}

// Key response
export interface KeyResponse {
	action: "key";
	key: string;
	keycode: number;
}

// Wait response
export interface WaitResponse {
	action: "wait";
	ms: number;
}

// Clear response
export interface ClearResponse {
	action: "clear";
}

// Hide keyboard response
export interface HideKeyboardResponse {
	action: "hide_keyboard";
}

// Fill response
export interface FillResponse {
	action: "fill";
	field: string;
	value: string;
	x: number;
	y: number;
	matched: string;
}

// Select all response
export interface SelectAllResponse {
	action: "select_all";
}

// Launch response
export interface LaunchResponse {
	action: "launch";
	package: string;
}

// Current activity response
export interface CurrentResponse {
	action: "current";
	activity: string;
	package: string;
}

// Wait-for response
export interface WaitForResponse {
	action: "wait_for";
	found: boolean;
	element?: UIElementData;
	timeout?: boolean;
	searched?: string;
	elapsed_ms: number;
}

// Long press response
export interface LongpressResponse {
	action: "longpress";
	x: number;
	y: number;
	duration: number;
	matched?: string;
}

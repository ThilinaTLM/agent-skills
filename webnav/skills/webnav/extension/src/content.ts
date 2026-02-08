// Runs in ISOLATED world. Receives captured console/error entries from the
// MAIN world script (content-main.ts) via window.postMessage, and responds
// to extension queries via chrome.runtime.onMessage.
export {};

interface ConsoleEntry {
	level: string;
	text: string;
	timestamp: string;
}

interface ErrorEntry {
	message: string;
	source: string;
	line: number;
	col: number;
	timestamp: string;
}

interface NetworkEntry {
	method: string;
	url: string;
	status: number;
	statusText: string;
	type: string;
	duration: number;
	timestamp: string;
	requestHeaders?: Record<string, string>;
	requestBody?: string | null;
	requestBodyTruncated?: boolean;
	responseHeaders?: Record<string, string>;
	responseBody?: string | null;
	responseBodyTruncated?: boolean;
	responseBodySkipped?: string;
	responseContentType?: string;
}

const WEBNAV_MSG = "__webnav__";
const MAX_ENTRIES = 100;
const MAX_NETWORK_ENTRIES = 200;
const MAX_NETWORK_BUFFER_BYTES = 512_000;
const consoleLogs: ConsoleEntry[] = [];
const errorLogs: ErrorEntry[] = [];
const networkLogs: NetworkEntry[] = [];
let networkBufferBytes = 0;

function estimateEntrySize(entry: NetworkEntry): number {
	let size = 200; // base overhead for fixed fields
	size += (entry.url || "").length;
	size += (entry.method || "").length;
	size += (entry.statusText || "").length;
	size += (entry.requestBody || "").length;
	size += (entry.responseBody || "").length;
	size += (entry.responseBodySkipped || "").length;
	size += (entry.responseContentType || "").length;
	if (entry.requestHeaders) {
		for (const k in entry.requestHeaders) {
			size += k.length + entry.requestHeaders[k].length;
		}
	}
	if (entry.responseHeaders) {
		for (const k in entry.responseHeaders) {
			size += k.length + entry.responseHeaders[k].length;
		}
	}
	return size;
}

// Receive captured entries from the MAIN world script
window.addEventListener("message", (event) => {
	if (event.source !== window) return;
	const data = event.data;
	if (!data || data.type !== WEBNAV_MSG) return;

	if (data.kind === "console") {
		consoleLogs.push({
			level: data.level,
			text: data.text,
			timestamp: data.timestamp,
		});
		if (consoleLogs.length > MAX_ENTRIES) consoleLogs.shift();
	} else if (data.kind === "error") {
		errorLogs.push({
			message: data.message,
			source: data.source,
			line: data.line,
			col: data.col,
			timestamp: data.timestamp,
		});
		if (errorLogs.length > MAX_ENTRIES) errorLogs.shift();
	} else if (data.kind === "network") {
		const entry: NetworkEntry = {
			method: data.method,
			url: data.url,
			status: data.status,
			statusText: data.statusText,
			type: data.requestType,
			duration: data.duration,
			timestamp: data.timestamp,
		};
		if (data.requestHeaders) entry.requestHeaders = data.requestHeaders;
		if (data.requestBody != null) entry.requestBody = data.requestBody;
		if (data.requestBodyTruncated) entry.requestBodyTruncated = true;
		if (data.responseHeaders) entry.responseHeaders = data.responseHeaders;
		if (data.responseBody != null) entry.responseBody = data.responseBody;
		if (data.responseBodyTruncated) entry.responseBodyTruncated = true;
		if (data.responseBodySkipped)
			entry.responseBodySkipped = data.responseBodySkipped;
		if (data.responseContentType)
			entry.responseContentType = data.responseContentType;

		const entrySize = estimateEntrySize(entry);
		networkBufferBytes += entrySize;
		networkLogs.push(entry);

		// Evict oldest entries if over count or byte budget
		while (
			networkLogs.length > 1 &&
			(networkLogs.length > MAX_NETWORK_ENTRIES ||
				networkBufferBytes > MAX_NETWORK_BUFFER_BYTES)
		) {
			const evicted = networkLogs.shift()!;
			networkBufferBytes -= estimateEntrySize(evicted);
		}
	}
});

// Respond to messages from the extension
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
	if (message.type === "getConsole") {
		const result = [...consoleLogs];
		if (message.clear) consoleLogs.length = 0;
		sendResponse({ logs: result });
		return true;
	}
	if (message.type === "getErrors") {
		const result = [...errorLogs];
		if (message.clear) errorLogs.length = 0;
		sendResponse({ errors: result });
		return true;
	}
	if (message.type === "getNetwork") {
		const result = [...networkLogs];
		if (message.clear) {
			networkLogs.length = 0;
			networkBufferBytes = 0;
		}
		sendResponse({ requests: result });
		return true;
	}
	return false;
});

// Runs in the page's MAIN world to capture actual page console output and errors.
// Relays captured entries to the content script (ISOLATED world) via window.postMessage.
export {};

const WEBNAV_MSG = "__webnav__";

interface CapturedConsole {
	type: typeof WEBNAV_MSG;
	kind: "console";
	level: string;
	text: string;
	timestamp: string;
}

interface CapturedError {
	type: typeof WEBNAV_MSG;
	kind: "error";
	message: string;
	source: string;
	line: number;
	col: number;
	timestamp: string;
}

interface CapturedNetwork {
	type: typeof WEBNAV_MSG;
	kind: "network";
	method: string;
	url: string;
	status: number;
	statusText: string;
	requestType: string;
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

const MAX_BODY_SIZE = 32768;

const TEXT_CONTENT_RE =
	/^(text\/|application\/(json|xml|javascript|x-www-form-urlencoded|graphql|ld\+json))/i;

function isTextContentType(ct: string | null): boolean {
	if (!ct) return false;
	return TEXT_CONTENT_RE.test(ct);
}

function truncateBody(body: string): { body: string; truncated: boolean } {
	if (body.length <= MAX_BODY_SIZE) return { body, truncated: false };
	return { body: body.slice(0, MAX_BODY_SIZE), truncated: true };
}

function headersToRecord(headers: Headers): Record<string, string> {
	const result: Record<string, string> = {};
	headers.forEach((value, key) => {
		result[key] = value;
	});
	return result;
}

async function readRequestBody(
	request: Request,
): Promise<{ body: string | null; truncated: boolean }> {
	try {
		const clone = request.clone();
		const text = await clone.text();
		if (!text) return { body: null, truncated: false };
		return truncateBody(text);
	} catch {
		return { body: null, truncated: false };
	}
}

// Wrap console methods
const origLog = console.log;
const origWarn = console.warn;
const origError = console.error;
const origInfo = console.info;
const origDebug = console.debug;

function capture(level: string, args: unknown[]) {
	const text = args
		.map((a) => {
			try {
				return typeof a === "string" ? a : JSON.stringify(a);
			} catch {
				return String(a);
			}
		})
		.join(" ");

	const msg: CapturedConsole = {
		type: WEBNAV_MSG,
		kind: "console",
		level,
		text,
		timestamp: new Date().toISOString(),
	};
	window.postMessage(msg, "*");
}

console.log = (...args: unknown[]) => {
	capture("log", args);
	origLog.apply(console, args);
};
console.warn = (...args: unknown[]) => {
	capture("warn", args);
	origWarn.apply(console, args);
};
console.error = (...args: unknown[]) => {
	capture("error", args);
	origError.apply(console, args);
};
console.info = (...args: unknown[]) => {
	capture("info", args);
	origInfo.apply(console, args);
};
console.debug = (...args: unknown[]) => {
	capture("debug", args);
	origDebug.apply(console, args);
};

// Capture runtime errors
window.addEventListener("error", (event) => {
	const msg: CapturedError = {
		type: WEBNAV_MSG,
		kind: "error",
		message: event.message,
		source: event.filename || "",
		line: event.lineno || 0,
		col: event.colno || 0,
		timestamp: new Date().toISOString(),
	};
	window.postMessage(msg, "*");
});

// Capture unhandled promise rejections
window.addEventListener("unhandledrejection", (event) => {
	const msg: CapturedError = {
		type: WEBNAV_MSG,
		kind: "error",
		message: String(event.reason),
		source: "",
		line: 0,
		col: 0,
		timestamp: new Date().toISOString(),
	};
	window.postMessage(msg, "*");
});

// Wrap fetch to capture network requests
const origFetch = window.fetch;
window.fetch = async function (...args: Parameters<typeof fetch>) {
	const start = Date.now();
	const req = new Request(...args);
	const method = req.method;
	const url = req.url;
	const reqHeaders = headersToRecord(req.headers);
	const reqBody = await readRequestBody(req);
	try {
		const response = await origFetch.apply(this, args);
		const respHeaders = headersToRecord(response.headers);
		const contentType = response.headers.get("content-type");

		const msg: CapturedNetwork = {
			type: WEBNAV_MSG,
			kind: "network",
			method,
			url,
			status: response.status,
			statusText: response.statusText,
			requestType: "fetch",
			duration: Date.now() - start,
			timestamp: new Date().toISOString(),
			requestHeaders: reqHeaders,
			requestBody: reqBody.body,
			requestBodyTruncated: reqBody.truncated || undefined,
			responseHeaders: respHeaders,
			responseContentType: contentType || undefined,
		};

		if (isTextContentType(contentType)) {
			try {
				const text = await response.clone().text();
				const truncated = truncateBody(text);
				msg.responseBody = truncated.body;
				msg.responseBodyTruncated = truncated.truncated || undefined;
			} catch {
				msg.responseBodySkipped = "[error reading response body]";
			}
		} else if (contentType) {
			// Binary or unknown content type — report size from content-length if available
			const cl = response.headers.get("content-length");
			const sizeLabel = cl ? `, ${cl} bytes` : "";
			msg.responseBodySkipped = `[binary: ${contentType}${sizeLabel}]`;
		}

		window.postMessage(msg, "*");
		return response;
	} catch (err) {
		const msg: CapturedNetwork = {
			type: WEBNAV_MSG,
			kind: "network",
			method,
			url,
			status: 0,
			statusText: err instanceof Error ? err.message : "Network error",
			requestType: "fetch",
			duration: Date.now() - start,
			timestamp: new Date().toISOString(),
			requestHeaders: reqHeaders,
			requestBody: reqBody.body,
			requestBodyTruncated: reqBody.truncated || undefined,
		};
		window.postMessage(msg, "*");
		throw err;
	}
};

// Wrap XMLHttpRequest to capture network requests
const origXHROpen = XMLHttpRequest.prototype.open;
const origXHRSend = XMLHttpRequest.prototype.send;
const origXHRSetHeader = XMLHttpRequest.prototype.setRequestHeader;

interface XHRExtended extends XMLHttpRequest {
	_wnMethod: string;
	_wnUrl: string;
	_wnReqHeaders: Record<string, string>;
}

XMLHttpRequest.prototype.setRequestHeader = function (
	name: string,
	value: string,
) {
	const xhr = this as XHRExtended;
	if (!xhr._wnReqHeaders) xhr._wnReqHeaders = {};
	xhr._wnReqHeaders[name.toLowerCase()] = value;
	return origXHRSetHeader.apply(this, [name, value]);
};

XMLHttpRequest.prototype.open = function (
	method: string,
	url: string | URL,
	...rest: unknown[]
) {
	const xhr = this as XHRExtended;
	xhr._wnMethod = method;
	xhr._wnUrl = String(url);
	xhr._wnReqHeaders = {};
	return origXHROpen.apply(this, [method, url, ...rest] as Parameters<
		typeof origXHROpen
	>);
};

XMLHttpRequest.prototype.send = function (
	...args: Parameters<typeof origXHRSend>
) {
	const start = Date.now();
	const xhr = this as XHRExtended;

	// Capture request body from send argument
	let reqBody: string | null = null;
	let reqBodyTruncated = false;
	const sendArg = args[0];
	if (sendArg != null) {
		try {
			const raw = typeof sendArg === "string" ? sendArg : String(sendArg);
			const t = truncateBody(raw);
			reqBody = t.body;
			reqBodyTruncated = t.truncated;
		} catch {
			// ignore
		}
	}

	xhr.addEventListener("loadend", () => {
		// Parse response headers
		const respHeaders: Record<string, string> = {};
		const rawHeaders = xhr.getAllResponseHeaders();
		if (rawHeaders) {
			for (const line of rawHeaders.trim().split(/[\r\n]+/)) {
				const idx = line.indexOf(": ");
				if (idx > 0) {
					respHeaders[line.slice(0, idx).toLowerCase()] = line.slice(idx + 2);
				}
			}
		}

		const contentType = respHeaders["content-type"] || null;

		const msg: CapturedNetwork = {
			type: WEBNAV_MSG,
			kind: "network",
			method: xhr._wnMethod || "GET",
			url: xhr._wnUrl || "",
			status: xhr.status,
			statusText: xhr.statusText || "",
			requestType: "xhr",
			duration: Date.now() - start,
			timestamp: new Date().toISOString(),
			requestHeaders:
				Object.keys(xhr._wnReqHeaders || {}).length > 0
					? xhr._wnReqHeaders
					: undefined,
			requestBody: reqBody,
			requestBodyTruncated: reqBodyTruncated || undefined,
			responseHeaders:
				Object.keys(respHeaders).length > 0 ? respHeaders : undefined,
			responseContentType: contentType || undefined,
		};

		// Read response body for text-like content types
		if (isTextContentType(contentType)) {
			try {
				// responseText throws if responseType is not "" or "text"
				const rt = xhr.responseType;
				if (rt === "" || rt === "text") {
					const t = truncateBody(xhr.responseText);
					msg.responseBody = t.body;
					msg.responseBodyTruncated = t.truncated || undefined;
				} else if (rt === "json") {
					const json = JSON.stringify(xhr.response);
					if (json) {
						const t = truncateBody(json);
						msg.responseBody = t.body;
						msg.responseBodyTruncated = t.truncated || undefined;
					}
				} else {
					msg.responseBodySkipped = `[binary responseType: ${rt}]`;
				}
			} catch {
				msg.responseBodySkipped = "[error reading XHR response]";
			}
		} else if (contentType) {
			const cl = respHeaders["content-length"];
			const sizeLabel = cl ? `, ${cl} bytes` : "";
			msg.responseBodySkipped = `[binary: ${contentType}${sizeLabel}]`;
		}

		window.postMessage(msg, "*");
	});
	return origXHRSend.apply(this, args);
};

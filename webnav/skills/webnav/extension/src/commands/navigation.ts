import { getElementBounds } from "../injected/element-screenshot";
import { scrollPage } from "../injected/scroll";
import { scrollIntoViewElement } from "../injected/scrollintoview";
import { takeSnapshot } from "../injected/snapshot";
import { attachDebugger, detachDebugger, sendCdpCommand } from "../lib/cdp";
import {
	activeWebnavTabId,
	commandHistory,
	persistState,
	setActiveWebnavTabId,
	webnavGroupId,
} from "../state";
import {
	addTabToGroup,
	ensureWebnavGroup,
	getActiveTab,
	waitForTabLoad,
} from "../tabs";
import type { CommandPayload } from "../types";

type ScriptResult = { result: Record<string, unknown> };

async function inject(
	tabId: number,
	func: (...args: never[]) => unknown,
	args: unknown[] = [],
): Promise<Record<string, unknown>> {
	const results = (await chrome.scripting.executeScript({
		target: { tabId },
		func: func as () => void,
		args,
	} as chrome.scripting.ScriptInjection)) as unknown as ScriptResult[];

	const result = results[0]?.result;
	if (result?.error) {
		throw new Error(result.error as string);
	}
	return result || {};
}

export async function handleScreenshot(
	payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const tab = await getActiveTab();

	if (payload.fullPage) {
		// Full-page screenshot via CDP
		try {
			await attachDebugger(tab.id!);
			const layout = await sendCdpCommand<{
				contentSize: { width: number; height: number };
			}>(tab.id!, "Page.getLayoutMetrics");
			const { width, height } = layout.contentSize;
			const result = await sendCdpCommand<{ data: string }>(
				tab.id!,
				"Page.captureScreenshot",
				{
					format: "png",
					captureBeyondViewport: true,
					clip: { x: 0, y: 0, width, height, scale: 1 },
				},
			);
			return {
				image: `data:image/png;base64,${result.data}`,
				url: tab.url,
				title: tab.title,
				fullPage: true,
			};
		} finally {
			await detachDebugger(tab.id!);
		}
	}

	if (payload.selector) {
		// Element screenshot via CDP clip
		const bounds = await inject(tab.id!, getElementBounds, [
			{ selector: payload.selector },
		]);
		try {
			await attachDebugger(tab.id!);
			const result = await sendCdpCommand<{ data: string }>(
				tab.id!,
				"Page.captureScreenshot",
				{
					format: "png",
					captureBeyondViewport: true,
					clip: {
						x: bounds.x as number,
						y: bounds.y as number,
						width: bounds.width as number,
						height: bounds.height as number,
						scale: 1,
					},
				},
			);
			return {
				image: `data:image/png;base64,${result.data}`,
				url: tab.url,
				title: tab.title,
				selector: payload.selector,
			};
		} finally {
			await detachDebugger(tab.id!);
		}
	}

	// Default: viewport screenshot via CDP (works on background tabs)
	try {
		await attachDebugger(tab.id!);
		const result = await sendCdpCommand<{ data: string }>(
			tab.id!,
			"Page.captureScreenshot",
			{ format: "png" },
		);
		return {
			image: `data:image/png;base64,${result.data}`,
			url: tab.url,
			title: tab.title,
		};
	} finally {
		await detachDebugger(tab.id!);
	}
}

export async function handleGoto(
	payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const { url, newTab } = payload;
	if (!url) {
		throw new Error("URL is required");
	}

	let tab: chrome.tabs.Tab;
	if (newTab) {
		// Create a new tab in the webnav group
		await ensureWebnavGroup();
		tab = await chrome.tabs.create({ url, active: false });
		await addTabToGroup(tab.id!);
		setActiveWebnavTabId(tab.id!);
		await persistState();
	} else {
		tab = await getActiveTab();
		await chrome.tabs.update(tab.id!, { url });
	}

	// Wait for page to load
	await waitForTabLoad(tab.id!);

	const updatedTab = await chrome.tabs.get(tab.id!);
	const result: Record<string, unknown> = {
		url: updatedTab.url,
		title: updatedTab.title,
	};

	if (payload.screenshot) {
		const screenshot = await handleScreenshot({});
		result.image = screenshot.image;
	}

	return result;
}

export async function handleInfo(
	_payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const tab = await getActiveTab();
	return {
		id: tab.id,
		url: tab.url,
		title: tab.title,
		status: tab.status,
		active: tab.active,
		windowId: tab.windowId,
	};
}

export async function handleBack(
	_payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const tab = await getActiveTab();
	await chrome.scripting.executeScript({
		target: { tabId: tab.id! },
		func: () => history.back(),
	});
	await waitForTabLoad(tab.id!);
	const updatedTab = await chrome.tabs.get(tab.id!);
	return { url: updatedTab.url, title: updatedTab.title };
}

export async function handleForward(
	_payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const tab = await getActiveTab();
	await chrome.scripting.executeScript({
		target: { tabId: tab.id! },
		func: () => history.forward(),
	});
	await waitForTabLoad(tab.id!);
	const updatedTab = await chrome.tabs.get(tab.id!);
	return { url: updatedTab.url, title: updatedTab.title };
}

export async function handleReload(
	_payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const tab = await getActiveTab();
	await chrome.tabs.reload(tab.id!);
	await waitForTabLoad(tab.id!);
	const updatedTab = await chrome.tabs.get(tab.id!);
	return { url: updatedTab.url, title: updatedTab.title };
}

export async function handleScroll(
	payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const { direction, x, y, amount, selector } = payload;
	const tab = await getActiveTab();
	return await inject(tab.id!, scrollPage, [
		{ direction, x, y, amount, selector },
	]);
}

export async function handleScrollIntoView(
	payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const { selector, text } = payload;
	const tab = await getActiveTab();
	return await inject(tab.id!, scrollIntoViewElement, [{ selector, text }]);
}

export async function handleWaitForUrl(
	payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const { pattern, timeout = 30000 } = payload;
	if (!pattern) throw new Error("URL pattern is required");
	const tab = await getActiveTab();

	// Convert glob pattern to regex: * → [^ ]*
	const regex = new RegExp(
		`^${pattern.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*")}$`,
	);

	return new Promise((resolve, reject) => {
		const listener = (tabId: number, changeInfo: { url?: string }) => {
			if (tabId === tab.id! && changeInfo.url && regex.test(changeInfo.url)) {
				chrome.tabs.onUpdated.removeListener(listener);
				resolve({ matched: true, url: changeInfo.url, pattern });
			}
		};

		chrome.tabs.onUpdated.addListener(listener);

		// Check current URL immediately
		if (tab.url && regex.test(tab.url)) {
			chrome.tabs.onUpdated.removeListener(listener);
			resolve({ matched: true, url: tab.url, pattern });
			return;
		}

		setTimeout(() => {
			chrome.tabs.onUpdated.removeListener(listener);
			reject(new Error(`URL did not match "${pattern}" within ${timeout}ms`));
		}, timeout);
	});
}

export async function handleWaitForLoad(
	payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const { timeout = 30000 } = payload;
	const tab = await getActiveTab();
	await waitForTabLoad(tab.id!, timeout);
	const updatedTab = await chrome.tabs.get(tab.id!);
	return { loaded: true, url: updatedTab.url, title: updatedTab.title };
}

export async function handleConsole(
	payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const tab = await getActiveTab();
	const response = await chrome.tabs.sendMessage(tab.id!, {
		type: "getConsole",
		clear: payload.clear ?? false,
	});
	return { logs: response.logs, count: response.logs.length };
}

export async function handleErrors(
	payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const tab = await getActiveTab();
	const response = await chrome.tabs.sendMessage(tab.id!, {
		type: "getErrors",
		clear: payload.clear ?? false,
	});
	return { errors: response.errors, count: response.errors.length };
}

const MAX_NATIVE_MSG_BYTES = 900_000; // headroom under 1MB Chrome limit

function stripBodies(
	requests: Record<string, unknown>[],
): Record<string, unknown>[] {
	let json = JSON.stringify({ requests, count: requests.length });
	if (json.length <= MAX_NATIVE_MSG_BYTES) return requests;

	// Pass 1: strip bodies from oldest entries first
	for (
		let i = 0;
		i < requests.length && json.length > MAX_NATIVE_MSG_BYTES;
		i++
	) {
		const r = requests[i];
		if (r.requestBody != null || r.responseBody != null) {
			r.requestBody = undefined;
			r.requestBodyTruncated = undefined;
			r.responseBody = undefined;
			r.responseBodyTruncated = undefined;
			if (!r.responseBodySkipped) {
				r.responseBodySkipped = "[stripped: message size limit]";
			}
			json = JSON.stringify({ requests, count: requests.length });
		}
	}

	// Pass 2: strip headers too if still over
	for (
		let i = 0;
		i < requests.length && json.length > MAX_NATIVE_MSG_BYTES;
		i++
	) {
		const r = requests[i];
		if (r.requestHeaders || r.responseHeaders) {
			r.requestHeaders = undefined;
			r.responseHeaders = undefined;
			json = JSON.stringify({ requests, count: requests.length });
		}
	}

	return requests;
}

export async function handleNetwork(
	payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const tab = await getActiveTab();
	const response = await chrome.tabs.sendMessage(tab.id!, {
		type: "getNetwork",
		clear: payload.clear ?? false,
	});
	const requests = stripBodies(response.requests);
	return { requests, count: requests.length };
}

export async function handleObserve(
	payload: CommandPayload,
): Promise<Record<string, unknown>> {
	const tab = await getActiveTab();
	const result: Record<string, unknown> = {
		url: tab.url,
		title: tab.title,
	};

	// Screenshot unless opted out
	if (!payload.noScreenshot) {
		const screenshot = await handleScreenshot({});
		result.image = screenshot.image;
	}

	// Accessibility snapshot (always included, compact by default)
	const snapshotResult = await inject(tab.id!, takeSnapshot, [
		{ interactive: true, compact: payload.compact ?? true },
	]);
	result.tree = snapshotResult.tree;
	result.nodeCount = snapshotResult.nodeCount;
	if (payload.compact !== undefined) {
		result.compact = payload.compact;
	}

	// Console logs (read-only, reuse existing handler)
	try {
		const consoleRes = await handleConsole({ clear: false });
		result.console = consoleRes.logs;
		result.consoleCount = consoleRes.count;
	} catch (_e) {
		result.console = [];
		result.consoleCount = 0;
	}

	// JS errors (read-only, reuse existing handler)
	try {
		const errorsRes = await handleErrors({ clear: false });
		result.errors = errorsRes.errors;
		result.errorsCount = errorsRes.count;
	} catch (_e) {
		result.errors = [];
		result.errorsCount = 0;
	}

	// Network requests (read-only, reuse existing handler)
	try {
		const networkRes = await handleNetwork({ clear: false });
		result.network = networkRes.requests;
		result.networkCount = networkRes.count;
	} catch (_e) {
		result.network = [];
		result.networkCount = 0;
	}

	return result;
}

export async function handleStatus(
	_payload: CommandPayload,
): Promise<Record<string, unknown>> {
	await ensureWebnavGroup();
	let tabs: Array<Record<string, unknown>> = [];
	if (webnavGroupId != null) {
		const groupTabs = await chrome.tabs.query({ groupId: webnavGroupId });
		tabs = groupTabs.map((tab) => ({
			id: tab.id,
			url: tab.url,
			title: tab.title,
			active: tab.id === activeWebnavTabId,
			windowId: tab.windowId,
		}));
	}
	return {
		connected: true,
		version: chrome.runtime.getManifest().version,
		tabs: {
			list: tabs,
			activeTabId: activeWebnavTabId,
			count: tabs.length,
		},
		historyCount: commandHistory.length,
	};
}

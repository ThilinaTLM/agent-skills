import {
	WEBNAV_GROUP_COLOR,
	WEBNAV_GROUP_NAME,
	activeWebnavTabId,
	persistState,
	setActiveWebnavTabId,
	setWebnavGroupId,
	webnavGroupId,
} from "./state";

// ============================================
// Programmatic content script injection
// ============================================

export async function injectContentScripts(tabId: number) {
	try {
		await chrome.scripting.executeScript({
			target: { tabId },
			files: ["content-main.js"],
			world: "MAIN",
		});
		await chrome.scripting.executeScript({
			target: { tabId },
			files: ["content.js"],
		});
	} catch {
		// Fails silently for chrome://, edge://, about: pages, etc.
	}
}

// ============================================
// Event listeners for external mutations
// ============================================

chrome.tabs.onRemoved.addListener(async (tabId) => {
	if (tabId === activeWebnavTabId) {
		console.log("[WebNav] Active webnav tab closed, auto-selecting another");
		setActiveWebnavTabId(null);
		await autoSelectActiveTab();
		await persistState();
	}
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
	// Tab joined the webnav group → inject content scripts
	if (
		changeInfo.groupId !== undefined &&
		changeInfo.groupId === webnavGroupId
	) {
		await injectContentScripts(tabId);
	}

	// Tab already in group navigated to a new page → re-inject
	if (changeInfo.status === "loading" && tab.groupId === webnavGroupId) {
		await injectContentScripts(tabId);
	}

	// Active tab removed from group → auto-select another
	if (tabId === activeWebnavTabId && changeInfo.groupId !== undefined) {
		if (changeInfo.groupId !== webnavGroupId) {
			console.log(
				"[WebNav] Active tab removed from group, auto-selecting another",
			);
			setActiveWebnavTabId(null);
			await autoSelectActiveTab();
			await persistState();
		}
	}
});

chrome.tabGroups.onRemoved.addListener(async (group) => {
	if (group.id === webnavGroupId) {
		console.log("[WebNav] Webnav group deleted, clearing state");
		setWebnavGroupId(null);
		setActiveWebnavTabId(null);
		await persistState();
	}
});

// ============================================
// Tab group helpers
// ============================================

export async function ensureWebnavGroup(): Promise<number | null> {
	// Check if current group ID is still valid
	if (webnavGroupId != null) {
		try {
			await chrome.tabGroups.get(webnavGroupId);
			return webnavGroupId;
		} catch {
			setWebnavGroupId(null);
		}
	}

	// Search for existing webnav group by title
	const allGroups = await chrome.tabGroups.query({
		title: WEBNAV_GROUP_NAME,
	});
	if (allGroups.length > 0) {
		setWebnavGroupId(allGroups[0].id);
		await persistState();
		return webnavGroupId;
	}

	// No existing group — will be created when a tab is added
	return null;
}

export async function createWebnavGroupWithTab(tabId: number): Promise<number> {
	const groupId = await chrome.tabs.group({ tabIds: [tabId] });
	await chrome.tabGroups.update(groupId, {
		title: WEBNAV_GROUP_NAME,
		color: WEBNAV_GROUP_COLOR,
		collapsed: false,
	});
	setWebnavGroupId(groupId);
	await persistState();
	return groupId;
}

export async function addTabToGroup(tabId: number) {
	await ensureWebnavGroup();
	if (webnavGroupId != null) {
		await chrome.tabs.group({ tabIds: [tabId], groupId: webnavGroupId });
	} else {
		await createWebnavGroupWithTab(tabId);
	}
}

export async function autoSelectActiveTab() {
	if (webnavGroupId == null) return;

	try {
		const tabs = await chrome.tabs.query({ groupId: webnavGroupId });
		if (tabs.length > 0) {
			setActiveWebnavTabId(tabs[0].id ?? null);
		} else {
			setActiveWebnavTabId(null);
		}
		await persistState();
	} catch {
		setActiveWebnavTabId(null);
	}
}

export async function getGroupTabCount(): Promise<number> {
	if (webnavGroupId == null) return 0;
	try {
		const tabs = await chrome.tabs.query({ groupId: webnavGroupId });
		return tabs.length;
	} catch {
		return 0;
	}
}

// ============================================
// Core tab resolution
// ============================================

export async function getActiveTab(): Promise<chrome.tabs.Tab> {
	// 1. Ensure the webnav group exists
	await ensureWebnavGroup();

	// 2. If we have a tracked active tab, validate it
	if (activeWebnavTabId != null) {
		try {
			const tab = await chrome.tabs.get(activeWebnavTabId);
			if (tab && tab.groupId === webnavGroupId) {
				return tab;
			}
		} catch {
			// Tab no longer exists
		}
		setActiveWebnavTabId(null);
	}

	// 3. Try to find a tab in the group
	if (webnavGroupId != null) {
		const tabs = await chrome.tabs.query({ groupId: webnavGroupId });
		if (tabs.length > 0) {
			setActiveWebnavTabId(tabs[0].id ?? null);
			await persistState();
			return tabs[0];
		}
	}

	// 4. No group or empty group — create a new blank tab and group it
	const newTab = await chrome.tabs.create({
		url: "about:blank",
		active: false,
	});
	await createWebnavGroupWithTab(newTab.id!);
	setActiveWebnavTabId(newTab.id!);
	await persistState();
	return newTab;
}

// ============================================
// Helpers
// ============================================

export function waitForTabLoad(tabId: number, timeout = 30000): Promise<void> {
	return new Promise((resolve) => {
		const listener = (
			updatedTabId: number,
			changeInfo: { status?: string },
		) => {
			if (updatedTabId === tabId && changeInfo.status === "complete") {
				chrome.tabs.onUpdated.removeListener(listener);
				resolve();
			}
		};

		chrome.tabs.onUpdated.addListener(listener);

		// Timeout
		setTimeout(() => {
			chrome.tabs.onUpdated.removeListener(listener);
			resolve(); // Resolve anyway after timeout
		}, timeout);
	});
}

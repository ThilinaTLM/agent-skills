import { connectToNativeHost } from "./native-messaging";
import { restoreState, webnavGroupId } from "./state";
import { injectContentScripts } from "./tabs";
import "./tabs"; // Register event listeners

// Initialize: restore state, inject into existing group tabs, then connect
restoreState().then(async () => {
	if (webnavGroupId != null) {
		const tabs = await chrome.tabs.query({ groupId: webnavGroupId });
		for (const tab of tabs) {
			if (tab.id != null) await injectContentScripts(tab.id);
		}
	}
	connectToNativeHost();
});

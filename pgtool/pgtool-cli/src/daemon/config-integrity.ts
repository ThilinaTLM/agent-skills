/**
 * Config integrity monitoring for the daemon.
 *
 * - Tracks config file hashes to detect modifications
 * - Detects security downgrades (removal of protected/readOnly flags)
 * - Maintains a protection ratchet (once protected, stays protected)
 * - Requires human GUI approval for security-relevant changes
 */

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import type { PgToolFileConfig, PgToolProfileConfig } from "../types";
import { requestConfigChangeApproval } from "./approval.ts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CachedConfig {
	hash: string;
	content: PgToolFileConfig;
	loadedAt: Date;
}

export interface SecurityDowngrade {
	profile: string;
	change: string;
}

// ---------------------------------------------------------------------------
// State (in daemon memory — resets on daemon restart)
// ---------------------------------------------------------------------------

/** Cached config files keyed by absolute config path */
const configCache = new Map<string, CachedConfig>();

/** Protection ratchet: profiles ever seen as protected, keyed by config path */
const protectionRatchet = new Map<string, Set<string>>();

/** Read-only ratchet: profiles ever seen as readOnly, keyed by config path */
const readOnlyRatchet = new Map<string, Set<string>>();

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Check config integrity. Returns the cached config if unchanged,
 * or handles the change (which may require GUI approval).
 *
 * @returns The effective config (may be cached if changes were rejected)
 */
export async function checkConfigIntegrity(
	configPath: string,
	currentContent: string,
	parsedConfig: PgToolFileConfig,
): Promise<{
	config: PgToolFileConfig;
	tampered: boolean;
	changeRejected: boolean;
}> {
	const hash = computeHash(currentContent);
	const cached = configCache.get(configPath);

	if (!cached) {
		// First time seeing this config — cache it and ratchet any protected profiles
		configCache.set(configPath, {
			hash,
			content: parsedConfig,
			loadedAt: new Date(),
		});
		ratchetProfiles(configPath, parsedConfig);
		return { config: parsedConfig, tampered: false, changeRejected: false };
	}

	if (cached.hash === hash) {
		// Config unchanged — use cached
		return { config: cached.content, tampered: false, changeRejected: false };
	}

	// Config was modified!
	const downgrades = detectSecurityDowngrades(cached.content, parsedConfig);

	if (downgrades.length === 0) {
		// No security-relevant changes — accept silently
		configCache.set(configPath, {
			hash,
			content: parsedConfig,
			loadedAt: new Date(),
		});
		ratchetProfiles(configPath, parsedConfig);
		return { config: parsedConfig, tampered: true, changeRejected: false };
	}

	// Security downgrade detected — require GUI approval
	const changeDescriptions = downgrades.map((d) => `${d.profile}: ${d.change}`);
	const approval = await requestConfigChangeApproval(changeDescriptions);

	if (approval === "approved") {
		// Human accepted — update cache and re-ratchet
		configCache.set(configPath, {
			hash,
			content: parsedConfig,
			loadedAt: new Date(),
		});
		// Re-ratchet from the new config (may have fewer protected profiles)
		ratchetProfiles(configPath, parsedConfig);
		return { config: parsedConfig, tampered: true, changeRejected: false };
	}

	// Rejected or unavailable — keep using cached config
	return { config: cached.content, tampered: true, changeRejected: true };
}

/**
 * Check if a profile is ratcheted as protected.
 * Even if the config file was modified to remove `protected: true`,
 * the daemon still treats it as protected until human approval.
 */
export function isProtectedByRatchet(
	configPath: string,
	profileName: string,
): boolean {
	return protectionRatchet.get(configPath)?.has(profileName) ?? false;
}

/**
 * Check if a profile is ratcheted as readOnly.
 */
export function isReadOnlyByRatchet(
	configPath: string,
	profileName: string,
): boolean {
	return readOnlyRatchet.get(configPath)?.has(profileName) ?? false;
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

function computeHash(content: string): string {
	return createHash("sha256").update(content).digest("hex");
}

function ratchetProfiles(configPath: string, config: PgToolFileConfig): void {
	for (const [name, profile] of Object.entries(config.profiles)) {
		if (profile.protected) {
			if (!protectionRatchet.has(configPath)) {
				protectionRatchet.set(configPath, new Set());
			}
			protectionRatchet.get(configPath)?.add(name);
		}
		if (profile.readOnly) {
			if (!readOnlyRatchet.has(configPath)) {
				readOnlyRatchet.set(configPath, new Set());
			}
			readOnlyRatchet.get(configPath)?.add(name);
		}
	}
}

/**
 * Detect security-relevant downgrades between old and new config.
 * Also checks the ratchet — if a profile was ever seen as protected/readOnly,
 * removing that flag is a downgrade even if the old config didn't have it.
 */
function detectSecurityDowngrades(
	oldConfig: PgToolFileConfig,
	newConfig: PgToolFileConfig,
): SecurityDowngrade[] {
	const downgrades: SecurityDowngrade[] = [];

	for (const [name, oldProfile] of Object.entries(oldConfig.profiles)) {
		const newProfile = newConfig.profiles[name];

		if (!newProfile) {
			if (oldProfile.protected) {
				downgrades.push({
					profile: name,
					change: "protected profile removed",
				});
			}
			if (oldProfile.readOnly) {
				downgrades.push({
					profile: name,
					change: "readOnly profile removed",
				});
			}
			continue;
		}

		if (wasProtected(oldProfile) && !newProfile.protected) {
			downgrades.push({
				profile: name,
				change: "'protected' flag removed",
			});
		}

		if (wasReadOnly(oldProfile) && !newProfile.readOnly) {
			downgrades.push({
				profile: name,
				change: "'readOnly' flag removed",
			});
		}
	}

	return downgrades;
}

function wasProtected(profile: PgToolProfileConfig): boolean {
	return profile.protected === true;
}

function wasReadOnly(profile: PgToolProfileConfig): boolean {
	return profile.readOnly === true;
}

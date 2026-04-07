/**
 * Shared IPC protocol types for daemon communication.
 * Protocol: Newline-delimited JSON (NDJSON) over Unix socket / named pipe.
 */

import type { ErrorResponse, QueryResult } from "../types";

// ---------------------------------------------------------------------------
// Request types (CLI → Daemon)
// ---------------------------------------------------------------------------

export interface PingRequest {
	id: string;
	action: "ping";
}

export interface QueryRequest {
	id: string;
	action: "query";
	configPath: string;
	profile: string;
	sql: string;
	params: unknown[];
	flags: {
		readOnly?: boolean;
		allowWrites?: boolean;
	};
}

export interface StatusRequest {
	id: string;
	action: "status";
}

export interface ShutdownRequest {
	id: string;
	action: "shutdown";
}

export type DaemonRequest =
	| PingRequest
	| QueryRequest
	| StatusRequest
	| ShutdownRequest;

// ---------------------------------------------------------------------------
// Response types (Daemon → CLI)
// ---------------------------------------------------------------------------

export interface PingResponse {
	id: string;
	ok: true;
}

export interface QuerySuccessResponse {
	id: string;
	ok: true;
	result: QueryResult;
}

export interface QueryErrorResponse {
	id: string;
	ok: false;
	error: string;
	code: string;
	hint?: string;
}

export interface StatusResponse {
	id: string;
	ok: true;
	pid: number;
	uptime: number;
	socket: string;
	pools: PoolStatus[];
}

export interface PoolStatus {
	key: string;
	active: number;
	idle: number;
	queries: number;
	readOnly: boolean;
}

export interface ShutdownResponse {
	id: string;
	ok: true;
}

export type DaemonResponse =
	| PingResponse
	| QuerySuccessResponse
	| QueryErrorResponse
	| StatusResponse
	| ShutdownResponse;

// ---------------------------------------------------------------------------
// Serialization helpers
// ---------------------------------------------------------------------------

export function serialize(msg: DaemonRequest | DaemonResponse): string {
	return `${JSON.stringify(msg)}\n`;
}

export function deserialize(line: string): DaemonRequest | DaemonResponse {
	return JSON.parse(line);
}

// Configuration types

/** Legacy single-connection config (backward compat) */
export interface PgToolLegacyConfig {
	host: string;
	port?: number;
	database: string;
	user: string;
	password?: string;
	passwordEnv?: string;
	schema?: string;
}

/** Multi-profile config file structure */
export interface PgToolFileConfig {
	profiles: Record<string, PgToolProfileConfig>;
	default?: string;
}

/** Individual profile config */
export interface PgToolProfileConfig {
	// Field-based connection (mutually exclusive with url)
	host?: string;
	port?: number;
	database?: string;
	user?: string;
	password?: string;
	passwordEnv?: string;

	// URL-based connection (mutually exclusive with field-based)
	url?: string;

	// Common options
	schema?: string;
	ssl?: boolean | SslConfig;
	readOnly?: boolean;
	protected?: boolean;
}

export interface SslConfig {
	rejectUnauthorized?: boolean;
	ca?: string;
	cert?: string;
	key?: string;
}

/** Resolved config ready for connection (always has concrete values) */
export interface ResolvedConnection {
	host: string;
	port: number;
	database: string;
	user: string;
	password: string;
	schema: string;
	ssl?: boolean | SslConfig;
	readOnly: boolean;
	protected: boolean;
	profileName: string;
	url?: string;
}

// Error codes
export type ErrorCode =
	| "CONFIG_NOT_FOUND"
	| "CONFIG_INVALID"
	| "CONNECTION_FAILED"
	| "QUERY_FAILED"
	| "TABLE_NOT_FOUND"
	| "SCHEMA_NOT_FOUND"
	| "PERMISSION_DENIED"
	| "TIMEOUT"
	| "READ_ONLY"
	| "PROTECTED_DENIED"
	| "CONFIG_TAMPERED";

// Base response types
export interface SuccessResponse<T> {
	ok: true;
	data?: T;
}

export interface ErrorResponse {
	ok: false;
	error: string;
	code: ErrorCode;
	hint?: string;
}

export type Response<T> = SuccessResponse<T> | ErrorResponse;

// Schema types
export interface SchemaInfo {
	name: string;
	owner: string;
}

export interface SchemasResult {
	schemas: SchemaInfo[];
}

// Table types
export interface TableInfo {
	name: string;
	schema: string;
	type: "table" | "view" | "materialized view" | "foreign table";
	owner: string;
	rowEstimate: number;
	rowEstimateUnknown?: boolean;
	sizeBytes: number | null;
	sizeHuman: string | null;
}

export interface TablesResult {
	schema: string;
	tables: TableInfo[];
}

// Column types
export interface ColumnInfo {
	name: string;
	type: string;
	nullable: boolean;
	defaultValue: string | null;
	isPrimaryKey: boolean;
	isForeignKey: boolean;
	foreignKeyRef: ForeignKeyRef | null;
	comment: string | null;
}

export interface ForeignKeyRef {
	schema: string;
	table: string;
	column: string;
}

export interface DescribeResult {
	schema: string;
	table: string;
	columns: ColumnInfo[];
	rowEstimate: number;
	sizeHuman: string | null;
}

// Index types
export interface IndexInfo {
	name: string;
	unique: boolean;
	primary: boolean;
	columns: string[];
	type: string;
	size: string | null;
	definition: string;
}

export interface IndexesResult {
	schema: string;
	table: string;
	indexes: IndexInfo[];
}

// Constraint types
export interface ConstraintInfo {
	name: string;
	type: "PRIMARY KEY" | "FOREIGN KEY" | "UNIQUE" | "CHECK" | "EXCLUDE";
	columns: string[];
	definition: string;
	foreignTable?: string;
	foreignColumns?: string[];
}

export interface ConstraintsResult {
	schema: string;
	table: string;
	constraints: ConstraintInfo[];
}

// Relationship types
export interface RelationshipInfo {
	constraintName: string;
	fromSchema: string;
	fromTable: string;
	fromColumns: string[];
	toSchema: string;
	toTable: string;
	toColumns: string[];
}

export interface RelationshipsResult {
	relationships: RelationshipInfo[];
}

// Query types
export interface QueryResult {
	rows: Record<string, unknown>[];
	rowCount: number;
	fields: FieldInfo[];
}

export interface FieldInfo {
	name: string;
	dataTypeID: number;
}

// Sample command
export interface SampleResult {
	schema: string;
	table: string;
	rows: Record<string, unknown>[];
	rowCount: number;
	columns: string[];
}

// Count command
export interface CountResult {
	schema: string;
	table: string;
	count: number;
}

// Search command
export interface SearchResult {
	pattern: string;
	matches: {
		tables: Array<{ schema: string; name: string }>;
		columns: Array<{
			schema: string;
			table: string;
			column: string;
			type: string;
		}>;
	};
}

// Overview command
export interface OverviewTable {
	name: string;
	rowEstimate: number | "unknown";
	primaryKey: string[];
	foreignKeys: Array<{
		column: string;
		references: { table: string; column: string };
	}>;
	referencedBy: Array<{ table: string; column: string }>;
}

export interface OverviewResult {
	schema: string;
	tableCount: number;
	tables: OverviewTable[];
}

// Explain command
export interface ExplainResult {
	query: string;
	plan: string[];
}

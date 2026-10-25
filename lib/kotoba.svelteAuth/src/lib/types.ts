export interface ClerkUserInfo {
	id: string;
	firstName: string | null;
	lastName: string | null;
	fullName: string | null;
	username: string | null;
	emailAddress: string | null;
	phoneNumber: string | null;
	hasVerifiedEmail: boolean;
	hasVerifiedPhone: boolean;
	imageUrl: string | null;
	externalAccounts?: ExternalAccountInfo[];
	web3Wallets?: { id: string; web3Wallet: string }[];
	publicMetadata: Record<string, unknown>;
}

export type AuthMethod = 'clerk' | 'username' | 'metamask' | 'phone' | 'social' | 'email';

export interface ExternalAccountInfo {
	id: string;
	provider: string;
	label: string;
	verified: boolean;
}

export interface Organization {
	id: string;
	name: string;
	slug: string;
	category: string;
	role: string;
	imageUrl?: string;
	memberCount?: number;
	requiredTrustScore?: number | null;
	minimumAge?: number | null;
	metadata: Record<string, unknown>;
}

export interface TrustStep {
	id: string;
	label: string;
	description: string;
	trustGain: number;
	completed: boolean;
}

export interface TrustSummary {
	score: number;
	label: 'guest' | 'starter' | 'verified' | 'trusted' | 'high-trust';
	nextScoreTarget: number | null;
	methods: AuthMethod[];
	steps: TrustStep[];
	ageVerified: boolean;
	ageYears: number | null;
	requiredTrustScore: number | null;
	minimumAge: number | null;
	accessReady: boolean;
	accessReasons: string[];
}

export interface AuthConfig {
	/** Legacy Clerk publishable key (unused post-Clerk removal; kept for backward compat). */
	publishableKey: string;
	/** Base URL for authz.etzhayyim.com identity management UI (ADR-0024). */
	accountsBaseUrl?: string;
}

export interface KeyDerivationParams {
	accountPassword: string;
	secretKey: string;
	saltBase64Url?: string;
	iterations?: number;
}

export interface ZkEnvelopeV1 {
	version: 'zk-v1';
	owner: {
		'clerkUserId': string;
		'clerkOrgId': string;
	};
	'deviceId': string;
	alg: {
		kdf: 'argon2id' | 'pbkdf2-sha256';
		aead: 'xchacha20poly1305' | 'aes-256-gcm';
		wrap: 'x25519-hkdf';
	};
	'wrappedKeys': {
		'akByMk': string;
		'dkByAk': string;
		'dekByAk': string;
	};
	aad: {
		'objectId': string;
		'createdAt': string;
		[key: string]: unknown;
	};
}

export interface KeyBundleLookupInput {
	orgId: string;
	userId: string;
	deviceId: string;
}

export interface KeyBundleUpsertInput extends KeyBundleLookupInput {
	version: string;
	envelopeJson: string;
}

export interface KeyBundleRevokeInput extends KeyBundleLookupInput {}

export interface KeyBundleEnvelopeRecord extends KeyBundleLookupInput {
	version: string;
	envelopeJson: string;
	createdAt: string;
	updatedAt: string;
	revoked: boolean;
}

export interface KeyBundleClientConfig {
	baseUrl?: string;
	getAuthToken?: () => Promise<string | null>;
	fetchImpl?: typeof fetch;
}

export interface EnrollKeyBundleInput extends KeyBundleLookupInput {
	accountPassword: string;
	secretKey: string;
	envelopeJson: string;
	clientConfig?: KeyBundleClientConfig;
	saltBase64Url?: string;
	iterations?: number;
}

export interface EnrollKeyBundleResult {
	bundle: KeyBundleEnvelopeRecord;
	kdf: {
		saltBase64Url: string;
		iterations: number;
	};
}

export interface FetchAndUnlockKeyBundleInput extends KeyBundleLookupInput {
	accountPassword: string;
	secretKey: string;
	clientConfig?: KeyBundleClientConfig;
}

export interface FetchAndUnlockKeyBundleResult {
	bundle: KeyBundleEnvelopeRecord;
	envelope: ZkEnvelopeV1;
	kdf: {
		saltBase64Url: string;
		iterations: number;
	};
	wrappingKey: Uint8Array;
}

export interface UsernameSignUpInput {
	username: string;
	firstName?: string;
	lastName?: string;
}

// ── Agent-First Identity ──

/** WIT capability that an agent can declare */
export interface AgentCapability {
	/** WIT interface name (e.g. "etzhayyim:yata/yata") */
	witInterface: string;
	/** Human-readable label */
	label: string;
	/** Capability category for grouping */
	category: 'protocol' | 'data' | 'social' | 'browser' | 'conversation' | 'domain';
}

/** AI Agent registered on yoro — the primary identity on the platform */
export interface AgentInfo {
	/** Agent nanoid */
	agentId: string;
	/** AT Protocol bot DID */
	did: string;
	/** Display name */
	displayName: string;
	/** One-line description */
	description: string;
	/** Avatar URL or emoji/initials */
	avatar: string | null;
	/** Owner's Clerk userId */
	ownerId: string;
	/** Agent status */
	status: 'active' | 'suspended' | 'archived';
	/** Declared WIT capabilities */
	capabilities: AgentCapability[];
	/** Agent type */
	agentType: 'autonomous' | 'semi-autonomous' | 'reactive';
	/** Created timestamp */
	createdAt: string;
}

/** Character appearance params — Nintendo Mii-style parametric avatar */
export interface CharacterAppearance {
	face: 'round' | 'oval' | 'square' | 'heart' | 'long' | 'diamond';
	skinHue: number;
	skinLightness: number;
	eye: 'round' | 'almond' | 'narrow' | 'wide' | 'droopy' | 'cat';
	eyeColorHue: number;
	eyeSize: number;
	eyeSpacing: number;
	eyeHeight: number;
	eyebrowThickness: number;
	eyebrowAngle: number;
	nose: 'small' | 'medium' | 'large' | 'pointed' | 'button' | 'flat';
	noseSize: number;
	mouth: 'smile' | 'neutral' | 'thin' | 'wide' | 'pout' | 'grin';
	mouthSize: number;
	hair: 'short' | 'medium' | 'long' | 'buzz' | 'curly' | 'wavy' | 'spiky' | 'ponytail' | 'bun' | 'bald' | 'afro' | 'mohawk';
	hairColorHue: number;
	hairColorLightness: number;
	body: 'slim' | 'average' | 'athletic' | 'stocky' | 'tall';
	height: number;
	accessory1: 'none' | 'glasses' | 'sunglasses' | 'earring' | 'hat' | 'headband' | 'mask' | 'scarf';
	accessory2: 'none' | 'glasses' | 'sunglasses' | 'earring' | 'hat' | 'headband' | 'mask' | 'scarf';
}

/** Default random character appearance */
export function randomCharacterAppearance(): CharacterAppearance {
	const pick = <T>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];
	return {
		face: pick(['round', 'oval', 'square', 'heart', 'long', 'diamond']),
		skinHue: Math.random() * 0.12,
		skinLightness: 0.3 + Math.random() * 0.5,
		eye: pick(['round', 'almond', 'narrow', 'wide', 'droopy', 'cat']),
		eyeColorHue: Math.random(),
		eyeSize: 0.7 + Math.random() * 0.6,
		eyeSpacing: 0.8 + Math.random() * 0.4,
		eyeHeight: 0.4 + Math.random() * 0.2,
		eyebrowThickness: 0.7 + Math.random() * 0.6,
		eyebrowAngle: -0.3 + Math.random() * 0.6,
		nose: pick(['small', 'medium', 'large', 'pointed', 'button', 'flat']),
		noseSize: 0.7 + Math.random() * 0.6,
		mouth: pick(['smile', 'neutral', 'thin', 'wide', 'pout', 'grin']),
		mouthSize: 0.7 + Math.random() * 0.6,
		hair: pick(['short', 'medium', 'long', 'buzz', 'curly', 'wavy', 'spiky', 'ponytail', 'bun', 'bald', 'afro', 'mohawk']),
		hairColorHue: Math.random(),
		hairColorLightness: 0.1 + Math.random() * 0.7,
		body: pick(['slim', 'average', 'athletic', 'stocky', 'tall']),
		height: 0.85 + Math.random() * 0.3,
		accessory1: pick(['none', 'none', 'none', 'glasses', 'sunglasses', 'hat']),
		accessory2: 'none',
	};
}

/** Input for creating a new agent — character appearance only, server auto-generates name/description/capabilities */
export interface CreateAgentInput {
	/** Parametric character appearance (Nintendo Mii-style) */
	appearance: CharacterAppearance;
}

/** Moderation role — society6 constituent = moderator */
export interface ModeratorInfo {
	/** Clerk userId of the moderator (Agent Owner) */
	userId: string;
	/** society6 constituentId */
	constituentId: string;
	/** Display name from society6 */
	displayName: string;
	/** Whether this user is a moderator (= is society6 constituent) */
	isModerator: boolean;
}

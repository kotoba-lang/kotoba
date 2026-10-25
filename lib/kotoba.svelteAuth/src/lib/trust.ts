import type {
	AuthMethod,
	ClerkUserInfo,
	Organization,
	TrustStep,
	TrustSummary,
} from './types.js';

const TRUST_THRESHOLDS = [25, 50, 75] as const;

function metadataNumber(
	record: Record<string, unknown> | undefined,
	...keys: string[]
): number | null {
	if (!record) return null;
	for (const key of keys) {
		const value = record[key];
		if (typeof value === 'number' && Number.isFinite(value)) {
			return Math.max(0, Math.round(value));
		}
		if (typeof value === 'string') {
			const parsed = Number.parseFloat(value);
			if (Number.isFinite(parsed)) {
				return Math.max(0, Math.round(parsed));
			}
		}
	}
	return null;
}

function metadataBoolean(
	record: Record<string, unknown> | undefined,
	...keys: string[]
): boolean | null {
	if (!record) return null;
	for (const key of keys) {
		const value = record[key];
		if (typeof value === 'boolean') return value;
		if (typeof value === 'string') {
			if (value === 'true') return true;
			if (value === 'false') return false;
		}
	}
	return null;
}

function metadataString(
	record: Record<string, unknown> | undefined,
	...keys: string[]
): string | null {
	if (!record) return null;
	for (const key of keys) {
		const value = record[key];
		if (typeof value === 'string' && value.trim()) {
			return value.trim();
		}
	}
	return null;
}

function calculateAgeYears(rawDate: string | null): number | null {
	if (!rawDate) return null;
	const birthday = new Date(rawDate);
	if (Number.isNaN(birthday.getTime())) return null;
	const now = new Date();
	let years = now.getFullYear() - birthday.getFullYear();
	const monthDelta = now.getMonth() - birthday.getMonth();
	if (monthDelta < 0 || (monthDelta === 0 && now.getDate() < birthday.getDate())) {
		years -= 1;
	}
	return years >= 0 ? years : null;
}

function pushMethod(methods: Set<AuthMethod>, enabled: boolean, method: AuthMethod): void {
	if (enabled) methods.add(method);
}

function providerLabel(provider: string): string {
	return provider
		.split(/[_-]+/g)
		.filter(Boolean)
		.map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
		.join(' ');
}

export function trustVariantFromScore(
	score: number,
): 'default' | 'warning' | 'accent' | 'success' {
	if (score >= 75) return 'success';
	if (score >= 50) return 'accent';
	if (score >= 25) return 'warning';
	return 'default';
}

export function buildTrustSummary(
	user: ClerkUserInfo | null,
	org: Organization | null,
): TrustSummary {
	const orgMeta = org?.metadata ?? {};
	const requiredTrustScore =
		metadataNumber(orgMeta, 'minimumTrustScore', 'requiredMinTrustScore', 'requiredTrustScore') ??
		org?.requiredTrustScore ??
		null;
	const minimumAge =
		metadataNumber(orgMeta, 'minimumAge', 'requiredMinimumAge', 'minimumAge') ??
		org?.minimumAge ??
		null;

	if (!user) {
		const accessReasons: string[] = [];
		if (requiredTrustScore != null && requiredTrustScore > 0) {
			accessReasons.push(`Trust score ${requiredTrustScore}+ required`);
		}
		if (minimumAge != null && minimumAge > 0) {
			accessReasons.push(`Age ${minimumAge}+ required`);
		}
		return {
			score: 0,
			label: 'guest',
			nextScoreTarget: TRUST_THRESHOLDS[0],
			methods: [],
			steps: [
				{
					id: 'clerk',
					label: 'Create a Clerk account',
					description: 'Start with social login or a lightweight account profile.',
					trustGain: 5,
					completed: false,
				},
				{
					id: 'metamask',
					label: 'Link MetaMask',
					description: 'Wallet-backed identity raises app-side trust and unlocks wallet apps.',
					trustGain: 20,
					completed: false,
				},
				{
					id: 'username',
					label: 'Claim a username',
					description: 'A stable public handle improves discoverability and trust.',
					trustGain: 15,
					completed: false,
				},
			],
			ageVerified: false,
			ageYears: null,
			requiredTrustScore,
			minimumAge,
			accessReady: accessReasons.length === 0,
			accessReasons,
		};
	}

	const userMeta = user.publicMetadata ?? {};
	const authMethods = new Set<AuthMethod>(['clerk']);
	pushMethod(authMethods, Boolean(user.username), 'username');
	pushMethod(authMethods, Boolean(user.hasVerifiedEmail), 'email');
	pushMethod(authMethods, Boolean(user.hasVerifiedPhone), 'phone');
	pushMethod(authMethods, Boolean(user.web3Wallets?.length), 'metamask');
	pushMethod(authMethods, Boolean(user.externalAccounts?.some((account) => account.verified)), 'social');

	const ageYears =
		metadataNumber(userMeta, 'ageYears', 'ageYears') ??
		calculateAgeYears(metadataString(userMeta, 'birthDate', 'birthDate'));
	const ageVerified = metadataBoolean(userMeta, 'ageVerified', 'ageVerified') ?? false;
	const explicitScore = metadataNumber(userMeta, 'trustScore', 'trustScore');

	let score = explicitScore ?? 0;
	if (explicitScore == null) {
		score += 5;
		if (user.username) score += 15;
		if (user.hasVerifiedEmail) score += 10;
		if (user.hasVerifiedPhone) score += 20;
		if (user.web3Wallets?.length) score += 20;
		if (user.externalAccounts?.some((account) => account.verified)) score += 10;
		if (ageVerified) score += 20;
	}
	score = Math.max(0, Math.min(100, score));

	let label: TrustSummary['label'] = 'guest';
	if (score >= 75) {
		label = 'high-trust';
	} else if (score >= 50) {
		label = 'trusted';
	} else if (score >= 25) {
		label = 'verified';
	} else if (score > 0) {
		label = 'starter';
	}

	const steps: TrustStep[] = [
		{
			id: 'username',
			label: 'Username',
			description: 'Pick a public handle so other orgs and apps can recognize you.',
			trustGain: 15,
			completed: Boolean(user.username),
		},
		{
			id: 'metamask',
			label: 'MetaMask',
			description: 'Link a wallet-backed identity for onchain and gated apps.',
			trustGain: 20,
			completed: Boolean(user.web3Wallets?.length),
		},
		{
			id: 'phone',
			label: 'Phone verification',
			description: 'Phone verification increases confidence for higher-risk actions.',
			trustGain: 20,
			completed: user.hasVerifiedPhone,
		},
		{
			id: 'social',
			label: 'SNS connection',
			description: 'Connecting an external social account boosts trust and recovery options.',
			trustGain: 10,
			completed: Boolean(user.externalAccounts?.some((account) => account.verified)),
		},
		{
			id: 'age',
			label: 'Age verification',
			description: 'Age-verified profiles can pass app-level age gates.',
			trustGain: 20,
			completed: ageVerified,
		},
	];

	const accessReasons: string[] = [];
	if (requiredTrustScore != null && score < requiredTrustScore) {
		accessReasons.push(`Needs trust score ${requiredTrustScore}+`);
	}
	if (minimumAge != null) {
		if (ageYears == null) {
			accessReasons.push(`Needs age ${minimumAge}+`);
		} else if (ageYears < minimumAge) {
			accessReasons.push(`Available for age ${minimumAge}+`);
		}
	}

	const nextScoreTarget = TRUST_THRESHOLDS.find((threshold) => threshold > score) ?? null;

	return {
		score,
		label,
		nextScoreTarget,
		methods: Array.from(authMethods),
		steps,
		ageVerified,
		ageYears,
		requiredTrustScore,
		minimumAge,
		accessReady: accessReasons.length === 0,
		accessReasons,
	};
}

export function normalizeExternalAccount(
	account: Record<string, unknown>,
): { id: string; provider: string; label: string; verified: boolean } | null {
	const id = metadataString(account, 'id');
	const provider =
		metadataString(account, 'provider', 'providerName', 'strategy', 'object') ?? 'social';
	if (!id) return null;
	return {
		id,
		provider,
		label: providerLabel(provider),
		verified: metadataString(account, 'verificationStatus') === 'verified' ||
			metadataString(account, 'verificationStatus') === 'verified' ||
			metadataString(account, 'status') === 'verified' ||
			Boolean(
				typeof account.verification === 'object' &&
					account.verification &&
					(account.verification as Record<string, unknown>).status === 'verified',
			),
	};
}

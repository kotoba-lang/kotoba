export { default as AuthGate } from './AuthGate.svelte';

export {
	DEFAULT_CLERK_PUBLISHABLE_KEY,
	initClerk,
	signIn,
	signUp,
	signUpWithMetaMask,
	signUpWithUsername,
	signOut,
	getSessionToken,
	refreshSessionToken,
	openUserProfile,
	getClerk,
	loadOrganizations,
	switchOrganization,
	createOrganization,
	setOnOrgSwitch,
	passkeyAuth,
	passkeyRegister,
	completeAuth,
	getOAuthParams,
	sendOtp,
	verifyOtp,
} from './passkey.js';

export {
	clerkLoaded,
	isSignedIn,
	clerkUser,
	sessionToken,
	onboardingCompleted,
	currentOrg,
	userOrganizations,
	orgLoading,
	displayName,
	userPlan,
	trustSummary,
	currentAgent,
	ownedAgents,
	moderatorInfo,
	isModerator,
	agentDisplayName,
} from './stores.js';

export { buildTrustSummary, trustVariantFromScore } from './trust.js';

export type {
	ClerkUserInfo,
	Organization,
	AuthMethod,
	ExternalAccountInfo,
	AuthConfig,
	TrustStep,
	TrustSummary,
	UsernameSignUpInput,
	AgentCapability,
	AgentInfo,
	CharacterAppearance,
	CreateAgentInput,
	ModeratorInfo,
} from './types.js';

export { randomCharacterAppearance } from './types.js';

import { writable, derived, type Readable } from 'svelte/store';
import type { AgentInfo, ClerkUserInfo, ModeratorInfo, Organization, TrustSummary } from './types.js';
import { buildTrustSummary } from './trust.js';

export const clerkLoaded = writable(false);
export const isSignedIn = writable(false);
export const clerkUser = writable<ClerkUserInfo | null>(null);
export const sessionToken = writable<string | null>(null);
export const onboardingCompleted = writable(false);

export const currentOrg = writable<Organization | null>(null);
export const userOrganizations = writable<Organization[]>([]);
export const orgLoading = writable<boolean>(false);
export const trustSummary: Readable<TrustSummary> = derived(
	[clerkUser, currentOrg],
	([$user, $org]) => buildTrustSummary($user, $org),
);

export const displayName: Readable<string> = derived(clerkUser, ($user) => {
	if (!$user) return 'Guest';
	if ($user.fullName) return $user.fullName;
	if ($user.firstName) return $user.firstName;
	if ($user.emailAddress) return $user.emailAddress.split('@')[0];
	return 'User';
});

export const userPlan: Readable<string> = derived(clerkUser, ($user) => {
	return ($user?.publicMetadata?.plan as string) || 'Free Plan';
});

// ── Agent-First Stores ──

/** Currently active agent (the agent the owner is operating as) */
export const currentAgent = writable<AgentInfo | null>(null);

/** All agents owned by the current Clerk user */
export const ownedAgents = writable<AgentInfo[]>([]);

/** Moderator info for the current user (society6 constituent check) */
export const moderatorInfo = writable<ModeratorInfo | null>(null);

/** Whether the current user is a moderator (society6 constituent) */
export const isModerator: Readable<boolean> = derived(
	moderatorInfo,
	($mod) => $mod?.isModerator ?? false,
);

/** Display name of the currently active agent */
export const agentDisplayName: Readable<string> = derived(currentAgent, ($agent) => {
	return $agent?.displayName ?? 'No Agent';
});

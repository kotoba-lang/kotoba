/**
 * Passkey (WebAuthn) auth — drop-in replacement for clerk.ts.
 * Same exported interface: initClerk → initAuth, signIn/signUp/signOut, getSessionToken, etc.
 * Uses navigator.credentials (WebAuthn) + AUTH_SERVICE for session management.
 */

import type { AuthConfig, Organization, UsernameSignUpInput } from './types.js';
import {
	clerkLoaded,
	isSignedIn,
	clerkUser,
	sessionToken,
	onboardingCompleted,
	currentOrg,
	userOrganizations,
	orgLoading,
} from './stores.js';

const AUTH_BASE = 'https://atproto.etzhayyim.com';
// ADR-0024 T4 split: auth.etzhayyim.com retired 2026-04-16 → authn.etzhayyim.com (AuthN Worker).
const AUTH_RPC_BASE = 'https://authn.etzhayyim.com';
const SESSION_STORAGE_KEY = 'etzhayyim-auth-session';
const REFRESH_STORAGE_KEY = 'etzhayyim-auth-refresh';
const CREDENTIAL_STORAGE_KEY = 'etzhayyim-auth-credential';
const DID_STORAGE_KEY = 'etzhayyim-auth-did';

// Keep the same export name for backward compat
export const DEFAULT_CLERK_PUBLISHABLE_KEY = '';

let initialized = false;
let sessionRefreshTimer: ReturnType<typeof setInterval> | null = null;
let onOrgSwitchCallback: (() => void) | null = null;

interface StoredSession {
	accessJwt: string;
	refreshJwt: string;
	did: string;
	handle: string;
	expiresAt: number;
}

export interface OAuthParams {
	clientId: string;
	redirectUri: string;
	state: string;
	codeChallenge: string;
	codeChallengeMethod: string;
}

interface PasskeyResult {
	did: string;
	handle: string;
	accessJwt: string;
	refreshJwt: string;
	credentialId: string;
}

function buildCrossOriginAuthUrl(target: string, session: StoredSession): string {
	const encoded = encodeURIComponent(JSON.stringify(session));
	const sep = target.includes('#') ? '&' : '#';
	return `${target}${sep}auth=${encoded}`;
}

function isAllowedRedirectUrl(url: string): boolean {
	try {
		const parsed = new URL(url);
		return (
			parsed.hostname === 'localhost' ||
			parsed.hostname === '127.0.0.1' ||
			parsed.hostname.endsWith('.etzhayyim.com')
		);
	} catch {
		return false;
	}
}

class AuthRpcError extends Error {
	status: number;
	path: string;
	raw: string;
	errorCode: string | null;

	constructor(path: string, status: number, raw: string, message: string, errorCode: string | null) {
		super(message);
		this.name = 'AuthRpcError';
		this.path = path;
		this.status = status;
		this.raw = raw;
		this.errorCode = errorCode;
	}
}

function getStoredSession(): StoredSession | null {
	if (typeof localStorage === 'undefined') return null;
	try {
		const raw = localStorage.getItem(SESSION_STORAGE_KEY);
		if (!raw) return null;
		const session = JSON.parse(raw) as StoredSession;
		if (session.expiresAt && Date.now() > session.expiresAt) {
			// Access token expired — try refresh
			return session;
		}
		return session;
	} catch {
		return null;
	}
}

function storeSession(session: StoredSession): void {
	if (typeof localStorage === 'undefined') return;
	localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

function clearStoredSession(): void {
	if (typeof localStorage === 'undefined') return;
	localStorage.removeItem(SESSION_STORAGE_KEY);
	localStorage.removeItem(REFRESH_STORAGE_KEY);
	localStorage.removeItem(CREDENTIAL_STORAGE_KEY);
	localStorage.removeItem(DID_STORAGE_KEY);
}

function storeCredentialId(credentialId: string): void {
	if (typeof localStorage === 'undefined') return;
	localStorage.setItem(CREDENTIAL_STORAGE_KEY, credentialId);
}

function getStoredCredentialId(): string | null {
	if (typeof localStorage === 'undefined') return null;
	return localStorage.getItem(CREDENTIAL_STORAGE_KEY);
}

function storeDid(did: string): void {
	if (typeof localStorage === 'undefined') return;
	localStorage.setItem(DID_STORAGE_KEY, did);
}

function getStoredDid(): string | null {
	if (typeof localStorage === 'undefined') return null;
	return localStorage.getItem(DID_STORAGE_KEY);
}

async function authRpc(path: string, body?: unknown): Promise<any> {
	const resp = await fetch(`${AUTH_RPC_BASE}${path}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: body ? JSON.stringify(body) : undefined,
	});
	if (!resp.ok) {
		const raw = await resp.text().catch((_err) => '');
		const isHtml = /<!doctype html>|<html/i.test(raw);
		const rayId = raw.match(/Ray ID:\s*([a-zA-Z0-9]+)/i)?.[1] || '';
		let errorCode: string | null = null;
		if (!isHtml) {
			try {
				const parsed = JSON.parse(raw) as { error?: string };
				errorCode = parsed?.error || null;
			} catch {
				// ignore non-JSON error body
			}
		}
		if (resp.status === 429 && isHtml) {
			const hint = rayId ? ` (Cloudflare Ray ID: ${rayId})` : '';
			throw new AuthRpcError(
				path,
				resp.status,
				raw,
				`auth RPC ${path} failed: 429 rate limited by Cloudflare${hint}`,
				errorCode
			);
		}
		let message = raw;
		if (isHtml) {
			message = raw.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
		}
		throw new AuthRpcError(
			path,
			resp.status,
			raw,
			`auth RPC ${path} failed: ${resp.status} ${message.slice(0, 300)}`,
			errorCode
		);
	}
	return resp.json();
}

function base64urlEncode(buffer: ArrayBuffer): string {
	const bytes = new Uint8Array(buffer);
	let binary = '';
	for (const b of bytes) binary += String.fromCharCode(b);
	return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function base64urlDecode(s: string): ArrayBuffer {
	s = s.replace(/-/g, '+').replace(/_/g, '/');
	while (s.length % 4) s += '=';
	const bytes = Uint8Array.from(atob(s), c => c.charCodeAt(0));
	return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function resolveAuthenticatorSelection(beginResp: any): AuthenticatorSelectionCriteria | undefined {
	const raw = beginResp?.authenticatorSelection || beginResp?.authenticator_selection;
	if (!raw || typeof raw !== 'object') return undefined;

	const residentKey = raw.residentKey ?? raw.resident_key;
	const userVerification = raw.userVerification ?? raw.user_verification;
	const authenticatorAttachment = raw.authenticatorAttachment ?? raw.authenticator_attachment;

	const resolved: AuthenticatorSelectionCriteria = {};
	if (residentKey) resolved.residentKey = residentKey as ResidentKeyRequirement;
	if (userVerification) resolved.userVerification = userVerification as UserVerificationRequirement;
	if (authenticatorAttachment) resolved.authenticatorAttachment = authenticatorAttachment as AuthenticatorAttachment;
	return Object.keys(resolved).length > 0 ? resolved : undefined;
}

export function getOAuthParams(): OAuthParams | null {
	if (typeof location === 'undefined') return null;
	const p = new URLSearchParams(location.search);
	const clientId = p.get('client_id') || p.get('clientId');
	const redirectUri = p.get('redirect_uri') || p.get('redirectUri') || '';
	if (!clientId) return null;
	if (!redirectUri || !isAllowedRedirectUrl(redirectUri)) return null;
	return {
		clientId,
		redirectUri,
		state: p.get('state') || '',
		codeChallenge: p.get('code_challenge') || p.get('codeChallenge') || '',
		codeChallengeMethod: p.get('code_challenge_method') || p.get('codeChallengeMethod') || 'S256',
	};
}

export async function completeAuth(did: string, handle: string, oauth?: OAuthParams | null): Promise<void> {
	if (oauth) {
		const issued = await authRpc('/oauth/issue-code', { ...oauth, did, handle });
		const sep = oauth.redirectUri.includes('?') ? '&' : '?';
		location.href =
			oauth.redirectUri +
			sep +
			'code=' +
			encodeURIComponent(issued.code) +
			'&state=' +
			encodeURIComponent(oauth.state);
		return;
	}

	let session: any;
	try {
		session = await authRpc('/xrpc/com.etzhayyim.auth.issueSession', { did, handle });
	} catch {
		session = await authRpc('/xrpc/com.atproto.server.createSession', { did, handle });
	}

	const s: StoredSession = {
		accessJwt: session.accessJwt,
		refreshJwt: session.refreshJwt,
		did: session.did || did,
		handle: session.handle || handle,
		expiresAt: Date.now() + 7 * 24 * 3600 * 1000 - 60_000,
	};
	storeSession(s);
	storeDid(s.did);
	sessionToken.set(s.accessJwt);
	isSignedIn.set(true);
	updateUserFromDid(s.did);

	if (typeof location !== 'undefined') {
		const p = new URLSearchParams(location.search);
		const returnTo =
			p.get('redirectUrl') ||
			p.get('redirect_url') ||
			p.get('returnTo') ||
			p.get('redirect') ||
			'';
		if (returnTo && isAllowedRedirectUrl(returnTo)) {
			location.href = buildCrossOriginAuthUrl(returnTo, s);
			return;
		}
		location.href = buildCrossOriginAuthUrl('https://yoro.etzhayyim.com/', s);
	}
}

export async function sendOtp(phone: string): Promise<void> {
	await authRpc('/xrpc/com.etzhayyim.auth.smsOtpSend', { phone });
}

export async function verifyOtp(phone: string, code: string): Promise<{ did: string }> {
	return authRpc('/xrpc/com.etzhayyim.auth.smsOtpVerify', { phone, code });
}

export function setOnOrgSwitch(callback: () => void): void {
	onOrgSwitchCallback = callback;
}

/**
 * Initialize auth. Compatible with initClerk signature.
 * Restores existing session from localStorage if available.
 */
export async function initClerk(config?: AuthConfig): Promise<any> {
	if (initialized) return null;
	initialized = true;

	// Receive session from authn.etzhayyim.com via hash fragment (cross-origin transfer)
	if (typeof window !== 'undefined' && window.location.hash.startsWith('#auth=')) {
		try {
			const encoded = window.location.hash.slice('#auth='.length);
			const transferred = JSON.parse(decodeURIComponent(encoded)) as StoredSession;
			if (transferred?.accessJwt && transferred?.did) {
				storeSession(transferred);
				storeCredentialId(''); // no credential ID from cross-origin
				storeDid(transferred.did);
				sessionToken.set(transferred.accessJwt);
				isSignedIn.set(true);
				updateUserFromDid(transferred.did);
				// Clear hash fragment without triggering navigation
				history.replaceState(null, '', window.location.pathname + window.location.search);
			}
		} catch (e) {
			console.warn('Auth hash fragment parse failed:', e);
		}
	}

	try {
		const stored = getStoredSession();
		if (stored?.accessJwt) {
			// Check if access token is still valid (< 2h)
			if (stored.expiresAt && Date.now() < stored.expiresAt) {
				sessionToken.set(stored.accessJwt);
				isSignedIn.set(true);
				updateUserFromDid(stored.did);
			} else if (stored.refreshJwt) {
				// Try refresh
				await refreshSessionFromStored(stored);
			}
		}
	} catch (e) {
		console.warn('Session restore failed:', e);
	}

	clerkLoaded.set(true);

	// Periodic session refresh (50s interval — same as Clerk keepalive)
	sessionRefreshTimer = setInterval(async () => {
		const stored = getStoredSession();
		if (stored?.refreshJwt) {
			// Refresh 30s before expiry
			if (stored.expiresAt && Date.now() > stored.expiresAt - 30_000) {
				await refreshSessionFromStored(stored);
			}
		}
	}, 50_000);

	return null;
}

async function refreshSessionFromStored(stored: StoredSession): Promise<void> {
	try {
		const result = await authRpc('/xrpc/com.atproto.server.refreshSession', {
			'refreshToken': stored.refreshJwt,
		});
		const newSession: StoredSession = {
			accessJwt: result.accessJwt,
			refreshJwt: result.refreshJwt,
			did: result.did || stored.did,
			handle: result.handle || stored.handle,
			expiresAt: Date.now() + 2 * 3600 * 1000 - 60_000, // 2h minus 1min buffer
		};
		storeSession(newSession);
		sessionToken.set(newSession.accessJwt);
		isSignedIn.set(true);
		updateUserFromDid(newSession.did);
	} catch (e) {
		console.warn('Session refresh failed:', e);
		clearStoredSession();
		sessionToken.set(null);
		isSignedIn.set(false);
		clerkUser.set(null);
	}
}

function updateUserFromDid(did: string): void {
	// ADR-0024 T4 split: accept both legacy (auth.etzhayyim.com) and current (authn.etzhayyim.com) DID prefixes.
	const handle = did
		.replace(/^did:web:(?:auth|authn)\.etzhayyim\.ai:/, '')
		.replace(/:/g, '.');
	clerkUser.set({
		id: did,
		firstName: null,
		lastName: null,
		fullName: handle,
		username: handle,
		emailAddress: null,
		phoneNumber: null,
		hasVerifiedEmail: false,
		hasVerifiedPhone: false,
		imageUrl: '',
		externalAccounts: [],
		web3Wallets: [],
		publicMetadata: {},
	});
	storeDid(did);
}

export async function passkeyAuth(): Promise<PasskeyResult> {
	const beginResp = await authRpc('/xrpc/com.etzhayyim.auth.passkeyBeginAuth');
	const publicKeyBase: PublicKeyCredentialRequestOptions = {
		challenge: base64urlDecode(beginResp.challenge),
		rpId: beginResp.rpId || beginResp.rp_id,
		timeout: beginResp.timeout,
		userVerification: (beginResp.userVerification || beginResp.user_verification || 'required') as UserVerificationRequirement,
	};

	let credential: PublicKeyCredential | null = null;
	credential = (await navigator.credentials.get({
		publicKey: publicKeyBase,
	})) as PublicKeyCredential | null;
	if (!credential) throw new Error('No passkey was selected for etzhayyim.com');

	const response = credential.response as AuthenticatorAssertionResponse;
	const credentialId = base64urlEncode(credential.rawId);
	let verifyResult: any;
	try {
		verifyResult = await authRpc('/xrpc/com.etzhayyim.auth.passkeyVerifyAuth', {
			challenge: beginResp.challenge,
			credentialId,
			clientDataJson: base64urlEncode(response.clientDataJSON),
			authenticatorData: base64urlEncode(response.authenticatorData),
			signature: base64urlEncode(response.signature),
		});
	} catch (error) {
		const rpcError = error as AuthRpcError;
		const isCredentialNotFound =
			rpcError?.path === '/xrpc/com.etzhayyim.auth.passkeyVerifyAuth' &&
			rpcError?.status === 404 &&
			rpcError?.errorCode === 'CredentialNotFound';
		if (!isCredentialNotFound) throw error;
		throw new Error('No account is linked to this passkey. Sign in failed.');
	}

	return {
		did: verifyResult.did,
		handle: verifyResult.sessionTokens?.handle || verifyResult.handle || verifyResult.did,
		accessJwt: verifyResult.sessionTokens?.accessJwt || '',
		refreshJwt: verifyResult.sessionTokens?.refreshJwt || '',
		credentialId,
	};
}

export async function passkeyRegister(): Promise<PasskeyResult> {
	const beginResp = await authRpc('/xrpc/com.etzhayyim.auth.passkeyBeginRegister', {
		userId: crypto.randomUUID(),
		userName: `${crypto.randomUUID().slice(0, 8)}@etzhayyim.com`,
	});
	const credential = await navigator.credentials.create({
		publicKey: {
			challenge: base64urlDecode(beginResp.challenge),
			rp: { id: beginResp.rp.id, name: beginResp.rp.name },
			user: {
				id: base64urlDecode(beginResp.user.id),
				name: beginResp.user.name,
				displayName: beginResp.user.displayName,
			},
			pubKeyCredParams: beginResp.pubKeyCredParams.map((p: any) => ({
				type: p.type as 'public-key',
				alg: p.alg,
			})),
			timeout: beginResp.timeout,
			authenticatorSelection: resolveAuthenticatorSelection(beginResp),
			attestation: beginResp.attestation as AttestationConveyancePreference,
		},
	}) as PublicKeyCredential | null;
	if (!credential) throw new Error('Passkey creation cancelled');

	const response = credential.response as AuthenticatorAttestationResponse;
	const credentialId = base64urlEncode(credential.rawId);
	const verifyResult = await authRpc('/xrpc/com.etzhayyim.auth.passkeyVerifyRegister', {
		challenge: beginResp.challenge,
		clientDataJson: base64urlEncode(response.clientDataJSON),
		attestationObject: base64urlEncode(response.attestationObject),
	});

	return {
		did: verifyResult.did,
		handle: verifyResult.handle || verifyResult.did,
		accessJwt: verifyResult.accessJwt || '',
		refreshJwt: verifyResult.refreshJwt || '',
		credentialId,
	};
}

/**
 * Sign in with Passkey (WebAuthn assertion).
 */
export async function signIn(): Promise<void> {
	if (typeof window === 'undefined' || !navigator.credentials) {
		console.error('WebAuthn not supported');
		return;
	}

	try {
		const verifyResult = await passkeyAuth();

		const session: StoredSession = {
			accessJwt: verifyResult.accessJwt,
			refreshJwt: verifyResult.refreshJwt,
			did: verifyResult.did,
			handle: verifyResult.handle,
			expiresAt: Date.now() + 2 * 3600 * 1000 - 60_000,
		};
		storeSession(session);
		storeCredentialId(verifyResult.credentialId);
		storeDid(verifyResult.did);
		sessionToken.set(session.accessJwt);
		isSignedIn.set(true);
		updateUserFromDid(session.did);
	} catch (error) {
		console.error('Passkey sign in failed:', error);
	}
}

/**
 * Sign up with Passkey (WebAuthn registration).
 */
export async function signUp(): Promise<void> {
	if (typeof window === 'undefined' || !navigator.credentials) {
		console.error('WebAuthn not supported');
		return;
	}

	try {
		const verifyResult = await passkeyRegister();
		let sessionResult: any;
		if (verifyResult.accessJwt && verifyResult.refreshJwt) {
			sessionResult = {
				accessJwt: verifyResult.accessJwt,
				refreshJwt: verifyResult.refreshJwt,
				did: verifyResult.did,
				handle: verifyResult.handle,
			};
		} else {
			sessionResult = await authRpc('/xrpc/com.atproto.server.createSession', {
				did: verifyResult.did,
				handle: verifyResult.handle,
			});
		}

		const session: StoredSession = {
			accessJwt: sessionResult.accessJwt,
			refreshJwt: sessionResult.refreshJwt,
			did: sessionResult.did,
			handle: sessionResult.handle,
			expiresAt: Date.now() + 2 * 3600 * 1000 - 60_000,
		};
		storeSession(session);
		storeCredentialId(verifyResult.credentialId);
		storeDid(verifyResult.did);
		sessionToken.set(session.accessJwt);
		isSignedIn.set(true);
		updateUserFromDid(session.did);
		onboardingCompleted.set(false);
	} catch (error) {
		console.error('Passkey sign up failed:', error);
	}
}

export async function signUpWithUsername(input: UsernameSignUpInput): Promise<void> {
	// Passkey doesn't need username input — redirect to standard signUp
	await signUp();
}

export async function signUpWithMetaMask(): Promise<void> {
	// MetaMask not supported in Passkey mode — fallback to standard signUp
	console.warn('MetaMask sign up not available with Passkey auth — using standard Passkey registration');
	await signUp();
}

export async function signOut(): Promise<void> {
	if (sessionRefreshTimer) {
		clearInterval(sessionRefreshTimer);
		sessionRefreshTimer = null;
	}
	clearStoredSession();
	sessionToken.set(null);
	isSignedIn.set(false);
	clerkUser.set(null);
	onboardingCompleted.set(false);
	currentOrg.set(null);
	userOrganizations.set([]);
}

export async function refreshSessionToken(): Promise<string | null> {
	const stored = getStoredSession();
	if (!stored?.accessJwt) {
		sessionToken.set(null);
		return null;
	}
	sessionToken.set(stored.accessJwt);
	return stored.accessJwt;
}

export async function getSessionToken(): Promise<string | null> {
	const stored = getStoredSession();
	if (!stored?.accessJwt) return null;
	// Auto-refresh if near expiry
	if (stored.expiresAt && Date.now() > stored.expiresAt - 30_000 && stored.refreshJwt) {
		await refreshSessionFromStored(stored);
		const refreshed = getStoredSession();
		return refreshed?.accessJwt ?? null;
	}
	return stored.accessJwt;
}

export async function openUserProfile(): Promise<void> {
	// No-op for passkey — profile is managed via yoro settings
	if (typeof window !== 'undefined') {
		window.location.href = '/settings/account';
	}
}

export function getClerk(): any {
	// Compat — returns null (no Clerk instance)
	return null;
}

export async function loadOrganizations(): Promise<void> {
	// Organizations are DID-based in Passkey mode — no Clerk org model.
	// For now, create a default "personal" organization.
	const did = getStoredDid();
	if (!did) return;

	orgLoading.set(true);
	try {
		const orgs: Organization[] = [{
			id: did,
			name: 'Personal',
			slug: 'personal',
			category: 'individual',
			role: 'org:admin',
			imageUrl: undefined,
			memberCount: 1,
			requiredTrustScore: null,
			minimumAge: null,
			metadata: {},
		}];
		userOrganizations.set(orgs);
		currentOrg.set(orgs[0]);
	} finally {
		orgLoading.set(false);
	}
}

export async function switchOrganization(orgId: string): Promise<void> {
	// Single org in Passkey mode
	orgLoading.set(true);
	try {
		let orgs: Organization[] = [];
		userOrganizations.subscribe((o) => (orgs = o))();
		const matched = orgs.find((o) => o.id === orgId);
		if (matched) currentOrg.set(matched);
		onOrgSwitchCallback?.();
		await refreshSessionToken();
	} finally {
		orgLoading.set(false);
	}
}

export async function createOrganization(name: string, slug?: string): Promise<string | null> {
	// DID-based organizations — create via PDS
	console.warn('createOrganization: DID-based orgs not yet implemented in Passkey mode');
	return null;
}

import React, { useState, useCallback } from 'react';
import { Shield, Chrome, Key, Loader, AlertCircle, CheckCircle, Lock, User, Eye, EyeOff, LogIn, ExternalLink } from 'lucide-react';
import { useSecurityContext } from '../../context/SecurityContext';
import AuthenticationSelector from './AuthenticationSelector';
import PageContainer from '@layout/PageContainer';
import SuppressedProbeBadge from './SuppressedProbeBadge';
import SuppressionDebugPanel from './SuppressionDebugPanel';

/**
 * Unified Login Page
 * - Rust (fks_auth) username/password JWT flow
 * - Primary (passkey / rust redirect) via existing AuthenticationSelector
 * - Optional Google OAuth (if enabled via localStorage security.googleOAuth || VITE_GOOGLE_OAUTH)
 */
const LoginPage: React.FC = () => {
	const {
		authenticated,
		user,
		loading,
		error: securityError,
		validateSecurity,
		login: initiateAuthFlow,
		completeLogin
	} = useSecurityContext();

	const [username, setUsername] = useState('');
	const [password, setPassword] = useState('');
	const [showPassword, setShowPassword] = useState(false);
	const [formError, setFormError] = useState<string | null>(null);
	const [formLoading, setFormLoading] = useState(false);
	const [jwtPreview, setJwtPreview] = useState<string | null>(null);
	const [showTokenDetails, setShowTokenDetails] = useState(false);
	const [activeTab, setActiveTab] = useState<'primary' | 'credentials' | 'google'>('credentials');
	const [redirecting, setRedirecting] = useState(false);
	const [introspectAccess, setIntrospectAccess] = useState<any | null>(null);
	const [introspectRefresh, setIntrospectRefresh] = useState<any | null>(null);
	const [showSuppressionPanel, setShowSuppressionPanel] = useState(() => {
		try { return localStorage.getItem('fks.suppression.debug') === 'true'; } catch { return false; }
	});

	const googleEnabled = (localStorage.getItem('security.googleOAuth') ?? (import.meta as any).env?.VITE_GOOGLE_OAUTH) === 'true';

	// Prefer build-time env; otherwise use relative /auth (nginx proxy). Local 4100 only if explicitly set.
	const rustAuthBase = ((): string => {
		const explicit = (import.meta as any).env?.VITE_RUST_AUTH_URL;
		if (explicit && explicit.trim().length) return explicit.replace(/\/$/, '');
		if (typeof window !== 'undefined' && window.location.port === '4100') return 'http://localhost:4100';
		return '/auth';
	})();

	const decodeJwt = (token: string): any | null => {
		try {
			const [headerB64, payloadB64] = token.split('.');
			if (!payloadB64) return null;
			const decode = (b64: string) => JSON.parse(decodeURIComponent(escape(atob(b64.replace(/-/g,'+').replace(/_/g,'/')))));
			const payload = decode(payloadB64);
			const header = headerB64 ? decode(headerB64) : {};
			return { header, ...payload };
		} catch { return null; }
	};

	const loginWithCredentials = useCallback(async () => {
		setFormError(null);
		setJwtPreview(null);
		setIntrospectAccess(null);
		setIntrospectRefresh(null);
		setFormLoading(true);
		try {
			// Clear stale tokens before fresh credential attempt
			try { localStorage.removeItem('auth_tokens'); localStorage.removeItem('auth_user'); } catch {}
			if (!username || !password) {
				throw new Error('Username & password required');
			}

			const resp = await fetch(`${rustAuthBase}/login`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, password })
			});

			if (!resp.ok) {
				const text = await resp.text();
				throw new Error(text || `Login failed (${resp.status})`);
			}
			const data = await resp.json();
			// Expect shape: { access_token, refresh_token?, expires_in? }
			if (!data.access_token) {
				throw new Error('Invalid response: no access_token');
			}
			localStorage.setItem('auth_tokens', JSON.stringify(data));
			localStorage.setItem('auth_provider', 'rust');
			const decoded = decodeJwt(data.access_token);
			setJwtPreview(decoded ? JSON.stringify({ sub: decoded.sub, exp: decoded.exp, typ: decoded.typ, iss: decoded.iss, aud: decoded.aud, jti: decoded.jti }, null, 2) : 'Token decoded (preview unavailable)');

			// Introspect both tokens for clarity
			try {
				const ai = await fetch(`${rustAuthBase}/introspect`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: data.access_token }) }).then(r => r.json().catch(()=>null));
				setIntrospectAccess(ai);
				const ri = await fetch(`${rustAuthBase}/introspect`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: data.refresh_token }) }).then(r => r.json().catch(()=>null));
				setIntrospectRefresh(ri);
			} catch { /* ignore */ }

			// Trigger security posture refresh
			await validateSecurity();
		} catch (e: any) {
			setFormError(e.message || 'Credential login failed');
		} finally {
			setFormLoading(false);
		}
	}, [username, password, rustAuthBase, validateSecurity]);

	const startRustRedirect = useCallback(async () => {
		try {
			setRedirecting(true);
			// Use orchestrator via security context login helper (returns URL for oauth/passkey flows) or build directly
			const authBase = rustAuthBase.replace(/\/$/, '');
			const ret = new URLSearchParams(window.location.search).get('returnTo') || '/';
			// Use /oauth/callback (outside /auth proxy) so nginx doesn't intercept before SPA router
			window.location.href = `${authBase}/login?redirect_uri=${encodeURIComponent(window.location.origin + '/oauth/callback?returnTo=' + encodeURIComponent(ret))}`;
		} catch (e:any) {
			setFormError(e.message || 'Failed to start auth redirect');
			setRedirecting(false);
		}
	}, [rustAuthBase]);

	const startGoogleOAuth = useCallback(async () => {
		if (!googleEnabled) return;
		try {
			setRedirecting(true);
			// Ask orchestrator for auth URL (through login(preferPasskey, 'google'))
			const url = await initiateAuthFlow(false, 'google');
			if (url && typeof url === 'string') {
				const ret = new URLSearchParams(window.location.search).get('returnTo') || '/';
				// Add state marker so callback can infer provider
				const sep = url.includes('?') ? '&' : '?';
				window.location.href = `${url}${sep}state=google_oauth::ret::${encodeURIComponent(ret)}`;
			} else {
				setRedirecting(false);
			}
		} catch (e:any) {
			setFormError(e.message || 'Failed to start Google OAuth');
			setRedirecting(false);
		}
	}, [initiateAuthFlow, googleEnabled]);

	if (authenticated && user) {
		return (
			<div className="max-w-lg mx-auto mt-16 p-8 bg-white dark:bg-gray-900 rounded-xl shadow-md border border-gray-200 dark:border-gray-700">
				<div className="flex items-center space-x-3 mb-4">
					<CheckCircle className="h-8 w-8 text-green-600" />
					<h2 className="text-xl font-semibold text-gray-900 dark:text-white">Authenticated</h2>
				</div>
				<p className="text-gray-600 dark:text-gray-300 mb-2">You are signed in as <span className="font-medium">{user.name || user.username}</span>.</p>
				<pre className="text-xs bg-gray-100 dark:bg-gray-800 p-3 rounded-md overflow-auto max-h-40">{jwtPreview || 'Session established.'}</pre>
				<p className="mt-4 text-sm text-gray-500 dark:text-gray-400">Navigate to the application dashboard.</p>
			</div>
		);
	}

	return (
		<PageContainer maxWidth="5xl" className="flex items-start pt-20">
			<div className="w-full grid lg:grid-cols-2 gap-10">
						<div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm p-8 relative overflow-hidden">
							<SuppressedProbeBadge />
					<div className="absolute -top-10 -right-10 h-32 w-32 bg-blue-500/10 rounded-full" />
					<div className="absolute -bottom-12 -left-12 h-40 w-40 bg-indigo-500/10 rounded-full" />
					<div className="relative">
						<div className="absolute -top-3 left-0 flex gap-2">
							<button
								className="text-[10px] px-2 py-1 rounded bg-amber-500/20 text-amber-200 border border-amber-400/40 hover:bg-amber-500/30"
								onClick={() => setShowSuppressionPanel(s => !s)}
								title="Toggle suppression diagnostics"
							>
								{showSuppressionPanel ? 'Hide' : 'Show'} Suppressions
							</button>
						</div>
						<div className="mb-6">
							<h1 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-white flex items-center gap-2"><Shield className="h-7 w-7 text-blue-600" /> Secure Login</h1>
							<p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Choose a method below to authenticate.</p>
						</div>
						<div className="flex flex-wrap gap-2 mb-6">
							{['credentials','primary', ...(googleEnabled ? ['google'] : [])].map(tab => (
								<button key={tab} onClick={() => setActiveTab(tab as any)} className={`px-4 py-2 rounded-md text-sm font-medium border transition-colors ${activeTab === tab ? 'bg-blue-600 text-white border-blue-600 shadow-sm' : 'border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'}`}>{tab === 'primary' ? 'Primary' : tab.charAt(0).toUpperCase()+tab.slice(1)}</button>
							))}
						</div>
						{activeTab === 'credentials' && (
							<div className="space-y-5">
								<h2 className="text-lg font-medium text-gray-900 dark:text-white flex items-center"><Lock className="h-5 w-5 mr-2" /> Username & Password</h2>
								{formError && (
									<div className="p-3 rounded-md border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20 flex items-start space-x-2 text-sm text-red-700 dark:text-red-300">
										<AlertCircle className="h-4 w-4 mt-0.5" />
										<span>{formError}</span>
									</div>
								)}
								{securityError && !formError && (
									<div className="p-3 rounded-md border border-yellow-300 dark:border-yellow-700 bg-yellow-50 dark:bg-yellow-900/20 flex items-start space-x-2 text-sm text-yellow-700 dark:text-yellow-300">
										<AlertCircle className="h-4 w-4 mt-0.5" />
										<span>{securityError}</span>
									</div>
								)}
								<div className="space-y-4">
									<label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Username</label>
									<div className="relative mb-2">
										<User className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
										<input type="text" autoComplete="username" className="w-full pl-9 pr-3 py-2 rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 dark:text-gray-100" value={username} onChange={e => setUsername(e.target.value)} />
									</div>
									<label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Password</label>
									<div className="relative">
										<Key className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
										<input type={showPassword ? 'text' : 'password'} autoComplete="current-password" className="w-full pl-9 pr-9 py-2 rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 dark:text-gray-100" value={password} onChange={e => setPassword(e.target.value)} />
										<button type="button" onClick={() => setShowPassword(p => !p)} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>
									</div>
									<button onClick={loginWithCredentials} disabled={formLoading || !username || !password} className="mt-4 w-full flex items-center justify-center px-4 py-2 rounded-md text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed">
										{formLoading ? <Loader className="h-4 w-4 animate-spin mr-2" /> : <Shield className="h-4 w-4 mr-2" />}
										Sign In
									</button>
									<p className="text-xs text-gray-500 dark:text-gray-400">Credentials sent securely to Rust auth service. JWT stored locally.</p>
													{jwtPreview && (
														<div className="mt-2 space-y-2">
															<button type="button" onClick={() => setShowTokenDetails(s => !s)} className="text-[11px] px-2 py-1 rounded border border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
																{showTokenDetails ? 'Hide' : 'Show'} token details
															</button>
															{showTokenDetails && (
																<div className="space-y-2">
																	<pre className="text-[10px] bg-gray-100 dark:bg-gray-800 p-2 rounded-md overflow-auto max-h-40 border border-gray-200 dark:border-gray-700">{jwtPreview}</pre>
																	<div className="text-[10px] text-gray-600 dark:text-gray-400">
																		<span className="font-semibold">Raw Access Token:</span>
																		<code className="block break-all mt-1 select-all">{(JSON.parse(localStorage.getItem('auth_tokens')||'{}') as any).access_token || ''}</code>
																	</div>
																	{(introspectAccess || introspectRefresh) && (
																		<div className="grid grid-cols-2 gap-2">
																			<div>
																				<div className="text-[10px] font-semibold text-gray-700 dark:text-gray-300 mb-1">Access Introspect</div>
																				<pre className="text-[9px] bg-gray-100 dark:bg-gray-800 p-2 rounded border border-gray-200 dark:border-gray-700 max-h-32 overflow-auto">{JSON.stringify(introspectAccess, null, 2)}</pre>
																			</div>
																			<div>
																				<div className="text-[10px] font-semibold text-gray-700 dark:text-gray-300 mb-1">Refresh Introspect</div>
																				<pre className="text-[9px] bg-gray-100 dark:bg-gray-800 p-2 rounded border border-gray-200 dark:border-gray-700 max-h-32 overflow-auto">{JSON.stringify(introspectRefresh, null, 2)}</pre>
																			</div>
																		</div>
																	)}
																</div>
															)}
														</div>
													)}
								</div>
							</div>
						)}

						{activeTab === 'primary' && (
							<div className="space-y-4">
								<h2 className="text-lg font-medium text-gray-900 dark:text-white flex items-center"><LogIn className="h-5 w-5 mr-2" /> Primary Auth</h2>
								<p className="text-sm text-gray-600 dark:text-gray-400">Use the Rust auth redirect flow (future: passkeys).</p>
								<div className="flex flex-col space-y-3">
									<button onClick={startRustRedirect} disabled={redirecting || loading} className="w-full flex items-center justify-center px-4 py-2 rounded-md text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50">
										{redirecting ? <Loader className="h-4 w-4 animate-spin mr-2" /> : <ExternalLink className="h-4 w-4 mr-2" />}
										Continue with Rust Auth
									</button>
									{googleEnabled && (
										<button onClick={startGoogleOAuth} disabled={redirecting || loading} className="w-full flex items-center justify-center px-4 py-2 rounded-md text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-50">
											{redirecting ? <Loader className="h-4 w-4 animate-spin mr-2" /> : <Chrome className="h-4 w-4 mr-2" />}
											Continue with Google
										</button>
									)}
								</div>
								<div className="text-xs text-gray-500 dark:text-gray-400">Redirect-based authentication. You'll return here after granting access.</div>
							</div>
						)}

						{activeTab === 'google' && googleEnabled && (
							<div className="space-y-4">
								<h2 className="text-lg font-medium text-gray-900 dark:text-white flex items-center"><Chrome className="h-5 w-5 mr-2" /> Google OAuth</h2>
								<p className="text-sm text-gray-600 dark:text-gray-400">Federated sign-in via Google.</p>
								<button onClick={startGoogleOAuth} disabled={redirecting || loading} className="w-full flex items-center justify-center px-4 py-2 rounded-md text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-50">
									{redirecting ? <Loader className="h-4 w-4 animate-spin mr-2" /> : <Chrome className="h-4 w-4 mr-2" />}
									Sign in with Google
								</button>
								<div className="text-xs text-gray-500 dark:text-gray-400">Enabled via security.googleOAuth flag.</div>
							</div>
						)}
						{showSuppressionPanel && <SuppressionDebugPanel onClose={() => setShowSuppressionPanel(false)} />}
					</div>
				</div>
				<div className="space-y-6">
					<div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm">
						<h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2 flex items-center"><Shield className="h-5 w-5 mr-2 text-blue-600" /> Security Layers</h3>
						<ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1 list-disc list-inside">
							<li>Rust JWT auth (primary)</li>
							<li>Optional Google OAuth (federated)</li>
							<li>Passkey placeholder (future)</li>
							<li>VPN awareness (Tailscale)</li>
							<li>Performance & audit instrumentation</li>
						</ul>
					</div>
					<div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm">
						<h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">How Credential Flow Works</h3>
						<ol className="list-decimal list-inside text-sm text-gray-600 dark:text-gray-400 space-y-1">
							<li>POST /login to Rust auth</li>
							<li>Store access/refresh tokens in localStorage</li>
							<li>Update security posture via context</li>
							<li>Subsequent protected requests enforce policies</li>
						</ol>
						<p className="mt-3 text-xs text-gray-500 dark:text-gray-500">Ensure VITE_RUST_AUTH_URL points at fks_auth service.</p>
						<div className="mt-4 border-t border-gray-200 dark:border-gray-700 pt-3">
							<h4 className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-1">Debug</h4>
							<ul className="text-[11px] space-y-1 text-gray-600 dark:text-gray-400">
								<li>Auth Base: <code>{rustAuthBase}</code></li>
								<li>Has Tokens: {localStorage.getItem('auth_tokens') ? 'yes' : 'no'}</li>
								<li>Last Error: <code>{localStorage.getItem('auth_last_error') || 'n/a'}</code></li>
								<li><button onClick={() => { localStorage.removeItem('auth_tokens'); localStorage.removeItem('auth_user'); location.reload(); }} className="px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700">Reset Session</button></li>
							</ul>
						</div>
					</div>
				</div>
			</div>
		</PageContainer>
	);
};

export default LoginPage;


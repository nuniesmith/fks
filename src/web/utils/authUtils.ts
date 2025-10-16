// Utility for constructing authentication login URLs that preserve return path
// Supports cross-subdomain redirects in production environments.

export function buildAuthLoginUrl(returnTo?: string): string {
	// Use provided return path or current location
	const target = returnTo || (typeof window !== 'undefined' ? window.location.pathname + window.location.search + window.location.hash : '/');

	// If running in a production environment with subdomains, direct to auth domain
	if (typeof window !== 'undefined') {
		const host = window.location.host; // e.g., app.example.com
		const protocol = window.location.protocol; // http: or https:
		// Heuristic: if host contains a dot and isn't localhost, assume auth subdomain available
		if (!host.startsWith('localhost') && host.split('.').length >= 2) {
			const rootDomainParts = host.split('.').slice(-2); // example.com
			const rootDomain = rootDomainParts.join('.');
			const authHost = `auth.${rootDomain}`;
			const encoded = encodeURIComponent(target);
			return `${protocol}//${authHost}/login?returnTo=${encoded}`;
		}
	}

	// Fallback relative path for local/dev where same host handles login
	const encodedLocal = encodeURIComponent(target);
	return `/login?returnTo=${encodedLocal}`;
}

export default buildAuthLoginUrl;

import React, { useEffect, useState } from 'react';

import { useSecurityContext } from '../../../context/SecurityContext';

function AuthCallback() {
  const { completeLogin, loading, error } = useSecurityContext();
  const [message, setMessage] = useState('Completing authentication...');

  useEffect(() => {
    const url = new URL(window.location.href);
    const code = url.searchParams.get('code');
    const state = url.searchParams.get('state');

    // Try to infer provider from state if set
  const provider = state?.includes('google_oauth') ? 'google' : 'rust';

    if (!code || !state) {
      setMessage('Missing OAuth parameters.');
      return;
    }

    const run = async () => {
      try {
  await completeLogin(code, state, provider as 'rust' | 'google');
        // Navigate back to home or intended page
        window.location.replace('/');
      } catch (e) {
        setMessage('Failed to complete authentication.');
      }
    };
    run();
  }, [completeLogin]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="glass-card p-6 text-white">
        <div className="text-lg font-medium">
          {loading ? 'Finalizing login…' : message}
        </div>
        {error && (
          <div className="text-red-300 mt-2 text-sm">{error}</div>
        )}
      </div>
    </div>
  );
}

export default AuthCallback;

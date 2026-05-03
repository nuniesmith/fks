import { redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
  // GET /logout just redirects to login — the action handles the actual logout
  redirect(302, '/login');
};

export const actions: Actions = {
  default: async ({ cookies }) => {
    cookies.delete('fks_session', { path: '/' });
    redirect(302, '/login');
  },
};

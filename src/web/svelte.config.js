import adapter from '@sveltejs/adapter-node';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter({
      out: 'build',
      precompress: true,
    }),
    alias: {
      '$lib': 'src/lib',
      '$api': 'src/lib/api',
      '$stores': 'src/lib/stores',
      '$components': 'src/lib/components',
    },
  },
};

export default config;

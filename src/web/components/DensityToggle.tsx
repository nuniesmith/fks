import React, { useEffect, useState } from 'react'

type Density = 'cozy' | 'compact'

export const DensityToggle: React.FC = () => {
  const [density, setDensity] = useState<Density>(() => {
    try { return (localStorage.getItem('fks.ui.density') as Density) || 'cozy' } catch { return 'cozy' }
  })

  useEffect(() => {
    try { localStorage.setItem('fks.ui.density', density) } catch {}
    const root = document.documentElement
    root.setAttribute('data-density', density)
  }, [density])

  const toggle = () => setDensity(density === 'cozy' ? 'compact' : 'cozy')

  return (
    <button
      onClick={toggle}
      className="p-2 rounded-lg bg-white/10 hover:bg-white/20 border border-white/20 text-white text-xs font-mono"
      title={`Switch to ${density === 'cozy' ? 'compact' : 'cozy'} density`}
      type="button"
    >
      {density === 'cozy' ? 'Cozy' : 'Compact'}
    </button>
  )
}

export default DensityToggle
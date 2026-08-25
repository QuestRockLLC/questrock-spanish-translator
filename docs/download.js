/** @typedef {'mac' | 'windows' | 'other'} Os */

/**
 * @param {string} userAgent
 * @returns {Os}
 */
export function detectOs(userAgent) {
  const ua = userAgent.toLowerCase()
  if (ua.includes('windows') || ua.includes('win32') || ua.includes('win64')) {
    return 'windows'
  }
  if (ua.includes('mac os') || ua.includes('macintosh') || ua.includes('darwin')) {
    return 'mac'
  }
  return 'other'
}

/**
 * @param {string} hostname
 * @param {string} pathname
 * @returns {{ owner: string, repo: string }}
 */
export function githubRepoFromPagesLocation(hostname, pathname) {
  const owner = hostname.replace(/\.github\.io$/i, '')
  const parts = pathname.split('/').filter(Boolean)
  const repo = parts[0] ?? owner
  return { owner, repo }
}

/**
 * @param {Array<{ name: string, browser_download_url: string }>} assets
 * @param {Os} os
 * @returns {{ name: string, browser_download_url: string } | null}
 */
export function pickInstaller(assets, os) {
  if (os === 'mac') {
    return assets.find((asset) => asset.name.toLowerCase().endsWith('.dmg')) ?? null
  }
  if (os === 'windows') {
    return assets.find((asset) => asset.name.toLowerCase().endsWith('.exe')) ?? null
  }
  return null
}

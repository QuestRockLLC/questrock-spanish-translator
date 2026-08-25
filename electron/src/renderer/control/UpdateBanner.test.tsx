import { render, screen } from '@testing-library/react'
import { UpdateBanner } from './UpdateBanner'

it('renders nothing when idle', () => {
  const { container } = render(<UpdateBanner state={{ status: 'idle' }} onInstall={() => undefined} />)
  expect(container.firstChild).toBeNull()
})

it('shows Update now when a version is available', () => {
  render(<UpdateBanner state={{ status: 'available', version: '0.2.0' }} onInstall={() => undefined} />)
  expect(screen.getByText(/0\.2\.0/)).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Update now' })).toBeTruthy()
})

it('shows download progress', () => {
  render(<UpdateBanner state={{ status: 'downloading', percent: 41 }} onInstall={() => undefined} />)
  expect(screen.getByText(/41%/)).toBeTruthy()
})

it('shows Update now when the download is ready', () => {
  render(<UpdateBanner state={{ status: 'ready', version: '0.2.0' }} onInstall={() => undefined} />)
  expect(screen.getByRole('button', { name: 'Update now' })).toBeTruthy()
})

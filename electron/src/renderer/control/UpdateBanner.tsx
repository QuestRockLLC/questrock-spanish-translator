import type { UpdateUiState } from '../../main/updater'

export function UpdateBanner(props: {
  state: UpdateUiState
  onInstall: () => void
}) {
  const { state, onInstall } = props
  if (state.status === 'idle') {
    return null
  }
  return (
    <div
      role="status"
      style={{
        marginBottom: 16,
        padding: '10px 12px',
        background: '#f2f2f7',
        border: '1px solid #d1d1d6',
        borderRadius: 8,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <span>
        {state.status === 'available' ? `Update ${state.version} available` : null}
        {state.status === 'downloading' ? `Downloading update ${state.percent}%` : null}
        {state.status === 'ready' ? `Update ${state.version} ready` : null}
        {state.status === 'error' ? state.message : null}
      </span>
      {state.status === 'available' || state.status === 'ready' ? (
        <button type="button" onClick={onInstall}>
          Update now
        </button>
      ) : null}
    </div>
  )
}

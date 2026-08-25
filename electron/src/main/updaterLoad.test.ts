import electronUpdater from 'electron-updater'

it('imports electron-updater as a CJS default export', () => {
  expect(electronUpdater).toBeTruthy()
  expect('autoUpdater' in (electronUpdater as object)).toBe(true)
})

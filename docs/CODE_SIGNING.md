# Code signing for QuestRock AI Assistant

The app ships unsigned today.
GitHub Actions still builds installers and the in-app Update now button still downloads them from a public Release.
Signing is what makes macOS Gatekeeper and Windows SmartScreen stop warning users.

Do this when you are ready to sell or hand the app to loan officers who should not fight OS trust dialogs.

## Apple Developer ID

1. Enroll in the Apple Developer Program at https://developer.apple.com/programs/ (paid, about $99 per year).
2. In Certificates, Identifiers and Profiles, create a Developer ID Application certificate.
3. Export the certificate from Keychain Access as a `.p12` file.
4. Create an app-specific password at https://appleid.apple.com for notarization.
5. In the GitHub repo, add these Actions secrets:

- `CSC_LINK` - base64 of the `.p12`, or a URL/path electron-builder accepts
- `CSC_KEY_PASSWORD` - password for the `.p12`
- `APPLE_ID` - Apple ID email
- `APPLE_APP_SPECIFIC_PASSWORD` - the app-specific password
- `APPLE_TEAM_ID` - 10-character Team ID

6. Remove `identity: null` from `electron/electron-builder.yml`.
7. Remove `CSC_IDENTITY_AUTO_DISCOVERY: "false"` from `.github/workflows/release.yml` on the macOS job, or leave it unset so electron-builder can pick the cert.
8. Push a new version tag. The Mac job should notarize the `.dmg` / `.zip`.

After that, first launch on a Mac should not require right-click Open.

## Windows Authenticode

1. Buy an Authenticode certificate from a public CA.
   An OV cert works. An EV cert reduces SmartScreen warnings faster. There is no free Microsoft cert for this.
2. Export a `.pfx` / `.p12`.
3. Add GitHub Actions secrets:

- `CSC_LINK` - the `.pfx` (same name electron-builder uses on Windows)
- `CSC_KEY_PASSWORD` - password for the `.pfx`

If you sign Mac and Windows in the same workflow, use one `CSC_LINK` per OS job by splitting secrets (`MAC_CSC_LINK` / `WIN_CSC_LINK`) and mapping them to `CSC_LINK` in that job.

4. Remove `CSC_IDENTITY_AUTO_DISCOVERY: "false"` from the Windows job.
5. Push a new version tag.

## Until you have certs

On Mac, first install: right-click the app, choose Open, confirm the Gatekeeper dialog.

On Windows, click More info then Run anyway if SmartScreen appears.

Auto-update from a public GitHub Release still works without signatures. It is just a worse first-run experience.

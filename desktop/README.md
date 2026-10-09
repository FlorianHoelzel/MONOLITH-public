# MONOLITH Desktop

Schlanker Electron-Wrapper für das MONOLITH-Dashboard unter
`https://monolith.local`.

Die Glocke im Dashboard aktiviert native Desktop-Benachrichtigungen. Die
Einstellung wird lokal für den Dashboard-Ursprung gespeichert.

## Entwicklung

```powershell
cd desktop
npm install
npm start
```

Eine andere Adresse kann vor dem Start über `MONOLITH_URL` gesetzt werden:

```powershell
$env:MONOLITH_URL = "http://192.0.2.75:5000"
npm start
```

## Windows-Installer bauen

```powershell
npm run build
```

Der Installer wird in `desktop/dist` abgelegt.

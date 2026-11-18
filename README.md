# AMS - Archaeological Matrix Software & AR Museum

Piattaforma web open-source progettata per generare automaticamente il **Matrix di Harris** (diagramma stratigrafico archeologico con riduzione transitiva) e collegare ogni Unità Stratigrafica (US) a ricostruzioni 3D navigabili in **Realtà Aumentata (WebXR / ARKit / ARCore)** direttamente dal browser, senza installare app.

## Funzionalità Principali
- **Calcolo Automatico Matrix di Harris**: Rimozione delle relazioni stratigrafiche ridondanti tramite algoritmi su grafi orientati aciclici (`NetworkX`).
- **Realtà Aumentata Nativa**: Proiezione dei rilievi fotogrammetrici (`.glb` e `.usdz`) nello spazio reale tramite `<model-viewer>`.
- **Gestione Multi-Sala & SQLite**: Separazione degli scavi per sale espositive con persistenza su database SQLite.
- **Pannello Archeologi (`/admin`)**: Area riservata protetta da autenticazione per inserire Unità Stratigrafiche e caricare modelli 3D dal browser.
- **Generatore QR Code**: Creazione istantanea di QR Code ad alta correzione d'errore per i cartellini delle teche museali con deep-linking diretto all'US.

## Avvio Rapido con Docker

1. Crea il file database vuoto per il volume persistente:
   ```bash
   touch ams_museum.db
   ```
2. Avvia il container:
   ```bash
   docker compose up -d --build
   ```
3. Accedi all'interfaccia pubblica su `http://localhost:8000` e al pannello archeologi su `http://localhost:8000/admin` (credenziali predefinite: `archeologo` / `CambiaQuestaPassword2026!`).

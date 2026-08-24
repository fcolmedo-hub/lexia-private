# Instalar LexIA en macOS

Esta instalación crea una instancia nueva de LexIA para macOS. El código se obtiene de GitHub, pero su biblioteca, bases SQLite, índices y configuraciones son independientes de Windows.

LexIA usa Qdrant Server en Docker Desktop, igual que la instancia de Windows. Qdrant queda limitado a la propia Mac y sus datos son persistentes.

## Ubicaciones

- Código: `~/LexIA_2.3_DEV`
- Biblioteca nueva y vacía: `~/Documents/LexIA Biblioteca`
- Datos operativos, índices, registros, copias y exportaciones: `~/Library/Application Support/LexIA`
- Datos persistentes de Qdrant: `~/Library/Application Support/LexIA/qdrant`

Podés agregar carpetas externas a la biblioteca desde LexIA; no hace falta guardar documentos dentro de `LexIA_2.3_DEV`.

## Primera instalación

Abrí Terminal y ejecutá, en orden:

```zsh
brew install gh
gh auth login
gh repo clone fcolmedo-hub/lexia-private "$HOME/LexIA_2.3_DEV" -- --branch estabilizacion/mantenimiento-servicios
cd "$HOME/LexIA_2.3_DEV"
zsh scripts/install_macos_3_4.sh
open INICIAR_LEXIA_MAC.command
```

El instalador instala Docker Desktop si hace falta, lo abre, crea el contenedor `lexia-qdrant` y guarda sus datos fuera del repositorio. La primera vez puede aparecer la aceptación de términos de Docker Desktop: aceptala y esperá a que indique que el motor está en ejecución. Si el instalador se detiene por ese motivo, ejecutá nuevamente el mismo comando.

Durante `gh auth login`, elegí GitHub.com, HTTPS y autenticación en el navegador. No pegues claves ni tokens en Terminal.

El instalador utiliza Python 3.11 de Homebrew en una máquina virtual aislada de LexIA. No modifica otros proyectos ni sus entornos virtuales.

## Actualizaciones futuras

Con LexIA cerrada:

```zsh
cd "$HOME/LexIA_2.3_DEV"
git pull --ff-only origin estabilizacion/mantenimiento-servicios
zsh scripts/install_macos_3_4.sh
```

La actualización del código no mezcla la biblioteca de macOS con la de Windows.

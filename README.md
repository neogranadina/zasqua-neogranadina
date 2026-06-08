# Zasqua — Neogranadina

**English version below.**

Este repositorio es el código de [zasqua.org](https://zasqua.org), el archivo
digital de materiales históricos de Neogranadina: más de 106.000 descripciones
archivísticas, 78.000 registros de autoridad de entidades y 6.900 de lugares,
provenientes de cinco repositorios en Colombia y Perú. Es una instancia del
[motor Zasqua](https://github.com/UCSB-AMPLab/zasqua), el software de código
abierto que convierte una exportación de datos archivísticos en un sitio web
estático y con búsqueda.

## Estructura del repositorio

Este repositorio es una capa ligera sobre el motor:

- `themes/neogranadina/` — la identidad visual (plantillas, estilos, logotipos)
  superpuesta al tema base, neutral, del motor
- `content/` — las páginas del sitio (inicio, colofón, portadas de sección)
- `hugo.toml` — la configuración del sitio
- `zasqua.manifest.toml` — qué módulos del motor están activos
- `deploy/` — el script de subida a R2, el fragmentador del sitemap y el Worker
  de Cloudflare que sirve el sitio
- `.github/workflows/deploy.yml` — el flujo de despliegue a producción

El motor —la interfaz de línea de comandos `zasqua`, el tema base, el proceso de
construcción y los importadores— es el paquete npm
[`@ucsb-ampl/zasqua`](https://www.npmjs.com/package/@ucsb-ampl/zasqua), fijado en
`package.json`. Este repositorio no contiene código del motor.

## Cómo funciona

Los datos archivísticos se catalogan en
[Fisqua](https://github.com/UCSB-AMPLab/fisqua) y se exportan como un contrato de
datos de seis archivos JSON, almacenado en Backblaze B2. Al construir el sitio,
el motor descarga la exportación, la enriquece y genera todo el archivo como HTML
estático, con búsqueda en el navegador (Pagefind), imágenes IIIF servidas en
mosaicos (TIFY) y mapas (MapLibre). El resultado es completamente estático —sin
servidor de aplicaciones ni base de datos en el momento de la consulta— y se
sirve desde Cloudflare (R2 más un Worker).

Es una aplicación deliberada de los principios del *minimal computing*. Servir un
corpus de este tamaño —con búsqueda por facetas, un grafo de entidades, mapas con
marcadores agrupados y visualización de imágenes en alta resolución, todo sin un
solo proceso del lado del servidor— mantiene el sitio rápido, almacenable en
caché, económico de alojar y resiliente. Como el sitio público son solo archivos,
se puede archivar, replicar o reconstruir a partir de sus exportaciones sin
depender de ningún servicio en ejecución.

## Desarrollo local

Requiere Node (ver `.nvmrc`) y las credenciales de Backblaze B2 para la
exportación de datos.

```
npm ci          # instala el motor más Hugo, Pagefind y Tailwind
npm run dev     # zasqua dev — vista previa local en 127.0.0.1:1313
npm run build   # zasqua build — construcción estática completa en public/
```

`zasqua build` ejecuta todo el proceso con los archivos del contrato que estén
en `exports/`; antes de construir en local, descárguelos de Backblaze B2 o use
su propia copia. Defina `DEV_LIMIT=<n>` para construir un subconjunto en
iteraciones rápidas (una construcción limitada no es un artefacto de producción
válido).

## Despliegue

`.github/workflows/deploy.yml` (ejecución manual) corre `zasqua build` y sube el
resultado a Cloudflare R2. La opción `target_bucket` es el interruptor entre
preproducción y producción: por defecto apunta al bucket de preproducción, y
desplegar a producción exige seleccionar explícitamente el bucket de producción.
La subida compara con lo que ya está publicado, limita las eliminaciones al cinco
por ciento como medida de seguridad y purga la caché de Cloudflare.

## Para montar su propio archivo

No necesita este repositorio para montar su propio sitio Zasqua. Empiece con la
[plantilla inicial](https://github.com/UCSB-AMPLab/zasqua-template) y siga la
[guía de despliegue](https://github.com/UCSB-AMPLab/zasqua/blob/main/docs/guide.md).
Este repositorio es el despliegue específico de Neogranadina —un ejemplo real
útil—, pero la plantilla es el punto de partida recomendado.

## Licencia

El código se publica bajo la licencia
[AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html). Las descripciones
archivísticas, los metadatos y las imágenes digitalizadas se publican bajo las
condiciones específicas de cada archivo aliado —consulte la sección "Condiciones
de reproducción" de cada descripción.

## Créditos

Zasqua es desarrollado por Juan Cobo Betancourt en el [Laboratorio de Archivos,
Memoria y Preservación (AMPL)](https://ampl.clair.ucsb.edu) de la Universidad de
California, Santa Bárbara, y [Neogranadina](https://neogranadina.org).

## Marcas

"Zasqua", "Fisqua", "AMPL" y los logotipos asociados no están cubiertos por la
licencia AGPL-3.0. Los forks pueden usar el código libremente bajo los términos
de la AGPL, pero no deben presentarse como versiones oficiales de Zasqua, Fisqua
o AMPL.

## Enlaces

- Sitio: https://zasqua.org
- Motor: https://github.com/UCSB-AMPLab/zasqua (npm `@ucsb-ampl/zasqua`)
- Plantilla inicial: https://github.com/UCSB-AMPLab/zasqua-template
- Aplicación de catalogación (Fisqua): https://github.com/UCSB-AMPLab/fisqua

---

# English

**Versión en español arriba.**

This repository is the source of [zasqua.org](https://zasqua.org), Neogranadina's
digital archive of historical materials — over 106,000 archival descriptions,
78,000 entity authority records, and 6,900 place authority records drawn from
five repositories in Colombia and Peru. It is an **instance** of the
[Zasqua engine](https://github.com/UCSB-AMPLab/zasqua) — the open-source software
that turns an archival data export into a static, searchable website.

## Repository layout

This repository is a thin **overlay** on top of the engine:

- `themes/neogranadina/` — the visual identity (layouts, styles, logos) layered
  over the engine's neutral base theme
- `content/` — the site's content pages (home, colophon, section landings)
- `hugo.toml` — site configuration
- `zasqua.manifest.toml` — which engine capability modules are enabled
- `deploy/` — the R2 upload script, the sitemap sharder, and the Cloudflare
  Worker that serves the site
- `.github/workflows/deploy.yml` — the production deploy pipeline

The engine itself — the `zasqua` command-line interface, the base theme, the
build pipeline, the importers — is the npm package
[`@ucsb-ampl/zasqua`](https://www.npmjs.com/package/@ucsb-ampl/zasqua), pinned in
`package.json`. This repository contains no engine code.

## How it works

The archival data is catalogued in
[Fisqua](https://github.com/UCSB-AMPLab/fisqua) and exported as a documented
six-file JSON data contract, stored in Backblaze B2. At build time the engine
downloads the export, enriches it, and renders the whole archive as static HTML
with client-side search (Pagefind), IIIF image tiles (TIFY), and place maps
(MapLibre). The result is fully static — no application server or database at
request time — and is served from Cloudflare (R2 plus a Worker).

This is a deliberate application of minimal computing principles. Serving a
corpus of this size — with faceted search, a force-directed entity graph,
clustered-marker maps, and high-resolution image viewing, all without a single
server-side process — keeps the site fast, cacheable, cheap to host, and
resilient. Because the public site is just files, it can be archived, mirrored,
or rebuilt from its exports with no dependency on a running service.

## Local development

Requires Node (see `.nvmrc`) and the Backblaze B2 credentials for the data
export.

```
npm ci          # installs the engine plus Hugo, Pagefind, and Tailwind
npm run dev     # zasqua dev — local preview at 127.0.0.1:1313
npm run build   # zasqua build — full static build into public/
```

`zasqua build` runs the whole pipeline against the contract files in `exports/`;
populate them from Backblaze B2 (or your own copy) before building locally. Set
`DEV_LIMIT=<n>` to build a subset for fast iteration (a capped build is not a
valid production artifact).

## Deployment

`.github/workflows/deploy.yml` (manual dispatch) runs `zasqua build` and uploads
to Cloudflare R2. The `target_bucket` input is the staging/production switch: it
defaults to the staging bucket, and a production deploy requires explicitly
selecting the production bucket. The upload diffs against what is already live,
caps deletions at five percent as a safety check, and purges the Cloudflare
cache.

## Running your own archive

You do not need this repository to set up your own Zasqua site. Start from the
[starter template](https://github.com/UCSB-AMPLab/zasqua-template) and follow the
[deployment guide](https://github.com/UCSB-AMPLab/zasqua/blob/main/docs/guide.md).
This repository is Neogranadina's specific deployment — a useful real-world
example, but the template is the supported starting point.

## License

The code is published under
[AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html). The archival
descriptions, metadata, and digitized images are published under the specific
terms of each partner archive — see the "Conditions of reproduction" section of
each description.

## Credits

Zasqua is developed by Juan Cobo Betancourt at the [Archives, Memory, and
Preservation Lab](https://ampl.clair.ucsb.edu) (AMPL) of the University of
California, Santa Barbara, and [Neogranadina](https://neogranadina.org).

## Trademarks

"Zasqua", "Fisqua", "AMPL", and the associated logos are not covered by the
AGPL-3.0 license. Forks may use the code freely under AGPL terms but should not
present themselves as official Zasqua, Fisqua, or AMPL releases.

## Links

- Live site: https://zasqua.org
- Engine: https://github.com/UCSB-AMPLab/zasqua (npm `@ucsb-ampl/zasqua`)
- Starter template: https://github.com/UCSB-AMPLab/zasqua-template
- Cataloguing application (Fisqua): https://github.com/UCSB-AMPLab/fisqua

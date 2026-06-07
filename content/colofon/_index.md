---
# Colophon page content — deployer-editable institutional prose.
#
# This is the Neogranadina colophon, authored as a Hugo markdown content
# page. Deployers edit the colophon HERE, as content, rather than in a
# theme template: every section below (credits, version, represented
# archives, citation, technology, accessibility, privacy, license,
# contact) is institution-specific prose, not engine chrome.
#
# The engine base template (themes/base/layouts/colofon/list.html)
# renders this page's .Content inside a prose-styled article. Three
# dynamic values stay out of the markdown, via engine shortcodes:
#   {{< version >}}        -> site.Params.version  (this INSTANCE's version)
#   {{< engine-version >}} -> hugo.Data.engine.version (the ENGINE's version,
#                             stamped at build time by lib/theme.js)
#   {{< year >}}           -> the current build year
# So a version bump in hugo.toml (or an engine bump) re-renders only this
# one page; the rest of the corpus stays on the diff-skip path.
#
# The colophon deliberately distinguishes the two things that share the
# name "Zasqua": the ARCHIVE (this Neogranadina deployment, versioned by
# {{< version >}}, source at neogranadina/zasqua-neogranadina) and the
# ENGINE that publishes it (versioned by {{< engine-version >}}, source at
# UCSB-AMPLab/zasqua).
#
# Spanish is verbatim es-CO deployment content; do not translate.
#
# The logo uses a raw <img> with Tailwind sizing classes (not a Markdown
# image) so the pomegranate renders at 200px, matching the prior layout-
# rendered colophon; goldmark unsafe=true permits the raw HTML.
#
# Version: v1.1.0
title: "Colofón"
---

<img src="/img/zasqua-3-burgundy-sm.svg" alt="Zasqua" class="block max-w-[200px] mx-auto pb-8">

Zasqua es el archivo digital de [Neogranadina](https://neogranadina.org) y sus instituciones aliadas: reúne materiales de archivo, libros, revistas e instrumentos de consulta digitalizados y sistematizados.

## Versión y código

Esta es la versión **{{< version >}}** de Zasqua, el archivo de Neogranadina. Su código fuente está en [neogranadina/zasqua-neogranadina](https://github.com/neogranadina/zasqua-neogranadina); puede consultar las [notas de esta versión](https://github.com/neogranadina/zasqua-neogranadina/releases/tag/v{{< version >}}) y el [historial completo](https://github.com/neogranadina/zasqua-neogranadina/blob/main/CHANGELOG.md).

Zasqua funciona sobre el motor de publicación de archivos digitales del mismo nombre, Zasqua, versión **{{< engine-version >}}** — software de código abierto (AGPL-3.0) desarrollado por el [Laboratorio de Archivos, Memoria y Preservación (AMPL)](https://ampl.clair.ucsb.edu) de la Universidad de California, Santa Bárbara, con código fuente en [UCSB-AMPLab/zasqua](https://github.com/UCSB-AMPLab/zasqua).

## Archivos representados

Zasqua reúne materiales digitalizados de cinco instituciones aliadas en Colombia y Perú:

- [Archivo Histórico de Rionegro](/co-ahr/) — Rionegro, Colombia
- [Archivo Histórico Regional de Boyacá](/co-ahrb/) — Tunja, Colombia
- [Archivo Histórico del Juzgado del Circuito de Istmina](/co-ahjci/) — Istmina, Colombia
- [Centro de Investigaciones Históricas José María Arboleda Llorente](/co-cihjml/), Universidad del Cauca — Popayán, Colombia
- [Biblioteca Nacional del Perú](/pe-bn/) — Lima, Perú

## Cómo citar

**Plataforma completa:**

> *Zasqua: plataforma de consulta de materiales de archivo* (v{{< version >}}). Fundación Histórica Neogranadina y Laboratorio de Archivos, Memoria y Preservación (AMPL), Universidad de California, Santa Bárbara, {{< year >}}. https://zasqua.org

**Descripción específica:** use el identificador canónico que aparece en la sección "Control" de cada descripción, por ejemplo:

> *Escritura de compraventa, 1723* (co-ahr-007-d015). Archivo Histórico de Rionegro, consultado en Zasqua. https://zasqua.org/co-ahr-007-d015/

Formato genérico; adapte a las convenciones de su disciplina — Chicago, APA, MLA, ISO 690, etc.

## Tecnología

Zasqua es un sitio estático alojado en Cloudflare. Cada página HTML se genera al momento de la publicación; no hay procesos de servidor en ejecución. Esta arquitectura se alinea con los principios de [*minimal computing*](http://go-dh.github.io/mincomp/) — sostenibilidad, portabilidad y resiliencia a largo plazo.

- **Generador de sitio estático:** [Hugo](https://gohugo.io/) (Extended 0.160)
- **Búsqueda en el navegador del usuario:** [Pagefind](https://pagefind.app/) v1.5.2 — tres índices independientes para descripciones, entidades y lugares
- **Mapas:** [MapLibre GL JS](https://maplibre.org/) con mapa base de [MapTiler](https://www.maptiler.com/)
- **Visor de imágenes:** [TIFY](https://tify.rocks/) — visor IIIF con visualización de zoom profundo; imágenes servidas como mosaicos estáticos IIIF Level 0
- **Estilos:** [Tailwind CSS](https://tailwindcss.com/) v4
- **Alojamiento:** [Cloudflare Workers](https://workers.cloudflare.com/) + [Cloudflare R2](https://www.cloudflare.com/products/r2/)
- **Almacenamiento de exportaciones:** [Backblaze B2](https://www.backblaze.com/b2/)
- **Integración continua:** GitHub Actions mediante [Ubicloud](https://www.ubicloud.com/)

Las descripciones archivísticas y los metadatos se catalogan en [Fisqua](https://github.com/UCSB-AMPLab/fisqua), la aplicación de catalogación de código abierto desarrollada por AMPL, y se exportan para su publicación en Zasqua.

## Accesibilidad

Con Zasqua buscamos que cualquier persona pueda consultar el archivo sin barreras. Empleamos HTML semántico, navegación completa por teclado y etiquetas ARIA cuando la estructura HTML no describe por sí sola la función del elemento. Aún no hemos realizado una auditoría formal de accesibilidad; si encuentra una barrera, escríbanos a [contacto@neogranadina.org](mailto:contacto@neogranadina.org) o [abra un *issue* en GitHub](https://github.com/neogranadina/zasqua-neogranadina/issues).

## Privacidad y datos

Zasqua no utiliza *cookies* ni almacena información personal. El sitio emplea [Cloudflare Web Analytics](https://www.cloudflare.com/web-analytics/) para recopilar estadísticas agregadas de uso — esta herramienta no utiliza *cookies*, no crea identificadores únicos del navegador y no comparte datos con terceros.

Las búsquedas se ejecutan localmente en su navegador (motor Pagefind en WebAssembly); ninguna consulta se envía a nuestros servidores. Los registros de acceso del CDN se conservan únicamente con fines operativos, en forma agregada.

## Licencia

El código de Zasqua y de su motor de publicación se publica bajo la licencia [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html). Las descripciones archivísticas, los metadatos y las imágenes digitalizadas se publican bajo las condiciones específicas de cada archivo aliado — consulte la sección "Condiciones de reproducción" de cada descripción.

## Contacto

- General: [contacto@neogranadina.org](mailto:contacto@neogranadina.org)
- Reportar un error: [GitHub Issues](https://github.com/neogranadina/zasqua-neogranadina/issues)

# RetailOps AI — Lineamientos de UI

**Versión:** 1.0  
**Plataforma:** aplicación web de escritorio, responsive para consulta  
**Base:** Project Brief de RetailOps AI + análisis de patrones de producto en Mobbin  

---

## 1. Propósito de la interfaz

RetailOps AI debe sentirse como un **centro de control operativo confiable**, no como un chatbot ni como una demo de IA. La interfaz debe ayudar a las personas a:

1. detectar qué requiere atención;
2. entender por qué el sistema recomienda una acción;
3. contrastar la recomendación con evidencia;
4. tomar o corregir una decisión con rapidez;
5. reconstruir después qué ocurrió, quién decidió y con qué versión del modelo.

La experiencia se optimiza para usuarios internos que trabajan con alta densidad de datos, decisiones repetitivas y consecuencias financieras.

### Resultado deseado

En cualquier pantalla de decisión, el usuario debe poder contestar en menos de diez segundos:

- ¿Qué pasó?
- ¿Qué tan importante es?
- ¿Qué recomienda el sistema?
- ¿En qué evidencia se apoya?
- ¿Qué acción debo tomar?

---

## 2. Principios rectores

### 2.1 Operación antes que decoración

- Priorizar legibilidad, comparación y velocidad sobre superficies visuales llamativas.
- Reservar el color saturado para estado, severidad, selección y acción.
- Evitar gradientes decorativos, tarjetas sin función y visualizaciones que no conduzcan a una decisión.

### 2.2 La IA propone; la interfaz demuestra

- Nunca presentar una recomendación de IA como hecho consumado.
- Identificar claramente qué información es original, calculada por reglas, inferida por IA o modificada por una persona.
- Mostrar **recomendación + confianza + evidencia + versión** como una unidad.
- No usar solo una etiqueta vaga como “Generado por IA”.

### 2.3 Excepción primero

- Ordenar el trabajo por impacto y urgencia, no solo por fecha.
- Elevar discrepancias, bloqueos y baja confianza; permitir que lo correcto permanezca silencioso pero verificable.
- Ofrecer vistas guardadas como “Alta severidad”, “Baja confianza”, “Vence hoy” y “Mis revisiones”.

### 2.4 Comparar en contexto

- Mantener simultáneamente visibles los valores que se están conciliando.
- Para documentos, vincular cada campo extraído con su ubicación en la fuente.
- Para pronósticos, mantener visibles real, pronóstico, intervalo y eventos relevantes en la misma escala.

### 2.5 Acciones explícitas y reversibles

- Usar verbos concretos: “Aprobar hallazgo”, “Corregir costo”, “Enviar a revisión”.
- Evitar “Aceptar” cuando no sea evidente qué se acepta.
- Conservar borradores automáticamente.
- Permitir deshacer operaciones reversibles; pedir confirmación solo cuando exista impacto material o irreversible.

### 2.6 Auditoría por diseño

- Toda decisión muestra actor, fecha, estado anterior, estado nuevo, comentario y procedencia.
- La actividad no debe quedar oculta en logs técnicos; debe existir un historial legible para operaciones.

---

## 3. Usuarios y prioridades

| Rol | Necesidad principal | Vista inicial recomendada |
|---|---|---|
| Analista de categoría | Evaluar demanda y excepciones del forecast | Resumen de forecast + categorías con mayor desviación |
| Compras / procurement | Revisar proveedores, costos y pedidos | Cola priorizada + documentos pendientes |
| Cuentas por pagar | Resolver discrepancias PO–recepción–factura | Conciliaciones abiertas por impacto financiero |
| Revisor humano | Decidir casos inciertos con evidencia | “Mis revisiones” |
| Líder de operaciones | Conocer riesgo, volumen y SLA | Overview ejecutivo y salud operativa |
| ML / AI Ops | Medir desempeño y degradación | Evaluación de IA por modelo, proveedor y categoría |
| Auditor / admin | Reconstruir decisiones y controlar acceso | Audit trail y configuración |

La navegación y las acciones deben respetar permisos: si una persona puede ver pero no decidir, la UI debe explicarlo sin mostrar controles activos engañosos.

---

## 4. Arquitectura de información

### Navegación primaria

Usar sidebar persistente y colapsable, con estas entradas:

1. **Overview**
2. **Revisiones** — contador de casos asignados o vencidos
3. **Pronósticos**
4. **Documentos de proveedor**
5. **Conciliaciones**
6. **Evaluación de IA**
7. **Auditoría**
8. **Configuración** — permisos, tolerancias, reglas y modelos

### Barra superior

- Selector de organización o entorno, si aplica.
- Búsqueda global por SKU, EAN, proveedor, PO, factura o documento.
- Centro de notificaciones con agrupación por severidad.
- Ayuda contextual.
- Perfil y rol activo.

### Estructura de página

1. Breadcrumb cuando la profundidad sea mayor a un nivel.
2. Título orientado a tarea.
3. Estado general y metadatos compactos.
4. Acción primaria única.
5. Filtros y vistas guardadas.
6. Contenido de trabajo.
7. Panel contextual o inspector, cuando aplique.

No duplicar navegación global mediante pestañas. Las tabs se reservan para diferentes vistas del mismo objeto: “Resumen”, “Hallazgos”, “Historial”.

---

## 5. Shell y layout

### Desktop prioritario

- Ancho objetivo: 1280–1600 px.
- Sidebar: 240 px expandida / 72 px colapsada.
- Barra superior: 56–64 px.
- Área de contenido: máximo de 1440 px, excepto tablas y espacios de revisión que pueden ocupar todo el ancho.
- Grid base: 12 columnas, gutter de 24 px.
- Densidad: cómoda por defecto; opción compacta para tablas de uso intensivo.

### Patrón maestro–detalle

Para revisiones, documentos y conciliaciones:

- **30–40 %:** lista o evidencia fuente.
- **60–70 %:** detalle, comparación y decisión.
- El panel lateral debe poder redimensionarse o colapsarse.
- Conservar filtros, selección y scroll al entrar y volver de un caso.

### Responsive

- **≥ 1200 px:** experiencia completa.
- **768–1199 px:** sidebar colapsada; panel contextual como drawer.
- **< 768 px:** solo consulta, triage y aprobaciones simples; edición tabular compleja debe indicar “Disponible en escritorio”.

---

## 6. Sistema visual

### Personalidad

**Precisa, sobria, operativa y humana.** La interfaz debe transmitir control y trazabilidad sin parecer bancaria en exceso ni “mágica”.

### Color

Base recomendada:

| Token | Uso | Valor inicial |
|---|---|---|
| `surface.canvas` | Fondo de aplicación | `#F6F8FA` |
| `surface.default` | Paneles y tablas | `#FFFFFF` |
| `text.primary` | Texto principal | `#17202A` |
| `text.secondary` | Metadatos | `#5D6B7A` |
| `border.default` | Divisiones | `#D9E0E7` |
| `brand.primary` | Acción primaria | `#176B5B` |
| `brand.hover` | Hover primario | `#125548` |
| `info` | Información / IA | `#2563EB` |
| `success` | Correcto / aprobado | `#18864B` |
| `warning` | Atención / media | `#B86B00` |
| `danger` | Error / alta | `#C73737` |
| `ai.accent` | Señal secundaria de IA | `#6D5BD0` |

Reglas:

- No depender exclusivamente del color: combinar icono, texto y forma.
- `ai.accent` identifica procedencia, nunca severidad.
- El estado seleccionado utiliza borde, fondo y/o check; no solo un cambio de tono.
- Mantener contraste mínimo WCAG AA.

### Tipografía

- Sans serif de interfaz: **Inter**, **Geist** o equivalente del sistema.
- Números tabulares (`font-variant-numeric: tabular-nums`) en costos, cantidades, porcentajes y métricas.
- Escala sugerida: 12 / 14 / 16 / 20 / 24 / 32 px.
- Texto base: 14 px para alta densidad; 16 px para formularios y lectura prolongada.
- Métricas críticas usan tamaño, peso y etiqueta; no color como único diferenciador.

### Espaciado y forma

- Unidad base: 4 px.
- Espaciados más usados: 8, 12, 16, 24 y 32 px.
- Radio: 6 px en controles; 8–10 px en paneles.
- Sombras mínimas; preferir bordes y jerarquía de superficies.
- Alto de controles: 36 px compacto / 40 px estándar.
- Objetivo táctil mínimo: 44 × 44 px en móvil.

### Iconografía

- Una sola familia de iconos lineales.
- Acompañar con texto las acciones de alto impacto.
- Tooltip para iconos sin etiqueta visible.
- No usar estrellas o destellos como señal genérica de IA si compiten con estado o severidad.

---

## 7. Modelo de estados

Mantener los estados del brief como vocabulario canónico:

| Estado | Etiqueta UI | Tratamiento | Acción siguiente típica |
|---|---|---|---|
| `AUTO_APPROVED` | Aprobado automáticamente | Verde neutro + icono de automatización | Ver evidencia |
| `REVIEW_REQUIRED` | Requiere revisión | Ámbar + icono de persona | Revisar ahora |
| `APPROVED` | Aprobado | Verde + check | Ver historial |
| `REJECTED` | Rechazado | Rojo + icono de cierre | Ver motivo |
| `CORRECTED` | Corregido | Azul + icono de edición | Comparar cambios |

### Severidad y estado son dimensiones distintas

- Severidad: crítica, alta, media, baja, informativa.
- Estado: pendiente, aprobado, rechazado, corregido, etc.
- Confianza: porcentaje o banda calibrada.

Nunca fusionar las tres en un solo badge. Ejemplo correcto: **Alta** · **Requiere revisión** · **72 % confianza**.

---

## 8. Overview operativo

### Objetivo

Contestar “¿Dónde necesito intervenir hoy?”.

### Orden recomendado

1. **Alertas críticas:** SLA vencido, alto impacto financiero, pipeline detenido.
2. **Mi trabajo:** asignados, vencen hoy, baja confianza.
3. **Flujo operativo:** pronósticos, documentos y conciliaciones por estado.
4. **Indicadores:** volumen, tiempo de revisión, tasa de override, valor en discrepancia.
5. **Tendencias:** máximo 3–4 gráficas accionables.

### Reglas

- Cada KPI incluye periodo, comparación, definición y fecha de actualización.
- Al hacer clic, abrir la lista ya filtrada que explica el número.
- No usar un “número grande” sin denominador o contexto.
- Mostrar skeleton durante carga y timestamp si los datos no son recientes.

**Inspiración aplicada:** el resumen por etapas y la separación entre workflow, tareas y desempeño observados en [Jobber](https://mobbin.com/screens/9de47309-e37f-40db-b3c8-847d17392de7); los filtros temporales visibles y tarjetas comparables de [Whop](https://mobbin.com/screens/0bb8b25f-0c3d-47c3-b20a-1447e7dbab9e); la combinación de alertas accionables y cola “para hoy” de [Deel](https://mobbin.com/screens/58cea1c6-be72-4753-9b9a-3075955c8654).

---

## 9. Cola unificada de revisiones

### Columnas por defecto

- Selección
- Severidad
- Tipo de caso
- Entidad: proveedor / categoría / PO
- Resumen de hallazgo
- Impacto estimado
- Confianza
- Asignado a
- SLA / antigüedad
- Estado
- Acción rápida

### Comportamiento

- Orden inicial por **severidad × impacto × proximidad al SLA**.
- Filtros persistentes y compartibles en URL.
- Búsqueda dentro de resultados.
- Selección múltiple solo para casos homogéneos y seguros.
- Bulk approve prohibido para severidad alta, baja confianza o alto impacto financiero.
- Preview en panel lateral sin perder posición en la lista.
- Atajos de teclado visibles: siguiente/anterior, aprobar, rechazar, comentar.

### Vacíos

- Cola vacía: confirmar que no quedan casos y ofrecer ver completados.
- Sin resultados por filtros: explicar los filtros activos y ofrecer limpiarlos.
- Sin asignación: ofrecer “Tomar caso” si el rol lo permite.

**Inspiración aplicada:** el patrón de bandeja con estado “Needs Review”, detalle central y panel de feedback de [LangChain](https://mobbin.com/flows/e1a71435-7bff-4c41-9659-7902dd00d04a), incluido un cierre explícito de “todo revisado”.

---

## 10. Forecasting

### Vista de portafolio

- Selector jerárquico: categoría → tienda → SKU.
- Periodo y granularidad visibles.
- Tabla con forecast, real, error, bias, WAPE, modelo y estado.
- Ordenar por mayor desviación absoluta o impacto estimado.
- Comparación entre modelos mediante una métrica principal consistente y métricas secundarias accesibles.

### Vista de detalle

- Gráfica principal con real, forecast e intervalo de predicción.
- Anotaciones para promociones, faltantes, feriados y cambios de surtido.
- Selector de versión del forecast y modelo.
- Panel “Por qué cambió” con factores conocidos; no afirmar causalidad si el modelo no la demuestra.
- Tabla inferior con valores exactos y exportación.

### Visualización

- Real: línea sólida oscura.
- Forecast: línea sólida de marca.
- Intervalo: banda translúcida.
- Forecast anterior: línea punteada.
- No mostrar más de cuatro series simultáneas por defecto.
- Tooltips sincronizados y leyenda interactiva.
- Toda métrica incluye definición accesible.

### Acciones

- Aprobar forecast.
- Enviar a revisión.
- Corregir con motivo obligatorio.
- Comparar modelos/versiones.
- Ejecutar backtest, si el permiso lo permite.

**Inspiración aplicada:** filtros persistentes y paneles comparables de [Whop](https://mobbin.com/screens/0bb8b25f-0c3d-47c3-b20a-1447e7dbab9e), y la lectura vertical de series financieras de [Revolut Business](https://mobbin.com/screens/642f8ac1-17b9-4735-a453-4efa31969116). Para RetailOps AI, las tarjetas se limitarán a métricas que permitan navegar a excepciones.

---

## 11. Revisión de documentos de proveedor

### Flujo

1. Cargar documento.
2. Procesar y mostrar progreso real.
3. Revisar campos y hallazgos.
4. Corregir o decidir.
5. Confirmar y registrar.

### Workspace de revisión

Usar una vista dividida:

- **Izquierda:** documento fuente con zoom, páginas, búsqueda y resaltado.
- **Centro:** campos extraídos y tabla de productos.
- **Derecha:** hallazgos, confianza, recomendación y acciones.

Al seleccionar un campo:

- resaltar su ubicación exacta en el documento;
- mostrar valor original y valor normalizado;
- indicar método: OCR, regla o IA;
- mostrar confianza y validaciones;
- permitir edición inline con teclado.

### Hallazgos

Cada tarjeta de hallazgo debe contener:

- título concreto: “VAT inconsistente”, no “Anomalía detectada”;
- severidad;
- campos involucrados;
- regla o explicación;
- confianza calibrada;
- evidencia enlazada;
- recomendación;
- acciones: aprobar, rechazar o corregir.

### Progreso y recuperación

- Distinguir “Cargando”, “Extrayendo”, “Validando reglas” y “Revisando semántica”.
- Si falla una etapa, conservar las anteriores y permitir reintentar solo la etapa fallida.
- Mostrar `document_id`, fecha de carga y versión del extractor en detalles técnicos, no en el foco principal.

**Inspiración aplicada:** vínculo entre contenido y sugerencias aceptables/rechazables en [Dovetail](https://mobbin.com/screens/0d5151ab-6ade-47f5-8b03-024571200782); preview de PDF más panel de aprobación y comentario en [Aboard](https://mobbin.com/screens/473a91f7-3b9f-4e2b-9c22-ff199209aa7f); revisión por pasos, filtro de errores y corrección inline en [Remote](https://mobbin.com/screens/ab52924c-333f-42fb-bc19-659aa03720e0).

---

## 12. Conciliación PO–recepción–factura

### Resumen superior

Mostrar siempre la ecuación operativa:

`Pedido − recibido − facturado = diferencia`

Incluir:

- valor total en discrepancia;
- número de líneas afectadas;
- tolerancia aplicada;
- estado;
- riesgo de duplicidad;
- última actualización.

### Tabla comparativa

Agrupar columnas en tres bloques visuales:

| Identidad | PO | Recepción | Factura | Resultado |
|---|---|---|---|---|
| SKU, descripción | Cantidad, costo | Cantidad, fecha | Cantidad, costo, VAT | Δ cantidad, Δ costo, regla, estado |

Reglas:

- Encabezados sticky y primera columna fija.
- Alinear números a la derecha y usar dígitos tabulares.
- Resaltar la celda discrepante, no pintar toda la fila salvo en errores críticos.
- Mostrar diferencia absoluta y relativa.
- Abrir un inspector lateral con documentos fuente y cálculo desglosado.
- Permitir “Mostrar solo discrepancias”.
- Explicar cada tolerancia con regla, valor configurado y cálculo ejecutado.

### Resolución

Opciones según el caso:

- aceptar dentro de tolerancia;
- solicitar nota de crédito;
- corregir asociación;
- marcar recepción faltante;
- escalar;
- rechazar factura.

Pedir comentario para overrides, rechazos y decisiones fuera de tolerancia. Antes de confirmar, resumir impacto: “Se aprobarán 12 líneas por $24,580; 2 quedarán abiertas”.

**Inspiración aplicada:** secuencia numerada de selección, suma y conciliación de [Xero](https://mobbin.com/screens/85cdec88-2dba-400d-aa56-172760982a9b); ecuación de balance y diferencia prominente de [QuickBooks](https://mobbin.com/screens/869dfa1d-8c53-4dac-96a1-6fd98999d1b8); resumen de balance, filtros y estados de matching de [Wave](https://mobbin.com/screens/d46cf8a7-74cd-4725-9714-f60f093efdb4).

---

## 13. Patrón Human-in-the-Loop

### Anatomía de una decisión

1. **Contexto:** entidad, impacto, fecha, SLA.
2. **Propuesta:** recomendación de IA en una frase.
3. **Evidencia:** datos fuente y reglas relevantes.
4. **Incertidumbre:** confianza y límites conocidos.
5. **Controles:** aprobar, corregir, rechazar, escalar.
6. **Justificación:** comentario, obligatorio cuando se modifica o rechaza.
7. **Consecuencia:** resumen previo a la confirmación.
8. **Registro:** confirmación con enlace al audit trail.

### Reglas de confianza

- Mostrar porcentaje solo si está calibrado y es interpretable.
- Acompañar con banda: alta, media o baja.
- Explicar en tooltip qué significa: “En casos con 80 % de confianza, aproximadamente 8 de 10 fueron correctos en evaluación”.
- No convertir confianza en severidad.
- La baja confianza debe cambiar el flujo —por ejemplo, exigir revisión—, no limitarse a cambiar el color.

### Aprobación y corrección

- Botón primario solo cuando la decisión sea clara.
- Aprobar y rechazar nunca deben verse equivalentes por accidente.
- “Corregir” abre el campo relevante en contexto, no un modal genérico.
- Mostrar diff antes de confirmar una corrección.
- Tras decidir, cargar el siguiente caso sin perder la posibilidad de deshacer cuando sea seguro.

**Inspiración aplicada:** revisión junto a evidencia y actividad posterior en [Hex](https://mobbin.com/flows/0d693e43-9e0e-43e6-bb62-19ce8ec92d65); tareas sugeridas con aceptación o descarte en [Loom](https://mobbin.com/flows/aff025ef-fae4-4663-afc7-88acc2503fe4); cierre explícito de revisión en [LangChain](https://mobbin.com/flows/e1a71435-7bff-4c41-9659-7902dd00d04a).

---

## 14. Evaluación de IA

### Preguntas que debe responder

- ¿Está mejorando o empeorando el sistema?
- ¿Dónde se equivoca?
- ¿Qué modelo o prompt produjo la decisión?
- ¿Qué grupos concentran overrides o falsos positivos?

### Estructura

- Filtros globales: periodo, capability, modelo, versión, proveedor, categoría y estado.
- KPIs: aceptación, override, precisión de extracción, FPR, FNR, tiempo medio de revisión.
- Tendencia con despliegues de modelos anotados.
- Matriz por proveedor/categoría.
- Tabla de casos evaluados con drill-down.
- Vista de calibración para confianza.

### Reglas

- Mostrar tamaño de muestra junto a cada porcentaje.
- Comparar solo periodos y poblaciones equivalentes.
- Señalar datos incompletos o demorados.
- Permitir navegar de una métrica agregada a los casos que la componen.
- Mostrar versión de modelo y prompt como filtros de primera clase.

---

## 15. Audit trail

### Timeline legible

Cada evento debe incluir:

- fecha y hora con zona horaria;
- actor humano o servicio;
- acción;
- antes → después;
- motivo/comentario;
- regla, modelo y prompt aplicables;
- enlace a evidencia o artefacto fuente.

### Comparación de versiones

- Usar diff de campos para correcciones.
- Para forecasts, comparar versiones con línea temporal y métricas.
- Para documentos, preservar el valor extraído y el corregido.
- Para conciliaciones, preservar el cálculo determinístico y la resolución humana.

La UI no debe permitir editar o borrar eventos de auditoría. Las correcciones posteriores generan nuevos eventos.

---

## 16. Componentes esenciales

### Tablas de datos

- Ordenamiento, filtros, columnas configurables y densidad.
- Encabezado sticky; paginación o virtualización según volumen.
- Selección con checkbox; fila clicable solo si no compite con otros controles.
- Estado, severidad y confianza en columnas separadas.
- Exportación respeta filtros y declara zona horaria y moneda.

### Filtros

- Chips para filtros activos.
- “Limpiar todo” visible.
- Conteo de resultados actualizado.
- Filtros avanzados en popover/drawer, sin ocultar periodo y estado.
- Vistas guardadas personales y compartidas.

### Panel lateral / inspector

- Para inspección rápida, comentarios, historial y evidencia.
- Debe preservar el contexto de la tabla.
- Ancho mínimo 360 px; redimensionable en workflows densos.
- Acción primaria sticky al pie si hay scroll.

### Modales

- Solo para confirmación, tarea breve o decisión irreversible.
- No usar para revisar documentos, editar tablas extensas o comparar evidencia.

### Badges

- Texto corto, icono opcional y color semántico.
- Máximo tres badges visibles por fila; el resto mediante detalle.
- No usar mayúsculas de código en UI; `REVIEW_REQUIRED` se presenta como “Requiere revisión”.

### Notificaciones

- Toast para confirmación inmediata y no bloqueante.
- Banner inline para problemas persistentes.
- Centro de notificaciones para asignaciones y SLA.
- Errores de validación junto al campo y resumen al inicio del formulario.

---

## 17. Estados del sistema

### Carga

- Skeleton con geometría final para páginas y listas.
- Progreso por etapa en procesos largos.
- Evitar spinner indeterminado después de 10 segundos; explicar qué se está haciendo.

### Error

Todo error debe incluir:

- qué falló;
- qué se conservó;
- qué puede hacer el usuario;
- identificador de soporte copiable, cuando aplique.

No culpar al usuario ni mostrar trazas técnicas.

### Vacío

Diferenciar:

- aún no hay datos;
- no hay resultados por filtros;
- no quedan tareas;
- el usuario no tiene permisos.

### Datos desactualizados

- Mostrar “Actualizado hace…” y permitir refrescar.
- Si una decisión se basa en datos obsoletos, bloquear o solicitar reconfirmación según el riesgo.

---

## 18. Contenido y microcopy

### Voz

- Directa, neutral y específica.
- La IA expresa incertidumbre: “Probable duplicado” en lugar de “Factura duplicada” cuando no está confirmado.
- Separar observación de recomendación.

### Fórmula recomendada para hallazgos

**Observación:** “El costo facturado es 8.4 % mayor que el pedido.”  
**Regla:** “La tolerancia configurada es 2 %.”  
**Recomendación:** “Solicitar validación del proveedor.”

### Etiquetas de botones

- Bien: “Aprobar 12 líneas”, “Corregir VAT”, “Enviar a revisión”.
- Evitar: “Continuar”, “Aceptar”, “Sí” sin objeto explícito.

### Fechas, números y moneda

- Formato localizado y zona horaria visible en auditoría.
- Mostrar moneda con código cuando pueda haber más de una: `MXN 24,580.00`.
- Unidades en encabezados de tabla.
- Porcentajes con precisión consistente; evitar decimales irrelevantes.

---

## 19. Accesibilidad

- Cumplir WCAG 2.2 AA como objetivo de producto.
- Navegación completa por teclado y foco visible.
- Orden de foco coincide con el orden visual.
- Tablas con encabezados semánticos y nombres accesibles.
- Gráficas con resumen textual y tabla de datos alternativa.
- No comunicar estado solo por color.
- Zoom de navegador al 200 % sin pérdida de acciones críticas.
- Respeto a `prefers-reduced-motion`.
- Mensajes de error anunciados por tecnología asistiva.
- Atajos de teclado desactivables y sin conflicto con lector de pantalla.

---

## 20. Seguridad y confianza en UI

- Mostrar entorno (`Producción`, `Staging`) con tratamiento inequívoco.
- En acciones financieras, mostrar alcance e impacto antes de confirmar.
- Ocultar o enmascarar datos sensibles según rol.
- Explicar por qué una acción está deshabilitada.
- Evitar exponer prompts internos, secretos o razonamientos privados del modelo; mostrar evidencia y explicación útil para la decisión.
- Indicar cuando un resultado fue recalculado y si cambió desde que se abrió la pantalla.
- Prevenir decisiones sobre versiones obsoletas mediante control de concurrencia y aviso de actualización.

---

## 21. Qué no hacer

- No iniciar la experiencia con una caja de chat vacía.
- No esconder acciones operativas dentro de conversación libre.
- No presentar confianza como sello de verdad.
- No saturar el overview con todas las métricas disponibles.
- No usar cards para reemplazar tablas cuando se comparan muchas entidades.
- No abrir cada caso en una página nueva si se trabaja una cola repetitiva.
- No usar modales para workflows densos.
- No permitir overrides sin motivo ni dejar cambios humanos fuera del audit trail.
- No mezclar severidad, estado y confianza en un único color.
- No animar continuamente gráficas, alertas o indicadores de IA.

---

## 22. Alcance recomendado para el primer release

### P0 — indispensable

- Shell, permisos y búsqueda global.
- Overview operativo.
- Cola unificada de revisiones.
- Tablas y filtros.
- Review workspace con evidencia, decisión y comentario.
- Estados canónicos y audit trail.
- Vacíos, carga, error y datos desactualizados.
- Accesibilidad de teclado y contraste.

### P1 — por capability

- Forecast: detalle, comparación y versionado.
- Documentos: source-to-field highlighting y corrección inline.
- Conciliación: tabla tripartita, tolerancias e inspector.
- Evaluación de IA con drill-down.

### P2 — optimización

- Vistas guardadas compartidas.
- Atajos de power user.
- Bulk actions condicionadas por riesgo.
- Preferencia de densidad.
- Personalización de overview por rol.

---

## 23. Checklist de aceptación UI

Una pantalla de decisión no se considera lista si alguna respuesta es “no”:

- [ ] ¿La tarea principal es evidente sin instrucciones externas?
- [ ] ¿Estado, severidad y confianza se distinguen claramente?
- [ ] ¿La evidencia fuente está accesible en uno o ningún clic?
- [ ] ¿Se entiende qué proviene de una regla, de IA o de una persona?
- [ ] ¿La acción primaria declara su objeto e impacto?
- [ ] ¿Una corrección muestra el antes y después?
- [ ] ¿El resultado genera un evento de auditoría?
- [ ] ¿La pantalla funciona completamente con teclado?
- [ ] ¿Carga, vacío, error, permisos y datos obsoletos están diseñados?
- [ ] ¿Filtros, selección y scroll se conservan al volver a la cola?
- [ ] ¿Los indicadores agregados permiten navegar a sus casos fuente?
- [ ] ¿El layout sigue siendo usable a 1280 px y con zoom de 200 %?

---

## 24. Referentes Mobbin seleccionados

Los siguientes referentes se seleccionaron por patrón funcional observado, no como guía de identidad visual:

| Referente | Patrón útil para RetailOps AI |
|---|---|
| [Jobber — dashboard operativo](https://mobbin.com/screens/9de47309-e37f-40db-b3c8-847d17392de7) | Etapas del workflow, tareas y desempeño en una jerarquía clara |
| [Deel — home con pendientes](https://mobbin.com/screens/58cea1c6-be72-4753-9b9a-3075955c8654) | Alertas accionables y cola priorizada “para hoy” |
| [Whop — analytics](https://mobbin.com/screens/0bb8b25f-0c3d-47c3-b20a-1447e7dbab9e) | Filtros temporales globales y tarjetas comparables |
| [Xero — conciliación](https://mobbin.com/screens/85cdec88-2dba-400d-aa56-172760982a9b) | Secuencia guiada de selección, ajuste y confirmación |
| [QuickBooks — balance](https://mobbin.com/screens/869dfa1d-8c53-4dac-96a1-6fd98999d1b8) | Diferencia financiera visible y ecuación verificable |
| [Wave — reconciliation](https://mobbin.com/screens/d46cf8a7-74cd-4725-9714-f60f093efdb4) | Balance, filtros y matching en una tabla compacta |
| [Remote — review de datos](https://mobbin.com/screens/ab52924c-333f-42fb-bc19-659aa03720e0) | Flujo por pasos, errores localizados y corrección inline |
| [Dovetail — sugerencias](https://mobbin.com/screens/0d5151ab-6ade-47f5-8b03-024571200782) | Evidencia vinculada con sugerencias aprobables o descartables |
| [Aboard — aprobación documental](https://mobbin.com/screens/473a91f7-3b9f-4e2b-9c22-ff199209aa7f) | Preview del documento, panel de contexto y comentario |
| [LangChain — completing a review](https://mobbin.com/flows/e1a71435-7bff-4c41-9659-7902dd00d04a) | Bandeja, revisión repetitiva, feedback y cierre de cola |
| [Hex — approving a project](https://mobbin.com/flows/0d693e43-9e0e-43e6-bb62-19ce8ec92d65) | Revisión junto a evidencia, aprobación y actividad auditable |
| [Loom — reviewing a task](https://mobbin.com/flows/aff025ef-fae4-4663-afc7-88acc2503fe4) | Recomendación contextual con aceptar/descartar |

### Criterio de adaptación

RetailOps AI debe combinar la claridad financiera de Xero/QuickBooks, la eficiencia de revisión de LangChain/Remote y la jerarquía operativa de Jobber/Deel. La identidad, los tokens, el modelo de riesgo y la trazabilidad deben ser propios; ningún referente cubre por sí solo un sistema Human-in-the-Loop para retail.


# Aprendizajes de CI/CD e infraestructura en Google Cloud

Notas del taller RAG (Milvus, Ollama, FastAPI y Streamlit) para reutilizar en la tesis. Registran lo que se configuró, los errores reales que aparecieron y lo que se haría distinto. No incluyen identificadores de proyecto, direcciones IP, correos ni credenciales: donde hace falta un valor concreto, se indica qué tipo de valor es.

## 1. Objetivo y alcance

El objetivo fue tener tres cosas sobre el mismo repositorio:

- **Integración continua (CI):** cada cambio en el proyecto se prueba y se construye en GitHub Actions.
- **Despliegue continuo (CD):** un cambio aprobado en `main` actualiza una demo que corre en una VM de Compute Engine.
- **Una demo accesible:** la API y la interfaz se pueden usar desde internet durante unos días, sin abrir el resto de servicios.

Quedan fuera del alcance la ingesta del corpus (se hace a mano, una sola vez), la gestión de modelos en Ollama y cualquier entorno de producción real. La demo es temporal.

Archivos de referencia en este repositorio:

- `.github/workflows/ci-taller-rag.yml`
- `.github/workflows/cd-taller-rag.yml`
- `workshops/taller-rag/proyecto/docker-compose.yml`

## 2. Integración continua

**Disparadores.** `push` y `pull_request` a `main`, filtrados por ruta: solo corre si cambia `workshops/taller-rag/**` o el propio archivo del workflow. El resto del repositorio (otros talleres) no gasta ejecuciones.

**Permisos y concurrencia.** El workflow solo pide permiso de lectura del contenido (`contents: read`) y no usa secretos. Un grupo de concurrencia por rama cancela la ejecución anterior si llega un push nuevo, porque solo importa el resultado del último commit.

**Qué valida cada job:**

| Job | Qué hace | Por qué |
|---|---|---|
| `pruebas` | Instala Python 3.11, torch para CPU y `requirements-api.txt`, y corre `pytest -q -rs` sin la variable que activa las pruebas en vivo. | Comprueba la lógica (métricas, chunking, contrato de la API, validador del gold) sin depender de Milvus ni de Ollama. Las pruebas en vivo quedan como saltadas, no como fallidas. |
| `compose` | Copia `.env.example` a `.env` solo dentro del runner y ejecuta `docker compose config -q`. | Detecta errores de sintaxis o de interpolación en el compose antes de llegar a la VM. Nunca usa el `.env` real. |
| `imagenes` | Construye las imágenes de la API y de la interfaz con `docker build`, sin publicarlas. | Comprueba que el `Dockerfile` y las dependencias siguen construyendo. No hace falta un registro de imágenes para esto. |

Instalar torch desde el índice de CPU antes del resto de dependencias evita descargar la variante con CUDA, que es mucho más pesada y no se usa.

**Error real encontrado.** La primera ejecución del job `pruebas` falló al recolectar las pruebas:

```
SyntaxError: f-string: f-string: unmatched '['
```

La causa fue un f-string con comillas anidadas del mismo tipo (un f-string dentro de otro, con `res['k']` adentro). Esa sintaxis es válida desde Python 3.12 (PEP 701), pero no en 3.11. En local no se notaba porque el entorno virtual usaba 3.12; el contenedor, en cambio, usa `python:3.11-slim`, así que el script tampoco habría funcionado dentro de la imagen.

**Cómo se detectó.** El CI fijó la versión de Python igual a la del contenedor. Después se compiló todo el código del proyecto con un contenedor de 3.11 para buscar otros casos: solo había uno. La corrección fue cambiar los delimitadores del f-string exterior a triple comilla, sin tocar la lógica, y comprobar que la salida era idéntica.

**Cómo se evita:**

- Fijar en el CI la misma versión menor de Python que usa la imagen del contenedor (no "la última").
- Si el entorno local usa otra versión, compilar el código con la versión del contenedor antes de subirlo (`python -m compileall` dentro de la imagen base).
- Tratar la versión de Python como parte de la configuración congelada del proyecto.

## 3. Despliegue continuo

**Disparador.** `push` a `main` con cambios en `workshops/taller-rag/**`, más `workflow_dispatch` para lanzarlo a mano. El filtro de rutas no incluye el propio archivo del workflow: subir solo el workflow no despliega nada.

**Concurrencia.** Un único grupo (`cd-taller-rag`) sin cancelar la ejecución en curso: nunca hay dos despliegues a la vez. Hay que saber cómo se comporta GitHub en ese caso: solo se guarda **una** ejecución pendiente por grupo; si llega otra, la pendiente anterior se cancela. No se pierde nada, porque cada despliegue trae el último `main`.

**Entorno con revisor obligatorio.** El job usa un entorno de GitHub con la regla de revisor obligatorio. Cada despliegue queda en espera hasta que alguien lo aprueba en la pestaña Actions. Dos lecciones:

- Crear el entorno y sus variables exige permisos de administrador del repositorio. Una cuenta con solo lectura puede ver el entorno, pero no sus variables.
- Si se sube un workflow que referencia un entorno que no existe, GitHub lo crea automáticamente **sin protección**, y el job corre sin esperar aprobación. Hay que crear el entorno con su revisor **antes** de subir el workflow.

**Configuración sin secretos.** El proveedor de identidad, la cuenta de servicio, el proyecto, la zona y la instancia se guardan como variables del entorno, no como secretos, porque no son credenciales. El workflow las lee con `vars.*`.

**Autenticación con federación de identidad (sin claves JSON).** GitHub Actions emite una identidad OIDC para cada job; Google Cloud la intercambia por credenciales temporales de una cuenta de servicio. Pasos:

- Un pool de identidades de carga de trabajo y un proveedor OIDC apuntando al emisor de GitHub Actions.
- Una condición de atributo que solo acepta el repositorio concreto (`assertion.repository == '<dueño>/<repositorio>'`). Sin esa condición, cualquier repositorio de GitHub podría intentar usar el pool.
- El rol `roles/iam.workloadIdentityUser` sobre la cuenta de despliegue, otorgado al conjunto de principales filtrado por ese repositorio.
- Las APIs de credenciales de IAM y de intercambio de credenciales (STS) habilitadas en el proyecto.
- El workflow pide el permiso para emitir la identidad OIDC del job y usa las acciones oficiales de autenticación y de instalación de gcloud.

No se creó ninguna clave JSON de cuenta de servicio.

**Roles mínimos de la cuenta de despliegue:**

| Rol | Alcance | Para qué |
|---|---|---|
| `roles/compute.instanceAdmin.v1` | Proyecto | Agregar la clave SSH efímera a la instancia (OS Login no estaba activo; con OS Login bastaría `roles/compute.osAdminLogin`). |
| `roles/iap.tunnelResourceAccessor` | Proyecto | Abrir el túnel IAP hacia la VM. |
| `roles/compute.viewer` | Proyecto | Consultar el estado de la VM antes de desplegar. |
| `roles/iam.serviceAccountUser` | **Solo** la cuenta de servicio adjunta a la VM | Necesario para modificar los metadatos de una instancia que tiene una cuenta de servicio adjunta. Se otorga sobre esa cuenta, no sobre el proyecto, para no permitir actuar como otras cuentas. |

El cuarto rol no estaba en el plan inicial. Es un requisito poco visible: sin él, el SSH falla aunque los otros tres roles estén bien.

**Acceso por IAP, sin IP pública.** El workflow entra a la VM con `gcloud compute ssh --tunnel-through-iap`. El tráfico pasa por Identity-Aware Proxy, así que la VM no necesita IP pública ni SSH abierto a internet. Requisitos: la API de IAP habilitada y una regla de firewall que permita el puerto 22 solo desde el rango de IAP publicado por Google.

**Reconstrucción de contenedores.** En la VM, el workflow:

1. Comprueba el estado de la instancia. Si no está en ejecución, emite un aviso y termina con éxito: el despliegue nunca enciende la VM.
2. Actualiza el clon del repositorio con `git pull --ff-only`.
3. Ejecuta `docker compose up -d --build api frontend`. Solo se reconstruyen la API y la interfaz; Milvus y Ollama no se tocan.

No se ejecuta la ingesta, no se usa `down -v` y no se borran volúmenes: la colección de Milvus y los modelos de Ollama sobreviven a cada despliegue.

Dos detalles que hicieron falta:

- El usuario SSH del runner no es el dueño del clon en la VM. El workflow usa la ruta absoluta del clon, ejecuta `git` como el dueño con `sudo -u` y `docker compose` con `sudo`. Usar `~/` habría apuntado al directorio del usuario del runner, que no tiene el clon.
- Un cambio local sin commit en la VM (el compose editado a mano) bloquea el `git pull --ff-only`, aunque el contenido sea idéntico al que llega. Hay que llevar esos cambios al repositorio y dejar el clon limpio antes de automatizar.

**Verificación con `/health`.** Después de reconstruir, el workflow consulta `/health` dentro de la VM hasta 30 veces, cada 5 segundos. Si no recibe `"ok"`, el job falla. Esto distingue "el contenedor arrancó" de "la API responde".

**El despliegue reinicia la demo.** Recrear la API y la interfaz corta las peticiones en curso y deja la demo sin servicio unos segundos. Además, la primera consulta después de reiniciar es más lenta, porque el encoder y el modelo se cargan de nuevo. Conviene aprobar los despliegues cuando nadie esté usando la demo.

## 4. Infraestructura en Google Cloud

**VM sin IP pública por defecto.** La VM se creó con `--no-address`. Todo el acceso administrativo pasa por IAP. La IP pública se agregó después, solo para la demo, y es efímera: cambia si la VM se detiene y se vuelve a iniciar.

**Red de salida con Cloud NAT.** Una VM sin IP pública no tiene salida a internet. Sin salida fallan la instalación de Docker, el `git clone`, la descarga de imágenes, la descarga de modelos de Ollama y la descarga desde el bucket (si la subred no tiene acceso privado a Google). Se resolvió con un Cloud Router y un Cloud NAT en la región: solo dan salida, no abren entradas. Hay que contarlo en el plan desde el principio, porque tiene costo propio.

**Firewall por etiqueta.** Las reglas que abren puertos de la demo usan una etiqueta de red (`--target-tags`), así que solo afectan a esa VM y no a otras del proyecto.

**Cuenta de servicio dedicada.** La VM usa una cuenta de servicio propia, con lectura del bucket del corpus, en lugar de la cuenta por defecto de Compute Engine. El despliegue usa otra cuenta distinta. Cada cuenta tiene solo los permisos de su función.

**Lección: el firewall por defecto dejó SSH expuesto.** La red `default` trae reglas que permiten SSH y RDP desde cualquier origen, aplicadas a todas las instancias. Mientras la VM no tenía IP pública, no importaban. Al asignarle una IP para la demo, el puerto 22 quedó accesible desde internet. Se cerró sin borrar las reglas por defecto:

- Se bajó a 800 la prioridad de la regla que permite SSH desde el rango de IAP.
- Se creó una regla **deny** de SSH desde cualquier origen, con prioridad 900 y limitada a la etiqueta de la VM.
- La regla por defecto queda con prioridad 65534. En GCP gana el número menor, así que el orden es: IAP permitido, todo lo demás denegado, la regla por defecto nunca llega a aplicarse para esta VM.

Se verificó desde fuera (el puerto 22 no responde) y por IAP (el SSH sigue funcionando).

**Costo.** La VM (8 vCPU, 32 GB de RAM) cobra por hora mientras está encendida. El disco persistente cobra por GB y mes **aunque la VM esté apagada**. El Cloud NAT cobra por hora y por datos procesados mientras exista. Detener la VM solo elimina el costo de cómputo; el disco y el NAT siguen cobrando hasta que se eliminan. Las cifras exactas se consultan en la calculadora de precios de Google Cloud para la región elegida.

## 5. Exposición pública

**Puertos públicos:**

- `8000` (API FastAPI): `/health` y `/ask`.
- `8501` (interfaz Streamlit).

**Puertos cerrados a internet:**

- `19530` y `9091` (Milvus) y `11434` (Ollama): publicados solo en la interfaz local de la VM (`localhost`) en el `docker-compose.yml`, y sin regla de firewall.
- `22` (SSH): bloqueado con la regla deny descrita arriba; solo entra por IAP.
- `3389` (RDP): la regla por defecto lo permite, pero no hay ningún servicio escuchando.

Hay dos capas de cierre: el firewall de GCP y el enlace de los puertos a `localhost` dentro de la VM. Si alguien abriera por error una regla de firewall, Milvus y Ollama seguirían sin responder desde fuera.

**Riesgo de no tener autenticación.** Ni la API ni la interfaz piden credenciales. Cualquiera con la dirección puede hacer preguntas, y cada pregunta ocupa la CPU de la VM durante 10 a 40 segundos. Unas pocas peticiones seguidas pueden saturar la demo. No hay límite de peticiones.

**La API devuelve fragmentos del corpus.** `/ask` responde con la evidencia recuperada: fragmentos de texto de los documentos del corpus, con su identificador y su URL. Exponer la API es, en la práctica, exponer partes del corpus. Para la demo se aceptó porque es temporal; en la tesis hay que revisar antes la licencia y la sensibilidad de los datos.

## 6. Decisiones que cambiarían en la tesis

- **Separar datos de cómputo.** Guardar el corpus, los embeddings y la colección de Milvus en almacenamiento persistente propio (un bucket o un disco separado), de modo que la VM se pueda borrar y recrear sin repetir la ingesta.
- **Almacenamiento con acceso uniforme y sin acceso público.** Activar el acceso uniforme a nivel de bucket y la prevención de acceso público desde la creación, y dar lectura solo a las cuentas de servicio que lo necesitan.
- **Presupuesto y alertas antes de crear recursos.** Definir un presupuesto en facturación con alertas por umbral antes de crear la primera VM, no después.
- **Apagar lo que no se usa.** Programar el apagado de la VM, eliminar el NAT y el disco cuando la demo termina, y revisar periódicamente los recursos huérfanos (IPs reservadas, discos sin VM).
- **Autenticación desde el inicio** si la API se expone, aunque sea una clave simple o un proxy con identidad, y un límite de peticiones.
- **IP estática solo si hace falta** una dirección estable; si no, acceso por túnel.
- **Revisar las reglas por defecto de la red** (o usar una red propia sin ellas) antes de asignar cualquier IP pública.
- **Infraestructura como código** (Terraform o scripts versionados) en lugar de comandos sueltos, para poder recrear y destruir todo de forma repetible.

## 7. Lista de verificación reutilizable

**Antes de crear recursos**

- [ ] Proyecto de GCP creado y facturación vinculada.
- [ ] Presupuesto con alertas configurado.
- [ ] APIs habilitadas: Compute Engine, IAP, credenciales de IAM y STS.
- [ ] Revisadas las reglas de firewall por defecto de la red.

**Red y VM**

- [ ] Cloud Router y Cloud NAT en la región de la VM (salida sin IP pública).
- [ ] Regla de firewall para SSH solo desde el rango de IAP.
- [ ] Cuenta de servicio dedicada para la VM, con los permisos mínimos sobre el bucket.
- [ ] VM creada sin IP pública (`--no-address`) y con esa cuenta de servicio.
- [ ] Docker y Docker Compose instalados por SSH a través de IAP.

**Aplicación**

- [ ] Repositorio clonado en la VM; `.env` creado a partir de `.env.example`, sin imprimirlo ni subirlo.
- [ ] Datos descargados del bucket y tamaños verificados contra el origen.
- [ ] Servicios internos (base vectorial, servidor de modelos) publicados solo en `localhost` en el compose.
- [ ] Servicios levantados, modelo descargado e ingesta ejecutada una vez.
- [ ] `/health` verificado dentro de la VM y por túnel.

**CI**

- [ ] Workflow de CI con filtro de rutas, permisos de solo lectura y sin secretos.
- [ ] Versión de Python del CI igual a la de la imagen del contenedor.
- [ ] Jobs de pruebas, validación del compose y construcción de imágenes en verde.

**CD**

- [ ] Pool y proveedor de federación de identidad, con condición por repositorio.
- [ ] Cuenta de despliegue con roles mínimos, incluido `serviceAccountUser` solo sobre la cuenta adjunta a la VM.
- [ ] `workloadIdentityUser` sobre la cuenta de despliegue para el repositorio.
- [ ] Entorno de GitHub con revisor obligatorio y sus variables, creado **antes** de subir el workflow.
- [ ] Clon de la VM limpio (sin cambios locales) antes del primer despliegue.
- [ ] Primera ejecución lanzada a mano y verificada.

**Exposición pública (solo si hace falta)**

- [ ] Etiqueta de red en la VM y reglas de firewall limitadas a esa etiqueta y a los puertos públicos.
- [ ] Regla deny de SSH desde cualquier origen, con prioridad mayor que la regla por defecto y menor que la de IAP.
- [ ] Puertos verificados desde fuera: los públicos responden; los demás no.
- [ ] Decisión explícita sobre autenticación y límite de peticiones.

**Al terminar**

- [ ] VM detenida.
- [ ] Decidido qué se borra (VM, disco, NAT, router, reglas, IP) y qué se conserva.
- [ ] Revisión de la facturación unos días después.

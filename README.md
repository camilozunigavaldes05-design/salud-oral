# Sistema web de monitoreo y evaluación de riesgo de salud oral

Proyecto del ramo **Ingeniería de Software (CINF1063)** — Universidad Viña del Mar.

**Equipo:** Diego Herraz · Javier Roa · Camilo Zuñiga · Nicolas Ivani
**Docente:** Pablo Ormeño Arriagada

Página web responsiva que permite al paciente fotografiar su cavidad bucal, validar la calidad de la imagen, obtener una clasificación orientativa del riesgo (Bajo, Moderado o Alto) mediante IA y solicitar una cita con un profesional de la salud oral.

---

## Índice

1. [Tecnologías](#1-tecnologías)
2. [Estructura del proyecto](#2-estructura-del-proyecto)
3. [Primera vez: cómo instalar el proyecto en tu PC](#3-primera-vez-cómo-instalar-el-proyecto-en-tu-pc)
4. [Cómo trabajar día a día](#4-cómo-trabajar-día-a-día)
5. [Trabajo con ramas y Pull Requests](#5-trabajo-con-ramas-y-pull-requests)
6. [Base de datos y migraciones](#6-base-de-datos-y-migraciones)
7. [Versiones del proyecto](#7-versiones-del-proyecto)
8. [Reglas del equipo](#8-reglas-del-equipo)
9. [Problemas frecuentes](#9-problemas-frecuentes)

---

## 1. Tecnologías

| Parte | Tecnología |
|---|---|
| Lenguaje | Python 3.13 |
| Framework web | Django (con plantillas HTML) |
| Base de datos | PostgreSQL alojado en **Supabase** |
| Almacenamiento de imágenes | Supabase Storage (bucket privado) |
| Filtro de calidad de imagen | OpenCV (luminancia y varianza del Laplaciano) |
| Clasificación de riesgo | PyTorch |
| Control de versiones | Git + GitHub |

---

## 2. Estructura del proyecto

Cada app de Django corresponde a un componente del informe (Tabla 6-2):

| Carpeta | Qué contiene | Requerimientos |
|---|---|---|
| `config/` | Configuración general del proyecto (`settings.py`, `urls.py`) | — |
| `cuentas/` | Usuarios, roles, registro e inicio de sesión | RF-01 |
| `evaluaciones/` | Consentimiento, carga de imagen, validación de calidad, IA, reporte e historial | RF-02 a RF-05 |
| `agenda/` | Horarios, bloqueo temporal de 15 minutos y citas | RF-06, RF-08, RF-09 |
| `notificaciones/` | Correos y alertas internas sobre las citas | RF-07 |
| `administracion/` | Verificación de profesionales, perfiles y auditoría | RF-10 |

Archivos importantes en la raíz:

| Archivo | Para qué sirve | ¿Se sube a GitHub? |
|---|---|---|
| `manage.py` | Ejecuta los comandos de Django | Sí |
| `requirements.txt` | Lista de paquetes que hay que instalar | Sí |
| `.gitignore` | Indica qué archivos **no** se suben | Sí |
| `.env` | Contraseñas y claves (base de datos, Django) | **No, nunca** |
| `venv/` | Entorno virtual de cada persona | **No** |

---

## 3. Primera vez: cómo instalar el proyecto en tu PC

Esto se hace **una sola vez** por computador.

### Paso 1. Aceptar la invitación

Revisa tu correo o la campana de notificaciones en github.com y acepta la invitación al repositorio `salud-oral`.

### Paso 2. Instalar los programas necesarios

| Programa | Dónde | Importante |
|---|---|---|
| Python 3.13 | python.org | En el instalador, **marca "Add Python to PATH"** |
| Git | git-scm.com, o en una terminal: `winget install --id Git.Git -e` | Opciones por defecto |
| VS Code | code.visualstudio.com | Opciones por defecto |

Después de instalar, **cierra y vuelve a abrir** VS Code.

Para comprobar que están instalados, en una terminal:

```bash
python --version
git --version
```

### Paso 3. Configurar Git con tus datos

Usa el **mismo correo de tu cuenta de GitHub**, para que tus cambios aparezcan con tu nombre:

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "correo_de_tu_github@gmail.com"
```

### Paso 4. Descargar el proyecto

1. Crea o elige una carpeta, por ejemplo `Documentos/Ing.Soft`.
2. Ábrela en VS Code: **Archivo → Abrir carpeta**.
3. Abre la terminal: **Terminal → Nueva terminal**.
4. Ejecuta:

```bash
git clone https://github.com/camilozunigavaldes05-design/salud-oral.git
```

5. Abre en VS Code la carpeta `salud-oral` que se acaba de crear (**Archivo → Abrir carpeta**) y abre de nuevo la terminal.

### Paso 5. Crear el entorno virtual e instalar los paquetes

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Sabrás que el entorno está activo porque aparece `(venv)` al inicio de la línea de la terminal.

> Si al activar aparece un error rojo sobre "ejecución de scripts deshabilitada", ejecuta una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, responde **S** y vuelve a activar.
>
> En Mac o Linux, el comando para activar es `source venv/bin/activate`.

### Paso 6. Crear el archivo `.env`

1. En VS Code, crea un archivo llamado exactamente `.env` en la raíz del proyecto, **al lado de `manage.py`**.
2. Pega el contenido que te enviará Camilo **por mensaje privado**. Tiene esta forma:

```
DB_NAME=postgres
DB_USER=...
DB_PASSWORD=...
DB_HOST=...
DB_PORT=5432
SECRET_KEY='...'
```

3. Guarda con `Ctrl + S`.

> **Nunca subas este archivo a GitHub ni lo compartas en grupos.** El `.gitignore` ya lo protege, pero no lo copies a otras carpetas ni lo pegues en otros lados.

### Paso 7. Probar que todo funciona

```bash
python manage.py showmigrations
```

Si aparece una lista de apps con `[ ]` o `[X]`, estás conectado a la base de datos del equipo. Si aparece un error, revisa la sección [Problemas frecuentes](#9-problemas-frecuentes).

---

## 4. Cómo trabajar día a día

### Al empezar a trabajar

1. Abre VS Code en la carpeta `salud-oral`.
2. Abre la terminal y activa el entorno:

```bash
venv\Scripts\activate
```

3. **Baja los cambios que subieron tus compañeros:**

```bash
git pull
```

4. Si alguien agregó paquetes nuevos, instálalos:

```bash
pip install -r requirements.txt
```

### Al terminar algo que funciona

```bash
git status
git add .
git commit -m "Agrega modelo Cita con sus estados"
git push
```

- `git status` muestra qué archivos cambiaste. **Revisa que no aparezca `.env`.**
- `git add .` prepara todos los cambios.
- `git commit -m "..."` guarda una versión con una descripción.
- `git push` la sube a GitHub para que el resto la vea.

### Cómo escribir buenos mensajes de commit

| Bien | Mal |
|---|---|
| `Agrega modelo Usuario con roles` | `cambios` |
| `Corrige validación de tamaño de imagen` | `arreglo` |
| `Crea plantilla de la pantalla P03` | `asdf` |

Empieza con un verbo (Agrega, Corrige, Crea, Actualiza, Elimina) y di **qué** cambió.

---

## 5. Trabajo con ramas y Pull Requests

Para no pisarnos el código, **nadie trabaja directo en `main`**. La rama `main` siempre debe tener una versión que funcione.

### Qué es una rama

Una rama es una copia del proyecto donde puedes hacer cambios sin afectar a los demás. Cuando terminas, pides que tus cambios se unan a `main` mediante un **Pull Request**.

### Flujo de trabajo

**1. Actualiza `main` antes de empezar algo nuevo:**

```bash
git checkout main
git pull
```

**2. Crea una rama para tu tarea:**

```bash
git checkout -b nombre-de-la-tarea
```

Nombres sugeridos:

| Tipo | Ejemplo |
|---|---|
| Funcionalidad nueva | `feature/modelo-usuario`, `feature/pantalla-agendamiento` |
| Corrección de error | `fix/validacion-imagen` |
| Documentación | `docs/readme` |

**3. Trabaja y haz commits en tu rama** (puedes hacer varios):

```bash
git add .
git commit -m "Agrega formulario de registro"
```

**4. Sube tu rama a GitHub:**

```bash
git push -u origin nombre-de-la-tarea
```

La primera vez se usa `-u origin nombre-de-la-tarea`; las siguientes veces basta con `git push`.

**5. Abre un Pull Request en GitHub:**

1. Entra al repositorio en github.com.
2. Aparecerá un aviso amarillo con el botón **Compare & pull request**. Presiónalo.
3. Escribe qué hiciste y qué requerimiento atiende (por ejemplo, "RF-01: registro e inicio de sesión").
4. Presiona **Create pull request**.

**6. Revisión:** otro integrante revisa los cambios. Si están bien, presiona **Merge pull request**. Así los cambios pasan a `main`.

**7. Vuelve a `main` y actualízala:**

```bash
git checkout main
git pull
```

Y para la siguiente tarea, vuelves al paso 2.

### Si tu rama quedó desactualizada

Si mientras trabajabas alguien unió cambios a `main`, trae esos cambios a tu rama:

```bash
git checkout main
git pull
git checkout nombre-de-la-tarea
git merge main
```

### Si aparece un conflicto

Un conflicto ocurre cuando dos personas cambiaron las mismas líneas de un archivo. VS Code marca las partes en conflicto con colores y botones:

- **Accept Current Change:** mantiene tu versión.
- **Accept Incoming Change:** mantiene la versión del otro.
- **Accept Both Changes:** mantiene ambas.

Elige la correcta (si tienes dudas, habla con quien hizo el otro cambio), guarda el archivo y luego:

```bash
git add .
git commit -m "Resuelve conflicto en models.py"
```

---

## 6. Base de datos y migraciones

**Todos usamos la misma base de datos en Supabase.** Lo que uno cree o borre, lo ven todos. Por eso los cambios en las tablas hay que coordinarlos.

### Qué es una migración

Cuando modificas un `models.py`, Django genera un archivo de migración con las instrucciones para crear o cambiar las tablas en la base de datos.

### Pasos al modificar un modelo

1. **Avisa en el grupo** que vas a modificar un modelo.
2. Haz `git pull` para tener las últimas migraciones.
3. Modifica el `models.py`.
4. Genera la migración:

```bash
python manage.py makemigrations
```

5. Aplícala a la base de datos:

```bash
python manage.py migrate
```

6. **Sube los archivos de migración** (las carpetas `migrations/`) junto con tu cambio, mediante un Pull Request.

### Reglas de migraciones

- **Siempre `git pull` antes de `makemigrations` y de `migrate`.**
- **Nunca borres ni edites a mano** archivos de migración que ya están en `main`.
- **Una sola persona a la vez** modifica modelos de una misma app.
- Si al hacer `git pull` llegan migraciones nuevas, ejecuta `python manage.py migrate` para aplicarlas.
- **No uses datos reales de pacientes.** Solo datos de prueba o inventados (RNF-07).

---

## 7. Versiones del proyecto

Cada entrega o avance importante se marca con una **etiqueta (tag)** en GitHub. Así siempre se puede volver a ver cómo estaba el proyecto en cada entrega.

### Versiones planificadas

| Versión | Contenido |
|---|---|
| `v0.1` | Proyecto Django conectado a Supabase y repositorio configurado |
| `v0.2` | Modelos de datos y migraciones (9 entidades) |
| `v0.3` | Registro e inicio de sesión con roles (CU-01) |
| `v0.4` | Carga de imagen, validación de calidad e historial (CU-03 a CU-09), con IA simulada |
| `v0.5` | Modelo de IA entrenado e integrado |
| `v0.6` | Agendamiento, citas y notificaciones (CU-10 a CU-13) |
| `v0.7` | Administración y auditoría (CU-02) |
| `v1.0` | Versión de entrega final, con pruebas |

### Cómo crear una versión

Solo se hace desde `main`, cuando todo funciona y el equipo está de acuerdo:

```bash
git checkout main
git pull
git tag -a v0.1 -m "Proyecto Django conectado a Supabase"
git push origin v0.1
```

Las versiones quedan visibles en GitHub, en la sección **Tags** o **Releases** del repositorio.

### Cómo ver una versión anterior

```bash
git checkout v0.1
```

Para volver al estado actual:

```bash
git checkout main
```

---

## 8. Reglas del equipo

1. **`git pull` siempre antes de empezar a trabajar.**
2. **Nadie trabaja directo en `main`**: cada tarea va en su propia rama y entra a `main` por Pull Request.
3. **Commits pequeños y frecuentes**, con mensajes claros.
4. **Cada uno trabaja preferentemente en su app** para evitar conflictos.
5. **Avisar en el grupo antes de modificar un `models.py`.**
6. **Nunca subir el `.env`** ni escribir contraseñas en el código.
7. **Si instalas un paquete nuevo**, actualiza la lista y avisa al grupo:

```bash
pip freeze > requirements.txt
```

8. **No subir código que no funcione a `main`.** Prueba antes con:

```bash
python manage.py runserver
```

9. **Solo datos de prueba**, nunca datos reales de pacientes.
10. **Si algo se rompe, avisa en el grupo** antes de intentar arreglarlo a la fuerza.

---

## 9. Problemas frecuentes

| Problema | Causa probable | Solución |
|---|---|---|
| `git` o `python` "no se reconoce" | El programa no está instalado o la terminal se abrió antes de instalarlo | Instálalo y **cierra y vuelve a abrir VS Code** (o reinicia el PC) |
| Error rojo al activar `venv` | PowerShell bloquea scripts | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y responde **S** |
| No aparece `(venv)` en la terminal | El entorno no está activo | `venv\Scripts\activate` |
| `ModuleNotFoundError: No module named 'django'` | Entorno no activo o paquetes no instalados | Activa el entorno y ejecuta `pip install -r requirements.txt` |
| `password authentication failed` | Contraseña incorrecta en el `.env` | Revisa la línea `DB_PASSWORD=` (sin espacios, sin comillas, sin repetir el nombre) y guarda el archivo |
| `no password supplied` | La línea `DB_PASSWORD=` está vacía | Escribe la contraseña y guarda |
| No conecta y antes funcionaba | Supabase pausa los proyectos gratuitos tras días sin uso | Entra a supabase.com y reactiva el proyecto |
| `git push` rechazado | Hay cambios nuevos en GitHub que no tienes | `git pull` y luego `git push` |
| Conflicto al hacer `git pull` o `merge` | Dos personas cambiaron las mismas líneas | Ver [Si aparece un conflicto](#si-aparece-un-conflicto) |
| El `.env` aparece en `git status` | El `.gitignore` no está funcionando | **No hagas commit.** Avisa al grupo |

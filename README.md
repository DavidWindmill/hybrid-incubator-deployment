# Hybrid Incubator Deployment

Este repositorio lee una especificación YAML que referencia tres repositorios de código y crea cinco servicios: un detector, un agregador y tres instancias del mismo sensor.

## Prueba local multirrepositorio

Los cuatro repositorios deben estar como carpetas hermanas:

```text
incubadora_multirepo/
├── incubator-sensor-service/
├── incubator-aggregator-service/
├── quantum-anomaly-detector-service/
└── hybrid-incubator-deployment/
```

Desde `hybrid-incubator-deployment`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m deployment.cli validate --spec specifications/application.local.yaml
python -m deployment.cli up --spec specifications/application.local.yaml
python scripts\run_demo.py --env-file .deployment\deployment.env --timeout 240
python -m deployment.cli status --spec specifications/application.local.yaml
python -m deployment.cli logs --spec specifications/application.local.yaml
python -m deployment.cli down --spec specifications/application.local.yaml
```

El despliegue local construye solo tres imágenes, aunque crea cinco contenedores.

## Crear los repositorios GitHub

Instala GitHub CLI, ejecuta `gh auth login` y desde este repositorio:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_github_repos.ps1 -Owner TU_USUARIO -Visibility public
python scripts\set_github_owner.py TU_USUARIO

git add specifications/application.cloud.yaml
git commit -m "Configure GitHub repository URLs"
git push
```

Para la primera versión cloud se recomiendan repositorios públicos. Los repositorios privados requieren proporcionar autenticación al proceso que los clona.

## Despliegue cloud manual

En Cloud Shell:

```bash
export PROJECT_ID="tu-project-id"
export REGION="europe-southwest1"
bash scripts/bootstrap_gcp.sh

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m deployment.cli cloud-up   --spec specifications/application.cloud.yaml   --project "$PROJECT_ID"   --region "$REGION"   --artifact-repository incubadora-quantum   --runtime-service-account "incubator-runtime@$PROJECT_ID.iam.gserviceaccount.com"

python scripts/run_demo.py   --env-file .deployment/cloud-deployment.env   --timeout 300
```

## Automatización

Conecta únicamente este repositorio a un trigger de Cloud Build que use `cloudbuild.yaml`. Cada cambio de la especificación hará que el despliegue:

1. Clone los repositorios de los componentes.
2. Construya tres imágenes en Artifact Registry.
3. Despliegue el detector.
4. Inyecte su URL en el agregador y lo despliegue.
5. Inyecte la URL del agregador en los tres sensores.
6. Ejecute la prueba de ocho lecturas y compruebe el estado `100`.

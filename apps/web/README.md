# Web App Wrapper

Frontend source currently stays in `frontend/`.

Production delivery target is S3 + CloudFront.

Build command:

```bash
cd frontend
npm ci
npm run build
```

Artifacts are uploaded from `frontend/dist` by the CodeBuild frontend stage.

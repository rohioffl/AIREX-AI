# Web App Wrapper

Frontend source lives in `apps/web/`.

Production delivery target is S3 + CloudFront.

Build command:

```bash
cd apps/web
npm ci
npm run build
```

Artifacts are uploaded from `apps/web/dist` by the CodeBuild frontend stage.
